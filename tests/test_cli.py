# test_cli.py (≤20 lines)
import importlib
import os
import pathlib
import subprocess
import sys

import click
import pytest
from click.testing import CliRunner

from src.benchwrap.core import add_impl

ROOT = pathlib.Path(__file__).parent.parent.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def tmp_user_root(tmp_path):
    return tmp_path / "xdg/benchwrap/benchmarks"


def test_add_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import benchwrap.cli as cli

    importlib.reload(cli)
    cli.add.callback.__globals__["USER_ROOT"] = tmp_path / "xdg/benchwrap/benchmarks"
    src = tmp_path / "hello_world.py"
    src.write_text("print('hello world')")
    r = CliRunner().invoke(cli.add, [str(src)])
    assert r.exit_code == 0, r.output


def test_add_impl_py_to_dir(tmp_path, tmp_user_root):
    src = tmp_path / "hello.py"
    src.write_text("print('hi')")
    dest = add_impl(src, tmp_user_root)
    assert dest.name == "hello"
    assert (dest / "hello.py").is_file()
    sh = dest / "job_start.sh"
    assert sh.is_file() and (sh.stat().st_mode & 0o111)


def test_add_impl_duplicate(tmp_path, tmp_user_root):
    s = tmp_path / "a.py"
    s.write_text("x")
    add_impl(s, tmp_user_root)
    with pytest.raises(Exception) as e:
        add_impl(s, tmp_user_root)
    # Prefer the exact type:
    assert e.type.__name__ == "ClickException"
    assert "already exists" in str(e.value)


def test_add_impl_rejects_invalid(tmp_path, tmp_user_root):
    bad = tmp_path / "notpy.txt"
    bad.write_text("x")
    try:
        add_impl(bad, tmp_user_root)
    except click.ClickException as e:
        assert "Need a .py file" in str(e)


def test_add_cli_writes_dir(tmp_path, tmp_user_root, monkeypatch):
    import benchwrap.cli as cli

    importlib.reload(cli)
    cli.add.callback.__globals__["USER_ROOT"] = tmp_user_root

    src = tmp_path / "hello.py"
    src.write_text("print('hi')")
    r = CliRunner().invoke(cli.add, [str(src)], env=dict(os.environ))
    assert r.exit_code == 0, r.output
    dest = tmp_user_root / "hello"
    assert (dest / "hello.py").is_file()
    assert (dest / "job_start.sh").is_file()


def test_add_cli_duplicate_fails(tmp_path, tmp_user_root, monkeypatch):
    import benchwrap.cli as cli

    importlib.reload(cli)
    cli.add.callback.__globals__["USER_ROOT"] = tmp_user_root
    src = tmp_path / "x.py"
    src.write_text("x")
    CliRunner().invoke(cli.add, [str(src)], env=dict(os.environ))
    r = CliRunner().invoke(cli.add, [str(src)], env=dict(os.environ))
    assert r.exit_code != 0
    assert "already exists" in r.output


def test_list_shows_user_modules(tmp_user_root, monkeypatch):
    import benchwrap.cli as cli

    importlib.reload(cli)
    cli._list.callback.__globals__["USER_ROOT"] = tmp_user_root
    (tmp_user_root).mkdir(parents=True)
    (tmp_user_root / "u.py").write_text("x")
    d = tmp_user_root / "d"
    d.mkdir()
    (d / "job_start.sh").write_text("echo")
    r = CliRunner().invoke(cli._list)
    assert r.exit_code == 0
    assert "== USER MODULES ==" in r.output
    assert "u  (py)" in r.output or "u.py" in r.output
    assert "d  (dir)" in r.output


def test_list_shows_builtin(monkeypatch, tmp_path):
    import benchwrap.cli as cli

    importlib.reload(cli)
    fake_pkg = tmp_path / "fakepkg"
    fake_pkg.mkdir()
    (fake_pkg / "builtin.py").write_text("# x")
    monkeypatch.setattr(cli.res, "files", lambda _: fake_pkg)
    r = CliRunner().invoke(cli._list)
    assert r.exit_code == 0
    assert "== STANDARD MODULES ==" in r.output
    assert "builtin" in r.output


def test_run_user_dir(tmp_user_root, tmp_path, monkeypatch):
    import benchwrap.cli as cli

    importlib.reload(cli)

    cli.run.callback.__globals__["USER_ROOT"] = tmp_user_root
    cli.USER_ROOT = tmp_user_root
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = str(tmp_user_root.parents[3] / "xdg")  # belt & suspenders

    empty_pkg = tmp_path / "stdpkg"
    empty_pkg.mkdir()
    monkeypatch.setattr(cli.res, "files", lambda _: empty_pkg)

    d = tmp_user_root / "u"
    d.mkdir(parents=True)
    sh = d / "job_start.sh"
    sh.write_text("echo hi")
    sh.chmod(0o755)

    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda args: calls.append(args))

    r = CliRunner().invoke(cli.run, ["u"], env=env)
    assert r.exit_code == 0, r.output
    assert calls and calls[0][0] == "bash"
    assert calls[0][1] == str(sh)


def test_run_builtin(monkeypatch):
    import benchwrap.cli as cli

    importlib.reload(cli)
    fake_pkg = pathlib.Path.cwd() / "fakepkg"
    fake_pkg.mkdir(exist_ok=True)
    (fake_pkg / "std.py").write_text("# x")
    monkeypatch.setattr(cli.res, "files", lambda _: fake_pkg)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args: calls.append(args))
    r = CliRunner().invoke(cli.run, ["std"])
    assert r.exit_code == 0
    assert any("-m" in c for c in calls)
