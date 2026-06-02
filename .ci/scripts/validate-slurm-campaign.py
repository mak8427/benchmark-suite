#!/usr/bin/env python3
"""Validate a Benchwrap Slurm campaign manifest."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


PATTERNS = {
    "coremark_mini": [r"coremark_mini", r"digest=\d+", r"score="],
    "fft_1d_small": [r"fft_1d_small", r"checksum=", r"estimated_gflops="],
    "flops_matrix_mul_mini": [r"GEMM done", r"Frobenius"],
    "npb_ep_small": [r"npb_ep_small", r"checksum=", r"pairs_per_s="],
    "npb_is_small": [r"npb_is_small", r"checksum=", r"keys_per_s="],
    "random_access_small": [r"random_access_small", r"checksum=", r"updates_per_s="],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    return parser.parse_args()


def read_sacct(job_id: str) -> str:
    try:
        result = subprocess.run(
            ["sacct", "-j", job_id, "--format=JobID,State,ExitCode", "-P", "-n"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"
    return result.stdout.strip()


def main() -> int:
    args = parse_args()
    artifact_root = Path(os.getenv("BENCHWRAP_CAMPAIGN_ARTIFACTS", "campaign-artifacts"))
    jobs_root = Path.home() / ".local/share/benchwrap/jobs"
    profile_root = Path(os.getenv("BENCHWRAP_SLURM_PROFILE_ROOT", "/opt/misc/profiling/u18101"))

    records = [json.loads(line) for line in args.manifest.read_text().splitlines() if line.strip()]
    validated = []
    errors: list[str] = []

    for record in records:
        benchmark = record["benchmark"]
        job_id = record["job_id"]
        job_dir = jobs_root / benchmark / f"job_{job_id}"
        out_path = job_dir / f"slurm-{job_id}.out"
        err_path = job_dir / f"slurm-{job_id}.err"
        copied_dir = artifact_root / benchmark / f"job_{job_id}"
        copied_dir.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            shutil.copy2(out_path, copied_dir / out_path.name)
        if err_path.exists():
            shutil.copy2(err_path, copied_dir / err_path.name)

        out_text = out_path.read_text(errors="replace") if out_path.exists() else ""
        err_text = err_path.read_text(errors="replace") if err_path.exists() else ""
        missing = [pattern for pattern in PATTERNS[benchmark] if not re.search(pattern, out_text)]
        h5_files = sorted(str(path) for path in profile_root.glob(f"{job_id}_*.h5")) if profile_root.exists() else []

        state = "validated"
        if not out_path.exists():
            errors.append(f"missing stdout for {benchmark} job {job_id}")
            state = "failed"
        if missing:
            errors.append(f"stdout contract failed for {benchmark} job {job_id}: {missing}")
            state = "failed"
        if err_text.strip():
            errors.append(f"stderr not empty for {benchmark} job {job_id}: {err_path}")
            state = "failed"
        if not h5_files:
            errors.append(f"no HDF5 profile found for {benchmark} job {job_id}")
            state = "failed"

        validated.append(
            {
                **record,
                "state": state,
                "stdout": str(out_path),
                "stderr": str(err_path),
                "h5_count": len(h5_files),
                "sacct": read_sacct(job_id),
            }
        )

    with args.manifest.open("w", encoding="utf-8") as handle:
        for record in validated:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"validated_campaign_jobs={len(validated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
