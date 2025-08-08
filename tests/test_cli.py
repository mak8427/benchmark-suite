# test_cli.py (≤20 lines)
import importlib, os, pathlib
from click.testing import CliRunner
import sys, pathlib
ROOT = pathlib.Path(__file__).parent.parent.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_add_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import benchwrap.cli as cli; importlib.reload(cli)
    cli.add.callback.__globals__['USER_ROOT'] = tmp_path / "xdg/benchwrap/benchmarks"
    src = tmp_path / "hello_world.py"; src.write_text("print('hello world')")
    r = CliRunner().invoke(cli.add, [str(src)])
    assert r.exit_code == 0, r.output
