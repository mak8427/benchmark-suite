"""Tests for Benchwrap authentication CLI helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

from click.testing import CliRunner

from benchwrap import cli_auth


def test_auth_status_reports_account_and_sync_state(monkeypatch, tmp_path) -> None:
    """auth status should show account identity without exposing token values."""
    token_file = tmp_path / "tokens"
    sync_state = tmp_path / "sync-state.json"
    token_file.write_text(json.dumps({"refresh": "secret", "username": "alice"}))
    sync_state.write_text(
        json.dumps({"accounts": {"alice": {"files": {"a.h5": {}, "b.out": {}}}}})
    )
    monkeypatch.setattr(cli_auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli_auth, "TOK_FILE", token_file)

    result = CliRunner().invoke(cli_auth.auth_status, ["--no-check-refresh"])

    assert result.exit_code == 0
    assert "Active account: alice" in result.output
    assert "alice: 2 file(s)" in result.output
    assert "secret" not in result.output


def test_auth_switch_logs_in_and_preserves_sync_state(monkeypatch, tmp_path) -> None:
    """auth switch should replace the active token without deleting old state."""
    token_file = tmp_path / "tokens"
    sync_state = tmp_path / "sync-state.json"
    token_file.write_text(json.dumps({"refresh": "old", "username": "alice"}))
    sync_state.write_text(json.dumps({"accounts": {"alice": {"files": {"a.h5": {}}}}}))
    monkeypatch.setattr(cli_auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli_auth, "TOK_FILE", token_file)

    def fake_post(_url, params, timeout):
        assert params["u"] == "bob"
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"refresh": "new", "access": "access-token"},
        )

    monkeypatch.setattr(cli_auth.requests, "post", fake_post)

    result = CliRunner().invoke(cli_auth.auth_switch, input="bob\npassword\n")

    assert result.exit_code == 0
    state = json.loads(token_file.read_text())
    assert state == {"refresh": "new", "username": "bob"}
    assert json.loads(sync_state.read_text())["accounts"]["alice"]["files"]
    assert "Previous account: alice" in result.output
    assert "Active account: bob" in result.output
