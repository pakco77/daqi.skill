#!/usr/bin/env python3
"""Small no-dependency release check for daqi."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
DAQI = ROOT / "skills" / "daqi"
SCRIPT = DAQI / "scripts" / "rebuild_shelf.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run(
    *args: str,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def load_scanner():
    spec = importlib.util.spec_from_file_location("daqi_rebuild_shelf_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    scanner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scanner
    spec.loader.exec_module(scanner)
    return scanner


def check_rebuild() -> None:
    scanner = load_scanner()
    sentinel_cwd = "/Projects/metadata-only-sentinel"
    sentinel_time = scanner.parse_time("2026-07-30T00:00:00Z")
    assert sentinel_time is not None
    sentinel_project = scanner.Project(cwd=sentinel_cwd, last_active=sentinel_time, agents={"C"})
    sentinel_args = scanner.parser().parse_args(["--as-of", "2026-07-30T00:00:00Z"])
    forbidden_reads = {Path(sentinel_cwd) / "NOW.md", Path(sentinel_cwd) / "HANDOFF.md"}
    original_read_text = Path.read_text

    def reject_project_read(path: Path, *args, **kwargs):
        if path in forbidden_reads:
            raise AssertionError(f"scanner attempted project read: {path}")
        return original_read_text(path, *args, **kwargs)

    with mock.patch.object(Path, "read_text", reject_project_read):
        sentinel_records = scanner.as_records([sentinel_project], sentinel_args)
        sentinel_output = scanner.markdown(sentinel_records, "en")
    assert (
        "| metadata-only-sentinel | /Projects/metadata-only-sentinel "
        "| 2026-07-30T00:00:00Z | C |"
    ) in sentinel_output

    common = (
        "python3",
        str(SCRIPT),
        "--claude-root",
        str(FIXTURES / "claude"),
        "--codex-root",
        str(FIXTURES / "codex"),
        "--codex-archive-root",
        str(FIXTURES / "missing-archive"),
        "--as-of",
        "2026-07-30T00:00:00Z",
    )
    result = run(*common, "--format", "json")
    records = json.loads(result.stdout)
    record_keys = {"project", "cwd", "last_active", "agents", "status"}
    assert all(set(record) == record_keys for record in records)
    assert [record["project"] for record in records] == ["alpha", "beta", "gamma"]
    assert records[0]["agents"] == "C/X"
    assert records[0]["status"] == "active"
    assert records[1]["status"] == "drifting"
    assert records[2]["status"] == "sleeping"
    assert all(record["project"] != "scratch" for record in records)

    scanner_source = SCRIPT.read_text()
    for forbidden in ("NOW.md", "HANDOFF.md", "next_step", "landing_condition"):
        assert forbidden not in scanner_source

    zh = run(*common, "--language", "zh").stdout
    assert "# SHELF 候选（确认后再写入）" in zh
    assert "## 🟢 在推" in zh and "## 🟡 漂了" in zh and "## 🔴 休眠" in zh
    assert zh.splitlines().count("| 项目 | 地址 | 最后活跃 | Agent |") == 3
    assert zh.splitlines().count("|---|---|---|---|") == 3

    en = run(*common, "--language", "en").stdout
    assert "# SHELF candidate (confirm before writing)" in en
    assert "## 🟢 Active" in en and "## 🟡 Drifting" in en
    assert en.splitlines().count("| Project | Path | Last active | Agent |") == 3
    assert en.splitlines().count("|---|---|---|---|") == 3

    fixture_rows = {
        "active": "| alpha | /Users/demo/Projects/alpha | 2026-07-30T00:00:00Z | C/X |",
        "drifting": "| beta | /Users/demo/Projects/beta | 2026-07-23T00:00:00Z | X |",
        "sleeping": "| gamma | /Users/demo/Projects/gamma | 2026-07-01T09:00:00Z | C |",
    }
    for output, headings in (
        (en, ("## 🟢 Active", "## 🟡 Drifting", "## 🔴 Sleeping")),
        (zh, ("## 🟢 在推", "## 🟡 漂了", "## 🔴 休眠")),
    ):
        for index, status in enumerate(("active", "drifting", "sleeping")):
            start = output.index(headings[index]) + len(headings[index])
            end = output.index(headings[index + 1]) if index + 1 < len(headings) else len(output)
            section = output[start:end]
            assert section.splitlines().count(fixture_rows[status]) == 1
            assert all(row not in section for key, row in fixture_rows.items() if key != status)
    assert "_None_" not in en and "_无_" not in zh

    for forbidden in ("Next step", "landing condition", "下一步", "落地条件"):
        assert forbidden not in zh
        assert forbidden not in en

    for language, header in (
        ("en", "| Project | Path | Last active | Agent |"),
        ("zh", "| 项目 | 地址 | 最后活跃 | Agent |"),
    ):
        template = (DAQI / "assets" / f"SHELF.{language}.template.md").read_text()
        lines = template.splitlines()
        assert lines.count(header) == 3
        assert lines.count("|---|---|---|---|") == 3
        for forbidden in ("Next step", "landing condition", "下一步", "落地条件"):
            assert forbidden not in template

    escaped_record = {
        "project": "escape-demo",
        "cwd": "/Projects/with|pipe\ncontinued",
        "last_active": "2026-07-30T00:00:00Z",
        "agents": "C/X",
        "status": "active",
    }
    escaped_row = "| escape-demo | /Projects/with\\|pipe continued | 2026-07-30T00:00:00Z | C/X |"
    escaped_en = scanner.markdown([escaped_record], "en")
    escaped_zh = scanner.markdown([escaped_record], "zh")
    assert escaped_en.splitlines().count(escaped_row) == 1
    assert escaped_zh.splitlines().count(escaped_row) == 1
    for output, headings, empty_row in (
        (escaped_en, ("## 🟢 Active", "## 🟡 Drifting", "## 🔴 Sleeping"), "| _None_ |  |  |  |"),
        (escaped_zh, ("## 🟢 在推", "## 🟡 漂了", "## 🔴 休眠"), "| _无_ |  |  |  |"),
    ):
        for index in (1, 2):
            start = output.index(headings[index]) + len(headings[index])
            end = output.index(headings[index + 1]) if index + 1 < len(headings) else len(output)
            assert output[start:end].splitlines().count(empty_row) == 1

    with tempfile.TemporaryDirectory(prefix="daqi-project-") as project_dir:
        project = Path(project_dir)
        session_root = project / "sessions"
        session_root.mkdir()
        session = session_root / "long.jsonl"
        session.write_text(
            json.dumps({"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z", "payload": {"cwd": str(project)}})
            + "\n"
            + "".join(
                json.dumps({"type": "event", "timestamp": "2026-01-02T00:00:00Z", "message": "ignored"}) + "\n"
                for _ in range(70)
            )
            + json.dumps({"type": "event", "timestamp": "2026-07-30T00:00:00Z", "message": "ignored"})
            + "\n"
        )
        replay = run(
            "python3",
            str(SCRIPT),
            "--claude-root",
            str(session_root),
            "--codex-root",
            str(project / "missing-codex"),
            "--codex-archive-root",
            str(project / "missing-archive"),
            "--as-of",
            "2026-07-30T00:00:00Z",
            "--language",
            "en",
            "--format",
            "json",
        )
        record = json.loads(replay.stdout)[0]
        assert record == {
            "project": project.name,
            "cwd": str(project),
            "last_active": "2026-07-30T00:00:00Z",
            "agents": "C",
            "status": "active",
        }


def check_install_and_hook() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-test-") as temp_home:
        env = dict(os.environ, HOME=temp_home)
        install = str(DAQI / "scripts" / "install.sh")
        first = run("sh", install, "--language", "zh", env=env)
        store = Path(temp_home) / ".daqi" / "SELF.md"
        assert store.exists() and "management_language: zh" in store.read_text()
        assert "default_projects_root:" in store.read_text()
        pool = Path(temp_home) / ".daqi" / "POOL.md"
        assert "schema_version: 3" in pool.read_text()
        original = store.read_text()
        store.write_text(original + "\nkeep-me\n")
        second = run("sh", install, "--language", "en", env=env, check=False)
        assert second.returncode == 2
        assert "explicit language migration is required" in second.stderr
        assert store.read_text().endswith("keep-me\n")
        assert "Claude Code automatic SessionStart setup is not shipped" in first.stdout
        assert str(DAQI / "scripts" / "bootup-hook.sh") not in first.stdout

        dangling_target = Path(temp_home) / "outside.md"
        dangling_store = Path(temp_home) / ".daqi" / "POOL.md"
        dangling_store.unlink()
        dangling_store.symlink_to(dangling_target)
        guarded = run("sh", install, "--language", "zh", env=env, check=False)
        assert guarded.returncode == 2
        assert "not safe store targets" in guarded.stderr
        assert not dangling_target.exists()

        hook_path = DAQI / "scripts" / "bootup-hook.sh"
        missing_root = run("sh", str(hook_path), env=env, check=False)
        assert missing_root.returncode == 2
        assert "Usage:" in missing_root.stderr

        project = Path(temp_home) / "project"
        project.mkdir()
        hook_env = dict(env, CLAUDE_PROJECT_DIR=str(project))
        event = json.dumps(
            {
                "hook_event_name": "SessionStart",
                "cwd": str(project),
                "source": "startup",
            }
        )
        hook = subprocess.run(
            ("sh", str(hook_path), "--root", str(project)),
            cwd=ROOT,
            env=hook_env,
            input=event,
            text=True,
            capture_output=True,
            check=False,
        )
        assert hook.returncode == 0
        assert hook.stdout == ""


def check_skill_contracts() -> None:
    assert not (ROOT / "SKILL.md").exists(), "repo root is a collection, not a mismatched skill"
    skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert [path.parent.name for path in skill_files] == ["context-fold", "daqi", "project-fold"]
    for path in skill_files:
        text = path.read_text()
        match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
        assert match, f"missing frontmatter: {path}"
        name_match = re.search(r"^name:\s*([^\n]+)$", match.group(1), re.MULTILINE)
        assert name_match, f"missing name: {path}"
        name = name_match.group(1).strip()
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), f"invalid name: {name}"
        assert name == path.parent.name, f"name/parent mismatch: {path}"

    daqi_text = (DAQI / "SKILL.md").read_text()
    for trigger in (
        "$daqi",
        "/daqi",
        "达奇",
        "/达奇",
        "项目进度",
        "开工",
        "我想做",
        "我发现",
        "收工",
        "情报",
        "点子",
        "计划",
    ):
        assert trigger in daqi_text
    for scenario in (
        "Your profile across Agents",
        "Cross-Agent job continuity",
        "Camp-ledger growth",
    ):
        assert scenario in daqi_text
    for reference in (
        "profile-policy.md",
        "hooks.md",
        "agent-compatibility.md",
        "project-roots.md",
        "automatic-continuity.md",
    ):
        assert reference in daqi_text
        assert (DAQI / "references" / reference).exists()
    for boundary in (
        "Do not scan sibling directories for a substitute",
        "List the full SHELF only when the user explicitly asks",
        "Never search for, substitute, or read another store",
    ):
        assert boundary in daqi_text

    fast_path = "## Codex automatic-context fast path"
    assert fast_path in daqi_text
    assert daqi_text.index(fast_path) < daqi_text.index("## First-use setup")
    for contract in (
        "sole hot continuity source",
        "Do not read `SELF.md`, `SHELF.md`, `POOL.md`, `NOW.md`, or `HANDOFF.md`",
        "Never edit managed `NOW.md` directly",
        "exactly one receipt",
        "preview-enable",
        "apply-enable",
        "preview-disable",
        "apply-disable",
        "status",
    ):
        assert contract in daqi_text

    prompts = json.loads((DAQI / "test-prompts.json").read_text())
    prompt_ids = {prompt["id"] for prompt in prompts}
    assert {
        "missing-explicit-store",
        "neutral-compact-progress",
        "existing-project-intake",
        "deferred-project-home",
        "help-choose-windows-root",
        "standalone-intel",
        "idea-to-plan",
        "legacy-pool-migration",
        "codex-no-delta",
        "codex-unverified",
        "codex-needs-decision",
        "codex-conflict",
        "codex-enable",
    } <= prompt_ids

    profile_policy = (DAQI / "references" / "profile-policy.md").read_text()
    for forbidden in ("API keys", "identity numbers", "full transcripts"):
        assert forbidden in profile_policy
    for profile_field in ("industry", "occupation", "age band", "life routines"):
        assert profile_field in profile_policy
    project_roots = (DAQI / "references" / "project-roots.md").read_text()
    for root_contract in ("default_projects_root", "New project from zero", "Existing project intake", "non-system fixed drive"):
        assert root_contract in project_roots
    hooks = (DAQI / "references" / "hooks.md").read_text()
    assert "Growth hook" in hooks and "Wrap-up hook" in hooks
    for stage_contract in ("intel/idea/plan", "signal → plan", "candidate → plan"):
        assert stage_contract in hooks
    assert hooks.index("NOW.md") < hooks.index("matching SHELF row")
    automatic = (DAQI / "references" / "automatic-continuity.md").read_text()
    for automatic_contract in (
        "NO_DELTA",
        "PROPOSE_UPDATE",
        "NEEDS_DECISION",
        "exact project root",
        "preview-enable",
        "CONFIGURED_NEEDS_HOOKS_REVIEW",
        "Codex `/hooks`",
        "plan",
        "bypassPermissions",
    ):
        assert automatic_contract in automatic
    for language in ("zh", "en"):
        pool = (DAQI / "assets" / f"POOL.{language}.template.md").read_text()
        assert "schema_version: 3" in pool
        assert "intel/idea/plan" in pool or "情报/点子/计划" in pool
    for language in ("zh", "en"):
        handoff = DAQI / "assets" / f"HANDOFF.{language}.template.md"
        assert handoff.exists() and "Landing condition" in handoff.read_text().replace("落地条件", "Landing condition")

    project_fold = (ROOT / "skills" / "project-fold" / "SKILL.md").read_text()
    assert "整理时可删除 `.DS_Store`" not in project_fold
    assert "references/folder-names.md" in project_fold
    assert "90_Archive" not in project_fold and "90_归档" not in project_fold
    assert "90_History" in project_fold and "90_历史" in project_fold
    assert "default_projects_root" in project_fold and "已有项目" in project_fold
    assert (ROOT / "skills" / "project-fold" / "references" / "folder-names.md").exists()

    readme = (ROOT / "README.md").read_text()
    assert "assets/daqi-icon.png" in readme
    assert "License-MIT" in readme
    zh_readme = (ROOT / "README.zh-CN.md").read_text()
    assert "Grow from zero" in readme and "Organize an existing project" in readme
    assert "default_projects_root" in readme
    assert "Signals, seeds, sprouts" in readme and "User approves promotion" in readme
    assert "No need to remember start or wrap up" in readme
    assert "Codex `/hooks`" in readme
    assert "从零生长" in zh_readme and "已有项目再梳理" in zh_readme
    assert "信号、种子、萌芽" in zh_readme and "用户确认立项" in zh_readme
    assert "不用记开工或收工" in zh_readme
    assert "Codex `/hooks`" in zh_readme
    assert readme.count("```mermaid") == 2 and zh_readme.count("```mermaid") == 2
    assert (ROOT / "LICENSE").read_text().startswith("MIT License")
    assert (ROOT / "assets" / "daqi-icon.png").stat().st_size > 100_000


def main() -> None:
    check_rebuild()
    check_install_and_hook()
    check_skill_contracts()
    print("PASS: rebuild fixtures, install guard, hook JSON, and skill contracts")


if __name__ == "__main__":
    main()
