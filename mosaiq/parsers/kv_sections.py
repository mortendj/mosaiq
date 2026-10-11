"""Shared section/key-value tokenizing for the two report shapes parsers build on.

Both the plain-text banner style and the Confluence markdown style are fundamentally
"section header, then a run of key: value lines" - only the delimiters differ. Keeping
that tokenizing here means each
concrete parser only has to supply its own section/field names, not re-implement parsing.
"""

from __future__ import annotations

import re

_BANNER_SECTION_RE = re.compile(r"^#+\s*([A-Z0-9 /&-]+?)\s*#+\s*$", re.MULTILINE)
_MARKDOWN_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

_KV_LINE_RE = re.compile(r"^\s*([A-Za-z0-9 /_.()-]+?):\s*(.*)$")
_KV_BOLD_LINE_RE = re.compile(r"^\s*\*\*([A-Za-z0-9 /_.()-]+?):?\*\*:?\s*(.*)$")


def tokenize_banner_sections(text: str) -> dict[str, dict[str, str]]:
    """'#### SECTION NAME ####' headers, 'Key: value' body lines."""
    return _tokenize(text, _BANNER_SECTION_RE, _KV_LINE_RE)


def tokenize_markdown_sections(text: str) -> dict[str, dict[str, str]]:
    """'## Section Name' headers, '**Key:** value' body lines."""
    return _tokenize(text, _MARKDOWN_SECTION_RE, _KV_BOLD_LINE_RE)


def flatten_any_sections(text: str) -> dict[str, str]:
    """Tries both tokenizing styles and merges every section's key/value pairs into
    one flat lookup, ignoring which section (or which style) each key came from.
    Useful when the same underlying tool can export either shape depending on how a
    report was captured, or when a caller just wants "give me every field this
    document has" without caring about section structure at all."""
    flat: dict[str, str] = {}
    for tokenizer in (tokenize_banner_sections, tokenize_markdown_sections):
        for section_values in tokenizer(text).values():
            flat.update(section_values)
    return flat


def _tokenize(
    text: str, section_pattern: re.Pattern[str], kv_pattern: re.Pattern[str]
) -> dict[str, dict[str, str]]:
    markers = list(section_pattern.finditer(text))
    sections: dict[str, dict[str, str]] = {}
    for i, marker in enumerate(markers):
        name = marker.group(1).strip()
        start = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        sections[name] = _parse_key_value_lines(text[start:end], kv_pattern)
    return sections


def _parse_key_value_lines(body: str, pattern: re.Pattern[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in body.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key, value = match.group(1).strip(), match.group(2).strip()
        if key and key not in values:
            values[key] = value
    return values
