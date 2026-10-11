"""Aggregates DeploymentSnapshots into one self-contained HTML dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mosaiq.model import DeploymentSnapshot

TEMPLATE_DIR = Path(__file__).parent / "templates"


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
    snapshots: list[DeploymentSnapshot], output_path: str | Path, unparsed_count: int = 0
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
        .replace("__MOSAIQ_GENERATED_AT__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        .replace("__MOSAIQ_DEPLOYMENT_COUNT__", str(len(deduplicated)))
        .replace("__MOSAIQ_UNPARSED_COUNT__", str(unparsed_count))
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path
