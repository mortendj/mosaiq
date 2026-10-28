"""Normalized data model that every parser produces, regardless of source format."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class RawDocument:
    """A single unparsed report, independent of where it came from."""

    text: str
    origin_id: str
    origin_url: str | None = None
    fetched_at: date | None = None


@dataclass
class DeploymentSnapshot:
    """One normalized point-in-time report for a single deployment."""

    deployment_name: str
    report_date: date | None
    customer_id: str | None = None
    product_version: str | None = None
    modules: set[str] = field(default_factory=set)
    connectors: list[str] = field(default_factory=list)
    database_type: str | None = None
    os_name: str | None = None
    cpu_cores: int | None = None
    ram_gb: float | None = None
    index_size_gb: float | None = None
    document_count: int | None = None
    license_expiry: str | None = None
    license_status: str | None = None
    auto_restart: str | None = None
    source_format: str = ""
    source_reference: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnparsedDocument:
    """A document no registered parser recognized, surfaced instead of dropped."""

    origin_id: str
    origin_url: str | None
    reason: str
