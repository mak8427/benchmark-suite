"""Tests for CLI endpoint configuration."""

from __future__ import annotations

import importlib


def test_default_api_url_uses_ingress_prefix(monkeypatch) -> None:
    """Default CLI traffic should use the routed backend path."""
    monkeypatch.delenv("BENCHWRAP_SERVER_URL", raising=False)
    monkeypatch.delenv("BENCHWRAP_API_URL", raising=False)

    import benchwrap.cli_constants as constants

    importlib.reload(constants)
    assert constants.BASE_URL == "https://141.5.110.112/api"


def test_api_url_can_be_overridden(monkeypatch) -> None:
    """Clusters can override the backend URL without editing code."""
    monkeypatch.setenv("BENCHWRAP_API_URL", "https://example.test/custom")

    import benchwrap.cli_constants as constants

    importlib.reload(constants)
    assert constants.BASE_URL == "https://example.test/custom"
