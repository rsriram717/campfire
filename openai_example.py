import os
import openai

# Load API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_similar_restaurants(favorite_restaurants, city, num_recommendations=3):
    # Construct a prompt for GPT-4
    prompt = (
        f"Recommend {num_recommendations} restaurants similar to the following: "
        f"{', '.join(favorite_restaurants)} in {city}. "
        f"List the responses as <name> - <2-3 short phrases of why it would be a good fit>"
    )

    try:
        # Call the GPT-4 API
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # Specify GPT-4 model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150  # Limit the response length
        )

        # Parse and return the recommendations
        restaurants = response.choices[0].message.content.split('\n')
        print("API Response:", restaurants)  # Debugging line
        recommendations = []
        for restaurant in restaurants:
            if restaurant.strip():  # This check removes empty lines
                parts = restaurant.split(' - ', 1)
                if len(parts) == 2:  # Ensure there are exactly two parts
                    name, description = parts
                    recommendations.append({"name": name, "description": description.strip()})
                else:
                    print(f"Unexpected format: {restaurant}")  # Log unexpected formats

        return recommendations  # Return the list of recommendations as a JSON-compatible structure

    except Exception as e:
        print(f"Error with GPT-4 API: {e}")
        return []

def check_api_key():
    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        print(openai.api_key)
        print("API key is valid.")
    except Exception as e:
        print(f"Error: {e}")
        print("API key may not be valid or there's a connection issue.")