import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

from mosaiq.model import RawDocument  # noqa: E402
from nodestat_parser import NodeStatJsonParser  # noqa: E402

FIXTURES = HERE / "nodestat_reports"


def test_sniffs_and_parses_blue_harbor():
    parser = NodeStatJsonParser()
    text = (FIXTURES / "blue-harbor.json").read_text(encoding="utf-8")
    raw = RawDocument(text=text, origin_id="blue-harbor.json")

    assert parser.sniff(text)
    snapshot = parser.parse(raw)

    assert snapshot.deployment_name == "Blue Harbor Logistics"
    assert snapshot.report_date == date(2026, 4, 2)
    assert snapshot.product_version == "3.8.1"
    assert snapshot.cpu_cores == 8
    assert snapshot.ram_gb == 32
    assert snapshot.database_type == "MSSQL"
    assert snapshot.index_size_gb == 54.2
    assert snapshot.document_count == 812000
    assert snapshot.connectors == ["email-sync", "file-share", "crm-bridge"]
    assert snapshot.modules == {"search", "insights"}


def test_does_not_sniff_other_formats():
    parser = NodeStatJsonParser()
    assert not parser.sniff("####### REPORT INFO #######\nCustomer: Acme")
    assert not parser.sniff("not json at all")
