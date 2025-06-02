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

def get_similar_restaurants(liked_restaurants, disliked_restaurants, city):
    logging.debug("Constructing prompt for GPT-4.")
    
    # Load the prompt template
    prompt_template = load_prompt_template()
    
    # Format the liked restaurants list
    liked_restaurants_formatted = '\n'.join(f'- {restaurant}' for restaurant in liked_restaurants)
    
    # Format the disliked restaurants section if it exists
    disliked_section = ""
    if disliked_restaurants:
        disliked_formatted = '\n'.join(f'- {restaurant}' for restaurant in disliked_restaurants)
        disliked_section = f"Disliked Restaurants (please avoid similar places):\n{disliked_formatted}\n\n"
    
    # Fill in the template
    prompt = prompt_template.format(
        city=city,
        liked_restaurants=liked_restaurants_formatted,
        disliked_section=disliked_section,
        num_recommendations=NUM_RECOMMENDATIONS
    )

    try:
        logging.debug("Sending request to GPT-4 API.")
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Specify GPT-4 model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150  # Limit the response length
        )

        logging.debug(f"Raw API Response: {response}")

        # Parse and return the recommendations
        restaurants = response.choices[0].message.content.split('\n')
        logging.debug(f"Parsed Restaurants: {restaurants}")
        recommendations = []
        for restaurant in restaurants:
            if restaurant.strip():
                parts = restaurant.split(' - ', 1)
                if len(parts) == 2:
                    name, description = parts
                    sanitized_name = sanitize_name(name)
                    recommendations.append({"name": sanitized_name, "description": description.strip()})
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
