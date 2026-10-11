# Sample fleet

Five fictional deployments combining Mosaiq's three built-in report formats — used to
produce the dashboard in the main README's screenshot, and as the "does this even
work" first step before you touch your own data. See [`../README.md`](../README.md)
for the full quickstart walkthrough this fits into.

## What's here

- `config.json` — combines two `directory` sources: `tests/fixtures/` (the banner,
  markdown, and host-profile samples Mosaiq's own test suite uses) and
  `extra_reports/` below.
- `extra_reports/` — two more fictional deployments added purely to give the sample
  fleet some spread to look at: `Initech Partners` (banner format, an older `5.8.0`
  release, MySQL, modest hardware) and `Umbrella Logistics` (markdown format,
  `7.20.0` — deliberately the same exact version as one of the bundled fixtures, so
  the version-distribution chart isn't just five flat, equal-height bars — Oracle,
  the largest deployment in the set).

## Running it

```bash
python -m mosaiq build --config quickstart/sample-fleet/config.json \
    --output quickstart/sample-fleet/dashboard.html
```

No custom parser or config mapping of any kind — every format here is already built
into Mosaiq.
