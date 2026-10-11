"""Dispatches each raw document to the first parser whose sniff() matches."""

from __future__ import annotations

from mosaiq.model import DeploymentSnapshot, RawDocument, UnparsedDocument
from mosaiq.parsers.banner_report import BannerReportParser
from mosaiq.parsers.base import ReportParser
from mosaiq.parsers.host_profile_report import HostProfileReportParser
from mosaiq.parsers.markdown_report import MarkdownReportParser

DEFAULT_PARSERS: list[ReportParser] = [
    BannerReportParser(),
    MarkdownReportParser(),
    HostProfileReportParser(),
]


class ParserRegistry:
    def __init__(self, parsers: list[ReportParser] | None = None):
        self._parsers = parsers if parsers is not None else list(DEFAULT_PARSERS)

    def parse(self, raw: RawDocument) -> DeploymentSnapshot | UnparsedDocument:
        for parser in self._parsers:
            if parser.sniff(raw.text):
                return parser.parse(raw)
        return UnparsedDocument(
            origin_id=raw.origin_id,
            origin_url=raw.origin_url,
            reason="No registered parser recognized this document's format.",
        )

    def parse_all(
        self, documents: list[RawDocument]
    ) -> tuple[list[DeploymentSnapshot], list[UnparsedDocument]]:
        snapshots: list[DeploymentSnapshot] = []
        unparsed: list[UnparsedDocument] = []
        for doc in documents:
            result = self.parse(doc)
            if isinstance(result, UnparsedDocument):
                unparsed.append(result)
            else:
                snapshots.append(result)
        return snapshots, unparsed
