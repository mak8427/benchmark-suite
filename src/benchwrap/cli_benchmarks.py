"""Benchmark listing and execution helpers for the Benchwrap CLI."""

from __future__ import annotations

import importlib.resources as res
import os
import pathlib
import string
import subprocess
import sys

import click

from benchwrap.core import add_impl

from .cli_constants import EXECUTORS_PKG, USER_ROOT


def _iter_user_content(
    user_root: pathlib.Path | None = None,
) -> tuple[list[str], list[str]]:
    """Return lists of user-provided Python files and benchmark directories."""
    root = pathlib.Path(user_root) if user_root is not None else USER_ROOT
    user_py_files: list[str] = []
    user_directories: list[str] = []
    if os.path.isdir(root):
        for path in pathlib.Path(root).iterdir():
            if path.is_file() and path.suffix == ".py" and path.stem != "__init__":
                user_py_files.append(path.stem)
            elif path.is_dir() and (path / "job_start.sh").exists():
                user_directories.append(path.name)
    return user_py_files, user_directories


def old_list_impl(start: str, show_dir: bool, subprocess_module=None) -> None:
    """Interactively browse benchmark files and optionally sub-directories."""
    proc = subprocess_module or subprocess

    def browse(path: pathlib.Path) -> None:
        if not path.exists():
            click.echo(f"[ERR] Path {path} does not exist")
            return

        escape_chars = (".", "_")
        files = [
            p
            for p in path.iterdir()
            if p.is_file() and p.suffix == ".py" and p.name[0] not in escape_chars
        ]
        dirs = (
            [p for p in path.iterdir() if p.is_dir() and p.name[0] not in escape_chars]
            if show_dir
            else []
        )

        if not files and not dirs:
            click.echo("(empty)")
            return

        if files:
            click.echo("- files ----------")
            for i, file_path in enumerate(files, 1):
                click.echo(f"{i:2}. {file_path.name}")
        if dirs:
            click.echo("- directories -----")
            for i, dir_path in enumerate(dirs):
                label = string.ascii_lowercase[i] if i < 26 else f"[{i}]"
                click.echo(f"{label}. {dir_path.name}")
        click.echo("")

        choice = click.prompt(
            "Select (empty to quit)", default="", show_default=False
        ).strip()
        if not choice:
            return

        if choice.isdigit() and 1 <= int(choice) <= len(files):
            target = files[int(choice) - 1]
            click.echo(f"▶ Running {target.name}")
            result = proc.run(
                [sys.executable, str(target)], capture_output=True, text=True
            )
            click.echo(result.stdout)
            if result.stderr:
                click.echo(result.stderr, err=True)
            click.echo(f"Exit code: {result.returncode}")

        elif show_dir and choice in string.ascii_lowercase[: len(dirs)]:
            idx = string.ascii_lowercase.index(choice)
            browse(dirs[idx])
        else:
            click.echo("Invalid input!")

    browse(pathlib.Path(start).expanduser().resolve())


def list_impl(user_root: pathlib.Path | None = None) -> None:
    """List available built-in and user-provided benchmarks."""
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    user_py_files, user_directories = _iter_user_content(user_root)

    if not pkg_modules and not user_py_files and not user_directories:
        click.echo("No benchmarks found")
        return

    click.echo("== STANDARD MODULES ==")
    for module in pkg_modules:
        click.echo(f"  - {module}")

    if user_py_files or user_directories:
        click.echo("== USER MODULES ==")
        for module in user_py_files:
            click.echo(f"  - {module}  (py)")
        for directory in user_directories:
            click.echo(f"  - {directory}  (dir)")


def run_impl(
    name,
    partition,
    nodes,
    opt_partition,
    opt_nodes,
    user_root: pathlib.Path | None = None,
    subprocess_module=None,
):
    """Drive the benchmark run command using the provided arguments."""
    user_root_path = pathlib.Path(user_root) if user_root is not None else USER_ROOT
    proc = subprocess_module or subprocess
    effective_partition = opt_partition if opt_partition is not None else partition
    effective_nodes = opt_nodes if opt_nodes is not None else nodes

    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]
    user_py_files, user_directories = _iter_user_content(user_root_path)

    all_benchmark_names = pkg_modules + user_py_files + user_directories
    if not all_benchmark_names:
        click.echo("No benchmarks found")
        return

    if not name:
        click.echo("== STANDARD MODULES ==")
        for module in pkg_modules:
            click.echo(f"  - {module}")
        if user_py_files or user_directories:
            click.echo("== USER MODULES ==")
            for module in user_py_files:
                click.echo(f"  - {module}  (py)")
            for directory in user_directories:
                click.echo(f"  - {directory}  (dir)")

    choice = (
        name.strip()
        if name
        else click.prompt("Enter name", default="", show_default=False).strip()
    )
    if not choice:
        return

    matches = [n for n in all_benchmark_names if n.startswith(choice)]
    if len(matches) == 1:
        choice = matches[0]

    normalized_nodes = None
    if effective_nodes is not None and str(effective_nodes).strip() != "":
        try:
            normalized_nodes = int(str(effective_nodes).strip())
        except ValueError:
            click.echo(f"[warn] Ignoring invalid nodes value: {effective_nodes}")
            normalized_nodes = None

    def extend_slurm_args(command: list[str]) -> list[str]:
        if effective_partition:
            command.extend(["--partition", str(effective_partition)])
        if normalized_nodes is not None:
            command.extend(["--nodes", str(normalized_nodes)])
        return command

    if choice in pkg_modules:
        click.echo(f"▶ running {EXECUTORS_PKG}.{choice}")
        command = [sys.executable, "-m", f"{EXECUTORS_PKG}.{choice}"]
        proc.run(extend_slurm_args(command))

    elif choice in user_py_files:
        target = pathlib.Path(user_root_path) / f"{choice}.py"
        click.echo(f"▶ running user py {target}")
        command = [sys.executable, str(target)]
        proc.run(extend_slurm_args(command))

    elif choice in user_directories:
        script = pathlib.Path(user_root_path) / choice / "job_start.sh"
        click.echo(f"▶ running {script}")
        proc.run(["bash", str(script)])
    else:
        if matches and len(matches) > 1:
            click.echo("Ambiguous name. Did you mean one of:")
            for match in matches:
                click.echo(f"  - {match}")
        else:
            click.echo("Invalid")


def add_impl_command(source: str, user_root: pathlib.Path | None = None) -> None:
    """Add a new benchmark source to the user benchmark directory."""
    target_root = pathlib.Path(user_root) if user_root is not None else USER_ROOT
    src = pathlib.Path(source).resolve()
    dest = add_impl(src, target_root)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")
