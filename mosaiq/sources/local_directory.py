"""Reads raw reports from a local folder - the offline/no-credentials source."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from mosaiq.model import RawDocument
from mosaiq.sources.base import Source

DEFAULT_EXTENSIONS = (".txt", ".md", ".html")


class LocalDirectorySource(Source):
    def __init__(self, path: str | Path, extensions: tuple[str, ...] = DEFAULT_EXTENSIONS):
        self.path = Path(path).resolve()
        self.extensions = extensions

    def discover(self) -> Iterable[RawDocument]:
        if not self.path.exists():
            raise FileNotFoundError(f"Local source path does not exist: {self.path}")

        for file_path in sorted(self.path.rglob("*")):
            if not file_path.is_file() or file_path.suffix.lower() not in self.extensions:
                continue
            yield RawDocument(
                text=file_path.read_text(encoding="utf-8", errors="replace"),
                origin_id=str(file_path.relative_to(self.path)),
                origin_url=file_path.as_uri(),
                fetched_at=_file_modified_date(file_path),
            )


def _file_modified_date(file_path: Path) -> date:
    return datetime.fromtimestamp(file_path.stat().st_mtime).date()
