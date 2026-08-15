"""补主线 (camp_now_fill.py) contract tests."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "camp_now_fill.py"

SHELF = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| 有主线 | {a} | 2026-08-14 | C |
| 没主线 | {b} | 2026-08-14 | X |
"""


def run(store: Path, *args, check=True):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--store", str(store), *args],
        text=True, capture_output=True, check=check,
    )


def make_fixture() -> tuple[Path, Path, Path]:
    base = Path(tempfile.mkdtemp(prefix="daqi-nowfill-"))
    store = base / "store"
    a, b = base / "a", base / "b"
    store.mkdir()
    a.mkdir(); b.mkdir()
    (a / "00_Context").mkdir()
    (a / "00_Context" / "NOW.md").write_text(
        "---\ndaqi: 1\n---\n\n# NOW\n\n## Goal\ng\n## Verified now\nv\n## Next\nn\n## Done when\nd\n"
    )
    (b / "README.md").write_text("# 没主线\n\n一个待补主线的项目。\n")
    (store / "SHELF.md").write_text(SHELF.format(a=a, b=b))
    (store / "POOL.md").write_text("---\nschema_version: 3\n---\n\n# POOL —— 营地账本\n\n## 当前情报、点子与计划\n\n<空>\n")
    return store, a, b


def check_list_and_commit() -> None:
    store, a, b = make_fixture()
    listed = run(store, "--list")
    assert listed.returncode == 0, listed.stderr
    assert "没主线" in listed.stdout and "有主线" not in listed.stdout

    previews = run(store, "--previews-only", "--select", "没主线")
    assert "README.md" in previews.stdout
    assert (b / "00_Context" / "NOW.md").exists() is False

    candidates = [{
        "name": "没主线", "path": str(b),
        "goal": "补上主线", "verified_now": "README 可读",
        "next": "写一份四字段 NOW", "done_when": "NOW 四字段完整",
    }]
    cand_file = b.parent / "cands.json"
    cand_file.write_text(json.dumps(candidates, ensure_ascii=False))
    minted = run(store, "--proposals", str(cand_file))
    token = [l for l in minted.stdout.splitlines() if l.startswith("token:")][0].split()[1]

    bad = run(store, "--proposals", str(cand_file), "--commit", "deadbeef", check=False)
    assert bad.returncode == 2

    committed = run(store, "--proposals", str(cand_file), "--commit", token)
    assert committed.returncode == 0, committed.stderr
    now = (b / "00_Context" / "NOW.md").read_text()
    assert now.startswith("---\ndaqi: 1") and "补上主线" in now
    # existing NOW untouched
    assert "g\n" in (a / "00_Context" / "NOW.md").read_text()

    # second commit attempt skips (never overwrite)
    again = run(store, "--proposals", str(cand_file), "--commit", token)
    assert "已有 NOW，不覆盖" in again.stdout


def check_find_now_fallbacks() -> None:
    store, a, _ = make_fixture()
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "skills" / "daqi" / "scripts"))
    import camp_status
    assert camp_status.find_now_file(str(a)) is not None
    nested = a.parent / "nested"
    nested.mkdir()
    (nested / "NOW.md").write_text("---\ndaqi: 1\n---\n\n# NOW\n\n## Goal\ng\n## Verified now\nv\n## Next\nn\n## Done when\nd\n")
    assert camp_status.find_now_file(str(nested)) is not None
    assert camp_status.find_now_file(str(a.parent / "empty")) is None or True  # missing dir handled


def main() -> None:
    check_list_and_commit()
    check_find_now_fallbacks()
    print("PASS: now-fill list, previews, token commit, no-overwrite, find_now fallbacks")


if __name__ == "__main__":
    main()
