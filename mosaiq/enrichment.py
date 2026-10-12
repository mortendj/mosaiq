"""Joins extra per-deployment attributes onto parsed snapshots from an external
dataset, so facts that live outside the reports themselves can still appear on the
dashboard.

A report describes a deployment as it saw itself at the moment it was captured.
Some things a fleet view wants are not in the report at all, or are stale there
because they change after a report is written - contract state, support tier,
owner, licence validity. Those live in some other system, keyed by an identifier
the report does carry.

An enrichment is that join: a lookup table keyed by one snapshot field, whose
values are copied onto named snapshot fields. Mosaiq stays agnostic about where
the table came from or what the values mean - producing it is your job, and the
producer is usually a small local script that never needs to be committed.

Config shape (see README):

    "enrichments": [
      {
        "type": "json-lookup",
        "file": "license-status.json",
        "match_on": "customer_id",
        "fields": {"license_status": "status"}
      }
    ]

`match_on` names the snapshot field used as the lookup key, and `fields` maps
snapshot field name -> key within the looked-up record. The JSON file itself is a
flat object of key -> record:

    {"4200001": {"status": "valid"}, "4200002": {"status": "perpetual"}}

Keys are compared as strings with surrounding whitespace stripped. A snapshot
whose key is missing, empty, or absent from the table is left untouched, so a
partial table degrades gracefully instead of blanking existing values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from mosaiq.model import DeploymentSnapshot


@dataclass
class JsonLookupEnrichment:
    """A lookup table keyed by one snapshot field, mapped onto other fields."""

    table: dict[str, dict[str, Any]]
    match_on: str
    fields: dict[str, str]

    @classmethod
    def from_file(cls, path: str | Path, match_on: str, fields: dict[str, str]) -> JsonLookupEnrichment:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(
                f"Enrichment file {path} must contain a JSON object of key -> record, "
                f"got {type(raw).__name__}"
            )
        table = {str(key).strip(): value for key, value in raw.items()}
        return cls(table=table, match_on=match_on, fields=fields)

    def apply(self, snapshots: Iterable[DeploymentSnapshot]) -> int:
        """Copies looked-up values onto matching snapshots. Returns the match count."""
        matched = 0
        for snapshot in snapshots:
            key = getattr(snapshot, self.match_on, None)
            if key is None:
                continue
            record = self.table.get(str(key).strip())
            if record is None:
                continue
            matched += 1
            for field_name, record_key in self.fields.items():
                value = record.get(record_key)
                if value is not None:
                    setattr(snapshot, field_name, value)
        return matched


def apply_enrichments(
    snapshots: list[DeploymentSnapshot], enrichments: Iterable[JsonLookupEnrichment]
) -> list[tuple[JsonLookupEnrichment, int]]:
    """Applies each enrichment in order, returning (enrichment, matched count) pairs
    so the caller can report coverage rather than silently joining nothing."""
    return [(enrichment, enrichment.apply(snapshots)) for enrichment in enrichments]
