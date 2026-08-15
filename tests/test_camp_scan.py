"""Agent-history scan (camp_scan.py) contract tests."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "camp_scan.py"

POOL = """---
schema_version: 3
---

# POOL —— 营地账本

## 当前情报、点子与计划

<空>
"""

SHELF = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
"""


def run(store: Path, home: Path, *args, check=True):
    env = dict(os.environ, HOME=str(home), DAQI_LLM_API_KEY="")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--store", str(store), *args],
        env=env, text=True, capture_output=True, check=check,
    )


def make_fixture() -> tuple[Path, Path, Path, Path]:
    base = Path(tempfile.mkdtemp(prefix="daqi-scan-"))
    store, home = base / "store", base / "home"
    ws1, ws2 = base / "ws1", base / "ws2"
    store.mkdir()
    (store / "POOL.md").write_text(POOL)
    (store / "SHELF.md").write_text(SHELF)
    (home / ".claude/projects/enc").mkdir(parents=True)
    (home / ".codex/sessions/2026").mkdir(parents=True)
    (home / ".dsh/storages").mkdir(parents=True)
    ws1.mkdir(); ws2.mkdir()
    (home / ".claude/projects/enc/a.jsonl").write_text(
        f'{{"cwd":"{ws1}","timestamp":"2026-08-14T10:00:00Z"}}\n'
    )
    (home / ".codex/sessions/2026/b.jsonl").write_text(
        f'{{"cwd":"{ws2}","timestamp":"2026-08-13T09:00:00Z"}}\n'
    )
    (home / ".dsh/storages/session_projcache.json").write_text(json.dumps({
        "tables": {"sessions": {
            "s1": {"identity": {"cwd": str(ws1), "createdAt": 1786632503721}},
            "s2": {"identity": {"cwd": str(ws2), "createdAt": 1786546103721}},
        }}
    }))
    (ws1 / "README.md").write_text("# 跨 Agent 复盘器\n想让换 Agent 不再重新解释项目。\n")
    (ws2 / "NOW.md").write_text("# NOW\n\n## Goal\n\n已立项的演示项目。\n")
    return store, home, ws1, ws2


def check_scan_pipeline() -> None:
    store, home, ws1, ws2 = make_fixture()
    pool_bytes = (store / "POOL.md").read_bytes()
    shelf_bytes = (store / "SHELF.md").read_bytes()

    phase1 = run(store, home)
    assert phase1.returncode == 0, phase1.stderr
    assert str(ws1) in phase1.stdout and str(ws2) in phase1.stdout
    assert "Claude Code" in phase1.stdout and "DSH" in phase1.stdout
    assert "发现 2 个工作区" in phase1.stdout
    assert "单选/多选" in phase1.stdout
    # phase 1 must not touch stores
    assert (store / "POOL.md").read_bytes() == pool_bytes
    assert (store / "SHELF.md").read_bytes() == shelf_bytes
    camp = (store / "camp.html").read_text()
    # 扫描入口在账本内（JS 动态按钮），不在场景上
    assert "扫描 · 找点子 / 找项目" in camp and "camp-scan-open" in camp
    assert "工作区候选" in camp
    # 颗粒火焰：CSS 燃烧动画 + 降级开关
    assert ".camp-fire-grain" in camp and "camp-grain-shift" in camp
    assert ".camp-sparks" in camp and "camp-spark-rise" in camp
    assert "prefers-reduced-motion" in camp
    # 马微动 + 风掠过地面/空气
    assert "camp-horse-breathe" in camp and "camp-horse-ear-l" in camp
    assert "camp-wind-streaks" in camp and "camp-wind-streak" in camp
    # Pixel UI 组件层 + 昼夜两套颜色 + 面板滚动 + 弹窗返回键
    assert "--camp-px-font" in camp and 'data-time="night"' in camp
    assert ".camp-panel-body { overflow-y: auto" in camp.replace("  ", " ")
    assert "data-action=\"panel-back\"" in camp
    # 单一项进度
    assert "camp-scan-mini" in camp and "camp-scan-chip" in camp
    # 删除：× 触发 → 居中弹窗确认
    assert 'class="camp-modal"' in camp and "确认删除" in camp and "camp-modal-confirm" in camp
    # 这票到哪了：深挖 + loading 态
    assert "深挖" in camp and "深挖中" in camp and "camp-loading-shift" in camp
    # 账本里的达奇形象 + 马厩里的摩根
    assert "camp-ledger-daqi" in camp and "camp-morgan" in camp and "摩根" in camp
    state = json.loads((store / ".scan-state.json").read_text())
    assert state["phase"] in ("scan", "select") and len(state["candidates"]) == 2

    selected = run(store, home, "--select", "ws1,ws2")
    assert selected.returncode == 0, selected.stderr
    assert "[idea]" in selected.stdout and "跨 Agent 复盘器" in selected.stdout
    assert "[project]" in selected.stdout and "ws2" in selected.stdout
    token = [l for l in selected.stdout.splitlines() if l.startswith("token:")][0].split()[1]

    bad = run(store, home, "--select", "ws1,ws2", "--commit", "deadbeef", check=False)
    assert bad.returncode == 2

    committed = run(store, home, "--select", "ws1,ws2", "--commit", token)
    assert committed.returncode == 0, committed.stderr
    assert "100%" in committed.stdout
    assert "阶段：点子｜跨 Agent 复盘器" in (store / "POOL.md").read_text()
    assert "| ws2 |" in (store / "SHELF.md").read_text() and "| scan |" in (store / "SHELF.md").read_text()


def check_deep_without_key_falls_back() -> None:
    store, home, ws1, _ = make_fixture()
    result = run(store, home, "--select", "ws1", "--depth", "deep")
    assert result.returncode == 0, result.stderr
    assert "降级为 shallow" in result.stderr or "shallow" in result.stdout


def check_missing_store() -> None:
    store, home, _, _ = make_fixture()
    (store / "POOL.md").unlink()
    result = run(store, home, check=False)
    assert result.returncode == 2 and "营地不完整" in result.stderr


def check_no_transcript_reads() -> None:
    store, home, ws1, _ = make_fixture()
    trap = home / ".claude/projects/enc/a.jsonl"
    trap.write_text(f'{{"cwd":"{ws1}","timestamp":"2026-08-14T10:00:00Z","content":"CANARY_SECRET"}}\n')
    result = run(store, home)
    assert result.returncode == 0, result.stderr
    for artifact in ((store / "camp.html").read_text(), (store / ".scan-state.json").read_text(), result.stdout):
        assert "CANARY_SECRET" not in artifact


def main() -> None:
    check_scan_pipeline()
    check_deep_without_key_falls_back()
    check_missing_store()
    check_no_transcript_reads()
    print("PASS: scan pipeline, token commit, fallback, readonly, transcript privacy")


if __name__ == "__main__":
    main()
