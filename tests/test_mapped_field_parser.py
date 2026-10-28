from datetime import date
from pathlib import Path

from mosaiq.model import RawDocument
from mosaiq.parsers.mapped_field_report import MappedFieldParser

FIXTURES = Path(__file__).parent / "fixtures_mapped_field"

CONFIG = {
    "format_name": "test-mapped-format",
    "sniff_requires": ["HOST REPORT"],
    "fields": {
        "deployment_name": {"keys": ["Client"]},
        "report_date": {"keys": ["Captured"], "type": "date"},
        "product_version": {"keys": ["Build"]},
        "database_type": {"keys": ["Data Engine"]},
        "os_name": {"keys": ["OS Build"]},
        "cpu_cores": {"keys": ["CPU Count"], "type": "int"},
        "ram_gb": {"keys": ["Memory"], "type": "size_gb"},
        "index_size_gb": {"keys": ["Catalog Size"], "type": "size_gb"},
    },
    "document_count": {"name_field": "sourceName", "count_field": "recordCount"},
    "modules": {
        "always": ["Search"],
        "rules": [
            {"module": "Auditor", "key": "Compliance Module", "contains": "Enabled"},
            {"module": "Agent", "key": "Copilot Mode", "not_in": ["", "disabled", "off", "none", "inactive"]},
        ],
    },
    "auto_restart": {
        "keys": ["Restart Window", "Scheduled Restart"],
        "off_values": ["", "none", "not scheduled"],
    },
    "exclude_if": {"key": "Purpose", "values": ["smoke-test"]},
}


def _load(name: str) -> RawDocument:
    return RawDocument(text=(FIXTURES / name).read_text(encoding="utf-8"), origin_id=name)


def _inline(body: str) -> RawDocument:
    text = "####################### HOST REPORT #######################\nClient: Inline Co\n" + body
    return RawDocument(text=text, origin_id="inline")


def test_sniffs_and_parses_a_report_format_never_seen_by_any_built_in_parser():
    parser = MappedFieldParser(CONFIG)
    raw = _load("sample.txt")

    assert parser.sniff(raw.text)
    snapshot = parser.parse(raw)

    assert snapshot.deployment_name == "Example Test Co"
    assert snapshot.report_date == date(2026, 2, 18)
    assert snapshot.product_version == "5.2.0"
    assert snapshot.database_type == "POSTGRES"
    assert snapshot.os_name == "Windows Server 2022 Datacenter"
    assert snapshot.cpu_cores == 12
    assert snapshot.ram_gb == 48.0
    assert snapshot.index_size_gb == 524.288  # 0.512 TB -> GB
    assert snapshot.connectors == ["filesystem", "mail"]
    assert snapshot.document_count == 1_124_500
    assert snapshot.modules == {"Search", "Auditor", "Agent"}
    assert snapshot.auto_restart == "Yes"
    assert snapshot.source_format == "test-mapped-format"


def test_auto_restart_reads_no_from_a_nothing_is_scheduled_sentinel():
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Restart Window: Not scheduled\n"))

    assert snapshot.auto_restart == "No"


def test_auto_restart_falls_back_to_a_later_key_spelling():
    """Tools rename their own field labels between versions, and both spellings stay
    in the wild as long as old reports do - the same reason `fields` takes a key list."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Scheduled Restart: Daily at 01:00\n"))

    assert snapshot.auto_restart == "Yes"


def test_auto_restart_is_unset_when_the_report_never_mentions_restarts():
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Build: 5.2.0\n"))

    assert snapshot.auto_restart is None


def test_exclude_if_rejects_matching_documents_via_sniff():
    parser = MappedFieldParser(CONFIG)
    raw = _load("excluded.txt")

    assert not parser.sniff(raw.text)


def test_sniff_fails_without_a_resolvable_deployment_name():
    parser = MappedFieldParser(CONFIG)
    text = "####################### HOST REPORT #######################\nBuild: 1.0.0"

    assert not parser.sniff(text)
