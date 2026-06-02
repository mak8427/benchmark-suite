"""Tests for the Slurm campaign artifact validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".ci/scripts/validate-slurm-campaign.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_slurm_campaign", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_campaign_validator_accepts_successful_manifest(monkeypatch, tmp_path) -> None:
    """A manifest with matching stdout, empty stderr, and HDF5 should pass."""
    home = tmp_path / "home"
    profile = tmp_path / "profiles"
    artifacts = tmp_path / "artifacts"
    job_dir = home / ".local/share/benchwrap/jobs/coremark_mini/job_42"
    job_dir.mkdir(parents=True)
    profile.mkdir()
    manifest = artifacts / "manifest.jsonl"
    artifacts.mkdir()

    (job_dir / "slurm-42.out").write_text(
        "coremark_mini digest=123 score=456 ops/s\n", encoding="utf-8"
    )
    (job_dir / "slurm-42.err").write_text("", encoding="utf-8")
    (profile / "42_batch_agq001.h5").write_bytes(b"h5")
    manifest.write_text(
        json.dumps(
            {
                "benchmark": "coremark_mini",
                "run": 1,
                "job_id": "42",
                "partition": "medium",
                "nodes": 1,
                "state": "submitted",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BENCHWRAP_SLURM_PROFILE_ROOT", str(profile))
    monkeypatch.setenv("BENCHWRAP_CAMPAIGN_ARTIFACTS", str(artifacts))
    validator = _load_validator()
    monkeypatch.setattr(validator, "read_sacct", lambda _job_id: "42|COMPLETED|0:0")
    monkeypatch.setattr(
        validator, "parse_args", lambda: type("Args", (), {"manifest": manifest})()
    )

    assert validator.main() == 0
    record = json.loads(manifest.read_text().strip())
    assert record["state"] == "validated"
    assert record["h5_count"] == 1
    assert (artifacts / "coremark_mini/job_42/slurm-42.out").is_file()


def test_campaign_validator_rejects_missing_output_signature(
    monkeypatch, tmp_path
) -> None:
    """Missing stdout signatures should fail the campaign."""
    home = tmp_path / "home"
    artifacts = tmp_path / "artifacts"
    job_dir = home / ".local/share/benchwrap/jobs/fft_1d_small/job_43"
    job_dir.mkdir(parents=True)
    artifacts.mkdir()
    manifest = artifacts / "manifest.jsonl"

    (job_dir / "slurm-43.out").write_text("wrong output\n", encoding="utf-8")
    (job_dir / "slurm-43.err").write_text("", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "benchmark": "fft_1d_small",
                "run": 1,
                "job_id": "43",
                "partition": "medium",
                "nodes": 1,
                "state": "submitted",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BENCHWRAP_SLURM_PROFILE_ROOT", str(tmp_path / "profiles"))
    monkeypatch.setenv("BENCHWRAP_CAMPAIGN_ARTIFACTS", str(artifacts))
    validator = _load_validator()
    monkeypatch.setattr(validator, "read_sacct", lambda _job_id: "")
    monkeypatch.setattr(
        validator, "parse_args", lambda: type("Args", (), {"manifest": manifest})()
    )

    assert validator.main() == 1
    assert json.loads(manifest.read_text().strip())["state"] == "failed"
