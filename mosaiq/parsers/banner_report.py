"""Parses the plain-text banner report format ('#### SECTION ####')."""

from __future__ import annotations

from mosaiq.model import DeploymentSnapshot, RawDocument
from mosaiq.parsers import fields
from mosaiq.parsers.base import BannerStyleParser


class BannerReportParser(BannerStyleParser):
    format_name = "banner-report"

    def sniff(self, text: str) -> bool:
        return "REPORT INFO" in text and "FleetProbe" in text and "#" in text

    def parse(self, raw: RawDocument) -> DeploymentSnapshot:
        sections = self._sections(raw.text)
        report_info = sections.get("REPORT INFO", {})
        hosting = sections.get("HOSTING SERVER", {})
        platform = sections.get("PLATFORM INFO", {})
        database = sections.get("DATABASE INFO", {})
        index_stats = sections.get("INDEX STATISTICS", {})
        features = sections.get("FEATURES", {})

        return DeploymentSnapshot(
            deployment_name=report_info.get("Customer", raw.origin_id),
            report_date=fields.parse_report_date(report_info.get("Local time")),
            product_version=platform.get("Platform version"),
            modules=set(fields.split_list(features.get("Enabled modules"))),
            connectors=fields.split_list(platform.get("Connectors in actual use")),
            database_type=database.get("Database type"),
            os_name=hosting.get("OS"),
            cpu_cores=fields.parse_int(hosting.get("CPU cores")),
            ram_gb=fields.parse_float_with_unit(hosting.get("RAM")),
            index_size_gb=fields.parse_float_with_unit(index_stats.get("Total index size")),
            document_count=fields.parse_int(index_stats.get("Total documents indexed")),
            source_format=self.format_name,
            source_reference=raw.origin_id,
        )
