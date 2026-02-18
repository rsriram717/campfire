# services/google_service.py

import os
import requests
from typing import List, Dict, Optional
from .places import PlacesService

import logging
import uuid

# City coordinates for location biasing
CITY_COORDINATES = {
    "Chicago": {"latitude": 41.8781, "longitude": -87.6298},
    "New York": {"latitude": 40.7128, "longitude": -74.0060}
}

# Neighbourhood coordinates and search radius (metres)
NEIGHBORHOOD_COORDINATES = {
    # Chicago
    "West Loop":    {"latitude": 41.8827, "longitude": -87.6480, "radius": 2000},
    "Wicker Park":  {"latitude": 41.9088, "longitude": -87.6795, "radius": 1800},
    "Lincoln Park": {"latitude": 41.9241, "longitude": -87.6467, "radius": 2200},
    "River North":  {"latitude": 41.8924, "longitude": -87.6344, "radius": 1500},
    "Logan Square": {"latitude": 41.9217, "longitude": -87.7077, "radius": 2000},
    "Pilsen":       {"latitude": 41.8566, "longitude": -87.6618, "radius": 1800},
    "Gold Coast":   {"latitude": 41.9038, "longitude": -87.6282, "radius": 1500},
    "Loop":         {"latitude": 41.8827, "longitude": -87.6278, "radius": 1500},
    "Lakeview":     {"latitude": 41.9400, "longitude": -87.6519, "radius": 2200},
    # New York
    "Manhattan":       {"latitude": 40.7831, "longitude": -73.9712, "radius": 3000},
    "Brooklyn":        {"latitude": 40.6782, "longitude": -73.9442, "radius": 3000},
    "Williamsburg":    {"latitude": 40.7081, "longitude": -73.9571, "radius": 1800},
    "SoHo":            {"latitude": 40.7233, "longitude": -74.0030, "radius": 1200},
    "East Village":    {"latitude": 40.7265, "longitude": -73.9815, "radius": 1200},
    "Tribeca":         {"latitude": 40.7163, "longitude": -74.0086, "radius": 1200},
    "West Village":    {"latitude": 40.7358, "longitude": -74.0036, "radius": 1200},
    "Upper East Side": {"latitude": 40.7736, "longitude": -73.9566, "radius": 2000},
}

class GooglePlacesService(PlacesService):
    """
    Google Places API (New) implementation of the PlacesService.
    Uses the v1 API (https://places.googleapis.com/v1/).
    """
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.base_url = "https://places.googleapis.com/v1"

    def autocomplete(self, query: str, city: str, session_token: Optional[str] = None) -> Optional[List[Dict]]:
        if not self.api_key:
            logging.error("GOOGLE_API_KEY is not set.")
            return None

        # Headers for the New API
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }

        # Request Body
        body = {
            "input": query,
            "includedRegionCodes": ["us"],
            # "includedPrimaryTypes": ["restaurant", "food"], # Optional: Filter strictly to food places
        }

        # Add session token if provided
        if session_token:
            body["sessionToken"] = session_token

        # Add location bias if city is known
        if city in CITY_COORDINATES:
            body["locationBias"] = {
                "circle": {
                    "center": CITY_COORDINATES[city],
                    "radius": 20000.0 # 20km
                }
            }

        try:
            logging.debug(f"Calling Google Places Autocomplete (New) with body: {body}")
            response = requests.post(f"{self.base_url}/places:autocomplete", headers=headers, json=body)
            
            # Handle specific New API errors
            if response.status_code != 200:
                 logging.error(f"Google API Error ({response.status_code}): {response.text}")
                 return None
                 
            data = response.json()
            suggestions = data.get("suggestions", [])
            logging.debug(f"Google Autocomplete found {len(suggestions)} results")
            
            results = []
            for s in suggestions:
                place_prediction = s.get("placePrediction", {})
                
                # The New API returns 'placeId' directly, or 'place' as resource name.
                place_id = place_prediction.get("placeId")
                if not place_id:
                    resource_name = place_prediction.get("place", "")
                    place_id = resource_name.replace("places/", "") if resource_name.startswith("places/") else resource_name
                
                text_obj = place_prediction.get("text", {})
                main_text = text_obj.get("text", "")
                
                # structuredFormat contains mainText and secondaryText (address)
                structured = place_prediction.get("structuredFormat", {})
                main_text_struct = structured.get("mainText", {}).get("text", main_text)
                secondary_text = structured.get("secondaryText", {}).get("text", "")

                results.append({
                    "name": main_text_struct,
                    "place_id": place_id,
                    "address": secondary_text,
                })
                
            return results

        except requests.RequestException as e:
            logging.error(f"Error calling Google Places API: {e}")
            return None

    def get_details(self, place_id: str, session_token: Optional[str] = None) -> Optional[Dict]:
        if not self.api_key:
            logging.error("GOOGLE_API_KEY is not set.")
            return None
        
        # Ensure place_id is in the format "places/..." for the URL if strictly required,
        # but v1 endpoint usually is /v1/places/{id}. 
        # Documentation says resource name: "places/{PLACE_ID}".
        resource_name = f"places/{place_id}" if not place_id.startswith("places/") else place_id
        
        headers = {
            "X-Goog-Api-Key": self.api_key,
            # Specify fields to return (FieldMask is required/recommended for billing control)
            # Fields are camelCase in v1.
            "X-Goog-FieldMask": "id,displayName,formattedAddress,nationalPhoneNumber,websiteUri,types,priceLevel,rating,userRatingCount,editorialSummary,primaryType,dineIn,takeout,delivery,reservable"
        }

        params = {}
        if session_token:
            params["sessionToken"] = session_token
        
        try:
            response = requests.get(f"{self.base_url}/{resource_name}", headers=headers, params=params)
            if response.status_code != 200:
                logging.error(f"Google API Error ({response.status_code}): {response.text}")
                return None
                
            place = response.json()

            # Map v1 response back to our internal schema
            # v1 returns types as snake_case values in a list, e.g. ["restaurant", "food"]
            
            # Extract ID without prefix
            raw_id = place.get("id", "")
            if not raw_id:
                # Fallback to parsing resource name
                raw_id = place.get("name", "").replace("places/", "")
            if not raw_id: raw_id = place_id # Ultimate fallback

            return {
                "name": place.get("displayName", {}).get("text"),
                "place_id": raw_id,
                "address": place.get("formattedAddress"),
                "phone": place.get("nationalPhoneNumber"),
                "website": place.get("websiteUri"),
                "categories": place.get("types", []),
                "price_level": place.get("priceLevel"),
                "rating": place.get("rating"),
                "user_rating_count": place.get("userRatingCount"),
                "editorial_summary": place.get("editorialSummary", {}).get("text"),
                "primary_type": place.get("primaryType"),
                "serves_dine_in": place.get("dineIn"),
                "serves_takeout": place.get("takeout"),
                "serves_delivery": place.get("delivery"),
                "reservable": place.get("reservable"),
            }
        except requests.RequestException as e:
            logging.error(f"Error calling Google Places API: {e}")
            return None

    def search_nearby_candidates(
        self,
        city: str,
        neighborhood: Optional[str] = None,
        restaurant_types: Optional[List] = None,
        radius: int = 8000,
        max_results: int = 20
    ) -> List[Dict]:
        if not self.api_key:
            logging.error("GOOGLE_API_KEY is not set.")
            return []

        if city not in CITY_COORDINATES:
            logging.warning(f"No coordinates configured for city: {city}")
            return []

        # Use neighbourhood coordinates + tighter radius if available
        if neighborhood and neighborhood in NEIGHBORHOOD_COORDINATES:
            nb = NEIGHBORHOOD_COORDINATES[neighborhood]
            centre = {"latitude": nb["latitude"], "longitude": nb["longitude"]}
            search_radius = nb["radius"]
            logging.debug(f"Using neighbourhood coordinates for {neighborhood} (radius {search_radius}m)")
        else:
            centre = CITY_COORDINATES[city]
            search_radius = radius
            logging.debug(f"Using city coordinates for {city} (radius {search_radius}m)")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.types,places.priceLevel,places.rating,places.userRatingCount,places.editorialSummary,places.primaryType,places.dineIn,places.takeout,places.delivery,places.reservable"
        }

        # Map frontend type selections to Google Place types for Bar searches.
        # Fine Dining and Casual stay broad ("restaurant") and are filtered post-fetch
        # using price_level, since Google's fine_dining_restaurant type is inconsistent.
        if restaurant_types and "Bar" in restaurant_types and len(restaurant_types) == 1:
            included_types = ["bar", "cocktail_bar", "wine_bar", "pub"]
        else:
            included_types = ["restaurant"]

        body = {
            "includedTypes": included_types,
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": centre,
                    "radius": search_radius
                }
            }
        }

        try:
            logging.debug(f"Calling Google Places searchNearby for city: {city}")
            response = requests.post(f"{self.base_url}/places:searchNearby", headers=headers, json=body)

            if response.status_code != 200:
                logging.error(f"Google searchNearby Error ({response.status_code}): {response.text}")
                return []

            data = response.json()
            places = data.get("places", [])
            logging.debug(f"searchNearby returned {len(places)} candidates for {city}")

            results = []
            for place in places:
                raw_id = place.get("id", "")
                if not raw_id:
                    raw_id = place.get("name", "").replace("places/", "")

                results.append({
                    "name": place.get("displayName", {}).get("text"),
                    "place_id": raw_id,
                    "address": place.get("formattedAddress"),
                    "phone": None,
                    "website": None,
                    "categories": place.get("types", []),
                    "price_level": place.get("priceLevel"),
                    "rating": place.get("rating"),
                    "user_rating_count": place.get("userRatingCount"),
                    "editorial_summary": place.get("editorialSummary", {}).get("text"),
                    "primary_type": place.get("primaryType"),
                    "serves_dine_in": place.get("dineIn"),
                    "serves_takeout": place.get("takeout"),
                    "serves_delivery": place.get("delivery"),
                    "reservable": place.get("reservable"),
                })

            return results

        except requests.RequestException as e:
            logging.error(f"Error calling Google searchNearby API: {e}")
            return []