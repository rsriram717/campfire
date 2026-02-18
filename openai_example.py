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
    logging.debug("Constructing prompt for GPT-4.")

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
        logging.debug(f"Sending request to GPT-4 API with prompt: {prompt}")
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
        logging.error(f"Error with GPT-4 API: {e}")
        return []


def build_taste_profile(liked_restaurants: list) -> dict:
    """
    Derive a structured taste profile from a list of liked Restaurant ORM objects.
    Returns a dict with aggregated preferences. Returns empty dict if no signal available.
    """
    if not liked_restaurants:
        return {}

    price_levels = [r.price_level for r in liked_restaurants if r.price_level]
    ratings = [r.rating for r in liked_restaurants if r.rating is not None]
    primary_types = [r.primary_type for r in liked_restaurants if r.primary_type]

    # Fields where we check >=50% preference
    dine_in_vals = [r.serves_dine_in for r in liked_restaurants if r.serves_dine_in is not None]
    takeout_vals = [r.serves_takeout for r in liked_restaurants if r.serves_takeout is not None]
    reservable_vals = [r.reservable for r in liked_restaurants if r.reservable is not None]

    profile = {}

    if price_levels:
        # Most common price level
        profile['preferred_price_level'] = Counter(price_levels).most_common(1)[0][0]

    if ratings:
        profile['min_rating'] = round(sum(ratings) / len(ratings), 1)

    if primary_types:
        profile['top_cuisine_types'] = [t for t, _ in Counter(primary_types).most_common(3)]

    if dine_in_vals:
        profile['prefers_dine_in'] = sum(dine_in_vals) / len(dine_in_vals) >= 0.5

    if takeout_vals:
        profile['prefers_takeout'] = sum(takeout_vals) / len(takeout_vals) >= 0.5

    if reservable_vals:
        profile['prefers_reservable'] = sum(reservable_vals) / len(reservable_vals) >= 0.5

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
    liked_restaurant_objs: list = None
) -> list:
    """
    Use GPT-4 to rank real candidate restaurants and return the top num_recommendations.
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

    # Build liked restaurant profiles for richer "Because you liked" reasoning
    liked_profiles_section = ""
    if liked_restaurant_objs:
        profile_lines = []
        for r in liked_restaurant_objs:
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
            profile_lines.append(f"- {r.name}" + (f": {meta}" if meta else ""))
        liked_profiles_section = "Liked Restaurant Profiles (use these to understand the user's taste — do not recommend them):\n" + "\n".join(profile_lines) + "\n\n"

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
        liked_profiles_section=liked_profiles_section,
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
            logging.warning("Received empty content from GPT-4 rank call.")
            return []

        logging.debug(f"GPT-4 rank response:\n{content}")

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

            # Split by ' - '
            parts = rest.split(' - ')
            name = parts[0].strip() if parts else ""
            reason = ""
            description = ""

            if len(parts) >= 3:
                raw_reason = parts[1].strip()
                if raw_reason and raw_reason != "-" and len(raw_reason) > 5:
                    reason = raw_reason
                description = " - ".join(parts[2:]).strip()
            elif len(parts) == 2:
                description = parts[1].strip()

            # Resolve via candidate_index — no API call needed
            candidate = candidate_index.get(candidate_num)
            if not candidate:
                logging.warning(f"GPT-4 referenced unknown candidate number {candidate_num}")
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
        logging.error(f"Error with GPT-4 rank call: {e}")
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
