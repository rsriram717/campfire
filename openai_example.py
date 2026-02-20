import os
from openai import OpenAI
import anthropic
import re
import logging
from pathlib import Path
from collections import Counter

# Constants
NUM_RECOMMENDATIONS = 3
RANK_MODEL = "claude-haiku-4-5-20251001"

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)

def get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
    return anthropic.Anthropic(api_key=api_key)

def load_prompt_template():
    prompt_path = Path(__file__).parent / 'prompt.txt'
    with open(prompt_path, 'r') as file:
        return file.read()

def load_rank_prompt_template():
    prompt_path = Path(__file__).parent / 'prompt_rank.txt'
    with open(prompt_path, 'r') as file:
        return file.read()

def get_similar_restaurants(liked_restaurants, disliked_restaurants, city, neighborhood=None, restaurant_types=None):
    logging.debug("Constructing legacy prompt.")

    # Load the prompt template
    prompt_template = load_prompt_template()

    # Format the liked restaurants list
    liked_restaurants_formatted = '\n'.join(f'- {restaurant}' for restaurant in liked_restaurants)

    # Format the disliked restaurants section
    disliked_section = ""
    if disliked_restaurants:
        disliked_formatted = '\n'.join(f'- {restaurant}' for restaurant in disliked_restaurants)
        disliked_section = f"Disliked Restaurants (please avoid similar places):\n{disliked_formatted}\n\n"

    # Format the neighborhood section
    neighborhood_section = ""
    if neighborhood:
        neighborhood_section = f"The user is looking for suggestions in the {neighborhood} neighborhood of {city}. Please ensure all recommendations are located there.\n\n"

    # Format the restaurant type section
    type_section = ""
    if restaurant_types:
        type_list = ", ".join(restaurant_types)
        type_section = f"The user prefers the following type(s) of restaurants: {type_list}. Please factor this into your suggestions.\n\n"

    # Fill in the template
    prompt = prompt_template.format(
        city=city,
        liked_restaurants=liked_restaurants_formatted,
        disliked_section=disliked_section,
        neighborhood_section=neighborhood_section,
        type_section=type_section,
        num_recommendations=NUM_RECOMMENDATIONS
    )

    try:
        logging.debug(f"Sending request to OpenAI API with prompt: {prompt}")
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4",  # Specify GPT-4 model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150  # Limit the response length
        )

        logging.debug(f"Raw API Response: {response}")

        # Parse and return the recommendations
        content = response.choices[0].message.content
        if not content:
            logging.warning("Received empty content from OpenAI API.")
            return []

        restaurants = content.split('\n')
        logging.debug(f"Parsed Restaurants: {restaurants}")
        recommendations = []
        for restaurant in restaurants:
            if restaurant.strip():
                # Strip leading numbers (e.g. "1. Au Cheval", "2. Girl & The Goat")
                cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', restaurant.strip())

                # Split by ' - '
                # Expected format: Name - Because you liked X - Description
                parts = cleaned_line.split(' - ')

                name = ""
                description = ""
                reason = ""

                if len(parts) >= 3:
                    name = parts[0].strip()
                    raw_reason = parts[1].strip()
                    # Check if reason is valid (not empty, not just hyphens)
                    if raw_reason and raw_reason != "-" and len(raw_reason) > 5:
                        reason = raw_reason

                    # Join the rest as description in case there are more hyphens
                    description = " - ".join(parts[2:]).strip()
                elif len(parts) == 2:
                    # Fallback to old format
                    name = parts[0].strip()
                    description = parts[1].strip()
                else:
                    # Fallback for weird formatting, treat whole line as name (risky but better than nothing)
                    name = cleaned_line

                if name:
                    sanitized_name = sanitize_name(name)
                    rec_obj = {"name": sanitized_name, "description": description}
                    if reason:
                        rec_obj["reason"] = reason
                    recommendations.append(rec_obj)
                else:
                    logging.warning(f"Unexpected format: {restaurant}")

        return recommendations

    except Exception as e:
        logging.error(f"Error with OpenAI API: {e}")
        return []


def _weighted_counter(history_items, input_items, alpha, key_fn):
    """Weighted voting for categorical features. Returns a Counter with fractional weights."""
    h_valid = [key_fn(r) for r in history_items if key_fn(r)]
    i_valid = [key_fn(r) for r in input_items if key_fn(r)]

    if not h_valid and not i_valid:
        return Counter()

    if h_valid and i_valid:
        h_w = (1 - alpha) / len(h_valid)
        i_w = alpha / len(i_valid)
    elif h_valid:
        h_w = 1.0 / len(h_valid)
        i_w = 0.0
    else:
        h_w = 0.0
        i_w = 1.0 / len(i_valid)

    counts = Counter()
    for v in h_valid:
        counts[v] += h_w
    for v in i_valid:
        counts[v] += i_w
    return counts


def _weighted_bool(history_items, input_items, alpha, key_fn):
    """Weighted boolean preference. Returns True/False/None."""
    h_vals = [1.0 if key_fn(r) else 0.0 for r in history_items if key_fn(r) is not None]
    i_vals = [1.0 if key_fn(r) else 0.0 for r in input_items if key_fn(r) is not None]

    if not h_vals and not i_vals:
        return None

    if h_vals and i_vals:
        h_w = (1 - alpha) / len(h_vals)
        i_w = alpha / len(i_vals)
    elif h_vals:
        h_w = 1.0 / len(h_vals)
        i_w = 0.0
    else:
        h_w = 0.0
        i_w = 1.0 / len(i_vals)

    weighted_sum = sum(h_w * v for v in h_vals) + sum(i_w * v for v in i_vals)
    return weighted_sum >= 0.5


def build_taste_profile(history_objs: list, input_objs: list, alpha: float = 0.7) -> dict:
    """
    Derive a weighted taste profile from history and current session inputs.
    alpha=1.0 means inputs fully control; alpha=0.0 means history fully controls.
    Returns a dict with aggregated preferences. Returns empty dict if no signal available.
    """
    if not history_objs and not input_objs:
        return {}

    price_counter = _weighted_counter(history_objs, input_objs, alpha, lambda r: r.price_level)
    type_counter = _weighted_counter(history_objs, input_objs, alpha, lambda r: r.primary_type)

    h_ratings = [r.rating for r in history_objs if r.rating is not None]
    i_ratings = [r.rating for r in input_objs if r.rating is not None]
    if h_ratings and i_ratings:
        h_w = (1 - alpha) / len(h_ratings)
        i_w = alpha / len(i_ratings)
        avg_rating = sum(h_w * v for v in h_ratings) + sum(i_w * v for v in i_ratings)
    elif h_ratings:
        avg_rating = sum(h_ratings) / len(h_ratings)
    elif i_ratings:
        avg_rating = sum(i_ratings) / len(i_ratings)
    else:
        avg_rating = None

    profile = {}

    if price_counter:
        profile['preferred_price_level'] = price_counter.most_common(1)[0][0]

    if avg_rating is not None:
        profile['min_rating'] = round(avg_rating, 1)

    if type_counter:
        profile['top_cuisine_types'] = [t for t, _ in type_counter.most_common(3)]

    dine_in = _weighted_bool(history_objs, input_objs, alpha, lambda r: r.serves_dine_in)
    if dine_in is not None:
        profile['prefers_dine_in'] = dine_in

    takeout = _weighted_bool(history_objs, input_objs, alpha, lambda r: r.serves_takeout)
    if takeout is not None:
        profile['prefers_takeout'] = takeout

    reservable = _weighted_bool(history_objs, input_objs, alpha, lambda r: r.reservable)
    if reservable is not None:
        profile['prefers_reservable'] = reservable

    return profile


def rank_candidates(
    taste_profile: dict,
    candidates: list,
    liked_names: list,
    disliked_names: list,
    city: str,
    neighborhood: str = None,
    restaurant_types: list = None,
    num_recommendations: int = NUM_RECOMMENDATIONS,
    liked_restaurant_objs: list = None,
    input_restaurant_objs: list = None,
    alpha: float = 0.7
) -> list:
    """
    Use Claude to rank real candidate restaurants and return the top num_recommendations.
    Returns a list of dicts with place_id, name, description, reason, address, rating, price_level.
    """
    if not candidates:
        logging.warning("rank_candidates called with empty candidate list")
        return []

    prompt_template = load_rank_prompt_template()

    # Build numbered candidate lines and index for lookup
    candidate_index = {}
    candidate_lines = []
    for i, c in enumerate(candidates, start=1):
        candidate_index[i] = c
        parts = []
        if c.get('primary_type'):
            parts.append(c['primary_type'])
        if c.get('price_level'):
            parts.append(c['price_level'])
        if c.get('rating') is not None:
            parts.append(f"rating: {c['rating']}")
        if c.get('editorial_summary'):
            parts.append(c['editorial_summary'])
        meta = ", ".join(parts)
        line = f"{i}. {c['name']}" + (f" — {meta}" if meta else "")
        candidate_lines.append(line)

    candidates_numbered = "\n".join(candidate_lines)
    liked_names_str = ", ".join(liked_names) if liked_names else "none"
    disliked_names_str = ", ".join(disliked_names) if disliked_names else "none"

    def _format_profile_lines(objs):
        lines = []
        for r in (objs or []):
            parts = []
            if r.primary_type:
                parts.append(r.primary_type)
            if r.price_level:
                parts.append(r.price_level)
            if r.rating is not None:
                parts.append(f"rating: {r.rating}")
            if r.serves_dine_in:
                parts.append("dine-in")
            if r.reservable:
                parts.append("reservable")
            if r.editorial_summary:
                parts.append(r.editorial_summary)
            meta = ", ".join(parts)
            lines.append(f"- {r.name}" + (f": {meta}" if meta else ""))
        return lines

    session_section = ""
    if input_restaurant_objs:
        lines = _format_profile_lines(input_restaurant_objs)
        session_section = "**Current session (prioritize matching these):**\n" + "\n".join(lines) + "\n\n"

    history_section = ""
    if liked_restaurant_objs:
        lines = _format_profile_lines(liked_restaurant_objs)
        history_section = "**Past preferences (use for broader taste context):**\n" + "\n".join(lines) + "\n\n"

    if alpha >= 0.7:
        alpha_instruction = "The user's current session inputs should heavily influence your selection.\n\n"
    elif alpha <= 0.3:
        alpha_instruction = "Draw primarily from the user's historical taste profile.\n\n"
    else:
        alpha_instruction = ""

    neighborhood_section = ""
    if neighborhood:
        neighborhood_section = f"Neighborhood preference: {neighborhood}\n"

    type_section = ""
    if restaurant_types:
        type_section = f"Restaurant type preference: {', '.join(restaurant_types)}\n"

    prompt = prompt_template.format(
        num_recommendations=num_recommendations,
        preferred_price_level=taste_profile.get('preferred_price_level', 'any'),
        min_rating=taste_profile.get('min_rating', 'any'),
        top_cuisine_types=", ".join(taste_profile.get('top_cuisine_types', [])) or 'any',
        prefers_dine_in=taste_profile.get('prefers_dine_in', 'unknown'),
        prefers_reservable=taste_profile.get('prefers_reservable', 'unknown'),
        session_section=session_section,
        history_section=history_section,
        alpha_instruction=alpha_instruction,
        liked_names=liked_names_str,
        disliked_names=disliked_names_str,
        neighborhood_section=neighborhood_section,
        type_section=type_section,
        candidates_numbered=candidates_numbered
    )

    try:
        logging.debug(f"Sending rank prompt to {RANK_MODEL}:\n{prompt}")
        client = get_anthropic_client()
        response = client.messages.create(
            model=RANK_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        if not content:
            logging.warning("Received empty content from Claude rank call.")
            return []

        logging.debug(f"Claude rank response:\n{content}")

        results = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Extract leading number
            num_match = re.match(r'^(\d+)[\.\)]\s*', line)
            if not num_match:
                continue

            candidate_num = int(num_match.group(1))
            rest = line[num_match.end():]

            # Normalize em-dashes and en-dashes to hyphens — Haiku mirrors the
            # candidate list format (which uses —) in its output, but our delimiter is ' - '
            rest = rest.replace(' \u2014 ', ' - ').replace(' \u2013 ', ' - ')
            parts = rest.split(' - ')
            name = parts[0].strip() if parts else ""
            reason = ""
            description = ""

            if len(parts) >= 3:
                raw_reason = parts[1].strip()
                if raw_reason and raw_reason != "-" and len(raw_reason) > 5:
                    reason = raw_reason
                description = re.sub(r'^[\s\u002D\u2013\u2014]+', '', " - ".join(parts[2:])).strip()
            elif len(parts) == 2:
                description = parts[1].strip()

            # Resolve via candidate_index — no API call needed
            candidate = candidate_index.get(candidate_num)
            if not candidate:
                logging.warning(f"Claude referenced unknown candidate number {candidate_num}")
                continue

            results.append({
                "place_id": candidate["place_id"],
                "name": candidate["name"],  # Use official Google name
                "description": description,
                "reason": reason,
                "address": candidate.get("address", ""),
                "rating": candidate.get("rating"),
                "price_level": candidate.get("price_level"),
            })

        return results[:num_recommendations]

    except Exception as e:
        logging.error(f"Error with Claude rank call: {e}")
        return []


def check_api_key():
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print("API key is loaded from environment.")
            # Test with a simple API call
            client = get_openai_client()
            print("OpenAI client initialized successfully.")
        else:
            print("OPENAI_API_KEY environment variable is not set.")
    except Exception as e:
        print(f"Error: {e}")
        print("API key may not be valid or there's a connection issue.")

def sanitize_name(name):
    # Remove special characters from the restaurant name
    return re.sub(r'[^a-zA-Z0-9\s]', '', name)
