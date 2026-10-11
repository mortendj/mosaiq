# Example: adding a format with config only, no code

This is the other way to teach Mosaiq a new report format — not by writing a parser
in Python (see `examples/custom-report-format/` for that), but purely through a
config file, for any report whose data lives in the "section header, then key: value
lines" shape (the same shape Mosaiq's three bundled parsers already use).

The fictional tool here, "StackSentry", is unrelated to anything else in this repo
and has its own field names nobody's seen before — `Client`, `Captured`, `CPU Count`,
`Catalog Size`, and so on. Mosaiq never needs code changes to understand it.

## What's here

- `stacksentry_reports/` — three fictional StackSentry reports: two real-looking
  deployments (`Riverside Mutual Insurance`, `Lakeside Timber Co`) and one that
  should be excluded (`Smoke Test Runner`, a non-deployment test run).
- `stacksentry-fields.json` — **this is the file that matters.** It maps Mosaiq's
  normalized fields to StackSentry's own literal field names. This is the *only*
  place any real-world-specific knowledge lives — see "The field-mapping schema"
  below for every option.
- `stacksentry-config.json` — the same kind of sources config as everywhere else in
  Mosaiq, plus a new `"parsers"` key pointing at the field-mapping file above.

## Running it

From the repo root, using the stock CLI — no example-specific script at all:

```bash
python -m mosaiq build --config examples/config-only-format/stacksentry-config.json \
    --output examples/config-only-format/dashboard.html
```

You should see one document reported as unparsed (`smoke-test-runner.txt` — correctly
excluded by the field-mapping's `exclude_if` rule) and a dashboard built from the
other two.

## The field-mapping schema

```json
{
  "format_name": "stacksentry-text",
  "sniff_requires": ["HOST REPORT"],
  "fields": {
    "deployment_name": {"keys": ["Client"]},
    "report_date":     {"keys": ["Captured"], "type": "date"},
    "cpu_cores":       {"keys": ["CPU Count"], "type": "int"},
    "ram_gb":          {"keys": ["Memory"], "type": "size_gb"}
  },
  "document_count": {"name_field": "sourceName", "count_field": "recordCount"},
  "modules": {
    "always": ["Search"],
    "rules": [
      {"module": "Auditor", "key": "Compliance Module", "contains": "Enabled"},
      {"module": "Agent", "key": "Copilot Mode", "not_in": ["", "disabled", "off"]}
    ]
  },
  "exclude_if": {"key": "Purpose", "values": ["smoke-test"]}
}
```

- **`fields`** — one entry per `DeploymentSnapshot` field you want populated.
  `"keys"` is a list tried in order (first non-empty, non-error value wins) — useful
  when a real tool renamed a field across versions and both still show up in the
  wild. `"type"` controls how the raw string is converted: `string` (default),
  `int`, `date` (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`), `size_gb` (any of
  B/KB/MB/GB/TB, converted to a plain GB number), or `list` (comma- or
  whitespace-separated).
- **`document_count`** *(optional)* — for reports that list one count per named
  source/connector rather than a single total. Sums every `count_field` value found
  immediately after each `name_field` occurrence — and only the first one per
  occurrence, so a nested per-sub-item breakdown that repeats the same total
  underneath doesn't get double-counted. Also supplies the `connectors` list.
- **`modules`** *(optional)* — `"always"` is a flat list added unconditionally;
  `"rules"` adds a module when a field `"contains"` a substring, or when a field's
  value is `"not_in"` a given set (case-insensitive) — i.e. "present and not one of
  these inactive-looking values." Multiple rules can target the same module name.
- **`exclude_if`** *(optional)* — drop any document where a field's value is in the
  given list. Checked as part of recognizing the document, so an excluded document
  shows up in the build output as "could not be parsed" rather than silently
  vanishing.
- **`sniff_requires`** *(optional)* — extra substrings that must all be present, on
  top of the `deployment_name` field being resolvable, before this parser claims a
  document. Only needed if you're registering more than one `mapped-field` parser
  and need to help them tell each other's reports apart.

## Using this for your own real report format

1. Copy `stacksentry-fields.json`, replace every key with your own tool's literal
   field names.
2. Copy `stacksentry-config.json`, point `sources` at your real reports (a local
   folder or a Confluence tree/page — see the main README).
3. Keep both files wherever you keep local, non-committed configuration (Mosaiq's
   own real-world setup does exactly this) — nothing about this mechanism requires
   any of it to be public. The Python code that reads it is 100% generic either way.
