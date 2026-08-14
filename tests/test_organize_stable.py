"""One-click stable organization (organize_stable.py) contract tests."""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "organize_stable.py"

SHELF = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| testproj | {proj} | 2026-08-14 | DSH |
"""


def run(*args, check=True):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def make_fixture() -> tuple[Path, Path]:
    base = Path(tempfile.mkdtemp(prefix="daqi-organize-"))
    store = base / "store"
    proj = base / "proj"
    store.mkdir()
    proj.mkdir()
    (store / "SHELF.md").write_text(SHELF.format(proj=proj))
    (proj / "10_Source").mkdir()
    for name in ("a.png", "notes.md", "old-v1.zip", "mystery.dat", "NOW.md"):
        (proj / name).touch()
    return store, proj


def check_preview_and_apply() -> None:
    store, proj = make_fixture()
    before = sorted(p.name for p in proj.iterdir())

    result = run("--store", str(store), "--project", "testproj")
    assert result.returncode == 0, result.stderr
    assert "目录语言：en" in result.stdout
    assert "00_Context/" in result.stdout and "20_Docs/" in result.stdout and "90_History/" in result.stdout
    assert "a.png -> 30_Assets/a.png" in result.stdout
    assert "notes.md -> 20_Docs/notes.md" in result.stdout
    assert "old-v1.zip -> 90_History/old-v1.zip" in result.stdout
    assert "mystery.dat" in result.stdout and "无法判断" in result.stdout
    token = [l for l in result.stdout.splitlines() if l.startswith("token:")][0].split()[1]

    # preview must be read-only
    assert sorted(p.name for p in proj.iterdir()) == before

    bad = run("--store", str(store), "--project", "testproj", "--apply", "deadbeef", check=False)
    assert bad.returncode == 2

    applied = run("--store", str(store), "--project", "testproj", "--apply", token)
    assert applied.returncode == 0, applied.stderr
    assert (proj / "30_Assets" / "a.png").exists()
    assert (proj / "20_Docs" / "notes.md").exists()
    assert (proj / "90_History" / "old-v1.zip").exists()
    assert (proj / "mystery.dat").exists()  # never moved
    assert (proj / "00_Context" / "NOW.md").exists()  # contract hot file moved in
    log = (proj / "90_History" / "cleanup-log.md").read_text()
    assert "a.png -> 30_Assets/a.png" in log
    assert "mystery.dat" not in log.replace("待判断", "")  # untouched files are not logged as moves

    # stores are never modified
    assert "testproj" in (store / "SHELF.md").read_text()


def check_missing_project() -> None:
    store, _ = make_fixture()
    result = run("--store", str(store), "--project", "nobody", check=False)
    assert result.returncode == 2
    assert "马厩里没有" in result.stderr


def check_zh_detection() -> None:
    store, proj = make_fixture()
    (proj / "10_源码").mkdir()
    result = run("--store", str(store), "--project", "testproj")
    assert "目录语言：zh" in result.stdout
    assert "00_上下文/" in result.stdout and "20_文档/" in result.stdout and "90_历史/" in result.stdout
    assert "a.png -> 30_素材/a.png" in result.stdout


def main() -> None:
    check_preview_and_apply()
    check_missing_project()
    check_zh_detection()
    print("PASS: organize stable preview, token apply, log, readonly, zh detection")


if __name__ == "__main__":
    main()
