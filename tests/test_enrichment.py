import json

import pytest

from mosaiq.config import load_enrichments_from_config
from mosaiq.enrichment import JsonLookupEnrichment, apply_enrichments
from mosaiq.model import DeploymentSnapshot

ACME_ID = "4200001"
CONTOSO_ID = "4200002"


def snapshot(name, customer_id=None, license_status=None):
    return DeploymentSnapshot(
        deployment_name=name,
        report_date=None,
        customer_id=customer_id,
        license_status=license_status,
    )


def write_table(tmp_path, table, name="table.json"):
    path = tmp_path / name
    path.write_text(json.dumps(table), encoding="utf-8")
    return path


def test_joins_values_onto_matching_snapshots(tmp_path):
    path = write_table(tmp_path, {ACME_ID: {"status": "valid"}, CONTOSO_ID: {"status": "perpetual"}})
    enrichment = JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})

    snapshots = [snapshot("Acme Nordics", ACME_ID), snapshot("Contoso Labs", CONTOSO_ID)]
    assert enrichment.apply(snapshots) == 2
    assert [s.license_status for s in snapshots] == ["valid", "perpetual"]


def test_leaves_unmatched_snapshots_untouched(tmp_path):
    """A partial table must degrade gracefully, not blank out existing values."""
    path = write_table(tmp_path, {ACME_ID: {"status": "valid"}})
    enrichment = JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})

    missing = snapshot("Globex Industries", "9999999", license_status="kept")
    no_key = snapshot("Nordgate Systems", None, license_status="kept")
    snapshots = [snapshot("Acme Nordics", ACME_ID), missing, no_key]

    assert enrichment.apply(snapshots) == 1
    assert missing.license_status == "kept"
    assert no_key.license_status == "kept"


def test_keys_compared_as_stripped_strings(tmp_path):
    """Report-derived ids arrive as strings and may carry stray whitespace."""
    path = write_table(tmp_path, {f" {ACME_ID} ": {"status": "valid"}})
    enrichment = JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})

    snapshots = [snapshot("Acme Nordics", f"{ACME_ID} ")]
    assert enrichment.apply(snapshots) == 1
    assert snapshots[0].license_status == "valid"


def test_absent_record_key_does_not_overwrite(tmp_path):
    path = write_table(tmp_path, {ACME_ID: {"other": "x"}})
    enrichment = JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})

    snapshots = [snapshot("Acme Nordics", ACME_ID, license_status="kept")]
    assert enrichment.apply(snapshots) == 1
    assert snapshots[0].license_status == "kept"


def test_rejects_non_object_table(tmp_path):
    path = write_table(tmp_path, [{"status": "valid"}])
    with pytest.raises(ValueError, match="must contain a JSON object"):
        JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})


def test_apply_enrichments_reports_match_counts(tmp_path):
    path = write_table(tmp_path, {ACME_ID: {"status": "valid"}})
    enrichment = JsonLookupEnrichment.from_file(path, "customer_id", {"license_status": "status"})

    results = apply_enrichments(
        [snapshot("Acme Nordics", ACME_ID), snapshot("Globex Industries", "1")], [enrichment]
    )
    assert [matched for _, matched in results] == [1]


def test_config_resolves_enrichment_path_relative_to_config_file(tmp_path):
    """Same config-relative rule as sources and parsers, so a build can run from anywhere."""
    nested = tmp_path / "nested"
    nested.mkdir()
    write_table(nested, {ACME_ID: {"status": "valid"}}, name="status.json")
    config = nested / "mosaiq-config.json"
    config.write_text(
        json.dumps(
            {
                "sources": [],
                "enrichments": [
                    {
                        "type": "json-lookup",
                        "file": "status.json",
                        "match_on": "customer_id",
                        "fields": {"license_status": "status"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    enrichments = load_enrichments_from_config(config)
    assert len(enrichments) == 1
    assert enrichments[0].table == {ACME_ID: {"status": "valid"}}


def test_enrichments_are_optional(tmp_path):
    config = tmp_path / "mosaiq-config.json"
    config.write_text(json.dumps({"sources": []}), encoding="utf-8")
    assert load_enrichments_from_config(config) == []


def test_rejects_unknown_enrichment_type(tmp_path):
    config = tmp_path / "mosaiq-config.json"
    config.write_text(json.dumps({"enrichments": [{"type": "csv-lookup"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown enrichment type"):
        load_enrichments_from_config(config)
