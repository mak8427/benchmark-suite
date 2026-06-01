"""Tests for benchwrap sync uploads."""

from __future__ import annotations

from types import SimpleNamespace

from click.testing import CliRunner

from benchwrap import cli_sync


def test_upload_one_sends_presigned_headers(monkeypatch, tmp_path) -> None:
    """Required S3 headers returned by the backend must be sent on PUT."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    seen = {}

    class Session:
        headers = {}

        def post(self, url, params, timeout):
            seen["params"] = params
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

    name, ok = cli_sync.upload_one(0, "token", str(source), "result.h5", "stream_triad")

    assert ok is True
    assert name == "result.h5"
    assert seen["params"]["benchmark_name"] == "stream_triad"
    assert seen["url"] == "https://s3.example/upload"
    assert seen["headers"]["x-amz-acl"] == "private"
    assert seen["headers"]["Content-Length"] == "3"


def test_upload_one_sends_benchmark_name(monkeypatch, tmp_path) -> None:
    """Sync should pass benchmark metadata to the backend presign endpoint."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    seen = {}

    class Session:
        headers = {}

        def post(self, url, params, timeout):
            seen["params"] = params
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"url": "https://s3.example/upload", "headers": {}},
            )

    monkeypatch.setattr(cli_sync.requests, "Session", Session)
    monkeypatch.setattr(
        cli_sync.requests,
        "put",
        lambda *args, **kwargs: SimpleNamespace(ok=True, status_code=200),
    )
    monkeypatch.setattr(cli_sync, "table_update", lambda *args, **kwargs: None)

    _name, ok = cli_sync.upload_one(
        0, "token", str(source), "result.h5", "flops_matrix_mul_mini"
    )

    assert ok is True
    assert seen["params"]["benchmark_name"] == "flops_matrix_mul_mini"


def test_benchmark_for_slurm_file_uses_job_directory(monkeypatch, tmp_path) -> None:
    """Slurm profile files should map back to their Benchwrap benchmark folder."""
    jobs = tmp_path / "jobs"
    (jobs / "stream_triad" / "job_12345").mkdir(parents=True)
    slurm_file = tmp_path / "profiles" / "12345_batch_node001.h5"
    slurm_file.parent.mkdir()
    slurm_file.write_text("x", encoding="utf-8")
    monkeypatch.setattr(cli_sync, "JOBS_DEFAULT", jobs)

    mapping = cli_sync._job_id_benchmark_map()

    assert cli_sync._benchmark_for_file(str(slurm_file), mapping) == "stream_triad"


def test_sync_accepts_metadata_file_tuples(monkeypatch, tmp_path) -> None:
    """Sync should handle the 3-tuple produced by metadata-aware discovery."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    monkeypatch.setattr(cli_sync, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli_sync, "SYNC_STATE_FILE", tmp_path / "sync-state.json")
    monkeypatch.setattr(cli_sync, "registered", lambda: True)
    monkeypatch.setattr(cli_sync, "get_access_token", lambda: "token")
    monkeypatch.setattr(
        cli_sync,
        "list_files_upload",
        lambda: [(str(source), "result.h5", "stream_triad")],
    )
    monkeypatch.setattr(
        cli_sync, "upload_many", lambda *_args, **_kwargs: [("result.h5", True)]
    )
    monkeypatch.setattr(cli_sync, "table_start", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(cli_sync.sync, ["--jobs", "1"], input="y\n")

    assert result.exit_code == 0
    assert "1/1 uploaded successfully" in result.output


def test_sync_skips_unchanged_files(monkeypatch, tmp_path) -> None:
    """A second normal sync should skip files already recorded for the account."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    monkeypatch.setattr(cli_sync, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli_sync, "SYNC_STATE_FILE", tmp_path / "sync-state.json")
    monkeypatch.setattr(cli_sync, "registered", lambda: True)
    monkeypatch.setattr(cli_sync, "get_access_token", lambda: "token")
    monkeypatch.setattr(
        cli_sync,
        "list_files_upload",
        lambda: [(str(source), "result.h5", "stream_triad")],
    )
    monkeypatch.setattr(cli_sync, "table_start", lambda *_args, **_kwargs: None)
    calls = []
    monkeypatch.setattr(
        cli_sync,
        "upload_many",
        lambda *_args, **_kwargs: calls.append(True) or [("result.h5", True)],
    )

    first = CliRunner().invoke(cli_sync.sync, ["--jobs", "1"], input="y\n")
    second = CliRunner().invoke(cli_sync.sync, ["--jobs", "1"], input="y\n")

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert len(calls) == 1
    assert "No changed files" in second.output


def test_sync_force_uploads_unchanged_files(monkeypatch, tmp_path) -> None:
    """--force should preserve the previous reupload-everything behavior."""
    source = tmp_path / "result.h5"
    source.write_bytes(b"abc")
    monkeypatch.setattr(cli_sync, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli_sync, "SYNC_STATE_FILE", tmp_path / "sync-state.json")
    monkeypatch.setattr(cli_sync, "registered", lambda: True)
    monkeypatch.setattr(cli_sync, "get_access_token", lambda: "token")
    monkeypatch.setattr(
        cli_sync,
        "list_files_upload",
        lambda: [(str(source), "result.h5", "stream_triad")],
    )
    monkeypatch.setattr(cli_sync, "table_start", lambda *_args, **_kwargs: None)
    calls = []
    monkeypatch.setattr(
        cli_sync,
        "upload_many",
        lambda *_args, **_kwargs: calls.append(True) or [("result.h5", True)],
    )

    CliRunner().invoke(cli_sync.sync, ["--jobs", "1"], input="y\n")
    forced = CliRunner().invoke(cli_sync.sync, ["--jobs", "1", "--force"], input="y\n")

    assert forced.exit_code == 0
    assert len(calls) == 2
