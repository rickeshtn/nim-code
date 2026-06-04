import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
MG = [sys.executable, str(HERE / "mg.py")]


def setup_module(_):
    fx = HERE / "fixtures"
    fx.mkdir(exist_ok=True)
    (fx / "a.py").write_text("import os\nprint('hello')\nx = 1\ny = 2\nprint('world')\n")
    (fx / "b.txt").write_text("plain text\nhello there\nbye\n")
    (fx / "sub").mkdir(exist_ok=True)
    (fx / "sub" / "c.py").write_text("def hello():\n    return 'hi'\n")
    (fx / "bin.dat").write_bytes(b"\x00\x01\x02hello\x00world\n")


def run(*args, cwd=HERE):
    return subprocess.run(MG + list(args), cwd=cwd, capture_output=True, text=True)


def test_match_basic():
    r = run("hello", "fixtures")
    assert r.returncode == 0
    assert "fixtures/a.py" in r.stdout
    assert "fixtures/b.txt" in r.stdout
    assert "fixtures/sub/c.py" in r.stdout


def test_no_match_exit_1():
    r = run("zzzzzzzzz", "fixtures")
    assert r.returncode == 1
    assert r.stdout.strip() == ""


def test_include_glob():
    r = run("--include", "*.py", "hello", "fixtures")
    assert r.returncode == 0
    assert "b.txt" not in r.stdout
    assert "a.py" in r.stdout
    assert "c.py" in r.stdout


def test_binary_skipped():
    r = run("hello", "fixtures")
    assert "bin.dat" not in r.stdout


def test_after_context():
    r = run("-A", "1", "hello", "fixtures/a.py")
    # match line + 1 after
    lines = [l for l in r.stdout.splitlines() if "fixtures/a.py" in l]
    assert any("hello" in l for l in lines)
    assert any("x = 1" in l for l in lines)


def test_before_context():
    r = run("-B", "1", "world", "fixtures/a.py")
    lines = [l for l in r.stdout.splitlines() if "fixtures/a.py" in l]
    assert any("y = 2" in l for l in lines)
    assert any("world" in l for l in lines)
