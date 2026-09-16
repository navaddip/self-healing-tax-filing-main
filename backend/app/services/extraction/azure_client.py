"""Azure Document Intelligence client helper."""

from __future__ import annotations

from typing import Any


def build_azure_client(endpoint: str, key: str):
    """Return an Azure DocumentIntelligenceClient."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    return DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
