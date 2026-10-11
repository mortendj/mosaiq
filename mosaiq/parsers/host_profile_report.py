"""Parses a second tool's plain-text banner report - same tokenizing style as the
first (section headers + key: value lines), but a different set of section/field
names (e.g. HOST IDENTITY, SYSTEM RESOURCES instead of HOSTING SERVER).
"""

from __future__ import annotations

from mosaiq.model import DeploymentSnapshot, RawDocument
from mosaiq.parsers import fields
from mosaiq.parsers.base import BannerStyleParser


class HostProfileReportParser(BannerStyleParser):
    format_name = "host-profile-report"

    def sniff(self, text: str) -> bool:
        return "HOST IDENTITY" in text and "SYSTEM RESOURCES" in text

    def parse(self, raw: RawDocument) -> DeploymentSnapshot:
        sections = self._sections(raw.text)
        report_info = sections.get("REPORT INFO", {})
        host_identity = sections.get("HOST IDENTITY", {})
        system_resources = sections.get("SYSTEM RESOURCES", {})
        installation = sections.get("PLATFORM INSTALLATION", {})
        database = sections.get("DATABASE INFO", {})
        index_stats = sections.get("INDEX STATISTICS", {})
        features = sections.get("FEATURES", {})

        return DeploymentSnapshot(
            deployment_name=report_info.get("Customer", raw.origin_id),
            report_date=fields.parse_report_date(report_info.get("Local time")),
            product_version=installation.get("Platform version"),
            modules=set(fields.split_list(features.get("Enabled modules"))),
            connectors=fields.split_list(installation.get("Connectors in actual use")),
            database_type=database.get("Database type"),
            os_name=host_identity.get("Operating system"),
            cpu_cores=fields.parse_int(system_resources.get("CPU cores")),
            ram_gb=fields.parse_float_with_unit(system_resources.get("RAM capacity")),
            index_size_gb=fields.parse_float_with_unit(index_stats.get("Total index size")),
            document_count=fields.parse_int(index_stats.get("Total documents indexed")),
            source_format=self.format_name,
            source_reference=raw.origin_id,
        )
