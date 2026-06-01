"""Synchronization commands and helpers for the Benchwrap CLI."""

from __future__ import annotations

import mimetypes
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import click
import requests

from .cli_auth import get_access_token, login, register, registered
from .cli_constants import (BASE_URL, JOBS_DEFAULT, MINIO_TUNNEL_URL,
                            SERVER_URL, SLURM_DEFAULT, TUNNELLING_URL)
from .cli_progress import (ProgressFile, inline_progress_line, pac_line,
                           table_start, table_update)


def _slurm_job_id(filename: str) -> str | None:
    match = re.match(r"^(\d+)_(?:batch|\d+)_", filename)
    return match.group(1) if match else None


def _benchmark_from_jobs_path(path: str) -> str | None:
    try:
        relative = os.path.relpath(path, JOBS_DEFAULT)
    except ValueError:
        return None
    first = relative.split(os.sep, 1)[0]
    return first if first and first != os.curdir and not first.startswith("..") else None


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
            files.append((filepath, archive_name, _benchmark_for_file(filepath, job_benchmarks)))

    for root, _, filenames in os.walk(SLURM_DEFAULT):
        for filename in filenames:
            if filename == "tokens":
                continue
            filepath = os.path.join(root, filename)
            archive_name = os.path.relpath(filepath, SLURM_DEFAULT)
            files.append((filepath, archive_name, _benchmark_for_file(filepath, job_benchmarks)))

    click.echo(f"Found {len(files)} files to upload.")
    return files


def upload_one(
    index: int, access_token: str, filepath: str, object_name: str, benchmark_name: str | None = None
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
def sync(jobs: int):
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

    files = list_files_upload()
    if not files:
        click.echo("No files to sync.")
        return True

    total_size = sum(os.path.getsize(filepath) for filepath, _ in files)
    click.echo(
        f":: Synchronizing {len(files)} files ({_human_readable_size(total_size)}) "
        f"with {jobs} jobs"
    )
    if not click.confirm(":: Proceed?", default=True):
        click.echo("Aborted.")
        return False

    table_start(len(files))
    indexed_files = list(enumerate(files))
    results = upload_many(access_token, indexed_files, workers=jobs)

    successful_uploads = sum(1 for _, success in results if success)
    click.echo(
        f":: Summary: {successful_uploads}/{len(files)} uploaded successfully, "
        f"{_human_readable_size(total_size)} total"
    )
    click.echo("✔ Sync complete.")

    return True
