"""Synchronization commands and helpers for the Benchwrap CLI."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

import click
import requests

from .cli_auth import get_access_token, login, register, registered
from .cli_constants import (
    BASE_URL,
    DATA_DIR,
    JOBS_DEFAULT,
    MINIO_TUNNEL_URL,
    SERVER_URL,
    SLURM_DEFAULT,
    TUNNELLING_URL,
)
from .cli_progress import ProgressFile, pac_line, table_start, table_update

SYNC_STATE_FILE = DATA_DIR / "sync-state.json"
DEFAULT_BATCH_SIZE = 500


@dataclass(frozen=True)
class UploadOutcome:
    """Result for one upload attempt."""

    object_name: str
    success: bool
    status_code: int | None = None
    stage: str | None = None
    error_message: str | None = None


def _slurm_job_id(filename: str) -> str | None:
    match = re.match(r"^(\d+)_(?:batch|\d+)_", filename)
    return match.group(1) if match else None


def _benchmark_from_jobs_path(path: str) -> str | None:
    try:
        relative = os.path.relpath(path, JOBS_DEFAULT)
    except ValueError:
        return None
    first = relative.split(os.sep, 1)[0]
    return (
        first if first and first != os.curdir and not first.startswith("..") else None
    )


def _job_id_benchmark_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not os.path.isdir(JOBS_DEFAULT):
        return mapping
    for benchmark_name in os.listdir(JOBS_DEFAULT):
        benchmark_dir = os.path.join(JOBS_DEFAULT, benchmark_name)
        if not os.path.isdir(benchmark_dir):
            continue
        for entry in os.listdir(benchmark_dir):
            if entry.startswith("job_"):
                mapping[entry.removeprefix("job_")] = benchmark_name
    return mapping


def _benchmark_for_file(filepath: str, job_benchmarks: dict[str, str]) -> str | None:
    benchmark = _benchmark_from_jobs_path(filepath)
    if benchmark:
        return benchmark
    job_id = _slurm_job_id(os.path.basename(filepath))
    return job_benchmarks.get(job_id) if job_id else None


def _fast_hash(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    """Hash file contents using BLAKE2b for fast local change detection."""
    digest = hashlib.blake2b(digest_size=16)
    with open(filepath, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_sync_state() -> dict:
    if not SYNC_STATE_FILE.exists():
        return {"accounts": {}}
    try:
        data = json.loads(SYNC_STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {"accounts": {}}
    if not isinstance(data, dict):
        return {"accounts": {}}
    data.setdefault("accounts", {})
    return data


def _save_sync_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _object_name(relative_name: str) -> str:
    """Normalize a discovered relative path into the backend object name."""
    return relative_name.replace(os.sep, "/").lstrip("/")[:256]


def _format_quota_value(value: object, unit: object) -> str:
    if not isinstance(value, int):
        return "?"
    if unit == "bytes":
        return _human_readable_size(value)
    return str(value)


def _presign_error_message(response: requests.Response) -> str:
    """Return a concise message for a failed backend presign response."""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:120] or "request rejected"

    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if isinstance(detail, dict):
        message = str(
            detail.get("message") or detail.get("error") or "request rejected"
        )
        if detail.get("error") in {"object_quota_exceeded", "storage_quota_exceeded"}:
            unit = detail.get("unit")
            used = _format_quota_value(detail.get("used"), unit)
            limit = _format_quota_value(detail.get("limit"), unit)
            return f"{message} Used {used}/{limit} {unit or ''}.".strip()
        return message
    if isinstance(detail, str):
        return detail
    return "request rejected"


def _file_signature(filepath: str, benchmark_name: str | None) -> dict[str, object]:
    stat = os.stat(filepath)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "hash": _fast_hash(filepath),
        "benchmark_name": benchmark_name,
    }


def _file_quick_signature(
    filepath: str, benchmark_name: str | None
) -> dict[str, object]:
    """Return cheap stat metadata used before hashing file contents."""
    stat = os.stat(filepath)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "benchmark_name": benchmark_name,
    }


def _account_key(username: str | None) -> str:
    return username or "legacy-account"


def filter_changed_files(
    files: list[tuple[str, str, str | None]],
    *,
    username: str | None,
    force: bool = False,
) -> tuple[list[tuple[str, str, str | None]], dict, dict[str, dict[str, object]]]:
    """Return files that need uploading and their computed signatures."""
    state = _load_sync_state()
    account = state.setdefault("accounts", {}).setdefault(
        _account_key(username), {"files": {}}
    )
    known_files = account.setdefault("files", {})
    changed: list[tuple[str, str, str | None]] = []
    signatures: dict[str, dict[str, object]] = {}
    for filepath, relative_name, benchmark_name in files:
        object_name = _object_name(relative_name)
        quick_signature = _file_quick_signature(filepath, benchmark_name)
        known_entry = known_files.get(object_name, {})
        known_quick = {
            key: known_entry.get(key) for key in ("size", "mtime_ns", "benchmark_name")
        }
        if not force and known_quick == quick_signature:
            if "hash" in known_entry:
                signatures[object_name] = {
                    **quick_signature,
                    "hash": known_entry["hash"],
                }
            continue

        signature = _file_signature(filepath, benchmark_name)
        signatures[object_name] = signature
        known_signature = {
            key: known_entry.get(key)
            for key in ("size", "mtime_ns", "hash", "benchmark_name")
        }
        if force or known_signature != signature:
            changed.append((filepath, relative_name, benchmark_name))
    return changed, state, signatures


def build_signatures(
    files: list[tuple[str, str, str | None]],
) -> dict[str, dict[str, object]]:
    """Compute full signatures for a file list, used by explicit baseline mode."""
    return {
        _object_name(relative_name): _file_signature(filepath, benchmark_name)
        for filepath, relative_name, benchmark_name in files
    }


def mark_synced(
    state: dict,
    *,
    username: str | None,
    results: list[tuple[str, bool]] | list[UploadOutcome],
    signatures: dict[str, dict[str, object]],
) -> None:
    """Update sync state for successful uploads only."""
    account = state.setdefault("accounts", {}).setdefault(
        _account_key(username), {"files": {}}
    )
    known_files = account.setdefault("files", {})
    for result in results:
        if isinstance(result, UploadOutcome):
            object_name, success = result.object_name, result.success
        else:
            object_name, success = result
        if success and object_name in signatures:
            known_files[object_name] = {
                **signatures[object_name],
                "uploaded_at": time.time(),
            }
    _save_sync_state(state)


def list_files_upload() -> list[tuple[str, str, str | None]]:
    """Walk ``JOBS_DEFAULT`` and collect every file that should be uploaded.

    Input: none (always scans the configured user root).
    Output: list of ``(absolute_path, relative_archive_name, benchmark_name)`` tuples.
    """
    files: list[tuple[str, str, str | None]] = []
    job_benchmarks = _job_id_benchmark_map()

    #
    for root, _, filenames in os.walk(JOBS_DEFAULT):
        for filename in filenames:
            if filename == "tokens":
                continue
            filepath = os.path.join(root, filename)
            archive_name = os.path.relpath(filepath, JOBS_DEFAULT)
            files.append(
                (filepath, archive_name, _benchmark_for_file(filepath, job_benchmarks))
            )

    for root, _, filenames in os.walk(SLURM_DEFAULT):
        for filename in filenames:
            if filename == "tokens":
                continue
            filepath = os.path.join(root, filename)
            archive_name = os.path.relpath(filepath, SLURM_DEFAULT)
            files.append(
                (filepath, archive_name, _benchmark_for_file(filepath, job_benchmarks))
            )

    return files


def _extension_bucket(path: str) -> str:
    suffix = os.path.splitext(path)[1].lower()
    return suffix if suffix in {".h5", ".out", ".err"} else "other"


def summarize_files(
    files: list[tuple[str, str, str | None]],
) -> dict[str, dict[str, int]]:
    """Return compact file-count and byte-count summaries by extension bucket."""
    summary = {
        key: {"count": 0, "bytes": 0} for key in (".h5", ".out", ".err", "other")
    }
    for filepath, relative_name, _benchmark_name in files:
        bucket = _extension_bucket(relative_name)
        summary[bucket]["count"] += 1
        summary[bucket]["bytes"] += os.path.getsize(filepath)
    return summary


def _print_file_summary(label: str, files: list[tuple[str, str, str | None]]) -> None:
    total_size = sum(os.path.getsize(filepath) for filepath, _, _ in files)
    click.echo(f"{label}: {len(files)} files, {_human_readable_size(total_size)}")
    summary = summarize_files(files)
    parts = []
    for key in (".h5", ".out", ".err", "other"):
        count = summary[key]["count"]
        if count:
            parts.append(f"{key}: {count}")
    if parts:
        click.echo("  " + ", ".join(parts))


def _upload_one_outcome(
    index: int,
    access_token: str,
    filepath: str,
    object_name: str,
    benchmark_name: str | None = None,
) -> UploadOutcome:
    """Upload one file while updating the row ``index`` in the progress table.

    Input: row index, auth token, local path, and S3-style object name.
    Output: tuple of ``(object_name, success_flag)``.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    response = session.post(
        f"{BASE_URL}/storage/presign/upload",
        params={
            "object_name": object_name,
            **({"benchmark_name": benchmark_name} if benchmark_name else {}),
        },
        timeout=(10, 30),
    )
    if response.status_code != 200:
        error_message = _presign_error_message(response)
        table_update(
            index,
            f"✗ {object_name}  [presign {response.status_code}: {error_message}]",
        )
        return UploadOutcome(
            object_name, False, response.status_code, "presign", error_message
        )

    presign_body = response.json()
    upload_url = presign_body["url"]
    upload_headers = {
        str(key): str(value)
        for key, value in presign_body.get("headers", {}).items()
        if value is not None
    }

    if TUNNELLING_URL:
        upload_url = presign_body["url"].replace(f"{SERVER_URL}:9000", MINIO_TUNNEL_URL)
    content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    file_size = os.path.getsize(filepath)

    if file_size == 0:
        put_response = requests.put(
            upload_url,
            data=b"",
            headers={
                **upload_headers,
                "Content-Type": content_type,
                "Content-Length": "0",
            },
            timeout=(10, 30),
        )
        table_update(
            index, f"{object_name[:24]:<24} ✓ zero-byte [{put_response.status_code}]"
        )
        return UploadOutcome(
            object_name, put_response.ok, put_response.status_code, "upload"
        )

    start_time = time.time()
    progress_file = ProgressFile(
        filepath,
        lambda sent, total: table_update(
            index, pac_line(object_name, sent, total, start_time)
        ),
    )
    try:
        put_response = requests.put(
            upload_url,
            data=progress_file,
            headers={
                **upload_headers,
                "Content-Type": content_type,
                "Content-Length": str(file_size),
            },
            timeout=(10, None),
        )
    finally:
        progress_file.close()

    final_status = (
        f"{object_name[:24]:<24} ✓ done"
        if put_response.ok
        else f"{object_name[:24]:<24} ✗ [{put_response.status_code}]"
    )
    table_update(index, final_status)
    return UploadOutcome(
        object_name, put_response.ok, put_response.status_code, "upload"
    )


def upload_one(
    index: int,
    access_token: str,
    filepath: str,
    object_name: str,
    benchmark_name: str | None = None,
) -> tuple[str, bool]:
    """Upload one file, returning the historical two-item result tuple."""
    outcome = _upload_one_outcome(
        index, access_token, filepath, object_name, benchmark_name
    )
    return outcome.object_name, outcome.success


def _upload_many_outcomes(
    access_token: str,
    indexed_files: Iterable[tuple[int, tuple[str, str, str | None]]],
    workers: int = 4,
) -> list[UploadOutcome]:
    """Upload multiple files concurrently using a worker pool.

    Input: access token, iterable of ``(row_index, file_tuple)`` pairs, worker count.
    Output: list of ``(object_name, success_flag)`` results collected from workers.
    """
    results: list[UploadOutcome] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _upload_one_outcome,
                idx,
                access_token,
                filepath,
                object_name,
                benchmark_name,
            )
            for idx, (filepath, relative_name, benchmark_name) in indexed_files
            for object_name in [_object_name(relative_name)]
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def upload_many(
    access_token: str,
    indexed_files: Iterable[tuple[int, tuple[str, str, str | None]]],
    workers: int = 4,
) -> list[tuple[str, bool]]:
    """Upload multiple files, returning the historical two-item result tuples."""
    return [
        (outcome.object_name, outcome.success)
        for outcome in _upload_many_outcomes(access_token, indexed_files, workers)
    ]


def _chunks(items: list[tuple[int, tuple[str, str, str | None]]], size: int):
    for start in range(0, len(items), size):
        yield start // size + 1, items[start : start + size]


def upload_in_batches(
    access_token: str,
    indexed_files: list[tuple[int, tuple[str, str, str | None]]],
    *,
    workers: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[UploadOutcome]:
    """Upload files in sequential batches to avoid backend request storms."""
    bounded_size = max(1, batch_size)
    results: list[UploadOutcome] = []
    total_batches = (len(indexed_files) + bounded_size - 1) // bounded_size
    for batch_number, batch in _chunks(indexed_files, bounded_size):
        click.echo(
            f":: Batch {batch_number}/{total_batches}: {len(batch)} file(s), "
            f"{workers} upload worker(s)"
        )
        batch_results = _upload_many_outcomes(access_token, batch, workers=workers)
        quota_messages = sorted(
            {
                result.error_message
                for result in batch_results
                if result.stage == "presign"
                and result.status_code == 413
                and result.error_message
            }
        )
        for message in quota_messages:
            click.echo(f":: Backend quota: {message}")
        results.extend(batch_results)
    return results


def _human_readable_size(num_bytes: int) -> str:
    """Convert a byte count to a MiB string for human consumption.

    Input: byte count as an integer.
    Output: string formatted as ``"<value> MiB"`` with one decimal place.
    """
    return f"{num_bytes / (1024 * 1024):.1f} MiB"


@click.command()
@click.option(
    "-j", "--jobs", type=int, default=4, show_default=True, help="Parallel uploads"
)
@click.option(
    "--force", is_flag=True, help="Upload all discovered files, ignoring sync state."
)
@click.option(
    "--baseline",
    is_flag=True,
    help="Mark discovered files as synced for the active account without uploading.",
)
@click.option(
    "--batch-size",
    type=int,
    default=DEFAULT_BATCH_SIZE,
    show_default=True,
    help="Maximum files scheduled per sequential upload batch.",
)
def sync(jobs: int, force: bool, baseline: bool, batch_size: int):
    """Synchronize user benchmarks with remote storage.

    Input: number of parallel upload jobs to run.
    Output: boolean success indicator printed alongside progress output.
    """
    access_token = None
    if not registered():
        click.echo("No registration found. Please register first.")
        access_token = register()
        if not access_token:
            click.echo("Registration failed. Cannot sync.")
            return False

    if not access_token:
        access_token = get_access_token() or login()
        if not access_token:
            click.echo("Login failed. Cannot sync.")
            return False

    from .cli_auth import active_username

    username = active_username()
    click.echo(f"Active account: {username or 'unknown'}")
    files = list_files_upload()
    if not files:
        click.echo("No files to sync.")
        return True

    _print_file_summary("Discovered", files)

    if baseline:
        if force:
            click.echo("--force has no effect with --baseline.")
        signatures = build_signatures(files)
        state = _load_sync_state()
        results = [(_object_name(relative_name), True) for _, relative_name, _ in files]
        mark_synced(state, username=username, results=results, signatures=signatures)
        click.echo(
            f"✔ Baseline complete. Marked {len(files)} file(s) as synced "
            "without uploading."
        )
        return True

    files_to_upload, sync_state, signatures = filter_changed_files(
        files, username=username, force=force
    )
    skipped = len(files) - len(files_to_upload)
    click.echo(f"Changed: {len(files_to_upload)} file(s), skipped: {skipped}")
    if not files_to_upload:
        click.echo("No changed files to sync.")
        return True

    _print_file_summary("Upload plan", files_to_upload)

    total_size = sum(os.path.getsize(filepath) for filepath, _, _ in files_to_upload)
    click.echo(
        f":: Synchronizing {len(files_to_upload)} changed file(s) "
        f"({skipped} skipped, {_human_readable_size(total_size)}) with {jobs} jobs "
        f"in batches of up to {max(1, batch_size)}"
    )
    if not click.confirm(":: Proceed?", default=True):
        click.echo("Aborted.")
        return False

    table_start(len(files_to_upload))
    indexed_files = list(enumerate(files_to_upload))
    results = upload_in_batches(
        access_token, indexed_files, workers=jobs, batch_size=batch_size
    )
    mark_synced(sync_state, username=username, results=results, signatures=signatures)

    successful_uploads = sum(1 for result in results if result.success)
    failed_uploads = len(results) - successful_uploads
    click.echo(
        f":: Summary: {successful_uploads} uploaded, {failed_uploads} failed, "
        f"{skipped} skipped, "
        f"{_human_readable_size(total_size)} total"
    )
    if failed_uploads:
        click.echo("✗ Sync completed with failed upload(s).")
        return False

    click.echo("✔ Sync complete.")

    return True
