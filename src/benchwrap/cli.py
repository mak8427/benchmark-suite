"""Benchwrap CLI entry point.

This module wires together the various command implementations that live across
smaller helper files.  The original public API is preserved by re-exporting the
most commonly used helpers so external tooling and tests can keep importing from
``benchwrap.cli``.
"""

from __future__ import annotations

import importlib.resources as res
import subprocess

import click

from .cli_auth import (ensure_data_dir, get_access_token, login, register,
                       registered)
from .cli_benchmarks import (add_impl_command, list_impl, old_list_impl,
                             run_impl)
from .cli_constants import (BASE_URL, BENCH_PKG, BENCH_ROOT, DATA_DIR,
                            EXECUTORS_PKG, TOK_FILE, USER_ROOT)
from .cli_progress import (PRINT_LOCK, ProgressFile, inline_progress_line,
                           pac_line, safe_print, table_start, table_update)
from .cli_sync import (_human_readable_size, list_files_upload, sync,
                       upload_file, upload_many, upload_one)


@click.group()
def benchwrap():
    """Energy-aware benchmark helper."""


@benchwrap.command("old_list")
@click.argument(
    "start",
    required=False,
    default="src/benchmarks",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option(
    "--dir/--no-dir", "show_dir", default=False, help="Also list sub-directories."
)
def old_list(start: str, show_dir: bool) -> None:
    old_list_impl(start, show_dir, subprocess_module=subprocess)


@benchwrap.command("list")
def _list():
    list_impl(USER_ROOT)


@benchwrap.command("run")
@click.argument("name", required=False)
@click.argument("partition", required=False)
@click.argument("nodes", required=False)
@click.option(
    "-p", "--partition", "opt_partition", required=False, help="SLURM partition"
)
@click.option(
    "-n", "--nodes", "opt_nodes", type=int, required=False, help="Number of nodes"
)
def run(name, partition, nodes, opt_partition, opt_nodes):
    run_impl(
        name,
        partition,
        nodes,
        opt_partition,
        opt_nodes,
        user_root=USER_ROOT,
        subprocess_module=subprocess,
    )


@benchwrap.command()
@click.argument("source", type=click.Path(exists=True))
def add(source):
    add_impl_command(source, user_root=USER_ROOT)


benchwrap.add_command(sync)

# Backwards compatibility aliases -------------------------------------------------
BASE = BASE_URL
_progress_line = inline_progress_line

__all__ = [
    "BASE",
    "BASE_URL",
    "BENCH_PKG",
    "BENCH_ROOT",
    "DATA_DIR",
    "EXECUTORS_PKG",
    "TOK_FILE",
    "USER_ROOT",
    "subprocess",
    "res",
    "benchwrap",
    "old_list",
    "_list",
    "run",
    "add",
    "sync",
    "ensure_data_dir",
    "register",
    "registered",
    "get_access_token",
    "login",
    "list_files_upload",
    "upload_file",
    "upload_one",
    "upload_many",
    "PRINT_LOCK",
    "ProgressFile",
    "pac_line",
    "table_start",
    "table_update",
    "safe_print",
    "_human_readable_size",
    "_progress_line",
]
