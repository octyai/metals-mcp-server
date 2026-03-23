from __future__ import annotations

from pathlib import Path

import yaml

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.adapters.cme import CMEQuoteAdapter
from metals_mcp.adapters.fred import FredAdapter
from metals_mcp.adapters.gdelt import GDELTAdapter
from metals_mcp.adapters.generic_document import GenericDocumentAdapter
from metals_mcp.adapters.nws import NWSAlertsAdapter
from metals_mcp.adapters.sec import SECSubmissionsAdapter
from metals_mcp.config import Settings
from metals_mcp.models.common import SourceManifest


ADAPTER_TYPES: dict[str, type[SourceAdapter]] = {
    "cme_quotes": CMEQuoteAdapter,
    "fred_series": FredAdapter,
    "nws_alerts": NWSAlertsAdapter,
    "gdelt_doc": GDELTAdapter,
    "sec_submissions": SECSubmissionsAdapter,
    "generic_document": GenericDocumentAdapter,
}


class AdapterRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog_path = Path(__file__).resolve().parent.parent / "resources" / "source_catalog.yaml"
        payload = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8"))
        self.manifests = [SourceManifest.model_validate(item) for item in payload["sources"]]

    def list_manifests(self) -> list[SourceManifest]:
        return [manifest for manifest in self.manifests if manifest.enabled]

    def get_manifest(self, source_id: str) -> SourceManifest:
        for manifest in self.manifests:
            if manifest.source_id == source_id:
                return manifest
        raise KeyError(source_id)

    def create(self, source_id: str) -> SourceAdapter:
        manifest = self.get_manifest(source_id)
        adapter_cls = ADAPTER_TYPES[manifest.adapter_type]
        return adapter_cls(manifest, self.settings)
