import os
from openai import OpenAI
import re
import logging
from pathlib import Path

# Constants
NUM_RECOMMENDATIONS = 3

def get_openai_client():
    """Get OpenAI client instance with API key from environment variable"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)

def load_prompt_template():
    prompt_path = Path(__file__).parent / 'prompt.txt'
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
