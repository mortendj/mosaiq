"""Loads a JSON config file describing which source(s) to pull reports from, and
optionally which custom parser(s) to register alongside the built-in ones, so a
single build can combine a local folder with one or more Confluence page trees and
teach Mosaiq a report format without writing a committed parser. See README for the
file format, and quickstart/config-only-format/ for a complete worked example.

Any relative path inside the config file (a `directory` source's `path`, a
`mapped-field` parser's `config_file`) is resolved relative to the config file's own
location, not the current working directory - so a config and the files it points at
can be run from anywhere without needing the caller to `cd` into their folder first.
The same applies to a `.mosaiq-credentials` file: each `confluence-*` source built from
a config looks for it next to the config file, not in the current working directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from mosaiq.enrichment import JsonLookupEnrichment
from mosaiq.model import RawDocument
from mosaiq.parsers.mapped_field_report import MappedFieldParser
from mosaiq.parsers.registry import DEFAULT_PARSERS, ParserRegistry
from mosaiq.sources.confluence import ConfluenceSinglePageSource, ConfluenceTreeSource
from mosaiq.sources.local_directory import LocalDirectorySource


def _build_directory_source(entry: dict, base_dir: Path) -> LocalDirectorySource:
    kwargs = {}
    if "extensions" in entry:
        kwargs["extensions"] = tuple(entry["extensions"])
    return LocalDirectorySource(path=_resolve(entry["path"], base_dir), **kwargs)


_SOURCE_BUILDERS = {
    "directory": _build_directory_source,
    "confluence-tree": lambda entry, base_dir: ConfluenceTreeSource(
        base_url=entry["base_url"],
        page_id=entry["page_id"],
        email=entry.get("email"),
        api_token=entry.get("api_token"),
        credentials_dir=base_dir,
    ),
    "confluence-page": lambda entry, base_dir: ConfluenceSinglePageSource(
        base_url=entry["base_url"],
        page_id=entry["page_id"],
        email=entry.get("email"),
        api_token=entry.get("api_token"),
        credentials_dir=base_dir,
    ),
}


def _resolve(path: str, base_dir: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else base_dir / candidate


def _load(config_path: str | Path) -> tuple[dict, Path]:
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return config, config_path.parent


def load_documents_from_config(config_path: str | Path) -> list[RawDocument]:
    config, base_dir = _load(config_path)

    documents: list[RawDocument] = []
    for entry in config.get("sources", []):
        documents.extend(_build_source(entry, base_dir).discover())

    exclude_ids = {str(value) for value in config.get("exclude", [])}
    if exclude_ids:
        documents = [d for d in documents if d.origin_id not in exclude_ids]

    return documents


def build_registry_from_config(config_path: str | Path) -> ParserRegistry:
    """Builds a registry with Mosaiq's built-in parsers plus any custom ones listed
    under the config's "parsers" key. The built-in parsers never match real-world
    data (their fingerprints are specific to their own test fixtures), so including
    them alongside your own is always safe."""
    config, base_dir = _load(config_path)

    parsers = list(DEFAULT_PARSERS)
    for entry in config.get("parsers", []):
        parsers.append(_build_parser(entry, base_dir))
    return ParserRegistry(parsers)


def load_enrichments_from_config(config_path: str | Path) -> list[JsonLookupEnrichment]:
    """Builds the enrichments listed under the config's "enrichments" key. Returns an
    empty list when the key is absent, so enrichment is entirely opt-in."""
    config, base_dir = _load(config_path)
    return [_build_enrichment(entry, base_dir) for entry in config.get("enrichments", [])]


def _build_enrichment(entry: dict, base_dir: Path) -> JsonLookupEnrichment:
    entry_type = entry.get("type")
    if entry_type != "json-lookup":
        raise ValueError(f"Unknown enrichment type {entry_type!r} - expected 'json-lookup'")
    return JsonLookupEnrichment.from_file(
        path=_resolve(entry["file"], base_dir),
        match_on=entry["match_on"],
        fields=entry["fields"],
    )


def _build_parser(entry: dict, base_dir: Path):
    entry_type = entry.get("type")
    if entry_type == "mapped-field":
        return MappedFieldParser.from_config_file(_resolve(entry["config_file"], base_dir))
    raise ValueError(f"Unknown parser type {entry_type!r} - expected 'mapped-field'")


def _build_source(entry: dict, base_dir: Path):
    entry_type = entry.get("type")
    builder = _SOURCE_BUILDERS.get(entry_type)
    if builder is None:
        raise ValueError(
            f"Unknown source type {entry_type!r} - expected one of {sorted(_SOURCE_BUILDERS)}"
        )
    return builder(entry, base_dir)
