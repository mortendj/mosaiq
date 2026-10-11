# Quickstart

Everything you need to go from "I have a pile of deployment reports" to a working
Mosaiq dashboard, in one place. Start here — the two subfolders below are reference
material you'll only need once you've decided which path applies to you.

## 1. Try it on the sample fleet first (zero setup)

```bash
pip install -r requirements.txt
python -m mosaiq build --config quickstart/sample-fleet/config.json \
    --output quickstart/sample-fleet/dashboard.html
```

This builds a dashboard from five fictional deployments using only the three report
formats already built into Mosaiq — no config, no code, nothing of yours involved yet.
Open the resulting `dashboard.html` in a browser to see the whole feature set (filters,
charts, the data table) working before you touch your own data. This is also exactly
how the main README's screenshot was produced — see
[`sample-fleet/`](sample-fleet/) for what's in it.

## 2. Check whether your own reports already match a bundled format

If your tool's reports already look like one of Mosaiq's three built-in formats (see
the main README's "Formats supported today" table), you're done — no example here
applies to you. Just point `--source local`/`--config` at your real reports instead of
the sample fleet (see the main README's "Usage" section).

## 3. Otherwise, pick how to teach Mosaiq your format

Two paths, depending on your report's shape — both folders below use the same kind of
fictional report-plus-config pair as the sample fleet above, just for a format Mosaiq
doesn't already know, so you can copy whichever matches your case as a starting point:

- **Your report has the shape "a section header, then a run of `Key: value` lines"**
  (plain text or markdown, whatever the exact delimiters) — no code needed, just a
  field-mapping config file. See [`config-only-format/`](config-only-format/) for the
  full worked example and field-mapping schema reference.
- **Your report is a different shape entirely** (JSON, CSV, XML, a database export...)
  — write a small `ReportParser` subclass. See
  [`custom-report-format/`](custom-report-format/) for the full worked example.

## 4. Point it at your real data

Once your config or parser correctly reads a couple of your own real reports, swap the
`sources` entry in your config from the fictional folder to your real one (a local
folder, or a Confluence page/tree — see the main README's "Combining multiple sources"
section). If your real report data or field names are proprietary, keep your
config/parser file wherever you keep things that don't get committed — nothing about
either mechanism here requires it to be public, only the generic Mosaiq code that reads
it.

All data in this folder (and its subfolders) is entirely fictional — Mosaiq's own
public repo never contains real deployment data.
