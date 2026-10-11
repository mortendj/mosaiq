"""A generic ReportParser driven entirely by a config dict, for any report whose
data lives in the "section header, then key: value lines" shape (banner or
markdown, or a tool that exports either depending on how a report was captured) -
no Python subclass needed, just a mapping from DeploymentSnapshot fields to the
report's own literal field names.

This is what makes it possible to keep a real, proprietary report format's field
names out of a public repo entirely: the code here is 100% generic, and the one
thing that's specific to any given real format - its literal section/field names -
lives only in a config file you load at runtime, which you simply don't commit.

See quickstart/config-only-format/ for a complete worked example and the config
schema, and README.md for the summary.
"""

from __future__ import annotations

import json
from pathlib import Path

from mosaiq.model import DeploymentSnapshot, RawDocument
from mosaiq.parsers import fields
from mosaiq.parsers.base import ReportParser
from mosaiq.parsers.kv_sections import flatten_any_sections

_FIELD_CONVERTERS = {
    "string": lambda value: value,
    "int": fields.parse_int,
    "date": fields.parse_report_date,
    "size_gb": fields.parse_size_to_gb,
    "float": fields.parse_float_with_unit,
    "list": fields.split_list,
}


class MappedFieldParser(ReportParser):
    def __init__(self, config: dict):
        self.config = config
        self.format_name = config.get("format_name", "mapped-field-report")
        self._error_marker = config.get("error_marker", "ERROR")

    @classmethod
    def from_config_file(cls, path: str | Path) -> MappedFieldParser:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _first_present(self, flat: dict[str, str], keys: list[str]) -> str | None:
        for key in keys:
            value = flat.get(key)
            if value and not value.startswith(self._error_marker):
                return value
        return None

    def _resolve(self, flat: dict[str, str], field_name: str, default=None):
        spec = self.config["fields"].get(field_name)
        if not spec:
            return default
        raw_value = self._first_present(flat, spec["keys"])
        if raw_value is None:
            return default
        return _FIELD_CONVERTERS[spec.get("type", "string")](raw_value)

    def sniff(self, text: str) -> bool:
        flat = flatten_any_sections(text)
        name_keys = self.config["fields"]["deployment_name"]["keys"]
        if not self._first_present(flat, name_keys):
            return False
        if any(required not in text for required in self.config.get("sniff_requires", [])):
            return False
        exclude = self.config.get("exclude_if")
        if exclude and flat.get(exclude["key"], "").strip() in exclude["values"]:
            return False
        return True

    def parse(self, raw: RawDocument) -> DeploymentSnapshot:
        flat = flatten_any_sections(raw.text)

        connectors = self._resolve(flat, "connectors", []) or []
        document_count = None
        count_cfg = self.config.get("document_count")
        if count_cfg:
            names, total = fields.extract_grouped_counts(
                raw.text, count_cfg["name_field"], count_cfg["count_field"]
            )
            if names:
                connectors = names
            document_count = total

        modules = set(self.config.get("modules", {}).get("always", []))
        for rule in self.config.get("modules", {}).get("rules", []):
            value = flat.get(rule["key"], "")
            if "contains" in rule and rule["contains"] in value:
                modules.add(rule["module"])
            elif "not_in" in rule and value.strip().lower() not in {v.lower() for v in rule["not_in"]}:
                modules.add(rule["module"])

        return DeploymentSnapshot(
            deployment_name=self._resolve(flat, "deployment_name", raw.origin_id),
            report_date=self._resolve(flat, "report_date"),
            product_version=self._resolve(flat, "product_version"),
            modules=modules,
            connectors=connectors,
            database_type=self._resolve(flat, "database_type"),
            os_name=self._resolve(flat, "os_name"),
            cpu_cores=self._resolve(flat, "cpu_cores"),
            ram_gb=self._resolve(flat, "ram_gb"),
            index_size_gb=self._resolve(flat, "index_size_gb"),
            document_count=document_count,
            source_format=self.format_name,
            source_reference=raw.origin_id,
        )
