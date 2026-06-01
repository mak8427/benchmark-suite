"""Synchronization commands and helpers for the Benchwrap CLI."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import click
import requests

from .cli_auth import get_access_token, login, register, registered
from .cli_constants import (BASE_URL, DATA_DIR, JOBS_DEFAULT, MINIO_TUNNEL_URL,
                            SERVER_URL, SLURM_DEFAULT, TUNNELLING_URL)
from .cli_progress import (ProgressFile, inline_progress_line, pac_line,
                           table_start, table_update)

SYNC_STATE_FILE = DATA_DIR / "sync-state.json"


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


def _file_signature(filepath: str, benchmark_name: str | None) -> dict[str, object]:
    stat = os.stat(filepath)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "hash": _fast_hash(filepath),
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
        object_name = relative_name.replace(os.sep, "/").lstrip("/")[:256]
        signature = _file_signature(filepath, benchmark_name)
        signatures[object_name] = signature
        known_signature = {
            key: known_files.get(object_name, {}).get(key)
            for key in ("size", "mtime_ns", "hash", "benchmark_name")
        }
        if force or known_signature != signature:
            changed.append((filepath, relative_name, benchmark_name))
    return changed, state, signatures


def mark_synced(
    state: dict,
    *,
    username: str | None,
    results: list[tuple[str, bool]],
    signatures: dict[str, dict[str, object]],
) -> None:
    """Update sync state for successful uploads only."""
    account = state.setdefault("accounts", {}).setdefault(
        _account_key(username), {"files": {}}
    )
    known_files = account.setdefault("files", {})
    for object_name, success in results:
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

    click.echo(f"Found {len(files)} files to upload.")
    return files


def upload_one(
    index: int,
    access_token: str,
    filepath: str,
    object_name: str,
    benchmark_name: str | None = None,
) -> tuple[str, bool]:
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
        table_update(index, f"✗ {object_name}  [presign {response.status_code}]")
        return object_name, False

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
        return object_name, put_response.ok

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
    return object_name, put_response.ok


def upload_many(
    access_token: str,
    indexed_files: Iterable[tuple[int, tuple[str, str, str | None]]],
    workers: int = 4,
) -> list[tuple[str, bool]]:
    """Upload multiple files concurrently using a worker pool.

    Input: access token, iterable of ``(row_index, file_tuple)`` pairs, worker count.
    Output: list of ``(object_name, success_flag)`` results collected from workers.
    """
    results: list[tuple[str, bool]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                upload_one,
                idx,
                access_token,
                filepath,
                object_name,
                benchmark_name,
            )
            for idx, (filepath, relative_name, benchmark_name) in indexed_files
            for object_name in [relative_name.replace(os.sep, "/").lstrip("/")[:256]]
        ]
        for future in as_completed(futures):
            results.append(future.result())
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
def sync(jobs: int, force: bool):
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

    files_to_upload, sync_state, signatures = filter_changed_files(
        files, username=username, force=force
    )
    skipped = len(files) - len(files_to_upload)
    if not files_to_upload:
        click.echo(f"No changed files to sync. Skipped {skipped} unchanged file(s).")
        return True

    total_size = sum(os.path.getsize(filepath) for filepath, _, _ in files_to_upload)
    click.echo(
        f":: Synchronizing {len(files_to_upload)} changed file(s) "
        f"({skipped} skipped, {_human_readable_size(total_size)}) with {jobs} jobs"
    )
    if not click.confirm(":: Proceed?", default=True):
        click.echo("Aborted.")
        return False

    table_start(len(files_to_upload))
    indexed_files = list(enumerate(files_to_upload))
    results = upload_many(access_token, indexed_files, workers=jobs)
    mark_synced(sync_state, username=username, results=results, signatures=signatures)

    successful_uploads = sum(1 for _, success in results if success)
    click.echo(
        f":: Summary: {successful_uploads}/{len(files_to_upload)} uploaded successfully, "
        f"{_human_readable_size(total_size)} total"
    )
    click.echo("✔ Sync complete.")

    return True
