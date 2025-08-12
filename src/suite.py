import os
import string
import subprocess

import click


@click.command()
def list(dir: bool) -> None:
    """
    Recursively explores directories and executes Python files via user input.

    Parameters:
        path (str): The starting directory to explore.

    Behavior:
        - Lists all non-hidden files and directories in `path`.
        - Files are labeled numerically (1., 2., 3., ...).
        - Directories are labeled alphabetically (a., b., c., ...).
        - User can:
            • Enter a number to execute a selected Python file.
            • Enter a letter to descend into a selected subdirectory.
        - Recurses on directory selection.
        - Executes selected file using subprocess and prints its output.

    Notes:
        - Files or directories that start with '.' or '_' are excluded.
        - Only Python files that can be executed with `python` will be run.
        - Recursion allows navigating deeply nested folder structures.
    """

    cwd = os.getcwd()
    path = cwd + "/benchmarks"

    escape_chars = [".", "_"]  # Skip hidden and special-named files/dirs

    # List visible files
    files = [
        f
        for f in os.listdir(path)
        if f[0] not in escape_chars and os.path.isfile(os.path.join(path, f))
    ]

    # List visible directories
    dirs = [
        d
        for d in os.listdir(path)
        if d[0] not in escape_chars and os.path.isdir(os.path.join(path, d))
    ]

    # Display file options with numeric labels: 1., 2., ...
    if files:
        print("-files---------")
        for i, f in enumerate(files):
            print(f"{i + 1}. {f}")

    # Display directory options with alphabetic labels: a., b., ...
    if dirs:
        print("-directories---")
        for i, d in enumerate(dirs):
            label = (
                string.ascii_lowercase[i] if i < 26 else f"[{i}]"
            )  # Extend beyond 'z' if needed
            print(f"{label}. {d}")
    print("")

    choice = input("Enter file number or directory letter: ")

    # If input is a number corresponding to a file, run it
    if choice.isdigit() and 1 <= int(choice) <= len(files):
        file = files[int(choice) - 1]
        print(f"Run: {file}")
        result = subprocess.run(
            ["python", os.path.join(path, file)], capture_output=True, text=True
        )
        print(result.stdout)
        print(result.stderr)
        print(f"Exit code: {result.returncode}")

    # If input is a letter corresponding to a directory, recurse into it
    elif choice in string.ascii_lowercase[: len(dirs)]:
        dir_index = string.ascii_lowercase.index(choice)
        new_path = os.path.join(path, dirs[dir_index])
        list(new_path)

    else:
        print("Invalid Input")


if __name__ == "__main__":
    print("###")
    print("Welcome to NHR Energy Efficiency Benchmarking suite")
    print("Please choose a benchmark to run\n")
