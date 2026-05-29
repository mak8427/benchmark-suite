"""Tests for benchwrap sync uploads."""

from __future__ import annotations

from types import SimpleNamespace

from benchwrap import cli_sync


def test_upload_one_sends_presigned_headers(monkeypatch, tmp_path) -> None:
    """Required S3 headers returned by the backend must be sent on PUT."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    seen = {}

    class Session:
        headers = {}

        def post(self, url, params, timeout):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "url": "https://s3.example/upload",
                    "headers": {"x-amz-acl": "private"},
                },
            )

    def fake_put(url, data, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        return SimpleNamespace(ok=True, status_code=200)

    monkeypatch.setattr(cli_sync.requests, "Session", Session)
    monkeypatch.setattr(cli_sync.requests, "put", fake_put)
    monkeypatch.setattr(cli_sync, "table_update", lambda *args, **kwargs: None)

    name, ok = cli_sync.upload_one(0, "token", str(source), "result.h5")

    assert ok is True
    assert name == "result.h5"
    assert seen["url"] == "https://s3.example/upload"
    assert seen["headers"]["x-amz-acl"] == "private"
    assert seen["headers"]["Content-Length"] == "3"
