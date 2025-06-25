import os
from .google_service import GooglePlacesService
from .yelp_service import YelpService
# Import other services like GoogleService here

def get_places_service():
    """
    Factory function to get the configured places service.
    """
    provider = os.getenv("PLACES_PROVIDER", "google").lower()
    
    if provider == "google":
        return GooglePlacesService()
    elif provider == "yelp":
        return YelpService()
    else:
        raise ValueError(f"Unsupported places provider: {provider}")

# Make it easily importable
places_service = get_places_service() 