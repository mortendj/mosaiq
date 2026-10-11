# Custom report format

The other of the two ways to teach Mosaiq a new report format — see
[`../README.md`](../README.md) for the full quickstart walkthrough this fits into, and
[`../config-only-format/`](../config-only-format/) for the no-code path when your
report happens to be "section header, then key: value lines" shaped. This path is for
everything else: demonstrated here against a deliberately unrelated, fictional tool
("NodeStat") that exports JSON instead of the banner/markdown text the bundled
parsers expect. All the data here is made up; this is the same pattern you'd use to
teach Mosaiq your own real-world tool, whatever shape its reports come in.

Extending Mosaiq to a new format is always two separate things:

1. **A data source** — where the raw report text comes from. Already built in: a
   local directory (`type: directory`, used by this example) or a Confluence page
   or page-tree (`type: confluence-page` / `confluence-tree`, see the main README's
   "Combining multiple sources" section). You don't write anything for this part
   unless your source is neither of those.
2. **A parser** — code that reads that raw text and produces a `DeploymentSnapshot`.
   This is the part you write. `nodestat_parser.py` in this folder is a complete,
   runnable example of it.

## What's here

- `nodestat_reports/` — two fictional NodeStat JSON exports (`Blue Harbor
  Logistics`, `Nordgate Systems`) — a shape nothing like what Mosaiq's bundled
  banner/markdown parsers expect.
- `nodestat_parser.py` — a `ReportParser` subclass that reads that JSON shape. It
  does **not** reuse `BannerStyleParser`/`MarkdownStyleParser` — those only help if
  your format happens to share their "section header, then key: value lines" shape.
  Implementing `sniff()`/`parse()` directly works for any input shape: JSON here,
  equally CSV, XML, a database export, anything.
- `nodestat-config.json` — points Mosaiq's directory source at `nodestat_reports/`.
- `build_example.py` — wires it together: loads the documents the normal way (the
  same `--config`-driven directory source every Mosaiq build uses), parses them
  with `NodeStatJsonParser` (registered standalone here, not merged into Mosaiq's
  built-in parser list), and calls the same `build_dashboard()` every other format
  uses. This script is just a runnable harness for the example, not a feature of
  Mosaiq itself — the handful of lines it contains (registry + `build_dashboard()`
  call) are exactly what you, the programmer adding a format, write once by hand when
  wiring your own parser into your own build.
- `test_nodestat_parser.py` — a couple of tests confirming the parser reads the
  fixtures correctly; `pytest` run from the repo root picks this up automatically
  alongside Mosaiq's own test suite.

## Running it

```bash
cd quickstart/custom-report-format
python build_example.py
```

Produces the exact same kind of single-file interactive dashboard as the main
README's screenshot — same charts, same filters — built entirely from a format
Mosaiq had never seen before, with about 50 lines of parser code and zero changes
to the committed package.

## Adapting this to your own tool

1. Copy `nodestat_parser.py` as a starting point. Replace the `sniff()` check with
   a fingerprint reliable for *your* tool's output, and `parse()`'s field mapping
   with your own report's fields.
2. Point a `directory` or `confluence-tree`/`confluence-page` source at your real
   reports.
3. Keep your parser — and any fixtures with real company/field names — **outside**
   this repo if you ever share your fork publicly and your source data contains
   anything proprietary. That's exactly why this example's parser lives here as a
   standalone script instead of inside `mosaiq/parsers/`: nothing stops you from
   registering a custom parser without ever touching the committed package.
