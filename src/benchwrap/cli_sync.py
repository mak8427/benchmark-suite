"""Synchronization commands and helpers for the Benchwrap CLI."""

from __future__ import annotations

import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import click
import requests

from .cli_auth import get_access_token, login, register, registered
from .cli_constants import BASE_URL, JOBS_DEFAULT
from .cli_progress import (ProgressFile, inline_progress_line, pac_line,
                           table_start, table_update)


def list_files_upload() -> list[tuple[str, str]]:
    """Walk ``JOBS_DEFAULT`` and collect every file that should be uploaded.

    Input: none (always scans the configured user root).
    Output: list of ``(absolute_path, relative_archive_name)`` tuples.
    """
    files: list[tuple[str, str]] = []
    for root, _, filenames in os.walk(JOBS_DEFAULT):
        for filename in filenames:
            if filename == "tokens":
                continue
            filepath = os.path.join(root, filename)
            archive_name = os.path.relpath(filepath, JOBS_DEFAULT)
            files.append((filepath, archive_name))
    click.echo(f"Found {len(files)} files to upload.")
    return files


def upload_file(filepath: str, archive_name: str, access_token: str) -> bool:
    """Push one file to remote storage with inline progress feedback.

    Input: local ``filepath``, relative ``archive_name``, and bearer ``access_token``.
    Output: ``True`` on success, ``False`` on any failure path.
    """
    object_name = archive_name.replace(os.sep, "/").lstrip("/")[:256]

    response = requests.post(
        f"{BASE_URL}/storage/presign/upload",
        params={"object_name": object_name},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        click.echo(
            f"Presign failed: {object_name}: {response.status_code} {response.text}"
        )
        return False

    upload_url = response.json()["url"]
    content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    file_size = os.path.getsize(filepath)

    if file_size == 0:
        put_response = requests.put(
            upload_url,
            data=b"",
            headers={"Content-Type": content_type, "Content-Length": "0"},
            timeout=(10, 30),
        )
    else:
        start_time = time.time()
        progress_file = ProgressFile(
            filepath,
            lambda sent, total: click.echo(
                inline_progress_line(object_name, sent, total, start_time),
                nl=False,
            ),
        )
        try:
            put_response = requests.put(
                upload_url,
                data=progress_file,
                headers={"Content-Type": content_type},
                timeout=(10, None),
            )
        finally:
            progress_file.close()
            click.echo("")

    success = put_response.status_code in (200, 201, 204)
    click.echo(("✓ " if success else "✗ ") + object_name)
    if not success:
        click.echo(f"    error: {put_response.status_code} {put_response.text[:200]}")
    return success


def upload_one(
    index: int, access_token: str, filepath: str, object_name: str
) -> tuple[str, bool]:
    """Upload one file while updating the row ``index`` in the progress table.

    Input: row index, auth token, local path, and S3-style object name.
    Output: tuple of ``(object_name, success_flag)``.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    response = session.post(
        f"{BASE_URL}/storage/presign/upload",
        params={"object_name": object_name},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        table_update(index, f"✗ {object_name}  [presign {response.status_code}]")
        return object_name, False

    upload_url = response.json()["url"]
    content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    file_size = os.path.getsize(filepath)

    if file_size == 0:
        put_response = requests.put(
            upload_url,
            data=b"",
            headers={"Content-Type": content_type, "Content-Length": "0"},
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
            headers={"Content-Type": content_type, "Content-Length": str(file_size)},
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
    indexed_files: Iterable[tuple[int, tuple[str, str]]],
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
                relative_name.replace(os.sep, "/").lstrip("/")[:256],
            )
            for idx, (filepath, relative_name) in indexed_files
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
