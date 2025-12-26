"""Genre configuration system for the d20 rules engine."""

from .config import GenreConfig, GENRES, get_genre, get_available_genres
from .terminology import GenreTerminology

__all__ = [
    "GenreConfig",
    "GenreTerminology",
    "GENRES",
    "get_genre",
    "get_available_genres",
]
