from pathlib import Path
import sys, pathlib

from src.benchwrap.core import add_impl

def test_add_impl(tmp_path):
    src = tmp_path / "hello_world.py"
    src.write_text("print('hello world')")
    user = tmp_path / "xdg/benchwrap/benchmarks"
    dest = add_impl(src, user)
    assert (dest / "hello_world.py").is_file()
    assert (dest / "job_start.sh").is_file()
