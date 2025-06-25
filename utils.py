import re
from slugify import slugify as pyslugify

def generate_slug(name: str, city: str) -> str:
    """
    Generates a URL-friendly slug from a restaurant name and city.
    
    Example:
        "Girl & The Goat", "Chicago" -> "girl-the-goat-chicago"
    """
    combined = f"{name} {city}"
    # Use python-slugify to handle most cases
    slug = pyslugify(combined)
    return slug 