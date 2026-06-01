# Benchmark Suite CLI Maintainer Guide

This repository contains `benchwrap`, the command-line tool users run on HPC systems to execute energy-aware benchmarks and sync Slurm profiling data to the backend.

The CLI is the user-facing half of the system. It discovers available benchmarks, submits Slurm jobs, keeps local run artifacts under the user's XDG data directory, finds Slurm HDF5 profile files, and uploads those files to the backend through private S3 presigned URLs.

## Repository Map

- `src/benchwrap/cli.py`: Click command group and public CLI commands.
- `src/benchwrap/cli_auth.py`: Registration, login, token storage, and access-token loading.
- `src/benchwrap/cli_benchmarks.py`: Benchmark discovery, description, running, and user benchmark registration.
- `src/benchwrap/cli_sync.py`: File discovery and upload to the backend/S3.
- `src/benchwrap/cli_constants.py`: Runtime paths and backend URLs.
- `src/benchwrap/executors/`: Python entry points for built-in benchmarks.
- `src/benchwrap/executors/utils/benchmarks_func.py`: Slurm submission helpers and post-processing helpers.
- `src/benchwrap/benchmarks/`: Built-in benchmark workloads and Slurm `job_start.sh` scripts.
- `tests/`: Unit tests for CLI behavior, benchmark scripts, and Slurm integration.

## User Data Layout

Benchwrap uses XDG-style paths:

- `~/.local/share/benchwrap/tokens`: auth tokens.
- `~/.local/share/benchwrap/benchmarks`: user-provided benchmarks and installed auxiliary benchmark assets.
- `~/.local/share/benchwrap/jobs`: local job output folders created by `benchwrap run`.

The Slurm profile source path is currently cluster-specific:

- `SLURM_DEFAULT = /opt/misc/profiling/u18101`

That path is where the CLI looks for `.h5` files produced by Slurm profiling. If deploying for another user or cluster, this value needs to become configurable or be patched for the target environment.

## Commands

Common user commands:

```bash
benchwrap list
benchwrap describe flops_matrix_mul_mini
benchwrap run flops_matrix_mul_mini -p jupyter -n 1
benchwrap sync -j 4
```

Important environment variables:

- `BENCHWRAP_SERVER_URL`: base public server URL, default `http://141.5.110.112`.
- `BENCHWRAP_API_URL`: API base URL, default `${BENCHWRAP_SERVER_URL}/api`.
- `BENCHWRAP_STORAGE_TUNNEL_URL`: legacy storage tunnel override. Production S3 uploads normally use the presigned URL returned by the backend.
- `XDG_DATA_HOME`: changes the local benchwrap data root.

## Slurm Execution Flow

`benchwrap run BENCHMARK` resolves the benchmark name and invokes the matching executor in `src/benchwrap/executors/`.

For built-in Slurm benchmarks, the executor calls `run_slurm_job()`:

1. Resolve `benchwrap.benchmarks.<name>/job_start.sh` from package resources.
2. Submit with `sbatch --parsable --hold`.
3. Set partition, node count, job name, output path, and error path.
4. Store local outputs under `~/.local/share/benchwrap/jobs/<benchmark>/job_<jobid>/`.
5. Release the held job with `scontrol release <jobid>`.

Most benchmark scripts enable Slurm profiling through directives such as `--profile=all` and `--acctg-freq=energy=1`. Slurm then writes profiling HDF5 files outside the benchwrap jobs directory, usually under `/opt/misc/profiling/u18101`.

## Sync Flow

`benchwrap sync` does not upload through the backend process. It asks the backend for a private presigned S3 URL, then uploads directly to S3.

```text
benchwrap sync
  -> scan ~/.local/share/benchwrap/jobs
  -> scan /opt/misc/profiling/u18101
  -> infer benchmark_name for each file when possible
  -> POST /api/storage/presign/upload?object_name=...&benchmark_name=...
  -> PUT file bytes to returned GWDG S3 URL
```

Files from `~/.local/share/benchwrap/jobs/<benchmark>/...` carry `<benchmark>` directly.

Slurm HDF5 files named like `14001040_batch_agq007.h5` or `14001040_0_agq007.h5` are mapped back to a benchmark by looking for `~/.local/share/benchwrap/jobs/<benchmark>/job_14001040`. If no matching job folder exists, the backend will store the benchmark as unknown.

This mapping is important because the HDF5 filename only contains Slurm job id, step id, and compute node. It does not contain the benchmark name.

## Slurm HDF5 Files

Slurm often emits two profile files per job and node:

- `JOBID_batch_NODE.h5`: batch script step.
- `JOBID_0_NODE.h5`: step `0`, usually the workload step.

These files can represent almost the same time interval and energy profile. The backend stores them as raw per-file data but Grafana uses one canonical row per Slurm job for job-level totals, preferring `_batch_` when present.

Do not make the CLI delete one of these files during sync unless the backend no longer needs step-level diagnostics. It is safer to upload both and aggregate correctly downstream.

## Adding or Fixing Benchmarks

Built-in benchmarks live under `src/benchwrap/benchmarks/<name>/` and usually contain:

- `job_start.sh`: Slurm script.
- `workload.py` or launcher code.
- `description.txt`: short description shown by the CLI.

Executor modules live under `src/benchwrap/executors/<name>.py` and call `run_slurm_job()` with the benchmark name, partition, node count, and exclusive flag.

When adding a benchmark:

1. Keep the package directory name, executor name, and CLI benchmark name aligned.
2. Add a short `description.txt`.
3. Ensure the Slurm script does not submit another `benchwrap run` recursively.
4. Use module execution for Python workloads, for example `python3 -u -m benchwrap.benchmarks.stream_triad.workload`.
5. Include Slurm profiling directives if energy data is required.
6. Add or update tests in `tests/test_benchmark_scripts.py`.

IO500 is currently excluded from active benchmark correctness work. Do not treat it as passing unless it is explicitly reintroduced.

## Development

Install locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest tests/test_cli_sync.py tests/test_benchmark_scripts.py
```

Run the full test suite:

```bash
pytest
```

Slurm tests are environment-dependent and are skipped when Slurm commands are unavailable.

## Deployment and Remote Updates

The CLI repository currently uses branch `main`.

After changes:

```bash
pytest tests/test_cli_sync.py tests/test_benchmark_scripts.py
git push origin main
git push gitlab main
```

On cluster machines that installed the CLI from a clone, update the clone and reinstall the package inside the target Python environment. On MDC the tested environment was the Miniforge environment named `energy`.

Typical remote update shape:

```bash
ssh MDC_intern
conda activate energy
cd /path/to/benchmark-suite
git pull --ff-only origin main
pip install -e .
```

Use the exact clone path for the target host; do not assume all clusters use the same directory layout.

## Backend Contract

The backend presign route accepts:

- `object_name`: relative upload name.
- `benchmark_name`: optional inferred benchmark name.

The CLI should continue using `/api/storage/presign/upload` until the compatibility route is removed. The backend records metadata in SQLite and later copies it into PostgreSQL normalized dashboard rows.

If Grafana shows `unknown` benchmark names for new uploads, check:

1. Whether the CLI sent `benchmark_name` in the presign query.
2. Whether a local `jobs/<benchmark>/job_<jobid>` folder existed when syncing Slurm HDF5 files.
3. Whether the backend has been updated to a version that stores `benchmark_name`.
4. Whether the analysis pipeline reprocessed the S3 object after metadata support was added.

## Known Maintenance Tasks

- Make `SLURM_DEFAULT` configurable per cluster/user.
- Avoid uploading unrelated historical profiling files during normal sync; add a recent-job or explicit-job selection mode.
- Add a CLI manifest per run so benchmark name, command, partition, nodes, Slurm job id, and timestamps are explicit rather than inferred.
- Improve incremental sync so already uploaded files are skipped unless requested.
- Keep backend and CLI metadata contracts tested together when changing upload behavior.
