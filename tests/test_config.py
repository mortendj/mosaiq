import json
from pathlib import Path

import pytest

from mosaiq.config import build_registry_from_config, load_documents_from_config

FIXTURES = Path(__file__).parent / "fixtures"


def _write_config(tmp_path: Path, config: dict) -> Path:
    path = tmp_path / "mosaiq-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_loads_documents_from_a_directory_source(tmp_path):
    config_path = _write_config(
        tmp_path, {"sources": [{"type": "directory", "path": str(FIXTURES)}]}
    )

    documents = load_documents_from_config(config_path)

    assert {d.origin_id for d in documents} == {
        "banner_report_acme.txt",
        "markdown_report_contoso.md",
        "host_profile_report_globex.txt",
    }


def test_exclude_drops_documents_by_origin_id(tmp_path):
    config_path = _write_config(
        tmp_path,
        {
            "sources": [{"type": "directory", "path": str(FIXTURES)}],
            "exclude": ["banner_report_acme.txt"],
        },
    )

    documents = load_documents_from_config(config_path)

    assert {d.origin_id for d in documents} == {
        "markdown_report_contoso.md",
        "host_profile_report_globex.txt",
    }


def test_directory_source_respects_custom_extensions(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "report.json").write_text('{"customer": "Test"}', encoding="utf-8")
    (data_dir / "ignored.txt").write_text("not picked up", encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        {"sources": [{"type": "directory", "path": str(data_dir), "extensions": [".json"]}]},
    )

    documents = load_documents_from_config(config_path)

    assert {d.origin_id for d in documents} == {"report.json"}


def test_unknown_source_type_raises(tmp_path):
    config_path = _write_config(tmp_path, {"sources": [{"type": "spreadsheet"}]})

    with pytest.raises(ValueError, match="Unknown source type"):
        load_documents_from_config(config_path)


def test_relative_directory_path_resolves_against_the_config_files_own_folder(tmp_path):
    # The config lives in tmp_path/config/, the data in tmp_path/data/ - a relative
    # "../data" path must resolve against the config file's folder, not whatever the
    # caller's current working directory happens to be.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "report.txt").write_text("content", encoding="utf-8")

    config_path = config_dir / "mosaiq-config.json"
    config_path.write_text(
        json.dumps({"sources": [{"type": "directory", "path": "../data"}]}), encoding="utf-8"
    )

    documents = load_documents_from_config(config_path)

    assert {d.origin_id for d in documents} == {"report.txt"}


def test_build_registry_from_config_recognizes_documents_via_the_mapped_field_parser(tmp_path):
    from mosaiq.model import RawDocument

    mapped_config = {"fields": {"deployment_name": {"keys": ["Customer"]}}}
    (tmp_path / "field-mapping.json").write_text(json.dumps(mapped_config), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        {"parsers": [{"type": "mapped-field", "config_file": "field-mapping.json"}]},
    )

    registry = build_registry_from_config(config_path)
    # None of the 3 built-in parsers recognize this text (they require their own
    # fictional-tool fingerprints) - only the configured mapped-field parser does.
    raw = RawDocument(text="####### REPORT #######\nCustomer: Test Co", origin_id="t.txt")

    result = registry.parse(raw)

    assert result.deployment_name == "Test Co"


def test_unknown_parser_type_raises(tmp_path):
    config_path = _write_config(tmp_path, {"parsers": [{"type": "regex-magic"}]})

    with pytest.raises(ValueError, match="Unknown parser type"):
        build_registry_from_config(config_path)
