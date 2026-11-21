"""Aggregates DeploymentSnapshots into one self-contained HTML dashboard."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from mosaiq.model import DeploymentSnapshot

TEMPLATE_DIR = Path(__file__).parent / "templates"

_ONE_CLOCK = (
    "One page, every deployment: connectors, versions, modules, and hardware "
    "&mdash; sliced however you like."
)
_PER_DEPLOYMENT = "Each customer's data is as of the date in the <strong>Report date</strong> column"


def _long_date(value: str) -> str:
    """2026-10-28 -> October 28th, 2026. A header is read in passing, and a bare ISO
    date next to a sentence reads as a serial number; spelled out, it registers as a
    date without anyone having to stop. Anything that isn't a plain ISO date is printed
    as given, since the value comes from whatever produced the table."""
    try:
        parsed = datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return str(value)
    suffix = "th" if parsed.day in (11, 12, 13) else {1: "st", 2: "nd", 3: "rd"}.get(parsed.day % 10, "th")
    return f"{parsed.strftime('%B')} {parsed.day}{suffix}, {parsed.year}"


def _subtitle(enrichments: Iterable) -> str:
    """The page's own freshness disclosure, built from what the data actually knows.

    Every column on a row is as of that deployment's own report date; an enriched column
    is as of the export it was joined from, one date shared by every row - which makes it
    the thing on the page most likely to be read as current when it isn't. Saying so is
    only safe if the date cannot drift from the data, so it comes from the enrichment
    itself rather than being written into the template: a build whose table carries no
    `as_of` names no exception at all instead of quoting a date nothing stands behind.
    """
    dated = [(e.label, e.as_of) for e in enrichments if getattr(e, "label", None) and getattr(e, "as_of", None)]
    if not dated:
        return _ONE_CLOCK
    if len(dated) == 1:
        label, as_of = dated[0]
        exception = (
            f"the <strong>{html.escape(str(label))}</strong> status, which is as of "
            f"{html.escape(_long_date(as_of))}, for all"
        )
    else:
        exception = ", ".join(
            f"<strong>{html.escape(str(label))}</strong> ({html.escape(_long_date(as_of))})"
            for label, as_of in dated
        ) + ", which are as of those dates for all"
    return f"{_PER_DEPLOYMENT}, with the exception of {exception}."


def deduplicate_latest_per_deployment(
    snapshots: list[DeploymentSnapshot],
) -> list[DeploymentSnapshot]:
    """No history is kept - if a deployment appears more than once, the newest
    report_date wins (snapshots with no date lose to any snapshot that has one)."""
    latest: dict[str, DeploymentSnapshot] = {}
    for snapshot in snapshots:
        existing = latest.get(snapshot.deployment_name)
        if existing is None or _is_newer(snapshot, existing):
            latest[snapshot.deployment_name] = snapshot
    return list(latest.values())


def _is_newer(candidate: DeploymentSnapshot, existing: DeploymentSnapshot) -> bool:
    if candidate.report_date is None:
        return False
    if existing.report_date is None:
        return True
    return candidate.report_date > existing.report_date


def _snapshot_to_json(snapshot: DeploymentSnapshot) -> dict:
    return {
        "deployment_name": snapshot.deployment_name,
        "customer_id": snapshot.customer_id,
        "license_expiry": snapshot.license_expiry,
        "license_status": snapshot.license_status,
        "auto_restart": snapshot.auto_restart,
        "hosting_provider": snapshot.hosting_provider,
        "report_date": snapshot.report_date.isoformat() if snapshot.report_date else None,
        "product_version": snapshot.product_version,
        "modules": sorted(snapshot.modules),
        "connectors": snapshot.connectors,
        "database_type": snapshot.database_type,
        "os_name": snapshot.os_name,
        "cpu_cores": snapshot.cpu_cores,
        "ram_gb": snapshot.ram_gb,
        "index_size_gb": snapshot.index_size_gb,
        "document_count": snapshot.document_count,
        "source_format": snapshot.source_format,
    }


def build_dashboard(
    snapshots: list[DeploymentSnapshot],
    output_path: str | Path,
    unparsed_count: int = 0,
    enrichments: Iterable = (),
) -> Path:
    """Writes one fully self-contained HTML file - chart library and dashboard logic
    are inlined, not referenced as separate files, so the output can be emailed/shared
    as a single attachment and still work when opened directly (no server)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    deduplicated = deduplicate_latest_per_deployment(snapshots)
    data_json = json.dumps([_snapshot_to_json(s) for s in deduplicated], indent=None)

    template = (TEMPLATE_DIR / "index.html.template").read_text(encoding="utf-8")
    chartjs = (TEMPLATE_DIR.parent / "assets" / "chart.umd.min.js").read_text(encoding="utf-8")
    dashboard_js = (TEMPLATE_DIR / "dashboard.js").read_text(encoding="utf-8")

    html = (
        template.replace("__MOSAIQ_CHARTJS_INLINE__", chartjs)
        .replace("__MOSAIQ_DASHBOARD_JS_INLINE__", dashboard_js)
        .replace("__MOSAIQ_DATA_JSON__", data_json)
        .replace("__MOSAIQ_SUBTITLE__", _subtitle(enrichments))
        .replace("__MOSAIQ_GENERATED_AT__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        .replace("__MOSAIQ_DEPLOYMENT_COUNT__", str(len(deduplicated)))
        .replace("__MOSAIQ_UNPARSED_COUNT__", str(unparsed_count))
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path
