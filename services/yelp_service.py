# services/yelp_service.py

import os
import requests
from typing import Optional
from .places import PlacesService

class YelpService(PlacesService):
    """
    Yelp implementation of the PlacesService.
    """
    def __init__(self):
        self.api_key = os.getenv("YELP_API_KEY")
        self.base_url = "https://api.yelp.com/v3"

    def autocomplete(self, query: str, city: str, session_token: Optional[str] = None) -> list[dict]:
        if not self.api_key:
            return []

        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {
            "text": query,
            "location": city,
            "limit": 5,
            "categories": "restaurants,food"
        }
        
        try:
            response = requests.get(f"{self.base_url}/businesses/search", headers=headers, params=params)
            response.raise_for_status()
            businesses = response.json().get("businesses", [])
            
            return [
                {
                    "name": b.get("name"),
                    "place_id": b.get("id"),
                    "address": ", ".join(b.get("location", {}).get("display_address", [])),
                }
                for b in businesses
            ]
        except requests.RequestException as e:
            print(f"Error calling Yelp API: {e}")
            return []

    def search_nearby_candidates(self, city, neighborhood=None, restaurant_types=None, radius=8000, max_results=20):
        # Yelp is now paid; returning empty list to satisfy abstract interface
        return []

    def get_details(self, place_id: str, session_token: Optional[str] = None) -> dict:
        if not self.api_key:
            return {}
            
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            response = requests.get(f"{self.base_url}/businesses/{place_id}", headers=headers)
            response.raise_for_status()
            business = response.json()

            return {
                "name": business.get("name"),
                "place_id": business.get("id"),
                "address": ", ".join(business.get("location", {}).get("display_address", [])),
                "phone": business.get("display_phone"),
                "website": business.get("url"),
                "categories": [c["title"] for c in business.get("categories", [])],
            }
        except requests.RequestException as e:
            print(f"Error calling Yelp API: {e}")
            return {} 