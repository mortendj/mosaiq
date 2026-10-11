"""Parser contract, plus the two shared tokenizing-style base classes concrete
format parsers build on."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mosaiq.model import DeploymentSnapshot, RawDocument
from mosaiq.parsers.kv_sections import tokenize_banner_sections, tokenize_markdown_sections


class ReportParser(ABC):
    """One concrete subclass per report format."""

    format_name: str = "unknown"

    @abstractmethod
    def sniff(self, text: str) -> bool:
        """Cheap fingerprint check: does this text look like this parser's format?"""

    @abstractmethod
    def parse(self, raw: RawDocument) -> DeploymentSnapshot:
        """Parse raw text into a normalized snapshot. Caller guarantees sniff() was True."""


class BannerStyleParser(ReportParser):
    """Base for the '#### SECTION ####' / 'Key: value' plain-text report style shared
    by multiple source tools - only their section/field names differ."""

    def _sections(self, text: str) -> dict[str, dict[str, str]]:
        return tokenize_banner_sections(text)


class MarkdownStyleParser(ReportParser):
    """Base for the '## Section' / '**Key:** value' markdown report style."""

    def _sections(self, text: str) -> dict[str, dict[str, str]]:
        return tokenize_markdown_sections(text)
