# services/google_service.py

import os
import requests
from typing import List, Dict, Optional
from .places import PlacesService

class GooglePlacesService(PlacesService):
    """
    Google Places API implementation of the PlacesService.
    """
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/place"

    def autocomplete(self, query: str, city: str) -> Optional[List[Dict]]:
        if not self.api_key:
            print("Error: GOOGLE_API_KEY is not set. Please check your .env file.")
            return None

        # Google's autocomplete is more effective with session tokens for billing
        # For this project, we'll make standalone requests for simplicity.
        params = {
            "input": f"{query} in {city}",
            "types": "establishment",
            "fields": "place_id,structured_formatting",
            "key": self.api_key,
        }
        
        try:
            response = requests.get(f"{self.base_url}/autocomplete/json", params=params)
            response.raise_for_status()
            predictions = response.json().get("predictions", [])
            
            return [
                {
                    "name": p["structured_formatting"]["main_text"],
                    "place_id": p["place_id"],
                    "address": p["structured_formatting"].get("secondary_text", ""),
                }
                for p in predictions
            ]
        except requests.RequestException as e:
            print(f"Error calling Google Places API: {e}")
            return None

    def get_details(self, place_id: str) -> Optional[Dict]:
        if not self.api_key:
            print("Error: GOOGLE_API_KEY is not set. Please check your .env file.")
            return None
            
        params = {
            "place_id": place_id,
            "fields": "name,place_id,formatted_address,website,formatted_phone_number,type",
            "key": self.api_key,
        }
        
        try:
            response = requests.get(f"{self.base_url}/details/json", params=params)
            response.raise_for_status()
            result = response.json().get("result", {})

            return {
                "name": result.get("name"),
                "place_id": result.get("place_id"),
                "address": result.get("formatted_address"),
                "phone": result.get("formatted_phone_number"),
                "website": result.get("website"),
                "categories": result.get("types", []),
            }
        except requests.RequestException as e:
            print(f"Error calling Google Places API: {e}")
            return None 