import importlib.resources as res
import os
import pathlib
import pkgutil
import shutil
import string
import subprocess

import click

from benchwrap.core import add_impl

BENCH_PKG = "benchwrap.benchmarks"
EXECUTORS_PKG = "benchwrap.executors"

USER_ROOT = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap/benchmarks"
)
BENCH_ROOT = pathlib.Path(__file__).parent.parent / "src/benchmarks"


@click.group()  # parent
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
    """
    Interactively browse benchmark files and (optionally) sub-directories.

    • FILES → numbered 1., 2., 3. …
    • DIRS  → letters  a., b., c. … (only if --dir)
    • Pick a number to *run* that Python file.
    • Pick a letter to *descend* into that folder.
    Hidden items ('.' or '_') are skipped.
    """
    path = pathlib.Path(start).expanduser().resolve()
    if not path.exists():
        click.echo(f"[ERR] Path {path} does not exist")
        return

    # collect visible items
    escape = (".", "_")
    files = [
        p
        for p in path.iterdir()
        if p.is_file() and p.suffix == ".py" and p.name[0] not in escape
    ]
    dirs = (
        [p for p in path.iterdir() if p.is_dir() and p.name[0] not in escape]
        if show_dir
        else []
    )

    if not files and not dirs:
        click.echo("(empty)")
        return

    # show menu
    if files:
        click.echo("- files ----------")
        for i, f in enumerate(files, 1):
            click.echo(f"{i:2}. {f.name}")
    if dirs:
        click.echo("- directories -----")
        for i, d in enumerate(dirs):
            label = string.ascii_lowercase[i] if i < 26 else f"[{i}]"
            click.echo(f"{label}. {d.name}")
    click.echo("")

    # get choice
    choice = click.prompt(
        "Select (empty to quit)", default="", show_default=False
    ).strip()
    if not choice:
        return

    # execute or recurse
    if choice.isdigit() and 1 <= int(choice) <= len(files):
        target = files[int(choice) - 1]
        click.echo(f"▶ Running {target.name}")
        res = subprocess.run(["python", str(target)], capture_output=True, text=True)
        click.echo(res.stdout)
        if res.stderr:
            click.echo(res.stderr, err=True)
        click.echo(f"Exit code: {res.returncode}")

    elif show_dir and choice in string.ascii_lowercase[: len(dirs)]:
        idx = string.ascii_lowercase.index(choice)
        old_list.callback(str(dirs[idx]), show_dir)  # recursive dive
    else:
        click.echo("Invalid input!")


@benchwrap.command("list")
def _list():
    """List available benchmarks (built-in and user)."""
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    user_py = []
    user_dirs = []
    if os.path.isdir(USER_ROOT):
        for p in pathlib.Path(USER_ROOT).iterdir():
            if p.is_file() and p.suffix == ".py" and p.stem != "__init__":
                user_py.append(p.stem)
            elif p.is_dir() and (p / "job_start.sh").exists():
                user_dirs.append(p.name)

    if not pkg_modules and not user_py and not user_dirs:
        click.echo("No benchmarks found")
        return

    click.echo("== STANDARD MODULES ==")
    for m in pkg_modules:
        click.echo(f"  - {m}")

    if user_py or user_dirs:
        click.echo("== USER MODULES ==")
        for m in user_py:
            click.echo(f"  - {m}  (py)")
        for d in user_dirs:
            click.echo(f"  - {d}  (dir)")


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
@click.pass_context
def run(ctx, name, partition, nodes, opt_partition, opt_nodes):
    """Run a benchmark (built-in module, user .py, or user directory with job_start.sh)."""
    import sys

    # Prefer options over positional args if provided
    partition = opt_partition if opt_partition is not None else partition
    eff_nodes = opt_nodes if opt_nodes is not None else nodes

    # Discover available modules
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    user_py = []
    user_dirs = []
    if os.path.isdir(USER_ROOT):
        for p in pathlib.Path(USER_ROOT).iterdir():
            if p.is_file() and p.suffix == ".py" and p.stem != "__init__":
                user_py.append(p.stem)
            elif p.is_dir() and (p / "job_start.sh").exists():
                user_dirs.append(p.name)

    all_names = pkg_modules + user_py + user_dirs
    if not all_names:
        click.echo("No benchmarks found")
        return

    # Print list if no input
    if not name:
        click.echo("== STANDARD MODULES ==")
        for m in pkg_modules:
            click.echo(f"  - {m}")
        if user_py or user_dirs:
            click.echo("== USER MODULES ==")
            for m in user_py:
                click.echo(f"  - {m}  (py)")
            for d in user_dirs:
                click.echo(f"  - {d}  (dir)")

    # Resolve input if provided
    if name:
        choice = name.strip()
    else:
        choice = click.prompt("Enter name", default="", show_default=False).strip()
        if not choice:
            return

    # Try to find matching benchmark by prefix
    matches = [n for n in all_names if n.startswith(choice)]
    if len(matches) == 1:
        choice = matches[0]

    # Normalize nodes (optional)
    normalized_nodes = None
    if eff_nodes is not None and str(eff_nodes).strip() != "":
        try:
            normalized_nodes = int(str(eff_nodes).strip())
        except ValueError:
            click.echo(f"[warn] Ignoring invalid nodes value: {eff_nodes}")
            normalized_nodes = None

    # Helper to append common args
    def extend_slurm_args(cmd: list) -> list:
        if partition:
            cmd.extend(["--partition", str(partition)])
        if normalized_nodes is not None:
            cmd.extend(["--nodes", str(normalized_nodes)])
        return cmd

    # Resolve and execute
    if choice in pkg_modules:
        click.echo(f"▶ running {BENCH_PKG}.{choice}")
        modname = f"{EXECUTORS_PKG}.{choice}"
        cmd = [sys.executable, "-m", modname]
        subprocess.run(extend_slurm_args(cmd))

    elif choice in user_py:
        target = pathlib.Path(USER_ROOT) / f"{choice}.py"
        click.echo(f"▶ running user py {target}")
        cmd = [sys.executable, str(target)]
        subprocess.run(extend_slurm_args(cmd))

    elif choice in user_dirs:
        script = pathlib.Path(USER_ROOT) / choice / "job_start.sh"
        click.echo(f"▶ running {script}")
        subprocess.run(["bash", str(script)])
    else:
        if matches and len(matches) > 1:
            click.echo("Ambiguous name. Did you mean one of:")
            for m in matches:
                click.echo(f"  - {m}")
        else:
            click.echo("Invalid")


@benchwrap.command()
@click.argument("source", type=click.Path(exists=True))
def add(source):
    """Add a new benchmark source."""
    src = pathlib.Path(source).resolve()
    dest = add_impl(src, USER_ROOT)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")


@benchwrap.command()
def sync():
    """Sync the data directory to remote storage."""
    click.echo("Syncing data directory to remote storage…")
    # Placeholder implementation
    click.echo("✔ Sync complete.")
