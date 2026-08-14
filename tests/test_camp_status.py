"""Read-only camp view script contract tests."""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "camp_status.py"

POOL_ZH = """---
schema_version: 3
---

# POOL —— 营地账本

## 当前情报、点子与计划

- 阶段：情报｜痛点一｜最近又出现｜无｜先观察｜2026-08-01
- 阶段：情报｜痛点二｜—｜—｜—｜2026-08-02
- 阶段：点子｜一个方向｜—｜—｜—｜2026-08-03
- 阶段：计划｜快能出发｜—｜—｜—｜2026-08-04
"""

POOL_EN = """---
schema_version: 3
---

# POOL — Camp ledger

- stage: intel | pain one | now | - | watch | 2026-08-01
- stage: idea | a direction | - | - | - | 2026-08-02
- stage: plan | ready to ride | - | - | - | 2026-08-03
"""

SHELF_ZH = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| A | /work/a | 2026-08-10 | Codex |

## 🟡 松了

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|

## 🔴 歇马

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| B | /work/b | 2026-07-01 | Qwen |
"""

SHELF_ZH_EMPTY = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|

## 🟡 松了

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|

## 🔴 歇马

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
"""

SHELF_EN = """# SHELF — Stables

## 🟢 Riding

| Project | Path | Last active | Agent |
|---|---|---|---|
| A | /work/a | 2026-08-10 | Codex |

## 🟡 Loose rein

| Project | Path | Last active | Agent |
|---|---|---|---|

## 🔴 Stabled

| Project | Path | Last active | Agent |
|---|---|---|---|
| B | /work/b | 2026-07-01 | Qwen |
"""


def run(*args, check=True):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def make_store(pool: str, shelf: str) -> Path:
    store = Path(tempfile.mkdtemp(prefix="daqi-camp-"))
    (store / "POOL.md").write_text(pool)
    (store / "SHELF.md").write_text(shelf)
    return store


def check_counts_and_readonly() -> None:
    store = make_store(POOL_ZH, SHELF_ZH)
    out = store / "camp.html"
    pool_bytes = (store / "POOL.md").read_bytes()
    shelf_bytes = (store / "SHELF.md").read_bytes()

    result = run("--store", str(store), "--out", str(out))
    assert result.returncode == 0, result.stderr
    assert "点子王" in result.stdout
    assert "情报 2 · 点子 1 · 计划 1" in result.stdout
    assert "在跑 1 · 松了 0 · 歇马 1" in result.stdout
    assert "只读" in result.stdout

    html = out.read_text()
    assert "情报 2 · 点子 1 · 计划 1" in html
    assert "在跑 1 · 松了 0 · 歇马 1" in html
    assert "点子王" in html
    assert "data:image/png" in html
    assert "/work/a" in html and "/work/b" in html
    assert "READ-ONLY" in html

    # the script must never modify the stores
    assert (store / "POOL.md").read_bytes() == pool_bytes
    assert (store / "SHELF.md").read_bytes() == shelf_bytes
    assert not (store / "SELF.md").exists()


def check_empty() -> None:
    pool_empty = '---\nschema_version: 3\n---\n\n# POOL —— 营地账本\n\n## 当前情报、点子与计划\n\n<空>\n'
    store = make_store(pool_empty, SHELF_ZH_EMPTY)
    result = run("--store", str(store))
    assert result.returncode == 0, result.stderr
    assert "情报 0 · 点子 0 · 计划 0" in result.stdout
    assert "账本和马厩还是空的" in result.stdout
    html = (store / "camp.html").read_text()
    assert "账本还是空的" in html
    assert "马厩还是空的" in html


def check_english() -> None:
    store = make_store(POOL_EN, SHELF_EN)
    result = run("--store", str(store))
    assert result.returncode == 0, result.stderr
    assert "情报 1 · 点子 1 · 计划 1" in result.stdout
    assert "在跑 1 · 松了 0 · 歇马 1" in result.stdout


def check_missing_store() -> None:
    store = Path(tempfile.mkdtemp(prefix="daqi-camp-"))
    out = store / "camp.html"
    result = run("--store", str(store), "--out", str(out), check=False)
    assert result.returncode == 2
    assert not out.exists()
    assert "营地不完整" in result.stderr


def check_unknown_stage_warning() -> None:
    pool = POOL_ZH + "- 阶段：异类｜怪条目｜—｜—｜—｜2026-08-05\n"
    store = make_store(pool, SHELF_ZH_EMPTY)
    result = run("--store", str(store))
    assert result.returncode == 0, result.stderr
    assert "unknown stage" in result.stdout


def main() -> None:
    check_counts_and_readonly()
    check_empty()
    check_english()
    check_missing_store()
    check_unknown_stage_warning()
    print("PASS: camp view counts, empty state, en parsing, missing store, readonly stores")


if __name__ == "__main__":
    main()
