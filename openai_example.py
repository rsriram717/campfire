import os
import openai
import re
import logging

# Load API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_similar_restaurants(input_restaurants, city, num_recommendations=3):
    logging.debug("Constructing prompt for GPT-4.")
    prompt = (
        f"Recommend {num_recommendations} restaurants similar to the following: "
        f"{', '.join(input_restaurants)} in {city}. "
        f"List the responses as <name> - <2-3 short phrases of why it would be a good fit>"
        f"Do not number the responses"
    )

    try:
        logging.debug("Sending request to GPT-4 API.")
        response = openai.chat.completions.create(
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
        openai.api_key = os.getenv("OPENAI_API_KEY")
        print(openai.api_key)
        print("API key is valid.")
    except Exception as e:
        print(f"Error: {e}")
        print("API key may not be valid or there's a connection issue.")

def sanitize_name(name):
    # Remove special characters from the restaurant name
    return re.sub(r'[^a-zA-Z0-9\s]', '', name)
