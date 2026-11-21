"""The page's freshness line, which is generated rather than written into the template
because what it can honestly claim depends on what the data carries."""

from dataclasses import dataclass

from mosaiq.dashboard.generator import _subtitle


@dataclass
class FakeEnrichment:
    label: str | None = None
    as_of: str | None = None


def test_names_the_exception_when_an_enrichment_knows_its_own_date():
    text = _subtitle([FakeEnrichment(label="Licence", as_of="2026-10-28")])

    assert "Report date" in text
    assert "<strong>Licence</strong>" in text
    assert "which is as of October 28th, 2026, for all" in text


def test_names_no_exception_when_no_date_is_available():
    """Quoting a date the data can't back is how a page starts lying about its own age,
    so a build whose table carries no `as_of` keeps the plain description instead."""
    text = _subtitle([FakeEnrichment(label="Licence"), FakeEnrichment(as_of="2026-10-28")])

    assert "exception" not in text
    assert "One page, every deployment" in text


def test_lists_every_dated_enrichment_when_there_is_more_than_one():
    text = _subtitle(
        [FakeEnrichment(label="Licence", as_of="2026-10-28"), FakeEnrichment(label="Support tier", as_of="2026-09-01")]
    )

    assert "<strong>Licence</strong> (October 28th, 2026)" in text
    assert "<strong>Support tier</strong> (September 1st, 2026)" in text


def test_spells_out_dates_but_prints_anything_else_as_given():
    """The date is whatever produced the table wrote, so an unexpected shape has to
    survive rather than be mangled into a wrong one."""
    assert "Q3 2026" in _subtitle([FakeEnrichment(label="Licence", as_of="Q3 2026")])
    assert "November 11th, 2026" in _subtitle([FakeEnrichment(label="Licence", as_of="2026-11-11")])
    assert "March 2nd, 2026" in _subtitle([FakeEnrichment(label="Licence", as_of="2026-03-02")])


def test_escapes_what_the_config_supplies():
    text = _subtitle([FakeEnrichment(label="<script>", as_of="2026-10-28")])

    assert "<script>" not in text
    assert "&lt;script&gt;" in text
