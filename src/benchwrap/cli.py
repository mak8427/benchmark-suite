"""
BenchWrap Synchronization Tool

A CLI tool for managing and synchronizing energy-aware benchmarks with a remote server.
Provides functionality for listing, running, adding, and syncing benchmarks.
"""

import importlib.resources as res
import mimetypes
import os
import pathlib
import pkgutil
import shutil
import string
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import click
import requests

from benchwrap.core import add_impl

# Configuration constants
BENCH_PKG = "benchwrap.benchmarks"
EXECUTORS_PKG = "benchwrap.executors"
DATA_DIR = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap"
)
TOK_FILE = DATA_DIR / "tokens"
USER_ROOT = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap/benchmarks"
)
BENCH_ROOT = pathlib.Path(__file__).parent.parent / "src/benchmarks"
BASE = "http://141.5.110.112:7800"

# Thread synchronization for safe printing
PRINT_LOCK = threading.Lock()
_rows = 0  # Global variable to track table rows for progress display


def safe_print(s: str):
    """
    Thread-safe printing function.

    Args:
        s (str): String to print safely across multiple threads
    """
    with PRINT_LOCK:
        click.echo(s)


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

    Provides an interactive menu system where:
    • FILES → numbered 1., 2., 3. …
    • DIRS  → letters  a., b., c. … (only if --dir)
    • Pick a number to *run* that Python file.
    • Pick a letter to *descend* into that folder.

    Hidden items (starting with '.' or '_') are skipped.

    Args:
        start (str): Starting directory path to browse
        show_dir (bool): Whether to show subdirectories in the listing
    """
    path = pathlib.Path(start).expanduser().resolve()
    if not path.exists():
        click.echo(f"[ERR] Path {path} does not exist")
        return

    # Collect visible items (skip hidden files/dirs starting with . or _)
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

    # Display interactive menu
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

    # Get user choice
    choice = click.prompt(
        "Select (empty to quit)", default="", show_default=False
    ).strip()
    if not choice:
        return

    # Execute selected file or recurse into directory
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
        old_list.callback(str(dirs[idx]), show_dir)  # Recursive navigation
    else:
        click.echo("Invalid input!")


@benchwrap.command("list")
def _list():
    """
    List available benchmarks (built-in and user-defined).

    Displays:
    - Standard modules from the executors package
    - User Python files (.py) in USER_ROOT
    - User directories with job_start.sh scripts
    """
    # Get built-in package modules
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    # Get user-defined benchmarks
    user_py = []
    user_dirs = []
    if os.path.isdir(USER_ROOT):
        for p in pathlib.Path(USER_ROOT).iterdir():
            if p.is_file() and p.suffix == ".py" and p.stem != "__init__":
                user_py.append(p.stem)
            elif p.is_dir() and (p / "job_start.sh").exists():
                user_dirs.append(p.name)

    # Display results
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
    """
    Run a benchmark (built-in module, user .py, or user directory with job_start.sh).

    Supports three types of benchmarks:
    1. Built-in package modules
    2. User Python files (.py)
    3. User directories with job_start.sh scripts

    Args:
        name: Benchmark name (can be partial for prefix matching)
        partition: SLURM partition (positional)
        nodes: Number of nodes (positional)
        opt_partition: SLURM partition (option, takes precedence)
        opt_nodes: Number of nodes (option, takes precedence)
    """
    import sys

    # Prefer command-line options over positional arguments
    partition = opt_partition if opt_partition is not None else partition
    eff_nodes = opt_nodes if opt_nodes is not None else nodes

    # Discover all available benchmark modules
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

    # Display available benchmarks if no name provided
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

    # Get benchmark name from user input if not provided
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

    # Normalize and validate nodes parameter
    normalized_nodes = None
    if eff_nodes is not None and str(eff_nodes).strip() != "":
        try:
            normalized_nodes = int(str(eff_nodes).strip())
        except ValueError:
            click.echo(f"[warn] Ignoring invalid nodes value: {eff_nodes}")
            normalized_nodes = None

    def extend_slurm_args(cmd: list) -> list:
        """
        Helper function to append SLURM arguments to command.

        Args:
            cmd (list): Base command list

        Returns:
            list: Command with SLURM arguments appended
        """
        if partition:
            cmd.extend(["--partition", str(partition)])
        if normalized_nodes is not None:
            cmd.extend(["--nodes", str(normalized_nodes)])
        return cmd

    # Execute the selected benchmark
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
    """
    Add a new benchmark source to the user benchmark directory.

    Args:
        source: Path to the benchmark source file or directory to add
    """
    src = pathlib.Path(source).resolve()
    dest = add_impl(src, USER_ROOT)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")


# Authentication and data management functions


def ensure_data_dir():
    """
    Ensure the data directory and token file exist with proper permissions.
    Creates the directory structure and token file if they don't exist.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TOK_FILE.exists():
        TOK_FILE.touch(mode=0o600)  # Secure permissions for token file


def register():
    """
    Register a new user account with the remote server.

    Prompts for username and password, registers with the server,
    and stores the refresh token locally.

    Returns:
        str|bool: Access token on success, False on failure
    """
    ensure_data_dir()
    import click
    import requests

    u = click.prompt("Username", type=str)
    p = click.prompt("Password", hide_input=True)
    if p != click.prompt("Re-enter Password", hide_input=True):
        click.echo("Passwords do not match!")
        return False

    r = requests.post(
        "http://141.5.110.112:7800/auth/register", json={"username": u, "password": p}
    )
    if r.status_code != 201:
        click.echo(f"Registration failed: {r.text}")
        return False

    data = r.json()
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Registration successful.")
    return data["access"]


def registered():
    """
    Check if user is already registered (has a valid token file).

    Returns:
        bool: True if registered, False otherwise
    """
    return TOK_FILE.exists() and TOK_FILE.read_text().strip() != ""


def get_access_token():
    """
    Get a fresh access token using the stored refresh token.

    Returns:
        str|bool: Access token on success, False on failure
    """
    import click
    import requests

    if not TOK_FILE.exists():
        click.echo("No registration found. Please register first.")
        return False

    rid = TOK_FILE.read_text().strip()
    r = requests.post("http://141.5.110.112:7800/auth/refresh", params={"rid": rid})
    if r.status_code != 200:
        click.echo(f"Token refresh failed: {r.text}")
        return False

    data = r.json()
    TOK_FILE.write_text(data["refresh"])
    return data["access"]


def login():
    """
    Login with username and password to get tokens.

    Returns:
        str|bool: Access token on success, False on failure
    """
    ensure_data_dir()
    import click
    import requests

    u = click.prompt("Username", type=str)
    p = click.prompt("Password", hide_input=True)
    r = requests.post(
        "http://141.5.110.112:7800/auth/password", params={"u": u, "p": p}
    )
    if r.status_code != 200:
        click.echo(f"Login failed: {r.text}")
        return False

    data = r.json()
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Login successful.")
    return data["access"]


# File management and upload functions


def list_files_upload():
    """
    Collect all files in USER_ROOT for upload, excluding token files.

    Returns:
        list: List of tuples (filepath, archive_name) for upload
    """
    files = []
    for root, dirs, filenames in os.walk(USER_ROOT):
        for filename in filenames:
            if filename == "tokens":  # Skip sensitive token files
                continue
            filepath = os.path.join(root, filename)
            arcname = os.path.relpath(filepath, USER_ROOT)
            files.append((filepath, arcname))
    click.echo(f"Found {len(files)} files to upload.")
    return files


def upload_file(filepath, arcname, access_token):
    """
    Upload a single file to the remote server using presigned URLs.

    Args:
        filepath (str): Local file path
        arcname (str): Archive name for the file
        access_token (str): Authentication token

    Returns:
        bool: True if upload successful, False otherwise
    """
    import mimetypes
    import os
    import time

    import click
    import requests

    BASE = "http://141.5.110.112:7800"
    name = arcname.replace(os.sep, "/").lstrip("/")[:256]  # Normalize path

    # Get presigned upload URL
    r = requests.post(
        f"{BASE}/storage/presign/upload",
        params={"object_name": name},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=(10, 30),
    )
    if r.status_code != 200:
        click.echo(f"presign failed: {name}: {r.status_code} {r.text}")
        return False

    url = r.json()["url"]
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    size = os.path.getsize(filepath)

    # Handle zero-byte files specially
    if size == 0:
        put = requests.put(
            url,
            data=b"",
            headers={"Content-Type": ctype, "Content-Length": "0"},
            timeout=(10, 30),
        )
    else:
        t0 = time.time()
        pf = ProgressFile(filepath, lambda s, t: _progress_line(name, s, t, t0))
        try:
            put = requests.put(
                url, data=pf, headers={"Content-Type": ctype}, timeout=(10, None)
            )
        finally:
            pf.close()
            print()

    ok = put.status_code in (200, 201, 204)
    click.echo(("✓ " if ok else "✗ ") + name)
    if not ok:
        click.echo(f"    error: {put.status_code} {put.text[:200]}")
    return ok


def upload_one(idx, access, fpath, name):
    """
    Upload a single file with table progress display.

    Args:
        idx (int): Row index for progress table
        access (str): Access token
        fpath (str): File path
        name (str): Object name for upload

    Returns:
        tuple: (name, success_boolean)
    """
    import mimetypes
    import os
    import time

    import requests

    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {access}"})

    # Get presigned URL
    r = s.post(
        f"{BASE}/storage/presign/upload", params={"object_name": name}, timeout=(10, 30)
    )
    if r.status_code != 200:
        table_update(idx, f"✗ {name}  [presign {r.status_code}]")
        return name, False

    url = r.json()["url"]
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    size = os.path.getsize(fpath)

    # Handle zero-byte files
    if size == 0:
        put = requests.put(
            url,
            data=b"",
            headers={"Content-Type": ctype, "Content-Length": "0"},
            timeout=(10, 30),
        )
        table_update(idx, f"{name[:24]:<24} ✓ zero-byte [{put.status_code}]")
        return name, put.ok

    # Upload with progress tracking
    t0 = time.time()
    pf = ProgressFile(
        fpath, lambda snt, tot: table_update(idx, pac_line(name, snt, tot, t0))
    )
    try:
        put = requests.put(
            url,
            data=pf,
            headers={"Content-Type": ctype, "Content-Length": str(size)},
            timeout=(10, None),
        )
    finally:
        pf.close()

    status_msg = (
        f"{name[:24]:<24} ✓ done"
        if put.ok
        else f"{name[:24]:<24} ✗ [{put.status_code}]"
    )
    table_update(idx, status_msg)
    return name, put.ok


def upload_many(access, indexed_files, workers=4):
    """
    Upload multiple files concurrently using thread pool.

    Args:
        access (str): Access token
        indexed_files (list): List of (index, (filepath, relname)) tuples
        workers (int): Number of worker threads

    Returns:
        list: List of (name, success) results
    """
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                upload_one, idx, access, fp, rel.replace(os.sep, "/").lstrip("/")[:256]
            )
            for idx, (fp, rel) in indexed_files
        ]
        for f in as_completed(futs):
            results.append(f.result())
    return results


# Progress display utilities


def pac_line(name, sent, size, t0, width=28):
    """
    Generate a Pac-Man style progress line with transfer statistics.

    Args:
        name (str): File name
        sent (int): Bytes sent
        size (int): Total file size
        t0 (float): Start time
        width (int): Progress bar width

    Returns:
        str: Formatted progress line
    """
    import time

    pct = 0 if size == 0 else int(sent * 100 / size)
    mb, total = sent / 1048576, max(size, 1) / 1048576
    dt = max(time.time() - t0, 1e-6)
    spd = mb / dt
    rem = (total - mb) / spd if spd > 0 else 0
    eta = f"{int(rem // 60):02d}:{int(rem % 60):02d}"

    # Create Pac-Man animation
    pos = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"  # Animate mouth
    rail = [
        ("-" if i < pos else ("o" if (i - pos) % 3 == 0 else " ")) for i in range(width)
    ]
    rail[pos] = mouth
    bar = "".join(rail)

    return (
        f"{name[:24]:<24} [{bar}] {pct:3d}% {mb:6.1f}/{total:6.1f} MiB "
        f"{spd:5.2f} MiB/s ETA {eta}"
    )


def table_start(n):
    """
    Initialize a progress table with n rows.

    Args:
        n (int): Number of rows to reserve
    """
    global _rows
    _rows = n
    sys.stdout.write("\n" * n)  # Reserve space
    sys.stdout.write(f"\x1b[{n}A")  # Move cursor up n lines
    sys.stdout.write("\x1b[s")  # Save cursor position (top of table)
    sys.stdout.flush()


def table_update(i, text):
    """
    Update a specific row in the progress table.

    Args:
        i (int): Row index (0-based)
        text (str): Text to display in the row
    """
    with PRINT_LOCK:
        sys.stdout.write("\x1b[u")  # Restore to top of table
        sys.stdout.write(f"\x1b[{i}B")  # Move down i rows
        sys.stdout.write("\x1b[2K")  # Clear line
        sys.stdout.write(text)  # Write row content
        sys.stdout.write(f"\x1b[{_rows - i}B")  # Return to bottom
        sys.stdout.flush()


class ProgressFile:
    """
    File wrapper that reports progress during reads.
    Useful for tracking upload progress with requests.
    """

    def __init__(self, path, on_progress):
        """
        Initialize progress file wrapper.

        Args:
            path (str): File path to wrap
            on_progress (callable): Callback function(bytes_sent, total_size)
        """
        import os

        self.f = open(path, "rb")
        self.size = os.path.getsize(path)
        self.sent = 0
        self.cb = on_progress

    def __len__(self):
        """Return file size for Content-Length header."""
        return self.size

    def read(self, n=1024 * 1024):
        """
        Read data and report progress.

        Args:
            n (int): Number of bytes to read

        Returns:
            bytes: Data read from file
        """
        b = self.f.read(n)
        if b:
            self.sent += len(b)
            self.cb(self.sent, self.size)
        return b

    def close(self):
        """Close the underlying file."""
        self.f.close()


def _progress_line(name, sent, size, t0, width=28):
    """
    Display a single-line progress indicator with Pac-Man animation.

    Args:
        name (str): File name
        sent (int): Bytes sent
        size (int): Total size
        t0 (float): Start time
        width (int): Progress bar width
    """
    import sys
    import time

    pct = 0 if size == 0 else int(sent * 100 / size)
    mb, total = sent / (1024 * 1024), max(size, 1) / (1024 * 1024)
    dt = max(time.time() - t0, 1e-6)
    spd = mb / dt
    rem = (total - mb) / spd if spd > 0 else 0
    eta = f"{int(rem // 60):02d}:{int(rem % 60):02d}"

    # Pac-Man progress bar
    pos = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"  # Animate mouth open/close
    rail = []
    for i in range(width):
        if i < pos:
            rail.append("-")  # Eaten track
        elif (i - pos) % 3 == 0:
            rail.append("o")  # Pellets ahead
        else:
            rail.append(" ")  # Empty space
    rail[pos] = mouth  # Pac-man at current position
    bar = "".join(rail)

    line = (
        f"{name[:24]:<24} [{bar}] {pct:3d}% {mb:6.1f}/{total:6.1f} MiB "
        f"{spd:5.2f} MiB/s ETA {eta}\r"
    )
    sys.stdout.write(line)
    sys.stdout.flush()


def _human(n):
    """
    Convert bytes to human-readable MiB format.

    Args:
        n (int): Number of bytes

    Returns:
        str: Formatted string in MiB
    """
    return f"{n / (1024 * 1024):.1f} MiB"


@benchwrap.command()
@click.option(
    "-j",
    "--jobs",
    type=int,
    default=4,
    show_default=True,
    help="Number of parallel upload workers",
)
def sync(jobs):
    """
    Synchronize local benchmark files with the remote server.

    This command:
    1. Authenticates with the server (register/login if needed)
    2. Scans local files for upload
    3. Uploads files concurrently with progress display
    4. Reports final statistics

    Args:
        jobs (int): Number of concurrent upload workers
    """
    # Handle authentication
    access = None
    if not registered():
        click.echo("No registration found. Please register first.")
        access = register()
        if not access:
            click.echo("Registration failed. Cannot sync.")
            return False

    if not access:
        access = get_access_token() or login()
        if not access:
            click.echo("Login failed. Cannot sync.")
            return False

    # Prepare files for upload
    files = list_files_upload()
    indexed = list(enumerate(files))  # Add indices for progress table
    total_size = sum(os.path.getsize(fp) for fp, _ in files)

    # Confirm upload
    click.echo(
        f":: Synchronizing {len(files)} files ({_human(total_size)}) with {jobs} jobs"
    )
    if not click.confirm(":: Proceed?", default=True):
        click.echo("Aborted.")
        return False

    # Initialize progress table and start uploads
    table_start(len(files))
    results = upload_many(access, indexed, workers=jobs)

    # Report final statistics
    ok = sum(1 for _, success in results if success)
    click.echo(
        f":: Summary: {ok}/{len(files)} uploaded successfully, {_human(total_size)} total"
    )
    click.echo("✔ Sync complete.")
