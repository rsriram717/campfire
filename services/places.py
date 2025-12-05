# services/places.py

from abc import ABC, abstractmethod
from typing import Optional

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