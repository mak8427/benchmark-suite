"""
Benchwrap synchronization module for managing benchmark uploads and user authentication.

This module provides functionality for:
- User registration and authentication
- File synchronization with remote storage
- Progress tracking with animated pacman display
- Benchmark management and execution
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
DATA_DIR = pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share")) / "benchwrap"
TOK_FILE = DATA_DIR / "tokens"
USER_ROOT = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap/benchmarks"
)
BENCH_ROOT = pathlib.Path(__file__).parent.parent / "src/benchmarks"
BASE = "http://141.5.110.112:7800"

# Global variables for progress tracking
PRINT_LOCK = threading.Lock()
_rows = 0


def safe_print(message: str) -> None:
    """
    Thread-safe printing function.

    Args:
        message: The string to print safely across threads
    """
    with PRINT_LOCK:
        click.echo(message)


@click.group()
def benchwrap():
    """Energy-aware benchmark helper."""
    pass


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

    Args:
        start: Starting directory path for browsing
        show_dir: Whether to show directories in the listing
    """
    path = pathlib.Path(start).expanduser().resolve()
    if not path.exists():
        click.echo(f"[ERR] Path {path} does not exist")
        return

    # Collect visible items (skip hidden files/dirs starting with '.' or '_')
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

    # Display menu options
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

    # Get user choice
    choice = click.prompt(
        "Select (empty to quit)", default="", show_default=False
    ).strip()
    if not choice:
        return

    # Execute file or navigate to directory
    if choice.isdigit() and 1 <= int(choice) <= len(files):
        target = files[int(choice) - 1]
        click.echo(f"▶ Running {target.name}")
        result = subprocess.run(["python", str(target)], capture_output=True, text=True)
        click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)
        click.echo(f"Exit code: {result.returncode}")

    elif show_dir and choice in string.ascii_lowercase[: len(dirs)]:
        idx = string.ascii_lowercase.index(choice)
        old_list.callback(str(dirs[idx]), show_dir)  # Recursive navigation
    else:
        click.echo("Invalid input!")


@benchwrap.command("list")
def _list():
    """List available benchmarks (built-in and user-defined)."""
    # Get built-in modules
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    # Get user-defined modules
    user_py_files = []
    user_directories = []
    if os.path.isdir(USER_ROOT):
        for path in pathlib.Path(USER_ROOT).iterdir():
            if path.is_file() and path.suffix == ".py" and path.stem != "__init__":
                user_py_files.append(path.stem)
            elif path.is_dir() and (path / "job_start.sh").exists():
                user_directories.append(path.name)

    # Display results
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

    Args:
        ctx: Click context
        name: Name of the benchmark to run
        partition: SLURM partition (positional)
        nodes: Number of nodes (positional)
        opt_partition: SLURM partition (option flag)
        opt_nodes: Number of nodes (option flag)
    """
    # Prefer command-line options over positional arguments
    effective_partition = opt_partition if opt_partition is not None else partition
    effective_nodes = opt_nodes if opt_nodes is not None else nodes

    # Discover available benchmark modules
    root = res.files(EXECUTORS_PKG)
    pkg_modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    user_py_files = []
    user_directories = []
    if os.path.isdir(USER_ROOT):
        for path in pathlib.Path(USER_ROOT).iterdir():
            if path.is_file() and path.suffix == ".py" and path.stem != "__init__":
                user_py_files.append(path.stem)
            elif path.is_dir() and (path / "job_start.sh").exists():
                user_directories.append(path.name)

    all_benchmark_names = pkg_modules + user_py_files + user_directories
    if not all_benchmark_names:
        click.echo("No benchmarks found")
        return

    # Display available benchmarks if no name provided
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

    # Get benchmark name from user if not provided
    if name:
        choice = name.strip()
    else:
        choice = click.prompt("Enter name", default="", show_default=False).strip()
        if not choice:
            return

    # Find matching benchmarks by prefix
    matches = [n for n in all_benchmark_names if n.startswith(choice)]
    if len(matches) == 1:
        choice = matches[0]

    # Normalize nodes parameter
    normalized_nodes = None
    if effective_nodes is not None and str(effective_nodes).strip() != "":
        try:
            normalized_nodes = int(str(effective_nodes).strip())
        except ValueError:
            click.echo(f"[warn] Ignoring invalid nodes value: {effective_nodes}")
            normalized_nodes = None

    def extend_slurm_args(command: list) -> list:
        """
        Add SLURM arguments to command if provided.

        Args:
            command: Base command list to extend

        Returns:
            Extended command list with SLURM arguments
        """
        if effective_partition:
            command.extend(["--partition", str(effective_partition)])
        if normalized_nodes is not None:
            command.extend(["--nodes", str(normalized_nodes)])
        return command

    # Execute the chosen benchmark
    if choice in pkg_modules:
        click.echo(f"▶ running {BENCH_PKG}.{choice}")
        module_name = f"{EXECUTORS_PKG}.{choice}"
        command = [sys.executable, "-m", module_name]
        subprocess.run(extend_slurm_args(command))

    elif choice in user_py_files:
        target = pathlib.Path(USER_ROOT) / f"{choice}.py"
        click.echo(f"▶ running user py {target}")
        command = [sys.executable, str(target)]
        subprocess.run(extend_slurm_args(command))

    elif choice in user_directories:
        script = pathlib.Path(USER_ROOT) / choice / "job_start.sh"
        click.echo(f"▶ running {script}")
        subprocess.run(["bash", str(script)])
    else:
        if matches and len(matches) > 1:
            click.echo("Ambiguous name. Did you mean one of:")
            for match in matches:
                click.echo(f"  - {match}")
        else:
            click.echo("Invalid")


@benchwrap.command()
@click.argument("source", type=click.Path(exists=True))
def add(source):
    """
    Add a new benchmark source to the user benchmarks directory.

    Args:
        source: Path to the benchmark source file or directory
    """
    src = pathlib.Path(source).resolve()
    dest = add_impl(src, USER_ROOT)
    click.echo(f"✔ Added {dest.name}.  Run `benchwrap list` to see it.")


def ensure_data_dir() -> None:
    """
    Ensure the data directory and token file exist with proper permissions.
    Creates the data directory if it doesn't exist and touches the token file.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TOK_FILE.exists():
        TOK_FILE.touch(mode=0o600)


def register() -> str | bool:
    """
    Register a new user account with the remote service.

    Returns:
        Access token if registration successful, False otherwise
    """
    ensure_data_dir()

    username = click.prompt("Username", type=str)
    password = click.prompt("Password", hide_input=True)
    if password != click.prompt("Re-enter Password", hide_input=True):
        click.echo("Passwords do not match!")
        return False

    response = requests.post(
        f"{BASE}/auth/register",
        json={"username": username, "password": password}
    )
    if response.status_code != 201:
        click.echo(f"Registration failed: {response.text}")
        return False

    data = response.json()
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Registration successful.")
    return data["access"]


def registered() -> bool:
    """
    Check if user is already registered by verifying token file exists and is not empty.

    Returns:
        True if user is registered, False otherwise
    """
    return TOK_FILE.exists() and TOK_FILE.read_text().strip() != ""


def get_access_token() -> str | bool:
    """
    Get a new access token using the stored refresh token.

    Returns:
        Access token if successful, False otherwise
    """
    if not TOK_FILE.exists():
        click.echo("No registration found. Please register first.")
        return False

    refresh_id = TOK_FILE.read_text().strip()
    response = requests.post(f"{BASE}/auth/refresh", params={"rid": refresh_id})
    if response.status_code != 200:
        click.echo(f"Token refresh failed: {response.text}")
        return False

    data = response.json()
    TOK_FILE.write_text(data["refresh"])
    return data["access"]


def login() -> str | bool:
    """
    Login with username and password to get access tokens.

    Returns:
        Access token if login successful, False otherwise
    """
    ensure_data_dir()

    username = click.prompt("Username", type=str)
    password = click.prompt("Password", hide_input=True)
    response = requests.post(
        f"{BASE}/auth/password",
        params={"u": username, "p": password}
    )
    if response.status_code != 200:
        click.echo(f"Login failed: {response.text}")
        return False

    data = response.json()
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Login successful.")
    return data["access"]


def list_files_upload() -> list[tuple[str, str]]:
    """
    Collect all files in USER_ROOT for uploading, excluding token files.

    Returns:
        List of tuples containing (filepath, archive_name) for each file
    """
    files = []
    for root, dirs, filenames in os.walk(USER_ROOT):
        for filename in filenames:
            if filename == "tokens":
                continue
            filepath = os.path.join(root, filename)
            archive_name = os.path.relpath(filepath, USER_ROOT)
            files.append((filepath, archive_name))
    click.echo(f"Found {len(files)} files to upload.")
    return files


def upload_file(filepath: str, archive_name: str, access_token: str) -> bool:
    """
    Upload a single file to remote storage with progress tracking.

    Args:
        filepath: Local path to the file
        archive_name: Name to use in remote storage
        access_token: Authentication token

    Returns:
        True if upload successful, False otherwise
    """
    # Normalize the object name for remote storage
    object_name = archive_name.replace(os.sep, "/").lstrip("/")[:256]

    # Get presigned upload URL
    response = requests.post(
        f"{BASE}/storage/presign/upload",
        params={"object_name": object_name},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=(10, 30)
    )
    if response.status_code != 200:
        click.echo(f"Presign failed: {object_name}: {response.status_code} {response.text}")
        return False

    upload_url = response.json()["url"]
    content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    file_size = os.path.getsize(filepath)

    # Handle zero-byte files specially
    if file_size == 0:
        put_response = requests.put(
            upload_url,
            data=b"",
            headers={"Content-Type": content_type, "Content-Length": "0"},
            timeout=(10, 30)
        )
    else:
        # Upload with progress tracking
        start_time = time.time()
        progress_file = ProgressFile(
            filepath,
            lambda sent, total: _progress_line(object_name, sent, total, start_time)
        )
        try:
            put_response = requests.put(
                upload_url,
                data=progress_file,
                headers={"Content-Type": content_type},
                timeout=(10, None)
            )
        finally:
            progress_file.close()
            print()  # New line after progress

    success = put_response.status_code in (200, 201, 204)
    click.echo(("✓ " if success else "✗ ") + object_name)
    if not success:
        click.echo(f"    error: {put_response.status_code} {put_response.text[:200]}")
    return success


def upload_one(index: int, access_token: str, filepath: str, object_name: str) -> tuple[str, bool]:
    """
    Upload a single file with table-based progress display.

    Args:
        index: Row index for progress table display
        access_token: Authentication token
        filepath: Local file path
        object_name: Remote object name

    Returns:
        Tuple of (object_name, success_boolean)
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    # Get presigned upload URL
    response = session.post(
        f"{BASE}/storage/presign/upload",
        params={"object_name": object_name},
        timeout=(10, 30)
    )
    if response.status_code != 200:
        table_update(index, f"✗ {object_name}  [presign {response.status_code}]")
        return object_name, False

    upload_url = response.json()["url"]
    content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    file_size = os.path.getsize(filepath)

    # Handle zero-byte files
    if file_size == 0:
        put_response = requests.put(
            upload_url,
            data=b"",
            headers={"Content-Type": content_type, "Content-Length": "0"},
            timeout=(10, 30)
        )
        table_update(index, f"{object_name[:24]:<24} ✓ zero-byte [{put_response.status_code}]")
        return object_name, put_response.ok

    # Upload with animated progress
    start_time = time.time()
    progress_file = ProgressFile(
        filepath,
        lambda sent, total: table_update(index, pac_line(object_name, sent, total, start_time))
    )
    try:
        put_response = requests.put(
            upload_url,
            data=progress_file,
            headers={"Content-Type": content_type, "Content-Length": str(file_size)},
            timeout=(10, None)
        )
    finally:
        progress_file.close()

    # Update final status
    final_status = (
        f"{object_name[:24]:<24} ✓ done" if put_response.ok
        else f"{object_name[:24]:<24} ✗ [{put_response.status_code}]"
    )
    table_update(index, final_status)
    return object_name, put_response.ok


def upload_many(access_token: str, indexed_files: list[tuple[int, tuple[str, str]]], workers: int = 4) -> list[tuple[str, bool]]:
    """
    Upload multiple files concurrently using thread pool.

    Args:
        access_token: Authentication token
        indexed_files: List of (index, (filepath, relative_name)) tuples
        workers: Number of worker threads

    Returns:
        List of (filename, success) tuples
    """
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                upload_one,
                idx,
                access_token,
                filepath,
                relative_name.replace(os.sep, "/").lstrip("/")[:256]
            )
            for idx, (filepath, relative_name) in indexed_files
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def pac_line(name: str, sent: int, size: int, start_time: float, width: int = 28) -> str:
    """
    Generate animated pacman progress line with transfer statistics.

    Args:
        name: File name being transferred
        sent: Bytes sent so far
        size: Total file size in bytes
        start_time: Transfer start timestamp
        width: Width of progress bar in characters

    Returns:
        Formatted progress line string
    """
    # Calculate progress statistics
    percentage = 0 if size == 0 else int(sent * 100 / size)
    megabytes_sent = sent / 1048576  # Convert to MiB
    total_megabytes = max(size, 1) / 1048576

    # Calculate transfer speed and ETA
    elapsed_time = max(time.time() - start_time, 1e-6)
    speed_mbps = megabytes_sent / elapsed_time
    remaining_mb = total_megabytes - megabytes_sent
    remaining_seconds = remaining_mb / speed_mbps if speed_mbps > 0 else 0
    eta = f"{int(remaining_seconds // 60):02d}:{int(remaining_seconds % 60):02d}"

    # Create animated pacman progress bar
    position = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"  # Animate mouth open/close

    # Build the progress rail
    rail = []
    for i in range(width):
        if i < position:
            rail.append("-")  # Eaten track
        elif (i - position) % 3 == 0:
            rail.append("o")  # Pellets ahead
        else:
            rail.append(" ")  # Empty spaces
    rail[position] = mouth  # Place pacman at current position

    progress_bar = "".join(rail)

    return (
        f"{name[:24]:<24} [{progress_bar}] {percentage:3d}% "
        f"{megabytes_sent:6.1f}/{total_megabytes:6.1f} MiB "
        f"{speed_mbps:5.2f} MiB/s ETA {eta}"
    )


def table_start(num_rows: int) -> None:
    """
    Initialize progress table by reserving screen space and positioning cursor.

    Args:
        num_rows: Number of rows to reserve for the progress table
    """
    global _rows
    _rows = num_rows
    sys.stdout.write("\n" * num_rows)      # Reserve screen space
    sys.stdout.write(f"\x1b[{num_rows}A")  # Move cursor up to start of table
    sys.stdout.write("\x1b[s")             # Save cursor position
    sys.stdout.flush()


def table_update(row_index: int, text: str) -> None:
    """
    Update a specific row in the progress table without affecting other rows.

    Args:
        row_index: Zero-based row index to update
        text: New text content for the row
    """
    with PRINT_LOCK:
        sys.stdout.write("\x1b[u")                    # Restore to saved cursor position (top of table)
        sys.stdout.write(f"\x1b[{row_index}B")       # Move down to target row
        sys.stdout.write("\x1b[2K")                   # Clear entire line
        sys.stdout.write(text)                        # Write new content
        sys.stdout.write(f"\x1b[{_rows - row_index}B")  # Move cursor back to bottom of table
        sys.stdout.flush()


class ProgressFile:
    """
    File wrapper that provides progress callbacks during read operations.
    Useful for tracking upload progress with requests library.
    """

    def __init__(self, filepath: str, progress_callback):
        """
        Initialize progress file wrapper.

        Args:
            filepath: Path to the file to wrap
            progress_callback: Function called with (bytes_sent, total_size)
        """
        self.file_handle = open(filepath, 'rb')
        self.size = os.path.getsize(filepath)
        self.bytes_sent = 0
        self.progress_callback = progress_callback

    def __len__(self) -> int:
        """Return file size to allow requests to set Content-Length header."""
        return self.size

    def read(self, chunk_size: int = 1024 * 1024) -> bytes:
        """
        Read data chunk and update progress.

        Args:
            chunk_size: Maximum bytes to read in one operation

        Returns:
            Data chunk read from file
        """
        data = self.file_handle.read(chunk_size)
        if data:
            self.bytes_sent += len(data)
            self.progress_callback(self.bytes_sent, self.size)
        return data

    def close(self) -> None:
        """Close the underlying file handle."""
        self.file_handle.close()


def _progress_line(name: str, sent: int, size: int, start_time: float, width: int = 28) -> None:
    """
    Display progress line with pacman animation that overwrites itself.

    Args:
        name: File name being processed
        sent: Bytes sent so far
        size: Total file size
        start_time: Start timestamp for speed calculation
        width: Progress bar width in characters
    """
    # Calculate progress statistics
    percentage = 0 if size == 0 else int(sent * 100 / size)
    megabytes_sent = sent / (1024 * 1024)
    total_megabytes = max(size, 1) / (1024 * 1024)

    elapsed_time = max(time.time() - start_time, 1e-6)
    speed_mbps = megabytes_sent / elapsed_time
    remaining_mb = total_megabytes - megabytes_sent
    remaining_seconds = remaining_mb / speed_mbps if speed_mbps > 0 else 0
    eta = f"{int(remaining_seconds // 60):02d}:{int(remaining_seconds % 60):02d}"

    # Create animated progress bar
    position = 0 if size == 0 else min(width - 1, int((sent / size) * width))
    mouth = "C" if int(time.time() * 6) % 2 == 0 else "c"  # Animate mouth

    rail = []
    for i in range(width):
        if i < position:
            rail.append("-")         # Eaten track
        elif (i - position) % 3 == 0:
            rail.append("o")         # Pellets ahead
        else:
            rail.append(" ")         # Gaps
    rail[position] = mouth           # Pacman position
    progress_bar = "".join(rail)

    # Create line that overwrites itself (key fix: \r at the end, no \n)
    line = (
        f"{name[:24]:<24} [{progress_bar}] {percentage:3d}% "
        f"{megabytes_sent:6.1f}/{total_megabytes:6.1f} MiB "
        f"{speed_mbps:5.2f} MiB/s ETA {eta}\r"
    )

    # Write and flush immediately to overwrite current line
    sys.stdout.write(line)
    sys.stdout.flush()


def _human_readable_size(num_bytes: int) -> str:
    """
    Convert bytes to human-readable MiB format.

    Args:
        num_bytes: Size in bytes

    Returns:
        Formatted string like "123.4 MiB"
    """
    return f"{num_bytes / (1024 * 1024):.1f} MiB"


@benchwrap.command()
@click.option("-j", "--jobs", type=int, default=4, show_default=True, help="Parallel uploads")
def sync(jobs: int):
    """
    Synchronize local benchmark files with remote storage.

    Args:
        jobs: Number of parallel upload workers
    """
    # Ensure user is authenticated
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

    # Prepare file list for upload
    files = list_files_upload()
    if not files:
        click.echo("No files to sync.")
        return True

    # Calculate total size and confirm with user
    total_size = sum(os.path.getsize(filepath) for filepath, _ in files)
    click.echo(
        f":: Synchronizing {len(files)} files ({_human_readable_size(total_size)}) "
        f"with {jobs} jobs"
    )
    if not click.confirm(":: Proceed?", default=True):
        click.echo("Aborted.")
        return False

    # Initialize progress table and start uploads
    table_start(len(files))
    indexed_files = list(enumerate(files))  # [(index, (filepath, relative_name)), ...]
    results = upload_many(access_token, indexed_files, workers=jobs)

    # Display summary
    successful_uploads = sum(1 for _, success in results if success)
    click.echo(
        f":: Summary: {successful_uploads}/{len(files)} uploaded successfully, "
        f"{_human_readable_size(total_size)} total"
    )
    click.echo("✔ Sync complete.")

    return True