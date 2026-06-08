"""Base parser interface."""

from abc import ABC, abstractmethod
from typing import List

from ..models import Flashcard


class BaseParser(ABC):
    """Abstract base class for all parsers."""

    @abstractmethod
    def parse(self) -> List[Flashcard]:
        """Parse source file and return flashcards."""
        ...
