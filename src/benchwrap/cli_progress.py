"""Progress display utilities for the Benchwrap CLI."""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable

import click

PRINT_LOCK = threading.Lock()
_rows = 0


def safe_print(message: str) -> None:
    """Emit a thread-safe message via Click.

    Input: message string to display.
    Output: writes to stdout while holding ``PRINT_LOCK``; returns ``None``.
    """
    with PRINT_LOCK:
        click.echo(message)


def table_start(num_rows: int) -> None:
    """Initialise terminal space for a fixed-size progress table.

    Input: number of rows that should be allocated.
    Output: positions the cursor appropriately; returns ``None``.
    """
    global _rows
    _rows = num_rows
    sys.stdout.write("\n" * num_rows)
    sys.stdout.write(f"\x1b[{num_rows}A")
    sys.stdout.write("\x1b[s")
    sys.stdout.flush()


def table_update(row_index: int, text: str) -> None:
    """Update a single row within the progress table.

    Input: zero-based row index and replacement text.
    Output: rewrites the row atomically; returns ``None``.
    """
    with PRINT_LOCK:
        sys.stdout.write("\x1b[u")
        sys.stdout.write(f"\x1b[{row_index}B")
        sys.stdout.write("\x1b[2K")
        sys.stdout.write(text)
        sys.stdout.write(f"\x1b[{_rows - row_index}B")
        sys.stdout.flush()


class ProgressFile:
    """File-like object that reports upload progress while streaming.

    Input: path to the file and a callback accepting (bytes_sent, total_size).
    Output: iterator-compatible wrapper exposing ``read``/``close`` plus ``__len__``.
    """

    def __init__(self, filepath: str, progress_callback: Callable[[int, int], None]):
        self.file_handle = open(filepath, "rb")
        self.size = os.path.getsize(filepath)
        self.bytes_sent = 0
        self.progress_callback = progress_callback

    def __len__(self) -> int:  # pragma: no cover - simple delegation
        return self.size

    def read(self, chunk_size: int = 1024 * 1024) -> bytes:
        data = self.file_handle.read(chunk_size)
        if data:
            self.bytes_sent += len(data)
            self.progress_callback(self.bytes_sent, self.size)
        return data

    def close(self) -> None:
        self.file_handle.close()


def pac_line(
    name: str, sent: int, size: int, start_time: float, width: int = 28
) -> str:
    """Build a pacman-style progress string for tabular updates.

    Input: object name, bytes sent/total, start timestamp, and optional width.
    Output: formatted status line suitable for ``table_update``.
    """
    percentage = 0 if size == 0 else int(sent * 100 / size)
    megabytes_sent = sent / 1048576
    total_megabytes = max(size, 1) / 1048576

    elapsed_time = max(time.time() - start_time, 1e-6)
    speed_mbps = megabytes_sent / elapsed_time
    remaining_mb = total_megabytes - megabytes_sent
    remaining_seconds = remaining_mb / speed_mbps if speed_mbps > 0 else 0
    eta = f"{int(remaining_seconds // 60):02d}:{int(remaining_seconds % 60):02d}"

    position = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"

    rail = []
    for i in range(width):
        if i < position:
            rail.append("-")
        elif (i - position) % 3 == 0:
            rail.append("o")
        else:
            rail.append(" ")
    rail[position] = mouth
    progress_bar = "".join(rail)

    return (
        f"{name[:24]:<24} [{progress_bar}] {percentage:3d}% "
        f"{megabytes_sent:6.1f}/{total_megabytes:6.1f} MiB "
        f"{speed_mbps:5.2f} MiB/s ETA {eta}"
    )


def inline_progress_line(
    name: str, sent: int, size: int, start_time: float, width: int = 28
) -> str:
    """Build an inline progress string ending with ``\r`` for streaming.

    Input: object name, bytes sent/total, start timestamp, optional bar width.
    Output: carriage-return terminated status line for inline printing.
    """
    percentage = 0 if size == 0 else int(sent * 100 / size)
    megabytes_sent = sent / 1048576
    total_megabytes = max(size, 1) / 1048576

    elapsed_time = max(time.time() - start_time, 1e-6)
    speed_mbps = megabytes_sent / elapsed_time
    remaining_mb = total_megabytes - megabytes_sent
    remaining_seconds = remaining_mb / speed_mbps if speed_mbps > 0 else 0
    eta = f"{int(remaining_seconds // 60):02d}:{int(remaining_seconds % 60):02d}"

    position = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"

    rail = []
    for i in range(width):
        if i < position:
            rail.append("-")
        elif (i - position) % 3 == 0:
            rail.append("o")
        else:
            rail.append(" ")
    rail[position] = mouth
    progress_bar = "".join(rail)

    return (
        f"{name[:24]:<24} [{progress_bar}] {percentage:3d}% "
        f"{megabytes_sent:6.1f}/{total_megabytes:6.1f} MiB "
        f"{speed_mbps:5.2f} MiB/s ETA {eta}\r"
    )
