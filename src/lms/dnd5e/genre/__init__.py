"""Genre configuration system for the d20 rules engine."""

from .config import (
    GenreConfig,
    GenreId,
    GENRES,
    CUSTOM_GENRES,
    get_genre,
    get_available_genres,
    get_genre_categories,
    register_custom_genre,
    create_custom_genre,
    delete_custom_genre,
)
from .terminology import GenreTerminology

__all__ = [
    "GenreConfig",
    "GenreId",
    "GenreTerminology",
    "GENRES",
    "CUSTOM_GENRES",
    "get_genre",
    "get_available_genres",
    "get_genre_categories",
    "register_custom_genre",
    "create_custom_genre",
    "delete_custom_genre",
]
