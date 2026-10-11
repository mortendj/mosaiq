"""Runs this example end to end: loads the NodeStat JSON reports via Mosaiq's
standard directory source, parses them with the custom NodeStatJsonParser (not part
of the committed mosaiq package), and builds the exact same kind of dashboard every
built-in format produces.

This script itself is just a runnable harness for the example - it exists so this
folder can be executed standalone without copy-pasting anything into a real project.
It's not a tool Mosaiq provides to automate adding a format: the few lines here
(construct a ParserRegistry with your parser, call build_dashboard) are exactly what
the programmer adding a new format - here, or for their own real tool - writes once,
by hand, as part of wiring that format into their own build.

Run from inside this folder:

    python build_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))  # repo root, so `import mosaiq` resolves

from mosaiq.config import load_documents_from_config  # noqa: E402
from mosaiq.dashboard.generator import build_dashboard  # noqa: E402
from mosaiq.parsers.registry import ParserRegistry  # noqa: E402
from nodestat_parser import NodeStatJsonParser  # noqa: E402


def main() -> None:
    documents = load_documents_from_config(HERE / "nodestat-config.json")
    registry = ParserRegistry([NodeStatJsonParser()])
    snapshots, unparsed = registry.parse_all(documents)

    output_path = build_dashboard(snapshots, HERE / "dashboard.html", unparsed_count=len(unparsed))
    print(f"Wrote dashboard for {len(snapshots)} deployment(s) to {output_path}")
    if unparsed:
        print(f"{len(unparsed)} document(s) could not be parsed.")


if __name__ == "__main__":
    main()
