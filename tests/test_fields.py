from mosaiq.parsers.fields import extract_grouped_counts, parse_size_to_gb


def test_parse_size_to_gb_handles_varying_units():
    assert parse_size_to_gb("128 GB") == 128.0
    assert parse_size_to_gb("305.617 MB") == round(305.617 / 1024, 3)
    assert parse_size_to_gb("2,190 TB") == 2190 * 1024.0
    assert parse_size_to_gb("0.000 B") == 0.0


def test_parse_size_to_gb_handles_missing_or_unmatched_values():
    assert parse_size_to_gb(None) is None
    assert parse_size_to_gb("") is None
    assert parse_size_to_gb("unknown") is None


def test_extract_grouped_counts_sums_top_level_only():
    text = """
sourceName: filesystem
recordCount: 500
subItems:
    recordCount: 500

sourceName: web
recordCount: 300
"""
    names, total = extract_grouped_counts(text, "sourceName", "recordCount")
    assert names == ["filesystem", "web"]
    assert total == 800  # not 1300 - the nested sub-item count isn't re-summed


def test_extract_grouped_counts_returns_none_total_when_nothing_found():
    names, total = extract_grouped_counts("nothing relevant here", "sourceName", "recordCount")
    assert names == []
    assert total is None
