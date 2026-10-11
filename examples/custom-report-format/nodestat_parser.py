"""Example custom parser: teaches Mosaiq a report shape it has never seen before.

'NodeStat' is a fictional, unrelated inventory tool that exports one JSON file per
deployment - nothing like the banner/markdown text the bundled parsers expect. This
is the same pattern you'd use to adapt Mosaiq to your own real-world tool: write a
ReportParser subclass, keep it outside the committed mosaiq/ package if it (or its
fixtures) ever need anything you don't want public, and register it yourself.

See README.md in this folder for the full walkthrough.
"""

from __future__ import annotations

import json
from datetime import date

from mosaiq.model import DeploymentSnapshot, RawDocument
from mosaiq.parsers.base import ReportParser


class NodeStatJsonParser(ReportParser):
    """Parses NodeStat's JSON export. Doesn't reuse BannerStyleParser/
    MarkdownStyleParser - those only help if your format happens to share their
    "section header, then key: value lines" shape. Implementing sniff()/parse()
    directly works for literally any input shape: JSON here, equally CSV, XML, a
    database export, anything a Source can hand back as text.
    """

    format_name = "nodestat-json"

    def sniff(self, text: str) -> bool:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return False
        return isinstance(data, dict) and "customer" in data and "hardware" in data

    def parse(self, raw: RawDocument) -> DeploymentSnapshot:
        data = json.loads(raw.text)
        hardware = data.get("hardware", {})
        index = data.get("index", {})

        return DeploymentSnapshot(
            deployment_name=data.get("customer", raw.origin_id),
            report_date=_parse_date(data.get("scan_date")),
            product_version=data.get("app_version"),
            modules=set(data.get("features_enabled", [])),
            connectors=list(data.get("integrations", [])),
            database_type=data.get("database"),
            cpu_cores=hardware.get("cpu_cores"),
            ram_gb=hardware.get("ram_gb"),
            index_size_gb=index.get("size_gb"),
            document_count=index.get("document_count"),
            source_format=self.format_name,
            source_reference=raw.origin_id,
        )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
