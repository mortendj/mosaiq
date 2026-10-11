"""Source contract: anything that can hand back RawDocuments, regardless of format."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from mosaiq.model import RawDocument


class Source(ABC):
    @abstractmethod
    def discover(self) -> Iterable[RawDocument]:
        """Yield every raw document this source currently has available."""
