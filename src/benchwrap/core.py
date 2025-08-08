import pathlib
import shutil

import click

LAUNCHER_TEXT = (
    "#!/usr/bin/env bash\nset -euo pipefail\n"
    "DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\npython \"$DIR/%s\"\n"
)

def add_impl(source: pathlib.Path, user_root: pathlib.Path, launcher_text: str = LAUNCHER_TEXT) -> pathlib.Path:
    user_root.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix == ".py":
        dest = user_root / source.stem
        if dest.exists():
            raise click.ClickException(f"{dest.name} already exists")
        dest.mkdir()
        shutil.copy2(source, dest / source.name)
        sh = dest / "job_start.sh"
        sh.write_text(launcher_text % source.name)
        sh.chmod(0o755)
        return dest
    elif source.is_dir() and (source / "job_start.sh").exists():
        dest = user_root / source.name
        if dest.exists():
            raise click.ClickException(f"{dest.name} already exists")
        shutil.copytree(source, dest)
        return dest
    raise click.ClickException("Need a .py file or a folder containing job_start.sh")