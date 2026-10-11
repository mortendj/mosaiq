"""Value-coercion helpers shared by every concrete parser (string -> typed field)."""

from __future__ import annotations

import re
from datetime import date, datetime

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
_NUMBER_RE = re.compile(r"[\d.,]+")


def parse_report_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    if not match:
        return None
    return int(match.group(0).replace(",", "").split(".")[0])


def parse_float_with_unit(value: str | None) -> float | None:
    """Pulls the leading number out of strings like '64 GB' or '1,234.5 GB'."""
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def split_list(value: str | None) -> list[str]:
    if not value:
        return []
    parts = value.split(",") if "," in value else value.split()
    return [p.strip() for p in parts if p.strip()]


_SIZE_RE = re.compile(r"([\d.,]+)\s*(B|KB|MB|GB|TB)\b", re.IGNORECASE)
_UNIT_TO_GB = {"B": 1 / 1024**3, "KB": 1 / 1024**2, "MB": 1 / 1024, "GB": 1.0, "TB": 1024.0}


def parse_size_to_gb(value: str | None) -> float | None:
    """Parses a size string with a variable unit (e.g. '305.617 MB', '2,190 TB',
    '128 GB') into a plain float number of GB. Different reports - or different
    deployments of the same report format - can use whatever unit fits the number,
    so a field like "index size" can't just assume GB the way parse_float_with_unit
    does."""
    if not value:
        return None
    match = _SIZE_RE.search(value)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    unit = match.group(2).upper()
    return round(number * _UNIT_TO_GB[unit], 3)


_GROUPED_COUNT_CACHE: dict[tuple[str, str], re.Pattern[str]] = {}


def extract_grouped_counts(
    text: str, name_field: str, count_field: str
) -> tuple[list[str], int | None]:
    """Finds repeated '<name_field>: X ... <count_field>: N' blocks - e.g. a report
    listing one count per named connector/source - and returns the distinct names
    plus the sum of their counts.

    Takes only the FIRST <count_field> value found after each <name_field>
    occurrence, not every one: some reports list a nested per-sub-item breakdown
    after the named block's own total (e.g. per-repository counts under a
    connector), which repeats or sums to that same total - summing every match
    would double-count.
    """
    cache_key = (name_field, count_field)
    pattern = _GROUPED_COUNT_CACHE.get(cache_key)
    if pattern is None:
        pattern = re.compile(
            rf"{re.escape(name_field)}:\**\s*(\S+).*?{re.escape(count_field)}:\**\s*([\d,]+)",
            re.DOTALL,
        )
        _GROUPED_COUNT_CACHE[cache_key] = pattern

    matches = pattern.findall(text)
    names = list(dict.fromkeys(name for name, _ in matches))
    total = sum(int(count.replace(",", "")) for _, count in matches) if matches else None
    return names, total
