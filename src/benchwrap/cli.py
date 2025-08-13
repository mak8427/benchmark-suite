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
        _list.callback(str(dirs[idx]), show_dir)  # recursive dive
    else:
        click.echo("Invalid input!")


@benchwrap.command("list")
def _list():
    """List available benchmarks (built-in and user)."""
    root = res.files(BENCH_ROOT)
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
@click.pass_context
def run(ctx, name, partition):
    """Run a benchmark (built-in module, user .py, or user directory with job_start.sh)."""
    root = res.files(BENCH_PKG)
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

    # Resolve and execute
    if choice in pkg_modules:
        click.echo(f"▶ running {BENCH_PKG}.{choice}")

        modname = f"{EXECUTORS_PKG}.{choice}"
        if partition:
            subprocess.run(["python", "-m", modname, "--partition", partition])
        else:
            subprocess.run(["python", "-m", modname])

    elif choice in user_py:
        target = pathlib.Path(USER_ROOT) / f"{choice}.py"
        click.echo(f"▶ running user py {target}")

        if partition:
            subprocess.run(["python", str(target), "--partition", partition])
        else:
            subprocess.run(["python", str(target)])

    elif choice in user_dirs:
        script = pathlib.Path(USER_ROOT) / choice / "job_start.sh"
        click.echo(f"▶ running {script}")
        subprocess.run(["bash", str(script)])
    else:
        click.echo("Invalid")


@benchwrap.command()
@click.argument("source", type=click.Path(exists=True))
def add(source):
    """Add a new benchmark source."""
    src = pathlib.Path(source).resolve()
    dest = add_impl(src, USER_ROOT)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")
