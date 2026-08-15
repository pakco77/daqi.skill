"""Read-only camp view script contract tests."""

from __future__ import annotations

import datetime
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "camp_status.py"

SPEC = importlib.util.spec_from_file_location("camp_status", SCRIPT)
camp_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(camp_status)

SELF_PROFILE = """---
management_language: zh
---

# SELF —— 你的档案

## 你的档案（热区，均为可选）

- 决策方式：先看真实材料，再定一个主方向
- 质量标准：必须有可观察的完成证据
- 沟通偏好：结论先说，过程保持紧凑
- 授权边界：发布和外部写入必须先确认

## 长期目标

- 把点子养到能被真实使用

## 记录规则

- 这段政策文字不能成为用户档案
"""

SELF_TEMPLATE_ONLY = """## 你的档案（热区，均为可选）

- 行业：<用户明确提供且影响协作时才写>
- 职业：<用户明确提供且影响协作时才写>

## 长期目标

<只有用户希望跨项目持续携带时才写>
"""

SELF_EN_DURABLE = """# SELF — Your profile

## Durable goals

- Grow ideas until people can use them
"""

NOW_ZH = """---
daqi: 1
---

# NOW —— 这票到哪了

## Goal

交付一个可运行营地。

## Verified now

- 只读解析已经通过。

## Next

完成场景交互。

## Done when

浏览器验收通过。
"""

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


def make_store(pool: str, shelf: str, self_text: str | None = None) -> Path:
    store = Path(tempfile.mkdtemp(prefix="daqi-camp-"))
    (store / "POOL.md").write_text(pool)
    (store / "SHELF.md").write_text(shelf)
    if self_text is not None:
        (store / "SELF.md").write_text(self_text)
    return store


def make_project(now_text: str | None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="daqi-project-"))
    if now_text is not None:
        context = root / "00_Context"
        context.mkdir()
        (context / "NOW.md").write_text(now_text)
    return root


def make_collision_store(self_text: str | None = SELF_PROFILE,
                         now_text: str | None = NOW_ZH) -> tuple[Path, Path]:
    project = make_project(now_text)
    shelf = f"""# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| 营地 | {project} | 2026-08-14 | Codex |

## 🟡 松了

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|

## 🔴 歇马

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
"""
    return make_store(POOL_ZH, shelf, self_text), project / "00_Context" / "NOW.md"


def check_profile_and_now_parsing() -> None:
    profile = camp_status.parse_self(SELF_PROFILE)
    assert [item["label"] for item in profile["traits"]] == [
        "决策方式", "质量标准", "沟通偏好", "授权边界"
    ]
    assert profile["goals"] == ["把点子养到能被真实使用"]
    assert camp_status.parse_self(SELF_TEMPLATE_ONLY) == {"traits": [], "goals": []}
    assert camp_status.parse_self(SELF_EN_DURABLE)["goals"] == [
        "Grow ideas until people can use them"
    ]

    now = camp_status.parse_now(NOW_ZH)
    assert now["goal"] == "交付一个可运行营地。"
    assert "只读解析已经通过" in now["verified"]
    assert now["next"] == "完成场景交互。"
    assert now["done_when"] == "浏览器验收通过。"


def check_activity_bands() -> None:
    today = datetime.date(2026, 8, 14)
    assert camp_status.classify_activity("2026-08-14", today) == "riding"
    assert camp_status.classify_activity("2026-08-08", today) == "riding"
    assert camp_status.classify_activity("2026-08-07", today) == "week"
    assert camp_status.classify_activity("2026-07-16", today) == "week"
    assert camp_status.classify_activity("2026-07-15", today) == "month"
    assert camp_status.classify_activity("unknown", today) == "unknown"
    assert camp_status.classify_activity("", today) == "unknown"

    now = datetime.datetime(2026, 8, 14, 12, tzinfo=datetime.timezone.utc)
    assert camp_status.classify_activity("2026-08-07T12:00:01Z", now) == "riding"
    assert camp_status.classify_activity("2026-08-07T12:00:00Z", now) == "week"
    assert camp_status.classify_activity("2026-08-07T20:00:00+08:00", now) == "week"
    assert camp_status.classify_activity("2026-07-15T12:00:01Z", now) == "week"
    assert camp_status.classify_activity("2026-07-15T12:00:00Z", now) == "month"
    assert camp_status.classify_activity("2026-08-14T12:00:01Z", now) == "unknown"
    assert camp_status.classify_activity("2026-08-07T12:00:00", now) == "unknown"
    assert camp_status.classify_activity("2026-13-40T99:00:00Z", now) == "unknown"


def check_project_enrichment_and_readonly() -> None:
    with_now = make_project(NOW_ZH)
    without_now = make_project(None)
    projects = [
        {"name": "A", "path": str(with_now), "last": "2026-08-14", "agent": "Codex"},
        {"name": "B", "path": str(without_now), "last": "bad-date", "agent": "Claude Code"},
    ]
    now_bytes = (with_now / "00_Context" / "NOW.md").read_bytes()
    result, warnings = camp_status.enrich_projects(projects, datetime.date(2026, 8, 14))
    assert result[0]["display_band"] == "riding"
    assert result[0]["now"]["next"] == "完成场景交互。"
    assert result[1]["display_band"] == "unknown"
    assert result[1]["now"] is None
    assert warnings == []
    assert (with_now / "00_Context" / "NOW.md").read_bytes() == now_bytes


def check_invalid_now_degrades_with_warning() -> None:
    bad_utf8 = make_project(None)
    (bad_utf8 / "00_Context").mkdir()
    bad_utf8_path = bad_utf8 / "00_Context" / "NOW.md"
    bad_utf8_path.write_bytes(b"\xff\xfe\x00")
    raw_bytes = bad_utf8_path.read_bytes()
    result, warnings = camp_status.enrich_projects(
        [{"name": "bad utf8", "path": str(bad_utf8), "last": "2026-08-14", "agent": "Codex"}],
        datetime.date(2026, 8, 14),
    )
    assert result[0]["now"] is None
    assert any("NOW unavailable for bad utf8" in warning for warning in warnings)
    assert bad_utf8_path.read_bytes() == raw_bytes

    empty_now_cases = (
        """## Goal

<目标>

## Verified now

<已验证>

## Next

<下一步>

## Done when

<完成条件>
""",
        "# NOW\n\n没有四个规定段落。\n",
    )
    for index, now_text in enumerate(empty_now_cases):
        project = make_project(now_text)
        result, warnings = camp_status.enrich_projects(
            [{"name": f"empty {index}", "path": str(project), "last": "2026-08-14", "agent": "Codex"}],
            datetime.date(2026, 8, 14),
        )
        assert result[0]["now"] is None
        assert any(f"NOW has no complete checkpoint for empty {index}" in warning for warning in warnings)


def check_exact_project_root_ignores_sibling_now() -> None:
    parent = Path(tempfile.mkdtemp(prefix="daqi-projects-"))
    selected = parent / "selected"
    selected.mkdir()
    decoy_context = parent / "decoy" / "00_Context"
    decoy_context.mkdir(parents=True)
    decoy_now = decoy_context / "NOW.md"
    decoy_now.write_text(NOW_ZH)
    decoy_bytes = decoy_now.read_bytes()

    result, warnings = camp_status.enrich_projects(
        [{"name": "selected", "path": str(selected), "last": "2026-08-14", "agent": "Codex"}],
        datetime.date(2026, 8, 14),
    )
    assert result[0]["now"] is None
    assert warnings == []
    assert decoy_now.read_bytes() == decoy_bytes


def check_main_data_assembly_and_readonly() -> None:
    with_now = make_project(NOW_ZH)
    without_now = make_project(None)
    shelf = f"""# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| 营地 | {with_now} | 2026-08-14 | Codex |

## 🟡 松了

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| 无时间 | {without_now} | bad-date | Claude Code |

## 🔴 歇马

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
"""
    store = make_store(POOL_ZH, shelf, SELF_PROFILE)
    out = store / "camp.html"
    input_paths = [
        store / "POOL.md",
        store / "SHELF.md",
        store / "SELF.md",
        with_now / "00_Context" / "NOW.md",
    ]
    before = {path: path.read_bytes() for path in input_paths}

    result = run("--store", str(store), "--out", str(out))
    assert result.returncode == 0, result.stderr
    rendered = out.read_text()
    assert "决策方式" in rendered
    assert "先看真实材料，再定一个主方向" in rendered
    assert "完成场景交互。" in rendered
    assert all(path.read_bytes() == data for path, data in before.items())

    no_self = make_store(POOL_ZH, shelf)
    result = run("--store", str(no_self))
    assert result.returncode == 0, result.stderr
    assert "现在还认不出你" in (no_self / "camp.html").read_text()
    assert not (no_self / "SELF.md").exists()

    template_self = make_store(POOL_ZH, shelf, SELF_TEMPLATE_ONLY)
    self_bytes = (template_self / "SELF.md").read_bytes()
    result = run("--store", str(template_self))
    assert result.returncode == 0, result.stderr
    rendered = (template_self / "camp.html").read_text()
    assert "现在还认不出你" in rendered
    assert "用户明确提供且影响协作时才写" not in rendered
    assert (template_self / "SELF.md").read_bytes() == self_bytes


def check_output_input_conflicts_are_rejected() -> None:
    for reserved in ("POOL.md", "SHELF.md", "SELF.md", "NOW.md"):
        store, now_path = make_collision_store()
        out = now_path if reserved == "NOW.md" else store / reserved
        inputs = [store / "POOL.md", store / "SHELF.md", store / "SELF.md", now_path]
        before = {path: path.read_bytes() for path in inputs}
        result = run("--store", str(store), "--out", str(out), check=False)
        assert result.returncode == 2
        assert "输出路径与只读输入冲突" in result.stderr
        assert all(path.read_bytes() == data for path, data in before.items())

    store, _ = make_collision_store(self_text=None)
    missing_self = store / "SELF.md"
    result = run("--store", str(store), "--out", str(missing_self), check=False)
    assert result.returncode == 2
    assert not missing_self.exists()

    store, missing_now = make_collision_store(now_text=None)
    result = run("--store", str(store), "--out", str(missing_now), check=False)
    assert result.returncode == 2
    assert not missing_now.exists()

    store, _ = make_collision_store()
    symlink_out = store / "pool-alias.html"
    symlink_out.symlink_to(store / "POOL.md")
    pool_bytes = (store / "POOL.md").read_bytes()
    result = run("--store", str(store), "--out", str(symlink_out), check=False)
    assert result.returncode == 2
    assert symlink_out.is_symlink()
    assert (store / "POOL.md").read_bytes() == pool_bytes

    store, _ = make_collision_store()
    hardlink_out = store / "shelf-alias.html"
    os.link(store / "SHELF.md", hardlink_out)
    shelf_bytes = (store / "SHELF.md").read_bytes()
    result = run("--store", str(store), "--out", str(hardlink_out), check=False)
    assert result.returncode == 2
    assert (store / "SHELF.md").read_bytes() == shelf_bytes

    store, now_path = make_collision_store()
    inputs = [store / "POOL.md", store / "SHELF.md", store / "SELF.md", now_path]
    before = {path: path.read_bytes() for path in inputs}
    result = run("--store", str(store))
    assert result.returncode == 0, result.stderr
    assert (store / "camp.html").is_file()
    assert all(path.read_bytes() == data for path, data in before.items())


def check_counts_and_readonly() -> None:
    store = make_store(POOL_ZH, SHELF_ZH)
    out = store / "camp.html"
    pool_bytes = (store / "POOL.md").read_bytes()
    shelf_bytes = (store / "SHELF.md").read_bytes()

    result = run("--store", str(store), "--out", str(out))
    assert result.returncode == 0, result.stderr
    assert "营地清点完毕" in result.stdout
    assert "情报 2 · 点子 1 · 计划 1" in result.stdout
    assert "在跑 1 · 松了 0 · 歇马 1" in result.stdout
    assert "只读" in result.stdout

    html = out.read_text()
    assert "营地账本" in html
    assert "情报 · 点子 · 计划" in html
    assert "马厩" in html and "干一票" in html
    assert ">火<" in html and "你是谁？" in html
    assert "7 天没动" in html and "30 天没动" in html
    assert "达奇对你的认知" in html
    assert "这票到哪了" in html
    assert html.count("data:image/png;base64,") >= 2
    assert "/work/a" in html and "/work/b" in html
    assert "Codex" in html and "Qwen" in html
    assert "POOL / CAMP LEDGER" not in html
    assert "LAST_SEEN · NO AGENT" not in html
    assert "READ-ONLY" not in html

    for hook in (
        'data-view="ledger"',
        'data-view="stable"',
        'data-view="self"',
        'data-action="back"',
        'data-action="time-auto"',
        'data-action="time-day"',
        'data-action="time-night"',
    ):
        assert hook in html
    assert 'id="camp-data"' in html
    assert "prefers-reduced-motion" in html
    assert "localStorage" in html
    assert "goBackOneLevel" in html
    assert "wheelLocked" in html
    assert "aria-live" in html
    assert "马掌望台" in html
    assert "transition: transform 520ms cubic-bezier" in html
    assert "translate3d(" in html
    assert "transition: transform 620ms steps" not in html
    assert "brightness(.34)" in html
    assert "camp-smoke" in html and "camp-smoke-rise" in html
    assert "camp-ember-light" in html and "camp-ember-pulse" in html
    assert "camp-horse-rig" in html
    assert "camp-horse-head" in html and "camp-horse-head-dip" in html
    assert "camp-horse-hoof" in html and "camp-horse-hoof-lift" in html
    assert "camp-horse-dust" in html and "camp-horse-dust-rise" in html
    assert "camp-treetop-rig" in html and "camp-treetop-sway" in html
    assert "camp-wind-dust" in html and "camp-wind-dust-cross" in html
    assert "camp-motion-layer" not in html
    assert "cloneNode(false)" not in html
    assert "camp-zoom-layer" in html
    assert "--camp-wheel-zoom" in html
    assert "Math.min(1.2" in html
    assert "event.deltaY < 0" in html
    assert "#E4B95F" in html and "#FFF0B0" in html
    assert ".camp-panel-self { left: 4%;" in html
    assert ".camp-feature-self { left: calc(50% + 58px);" in html

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
    assert "这个阶段还没有条目" in html
    assert "这个时间段没有项目" in html
    assert "现在还认不出你" in html


def check_english() -> None:
    store = make_store(POOL_EN, SHELF_EN)
    result = run("--store", str(store))
    assert result.returncode == 0, result.stderr
    assert "情报 1 · 点子 1 · 计划 1" in result.stdout
    assert "在跑 1 · 松了 0 · 歇马 1" in result.stdout


def check_missing_store() -> None:
    for present_name, present_text in (("POOL.md", POOL_ZH), ("SHELF.md", SHELF_ZH)):
        store = Path(tempfile.mkdtemp(prefix="daqi-camp-"))
        (store / present_name).write_text(present_text)
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


def check_custom_header_aliases() -> None:
    custom = """# NOW —— 小窗相机

## 一句定位

去相机化的摄影应用。

## 当前状态

demo 已完成。

## 下一步

实测三种动作。

## 本阶段完成条件

三种动作跑通。

## 当前决策

- 小窗是完整产品语言
"""
    now = camp_status.parse_now(custom)
    assert now["goal"].strip() and now["verified"].strip() and now["next"].strip() and now["done_when"].strip()


def main() -> None:

    check_profile_and_now_parsing()
    check_activity_bands()
    check_project_enrichment_and_readonly()
    check_invalid_now_degrades_with_warning()
    check_exact_project_root_ignores_sibling_now()
    check_main_data_assembly_and_readonly()
    check_output_input_conflicts_are_rejected()
    check_counts_and_readonly()
    check_empty()
    check_english()
    check_missing_store()
    check_unknown_stage_warning()
    print("PASS: camp view counts, empty state, en parsing, missing store, readonly stores")


if __name__ == "__main__":
    main()
