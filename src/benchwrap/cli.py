import importlib.resources as res
import os
import pathlib
import pkgutil, subprocess, click
import shutil
import string

BENCH_PKG = "benchwrap.benchmarks"
USER_ROOT = pathlib.Path(os.getenv("XDG_DATA_HOME",
                    pathlib.Path.home()/".local/share")) / "benchwrap/benchmarks"
BENCH_ROOT = pathlib.Path(__file__).parent.parent / "src/benchmarks"

@click.group()                      # parent
def benchwrap():
    """Energy-aware benchmark helper."""






@benchwrap.command("old_list")
@click.argument("start", required=False, default="src/benchmarks",
                type=click.Path(file_okay=False, dir_okay=True))
@click.option("--dir/--no-dir", "show_dir", default=False,
              help="Also list sub-directories.")
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
        click.echo(f"[ERR] Path {path} does not exist"); return

    # collect visible items
    escape = ('.', '_')
    files = [p for p in path.iterdir()
             if p.is_file() and p.suffix == ".py" and p.name[0] not in escape]
    dirs  = [p for p in path.iterdir()
             if p.is_dir()  and p.name[0] not in escape] if show_dir else []

    if not files and not dirs:
        click.echo("(empty)"); return

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
    choice = click.prompt("Select (empty to quit)", default="", show_default=False).strip()
    if not choice: return

    # execute or recurse
    if choice.isdigit() and 1 <= int(choice) <= len(files):
        target = files[int(choice) - 1]
        click.echo(f"▶ Running {target.name}")
        res = subprocess.run(["python", str(target)], capture_output=True, text=True)
        click.echo(res.stdout)
        if res.stderr: click.echo(res.stderr, err=True)
        click.echo(f"Exit code: {res.returncode}")


    elif show_dir and choice in string.ascii_lowercase[:len(dirs)]:
        idx = string.ascii_lowercase.index(choice)
        _list.callback(str(dirs[idx]), show_dir)   # recursive dive
    else:
        click.echo("Invalid input!")

@benchwrap.command("list")
def _list():
    """List and run built-in benchmarks shipped with the wheel."""
    root = res.files(BENCH_PKG)
    pkg_modules = [p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"]

    user_modules = []
    if os.path.isdir(USER_ROOT):
        user_modules = [ p.stem for p in USER_ROOT.iterdir() if p.is_file() and p.suffix == ".py" and p.stem != "__init__"]
    modules = pkg_modules + user_modules

    if not modules:
        click.echo("No benchmarks found"); return

    print("== STANDARD MODULES ==")
    index = 1
    for m in pkg_modules:
        click.echo(f"{index:2}. {m}")
        index += 1

    if len(user_modules) > 1:
        print("== USER MODULES ==")
        for m in user_modules:
            click.echo(f"{index:2}. {m}")
            index += 1



@benchwrap.command("run")
@click.argument("name", required=False)
@click.pass_context
def run(ctx, name):
    """Run built-in benchmarks shipped with the wheel."""
    root = res.files(BENCH_PKG)
    pkg_modules = [p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"]

    user_modules = []
    if os.path.isdir(USER_ROOT):
        user_modules = [p.stem for p in USER_ROOT.iterdir() if p.is_file() and p.suffix == ".py" and p.stem != "__init__"]

    modules = pkg_modules + user_modules
    if not modules:
        click.echo("No benchmarks found"); return

    # Print list if no input
    if not name:
        index = 1
        click.echo("== STANDARD MODULES ==")
        for m in pkg_modules:
            click.echo(f"{index:2}. {m}")
            index += 1
        if user_modules:
            click.echo("== USER MODULES ==")
            for m in user_modules:
                click.echo(f"{index:2}. {m}")
                index += 1

    # Resolve input if provided
    if name:
        choice = name.strip()
    else:
        choice = click.prompt("Select number", default="", show_default=False).strip()
        if not choice:
            return

    # Match by number or name
    if choice.isdigit() and 1 <= int(choice) <= len(modules):
        selected = modules[int(choice) - 1]
    elif choice in modules:
        selected = choice
    else:
        click.echo("Invalid"); return

    modname = f"{BENCH_PKG}.{selected}"
    click.echo(f"▶ running {modname}")
    subprocess.run(["python", "-m", modname])


@benchwrap.command()
@click.argument("source", type=click.Path(exists=True))
def add(source):
    """Copy a .py file *or* folder with job_start.sh into the user benchmarks dir."""
    src = pathlib.Path(source).resolve()
    USER_ROOT.mkdir(parents=True, exist_ok=True)

    if src.is_file() and src.suffix == ".py":
        dest = USER_ROOT / src.name
    elif src.is_dir() and (src/"job_start.sh").exists():
        dest = USER_ROOT / src.name
    else:
        raise click.ClickException("Need a .py file or a folder containing job_start.sh")

    if dest.exists():
        raise click.ClickException(f"{dest.name} already exists")

    #TODO ADD LAUNCHER BASH SCRIPT FOR EACH PY FILE
    

    shutil.copytree(src, dest) if src.is_dir() else shutil.copy2(src, dest)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")  # paca