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
    "hosting_provider": {
        "keys": ["Network Adapter", "Host FQDN"],
        "providers": [
            {"label": "Northwind Hosting", "domains": ["cust.northwind-mh.example", "nwh-shared.example"]}
        ],
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
    assert snapshot.hosting_provider == "Northwind Hosting"
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


def test_hosting_provider_is_read_from_a_hostname_under_the_providers_domain():
    """The adapter field names the domain on its own; the hostname field carries it as
    a suffix. Either shape has to resolve to the same provider, since which of the two
    a given report carries is not something the reader gets to choose."""
    parser = MappedFieldParser(CONFIG)

    adapter = parser.parse(_inline("Network Adapter: ltc.cust.northwind-mh.example/Ethernet0\n"))
    hostname = parser.parse(_inline("Host FQDN: ltc-x-s-4.ltc.cust.northwind-mh.example\n"))

    assert adapter.hosting_provider == "Northwind Hosting"
    assert hostname.hosting_provider == "Northwind Hosting"


def test_hosting_provider_matches_the_providers_domain_case_insensitively():
    """Windows reports its own hostname in whatever case it feels like; DNS does not
    care about case and neither can this."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Host FQDN: LTC-X-S-4.LTC.Cust.Northwind-MH.Example\n"))

    assert snapshot.hosting_provider == "Northwind Hosting"


def test_hosting_provider_matches_a_shared_domain_customers_join_directly():
    """The same provider can run more than one estate: one domain per customer under a
    suffix it owns, and one shared domain every customer's machines join directly. Both
    are just "domains this provider's machines live under", so both are one list."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Host FQDN: ltc-app-04.nwh-shared.example\n"))

    assert snapshot.hosting_provider == "Northwind Hosting"


def test_hosting_provider_falls_back_to_a_later_key_when_the_first_carries_no_domain():
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(
        _inline("Network Adapter: 10.4.1.20/Ethernet0\nHost FQDN: ltc-x-s-4.ltc.cust.northwind-mh.example\n")
    )

    assert snapshot.hosting_provider == "Northwind Hosting"


def test_hosting_provider_reads_other_when_the_report_carries_no_domain_at_all():
    """A machine that was never joined to a domain reports a bare computer name. That
    is still "no provider of mine owns this", so it belongs with every other non-match
    - otherwise ticking every provider plus `Other` would not account for the fleet."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Network Adapter: Network/Ethernet (Public)\nHost FQDN: LOCATORSERVER\n"))

    assert snapshot.hosting_provider == "Other"


def test_hosting_provider_reads_other_from_a_domain_no_provider_claims():
    """Not "self-hosted": an unrecognized domain could be a provider nobody has
    configured yet. `Other` says only what the evidence supports, while still giving
    the filter a tickable complement."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Host FQDN: RM-APP-07.corp.riverside-mutual.example\n"))

    assert snapshot.hosting_provider == "Other"


def test_hosting_provider_does_not_match_a_domain_that_merely_ends_in_the_same_letters():
    """A lookalike like "notcust.northwind-mh.example" is a different domain from
    "cust.northwind-mh.example" and belongs to whoever registered it - the suffix only
    matches on a label boundary, never mid-label."""
    parser = MappedFieldParser(CONFIG)

    snapshot = parser.parse(_inline("Host FQDN: host.notcust.northwind-mh.example\n"))

    assert snapshot.hosting_provider == "Other"


def test_hosting_provider_is_unset_when_no_providers_are_configured():
    """Asking which provider hosts a deployment and asking whether anyone was checked
    at all are different questions. With no provider configured the field stays unset for everybody and the
    filter hides itself, rather than labelling the whole fleet `Other` as though
    something had been checked and found absent."""
    no_block = MappedFieldParser({**CONFIG, "hosting_provider": None})
    empty_list = MappedFieldParser({**CONFIG, "hosting_provider": {"keys": ["Host FQDN"], "providers": []}})
    raw = _inline("Host FQDN: ltc-x-s-4.ltc.cust.northwind-mh.example\n")

    assert no_block.parse(raw).hosting_provider is None
    assert empty_list.parse(raw).hosting_provider is None


def test_exclude_if_rejects_matching_documents_via_sniff():
    parser = MappedFieldParser(CONFIG)
    raw = _load("excluded.txt")

    assert not parser.sniff(raw.text)


def test_sniff_fails_without_a_resolvable_deployment_name():
    parser = MappedFieldParser(CONFIG)
    text = "####################### HOST REPORT #######################\nBuild: 1.0.0"

    assert not parser.sniff(text)
