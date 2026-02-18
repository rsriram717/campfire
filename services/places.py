# services/places.py

from abc import ABC, abstractmethod
from typing import Optional, List

class PlacesService(ABC):
    """
    An abstract base class for a places service.
    Defines the interface for fetching place information.
    """

    @abstractmethod
    def autocomplete(self, query: str, city: str, session_token: Optional[str] = None) -> list[dict]:
        """
        Given a query string and a city, return a list of autocomplete suggestions.
        
        Each suggestion should be a dictionary with at least:
        - 'name': The restaurant's name
        - 'place_id': The provider's unique ID for the restaurant
        - 'address': The restaurant's address
        """
        pass

    @abstractmethod
    def get_details(self, place_id: str, session_token: Optional[str] = None) -> dict:
        """
        Given a place_id, return detailed information about the place.

        The returned dictionary should contain:
        - 'name'
        - 'place_id'
        - 'address'
        - 'phone'
        - 'website'
        - 'categories'
        """
        pass

    @abstractmethod
    def search_nearby_candidates(
        self, city: str, neighborhood: Optional[str] = None,
        restaurant_types: Optional[List] = None, radius: int = 8000,
        max_results: int = 20
    ) -> List[dict]:
        """
        Return up to max_results real restaurant candidates near city.

        Each dict should have the same shape as get_details() plus rich fields:
        price_level, rating, user_rating_count, editorial_summary, primary_type,
        serves_dine_in, serves_takeout, serves_delivery, reservable.
        """
        pass