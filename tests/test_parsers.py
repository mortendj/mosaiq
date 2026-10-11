from datetime import date
from pathlib import Path

import pytest

from mosaiq.model import RawDocument
from mosaiq.parsers.banner_report import BannerReportParser
from mosaiq.parsers.host_profile_report import HostProfileReportParser
from mosaiq.parsers.markdown_report import MarkdownReportParser
from mosaiq.parsers.registry import ParserRegistry

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> RawDocument:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return RawDocument(text=text, origin_id=name)


def test_banner_report_parses_acme():
    parser = BannerReportParser()
    raw = _load("banner_report_acme.txt")
    assert parser.sniff(raw.text)

    snapshot = parser.parse(raw)
    assert snapshot.deployment_name == "Acme Nordics"
    assert snapshot.report_date == date(2026, 5, 14)
    assert snapshot.product_version == "7.19.0"
    assert snapshot.connectors == ["sharepoint", "fileserver", "exchange"]
    assert snapshot.database_type == "POSTGRES"
    assert snapshot.cpu_cores == 8
    assert snapshot.ram_gb == 64.0
    assert snapshot.index_size_gb == 128.0
    assert snapshot.document_count == 4_250_000
    assert snapshot.modules == {"Search", "Insights"}
    assert snapshot.source_format == "banner-report"


def test_markdown_report_parses_contoso():
    parser = MarkdownReportParser()
    raw = _load("markdown_report_contoso.md")
    assert parser.sniff(raw.text)

    snapshot = parser.parse(raw)
    assert snapshot.deployment_name == "Contoso Labs"
    assert snapshot.report_date == date(2025, 11, 2)
    assert snapshot.product_version == "7.4.0"
    assert snapshot.connectors == ["fileserver", "web"]
    assert snapshot.database_type == "MSSQL"
    assert snapshot.cpu_cores == 12
    assert snapshot.ram_gb == 48.0
    assert snapshot.index_size_gb == 41.0
    assert snapshot.document_count == 980_000
    assert snapshot.modules == {"Search"}
    assert snapshot.source_format == "markdown-report"


def test_host_profile_report_parses_globex():
    parser = HostProfileReportParser()
    raw = _load("host_profile_report_globex.txt")
    assert parser.sniff(raw.text)

    snapshot = parser.parse(raw)
    assert snapshot.deployment_name == "Globex Industries"
    assert snapshot.report_date == date(2026, 7, 20)
    assert snapshot.product_version == "7.20.0"
    assert snapshot.connectors == ["sharepoint", "exchange", "web", "fileserver"]
    assert snapshot.database_type == "POSTGRES"
    assert snapshot.os_name == "Microsoft Windows Server 2022 Standard, v. 10.0.20348"
    assert snapshot.cpu_cores == 16
    assert snapshot.ram_gb == 96.0
    assert snapshot.index_size_gb == 310.0
    assert snapshot.document_count == 12_400_000
    assert snapshot.modules == {"Search", "Insights", "Assistant"}
    assert snapshot.source_format == "host-profile-report"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "banner_report_acme.txt",
        "markdown_report_contoso.md",
        "host_profile_report_globex.txt",
    ],
)
def test_registry_dispatches_to_the_right_parser(fixture_name: str):
    registry = ParserRegistry()
    snapshot = registry.parse(_load(fixture_name))
    assert snapshot.deployment_name


def test_registry_surfaces_unparsed_documents_instead_of_dropping_them():
    registry = ParserRegistry()
    raw = RawDocument(text="not a recognizable report format at all", origin_id="mystery.txt")
    snapshots, unparsed = registry.parse_all([raw])
    assert snapshots == []
    assert len(unparsed) == 1
    assert unparsed[0].origin_id == "mystery.txt"
