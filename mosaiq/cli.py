"""Command-line entry point: `python -m mosaiq build ...`"""

from __future__ import annotations

import argparse
import sys

from mosaiq.dashboard.generator import build_dashboard
from mosaiq.parsers.registry import ParserRegistry
from mosaiq.sources.local_directory import LocalDirectorySource


def _build(args: argparse.Namespace) -> int:
    if args.config:
        from mosaiq.config import build_registry_from_config, load_documents_from_config

        documents = load_documents_from_config(args.config)
        registry = build_registry_from_config(args.config)
    elif args.source == "local":
        documents = list(LocalDirectorySource(args.path).discover())
        registry = ParserRegistry()
    elif args.source == "confluence":
        from mosaiq.sources.confluence import ConfluenceSource

        source = ConfluenceSource(
            base_url=args.confluence_url,
            space_keys=args.space,
            email=args.confluence_email,
            api_token=args.confluence_token,
        )
        documents = list(source.discover())
        registry = ParserRegistry()
    else:
        raise ValueError(f"Unknown source: {args.source}")

    snapshots, unparsed = registry.parse_all(documents)

    for doc in unparsed:
        print(f"[unparsed] {doc.origin_id}: {doc.reason}", file=sys.stderr)

    output_path = build_dashboard(snapshots, args.output, unparsed_count=len(unparsed))
    print(f"Wrote dashboard for {len(snapshots)} deployment(s) to {output_path}")
    if unparsed:
        print(f"{len(unparsed)} document(s) could not be parsed - see warnings above.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mosaiq")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the dashboard HTML page.")
    build_parser.add_argument(
        "--config", help="JSON config file combining multiple sources (see README) - takes precedence over --source."
    )
    build_parser.add_argument("--source", choices=["local", "confluence"], help="Single source (ignored if --config is given).")
    build_parser.add_argument("--path", help="Folder of reports (required for --source local).")
    build_parser.add_argument(
        "--space", action="append", default=[], help="Confluence space key (repeatable)."
    )
    build_parser.add_argument("--confluence-url", help="Confluence base URL, e.g. https://x.atlassian.net/wiki")
    build_parser.add_argument("--confluence-email", help="Confluence account email (or set MOSAIQ_CONFLUENCE_EMAIL).")
    build_parser.add_argument("--confluence-token", help="Confluence API token (or set MOSAIQ_CONFLUENCE_TOKEN).")
    build_parser.add_argument("--output", default="dist/index.html", help="Output HTML file path.")
    build_parser.set_defaults(func=_build)

    parsed_args = parser.parse_args(argv)
    if parsed_args.command == "build" and not parsed_args.config and not parsed_args.source:
        parser.error("one of --config or --source is required")
    return parsed_args.func(parsed_args)


if __name__ == "__main__":
    raise SystemExit(main())
