#!/usr/bin/env python3
"""No-dependency contract check for canonical NOW checkpoints."""

from __future__ import annotations

import base64
import copy
import errno
import hashlib
import html
import io
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
DAQI = ROOT / "skills" / "daqi"
HELPER = DAQI / "scripts" / "checkpoint.py"
ADAPTER = DAQI / "scripts" / "bootup-hook.sh"
GUARD = DAQI / "scripts" / "permission_guard.py"
sys.path.insert(0, str(DAQI / "scripts"))

import checkpoint  # noqa: E402


FIELDS = {
    "goal": "Ship one stable, user-visible checkpoint contract.",
    "verified_now": "The schema is specified.\n\n- UTF-8 only\n- No dependencies",
    "next": "Run exactly one safe local verification.",
    "done_when": "The assert runner prints its PASS line.",
}

MANAGED = (
    "---\n"
    "daqi: 1\n"
    "---\n"
    "\n"
    "# NOW\n"
    "\n"
    "## Goal\n"
    "\n"
    "Ship one stable, user-visible checkpoint contract.\n"
    "\n"
    "## Verified now\n"
    "\n"
    "The schema is specified.\n"
    "\n"
    "- UTF-8 only\n"
    "- No dependencies\n"
    "\n"
    "## Next\n"
    "\n"
    "Run exactly one safe local verification.\n"
    "\n"
    "## Done when\n"
    "\n"
    "The assert runner prints its PASS line.\n"
).encode()

UNMANAGED = MANAGED.removeprefix(b"---\ndaqi: 1\n---\n\n")

EN_TEMPLATE = """---
daqi: 1
---

# NOW — Where this job stands

## Goal

<project-level user-visible result and stable boundaries>

## Verified now

<evidence-backed results, failures, blockers, and critical unknowns>

## Next

<exactly one selected safe action within current authority>

## Done when

<observable evidence that proves Next is complete>
"""

ZH_TEMPLATE = """---
daqi: 1
---

# NOW —— 这票到哪了

## Goal

<项目级、用户可见的结果与稳定边界>

## Verified now

<已有证据支持的结果、失败、阻塞事实与关键未知>

## Next

<当前选定、权限范围内的一个安全动作>

## Done when

<证明 Next 完成的可观察条件>
"""

PLACEHOLDERS = (
    "<project-level user-visible result and stable boundaries>",
    "<evidence-backed results, failures, blockers, and critical unknowns>",
    "<exactly one selected safe action within current authority>",
    "<observable evidence that proves Next is complete>",
    "<项目级、用户可见的结果与稳定边界>",
    "<已有证据支持的结果、失败、阻塞事实与关键未知>",
    "<当前选定、权限范围内的一个安全动作>",
    "<证明 Next 完成的可观察条件>",
)


def rejected(call: Callable[[], object]) -> None:
    try:
        call()
    except ValueError:
        return
    raise AssertionError("invalid checkpoint input was accepted")


def token_for(payload: str | bytes) -> str:
    raw = payload.encode() if isinstance(payload, str) else payload
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def run_script(
    script: Path,
    *args: str,
    stdin: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (str(script), *args),
        cwd=ROOT,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def check_templates() -> None:
    for language, expected in (("en", EN_TEMPLATE), ("zh", ZH_TEMPLATE)):
        raw = (DAQI / "assets" / f"NOW.{language}.template.md").read_bytes()
        assert b"\r" not in raw
        assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
        assert raw.decode("utf-8") == expected
    assert "## 目标" not in ZH_TEMPLATE and "## Goal" in ZH_TEMPLATE


def check_schema() -> None:
    assert checkpoint.MAX_NOW_BYTES == 8192
    assert checkpoint.FIELD_KEYS == ("goal", "verified_now", "next", "done_when")
    assert checkpoint.FIELD_TITLES == ("Goal", "Verified now", "Next", "Done when")

    assert checkpoint.normalize_field("  paragraph\n\n- item  \n") == "paragraph\n\n- item"
    assert checkpoint.render_now(FIELDS, managed=True) == MANAGED
    assert checkpoint.render_now(FIELDS, managed=False) == UNMANAGED
    assert checkpoint.parse_now(MANAGED, managed=True) == FIELDS
    assert checkpoint.parse_now(UNMANAGED, managed=False) == FIELDS
    assert checkpoint.render_now(
        checkpoint.parse_now(MANAGED, managed=True), managed=True
    ) == MANAGED

    chinese = {
        "goal": "交付用户可见且边界稳定的结果。",
        "verified_now": "中文正文已验证。\n\n- 标题仍是英文\n- 列表可保留",
        "next": "在当前权限内运行一次本地验证。",
        "done_when": "终端打印约定的 PASS 行。",
    }
    chinese_raw = checkpoint.render_now(chinese, managed=True)
    assert b"## Goal\n" in chinese_raw and "中文正文" in chinese_raw.decode()
    assert checkpoint.parse_now(chinese_raw, managed=True) == chinese

    reordered = {
        "done_when": FIELDS["done_when"],
        "next": FIELDS["next"],
        "verified_now": FIELDS["verified_now"],
        "goal": FIELDS["goal"],
    }
    assert checkpoint.render_now(reordered, managed=True) == MANAGED


def check_invalid_now() -> None:
    wrong_marker = MANAGED.replace(b"daqi: 1", b"daqi: 2", 1)
    extra_frontmatter = MANAGED.replace(b"daqi: 1\n", b"daqi: 1\nextra: true\n", 1)
    second_frontmatter = MANAGED.replace(
        b"# NOW", b"---\nextra: true\n---\n\n# NOW", 1
    )
    wrong_heading = MANAGED.replace(b"## Verified now", b"## Verified Now", 1)
    duplicate_heading = MANAGED.replace(
        b"The schema is specified.", b"The schema is specified.\n\n## Goal\n\nAgain", 1
    )
    extra_heading = MANAGED.replace(
        b"The schema is specified.", b"The schema is specified.\n\n## Notes\n\nNope", 1
    )
    chinese_heading = MANAGED.replace(b"## Goal", "## 目标".encode(), 1)
    wrong_order = (
        MANAGED.replace(b"## Goal", b"## __swap__", 1)
        .replace(b"## Next", b"## Goal", 1)
        .replace(b"## __swap__", b"## Next", 1)
    )
    empty_goal = MANAGED.replace(FIELDS["goal"].encode(), b"", 1)
    body_heading = MANAGED.replace(
        FIELDS["next"].encode(), b"Run one check.\n\n### Detail\n\nNot allowed", 1
    )

    for raw, managed in (
        (wrong_marker, True),
        (extra_frontmatter, True),
        (second_frontmatter, True),
        (wrong_heading, True),
        (duplicate_heading, True),
        (extra_heading, True),
        (chinese_heading, True),
        (wrong_order, True),
        (empty_goal, True),
        (body_heading, True),
        (MANAGED, False),
        (UNMANAGED, True),
        (MANAGED.replace(b"\n", b"\r\n"), True),
        (MANAGED[:-1], True),
        (MANAGED.replace(b"schema", b"sche\x00ma", 1), True),
        (MANAGED.replace(b"schema", b"sche\rma", 1), True),
        (b"\xff", True),
    ):
        rejected(lambda raw=raw, managed=managed: checkpoint.parse_now(raw, managed=managed))

    for value in ("", " \n ", "# Heading", "###### Heading", "bad\x00value", "bad\rvalue"):
        rejected(lambda value=value: checkpoint.normalize_field(value))
    for spaces in (1, 2, 3):
        rejected(
            lambda spaces=spaces: checkpoint.normalize_field(
                f"Paragraph\n{' ' * spaces}### Internal heading"
            )
        )
    rejected(
        lambda: checkpoint.render_now(
            {**FIELDS, "next": "Paragraph\n   ## Internal heading"}, managed=True
        )
    )
    assert checkpoint.normalize_field("Paragraph\n   - indented list") == "Paragraph\n   - indented list"
    assert checkpoint.normalize_field("Paragraph\n    # code") == "Paragraph\n    # code"
    rejected(lambda: checkpoint.normalize_field(1))  # type: ignore[arg-type]
    rejected(lambda: checkpoint.render_now({**FIELDS, "extra": "no"}, managed=True))
    rejected(lambda: checkpoint.render_now({k: v for k, v in FIELDS.items() if k != "next"}, managed=True))
    rejected(lambda: checkpoint.render_now({**FIELDS, "goal": 1}, managed=True))  # type: ignore[dict-item]


def check_template_placeholders() -> None:
    for placeholder in PLACEHOLDERS:
        rejected(lambda placeholder=placeholder: checkpoint.normalize_field(f" \n{placeholder}\n "))

    raw = MANAGED.replace(FIELDS["goal"].encode(), PLACEHOLDERS[0].encode(), 1)
    rejected(lambda: checkpoint.parse_now(raw, managed=True))
    rejected(lambda: checkpoint.render_now({**FIELDS, "goal": PLACEHOLDERS[4]}, managed=True))
    rejected(lambda: checkpoint.encode_candidate({**FIELDS, "next": PLACEHOLDERS[2]}))

    placeholder_json = json.dumps(
        {**FIELDS, "done_when": PLACEHOLDERS[7]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    rejected(lambda: checkpoint.decode_candidate(token_for(placeholder_json)))

    angle_brackets_are_normal_text = {**FIELDS, "goal": "Keep <literal> text."}
    assert checkpoint.decode_candidate(
        checkpoint.encode_candidate(angle_brackets_are_normal_text)
    ) == angle_brackets_are_normal_text


def check_size_boundary() -> None:
    baseline = checkpoint.render_now({**FIELDS, "goal": "g"}, managed=True)
    exact = {**FIELDS, "goal": "g" + "x" * (checkpoint.MAX_NOW_BYTES - len(baseline))}
    raw = checkpoint.render_now(exact, managed=True)
    assert len(raw) == checkpoint.MAX_NOW_BYTES
    assert checkpoint.parse_now(raw, managed=True) == exact

    too_large = raw.replace(exact["goal"].encode(), (exact["goal"] + "x").encode(), 1)
    assert len(too_large) == checkpoint.MAX_NOW_BYTES + 1
    rejected(lambda: checkpoint.parse_now(too_large, managed=True))
    rejected(lambda: checkpoint.render_now({**exact, "goal": exact["goal"] + "x"}, managed=True))


def check_candidate_codec() -> None:
    encoded = checkpoint.encode_candidate(FIELDS)
    assert encoded and encoded.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-") == ""
    payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    expected = json.dumps(
        FIELDS, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert payload == expected
    assert checkpoint.decode_candidate(encoded) == FIELDS
    assert checkpoint.encode_candidate(checkpoint.decode_candidate(encoded)) == encoded

    chinese = {**FIELDS, "goal": "交付一个结果", "next": "只做下一步"}
    chinese_token = checkpoint.encode_candidate(chinese)
    assert "交付一个结果".encode() in base64.urlsafe_b64decode(
        chinese_token + "=" * (-len(chinese_token) % 4)
    )
    assert checkpoint.decode_candidate(chinese_token) == chinese

    invalid_payloads = (
        '{"goal":"g","verified_now":"v","next":"n","done_when":"d","extra":"x"}',
        '{"goal":"g","verified_now":"v","next":"n"}',
        '{"goal":"g","goal":"again","verified_now":"v","next":"n","done_when":"d"}',
        '{1:"g","verified_now":"v","next":"n","done_when":"d"}',
        '{"goal":1,"verified_now":"v","next":"n","done_when":"d"}',
        '["g","v","n","d"]',
        '{"verified_now":"v","goal":"g","next":"n","done_when":"d"}',
        '{"goal": "g", "verified_now": "v", "next": "n", "done_when": "d"}',
    )
    for payload_text in invalid_payloads:
        rejected(lambda payload_text=payload_text: checkpoint.decode_candidate(token_for(payload_text)))

    for encoded_bad in ("", encoded + "=", encoded + "%", "A"):
        rejected(lambda encoded_bad=encoded_bad: checkpoint.decode_candidate(encoded_bad))
    rejected(lambda: checkpoint.decode_candidate(token_for(b"\xff")))

    canonical = encoded
    candidate = dict(FIELDS)
    while len(canonical) % 4 == 0:
        candidate["goal"] += "x"
        canonical = checkpoint.encode_candidate(candidate)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    last = alphabet.index(canonical[-1])
    noncanonical = canonical[:-1] + alphabet[last + 1]
    assert base64.urlsafe_b64decode(noncanonical + "=" * (-len(noncanonical) % 4)) == base64.urlsafe_b64decode(
        canonical + "=" * (-len(canonical) % 4)
    )
    rejected(lambda: checkpoint.decode_candidate(noncanonical))

    max_encoded = (checkpoint.MAX_NOW_BYTES * 4 + 2) // 3
    rejected(lambda: checkpoint.decode_candidate("A" * (max_encoded + 1)))

    payload_boundary = {
        "goal": "g",
        "verified_now": "v",
        "next": "n",
        "done_when": "d",
    }
    baseline_payload = json.dumps(
        payload_boundary, ensure_ascii=False, separators=(",", ":")
    ).encode()
    payload_boundary["goal"] += "x" * (checkpoint.MAX_NOW_BYTES - len(baseline_payload))
    boundary_token = checkpoint.encode_candidate(payload_boundary)
    boundary_bytes = base64.urlsafe_b64decode(
        boundary_token + "=" * (-len(boundary_token) % 4)
    )
    assert len(boundary_bytes) == checkpoint.MAX_NOW_BYTES
    assert checkpoint.decode_candidate(boundary_token) == payload_boundary
    rejected(
        lambda: checkpoint.encode_candidate(
            {**payload_boundary, "goal": payload_boundary["goal"] + "x"}
        )
    )


def check_enrollment_contract() -> None:
    helper = Path("/opt/Daqi Install/skills/daqi/scripts/checkpoint.py")
    adapter = Path("/opt/Daqi Install/skills/daqi/scripts/bootup-hook.sh")
    guard = Path("/opt/Daqi Install/skills/daqi/scripts/permission_guard.py")
    root = Path("/tmp/project with spaces")
    prefix = shlex.join([str(helper), "update", "--root", str(root)])
    expected = checkpoint.enrollment_entries(helper, adapter, guard, root)

    assert checkpoint.canonical_update_prefix(helper, root) == prefix
    assert expected == {
        "permissions": {"allow": [f"Bash({prefix} *)"]},
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": str(adapter),
                            "args": ["--root", str(root)],
                        }
                    ]
                }
            ],
            "PermissionRequest": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "if": f"Bash({shlex.join([str(helper)])} *)",
                            "command": str(guard),
                            "args": [
                                "--helper",
                                str(helper),
                                "--root",
                                str(root),
                            ],
                        }
                    ],
                }
            ],
        },
    }
    staged = checkpoint.staged_entries(helper, guard, root)
    assert staged == {
        "permissions": expected["permissions"],
        "hooks": {"PermissionRequest": expected["hooks"]["PermissionRequest"]},
    }
    assert "SessionStart" not in staged["hooks"]

    assert checkpoint.classify_enrollment({}, expected) == "UNENROLLED"
    assert checkpoint.classify_enrollment({"theme": "dark"}, expected) == "UNENROLLED"
    settings = copy.deepcopy(expected)
    settings["theme"] = "dark"
    settings["permissions"]["deny"] = ["Read(.env)"]
    settings["hooks"]["Stop"] = [{"hooks": []}]
    assert checkpoint.classify_enrollment(settings, expected) == "ENROLLED_READY"
    assert checkpoint.classify_enrollment(staged, expected) == "ENROLLED_EXCEPTION"

    partials = []
    for section, key in (
        ("permissions", "allow"),
        ("hooks", "SessionStart"),
        ("hooks", "PermissionRequest"),
    ):
        partial = copy.deepcopy(expected)
        del partial[section][key]
        partials.append(partial)
    for partial in partials:
        assert checkpoint.classify_enrollment(partial, expected) == "ENROLLED_EXCEPTION"

    duplicate_allow = copy.deepcopy(expected)
    duplicate_allow["permissions"]["allow"].append(
        duplicate_allow["permissions"]["allow"][0]
    )
    duplicate_hook = copy.deepcopy(expected)
    duplicate_hook["hooks"]["SessionStart"].append(
        copy.deepcopy(duplicate_hook["hooks"]["SessionStart"][0])
    )
    duplicate_guard = copy.deepcopy(expected)
    duplicate_guard["hooks"]["PermissionRequest"].append(
        copy.deepcopy(duplicate_guard["hooks"]["PermissionRequest"][0])
    )
    assert checkpoint.classify_enrollment(duplicate_allow, expected) == "ENROLLED_EXCEPTION"
    assert checkpoint.classify_enrollment(duplicate_hook, expected) == "ENROLLED_EXCEPTION"
    assert checkpoint.classify_enrollment(duplicate_guard, expected) == "ENROLLED_EXCEPTION"

    expected_guard = expected["hooks"]["PermissionRequest"][0]
    for matcher in (None, "WrongMatcher"):
        stale_guard = copy.deepcopy(expected_guard)
        if matcher is None:
            del stale_guard["matcher"]
        else:
            stale_guard["matcher"] = matcher
        with_stale = copy.deepcopy(expected)
        with_stale["hooks"]["PermissionRequest"].append(stale_guard)
        assert (
            checkpoint.classify_enrollment(with_stale, expected)
            == "ENROLLED_EXCEPTION"
        )
        if matcher == "WrongMatcher":
            assert (
                checkpoint.classify_enrollment(
                    {"hooks": {"PermissionRequest": [stale_guard]}}, expected
                )
                == "ENROLLED_EXCEPTION"
            )

    other_root = checkpoint.enrollment_entries(
        helper, adapter, guard, Path("/tmp/other-root")
    )
    other_install = checkpoint.enrollment_entries(
        Path("/old/skills/daqi/scripts/checkpoint.py"),
        Path("/old/skills/daqi/scripts/bootup-hook.sh"),
        Path("/old/skills/daqi/scripts/permission_guard.py"),
        root,
    )
    assert checkpoint.classify_enrollment(other_root, expected) == "ENROLLED_EXCEPTION"
    assert checkpoint.classify_enrollment(other_install, expected) == "ENROLLED_EXCEPTION"

    installed = checkpoint.installed_paths()
    assert installed == (HELPER.resolve(), ADAPTER.resolve(), GUARD.resolve())


def check_root_and_cli_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-checkpoint-") as temp:
        parent = Path(temp)
        root = parent / "project"
        source = root / "src"
        outside = parent / "project-copy"
        root.mkdir()
        source.mkdir()
        outside.mkdir()
        root_alias = parent / "project-alias"
        root_alias.symlink_to(root, target_is_directory=True)

        assert checkpoint.canonical_root(str(root)) == root.resolve()
        assert checkpoint.canonical_root(str(root_alias)) == root.resolve()
        rejected(lambda: checkpoint.canonical_root(""))
        rejected(lambda: checkpoint.canonical_root(str(parent / "missing")))
        file_root = parent / "CANARY_FILE"
        file_root.write_text("not a directory")
        rejected(lambda: checkpoint.canonical_root(str(file_root)))

        event = json.dumps(
            {
                "hook_event_name": "SessionStart",
                "cwd": str(source),
                "source": "startup",
            }
        )
        unavailable_roots = (parent / "CANARY_MISSING", file_root)
        for unavailable_root in unavailable_roots:
            unavailable = run_script(
                HELPER,
                "read",
                "--root",
                str(unavailable_root),
                "--project-root",
                str(unavailable_root),
                stdin=event,
            )
            assert unavailable.returncode == 0, unavailable
            assert unavailable.stdout == ""
            assert unavailable.stderr == "daqi:root_unavailable\n"
            assert str(unavailable_root) not in unavailable.stderr
            assert "CANARY" not in unavailable.stderr

        unenrolled = run_script(
            HELPER,
            "read",
            "--root",
            str(root),
            "--project-root",
            str(root),
            stdin=event,
        )
        assert unenrolled.returncode == 0
        assert unenrolled.stdout == ""

        settings_path = root / ".claude" / "settings.local.json"
        settings_path.parent.mkdir()
        helper, _adapter, guard = checkpoint.installed_paths()
        settings_path.write_text(
            json.dumps(checkpoint.staged_entries(helper, guard, root.resolve()))
        )
        staged = run_script(
            HELPER,
            "read",
            "--root",
            str(root),
            "--project-root",
            str(root),
            stdin=event,
        )
        assert staged.returncode == 0
        assert staged.stdout == ""
        settings_path.unlink()

        for project_root, cwd in ((outside, source), (root, outside)):
            result = run_script(
                HELPER,
                "read",
                "--root",
                str(root),
                "--project-root",
                str(project_root),
                stdin=json.dumps(
                    {
                        "hook_event_name": "SessionStart",
                        "cwd": str(cwd),
                        "source": "resume",
                    }
                ),
            )
            assert result.returncode == 0
            assert result.stdout == ""

        malformed_calls = (
            (),
            ("read",),
            ("read", "--project-root", str(root), "--root", str(root)),
            ("read", "--root", str(root), "--project-root", ""),
            ("read", "--root", str(root), "--project-root", str(root), "extra"),
            ("update", "--root", str(root), "BAD", "abc"),
            ("update", "--root", str(root), "0" * 64, ""),
            ("update", "--root", str(root), "0" * 64, "abc="),
            ("unknown", "--root", str(root)),
        )
        for argv in malformed_calls:
            result = run_script(HELPER, *argv, stdin=event)
            assert result.returncode == 2, (argv, result)

        for bad_stdin in (
            "",
            "not-json",
            "[]",
            json.dumps({"hook_event_name": "Stop", "cwd": str(source)}),
            json.dumps({"hook_event_name": "SessionStart", "cwd": 1}),
        ):
            result = run_script(
                HELPER,
                "read",
                "--root",
                str(root),
                "--project-root",
                str(root),
                stdin=bad_stdin,
            )
            assert result.returncode == 2, (bad_stdin, result)

        unavailable_update = run_script(
            HELPER,
            "update",
            "--root",
            str(root),
            "0" * 64,
            checkpoint.encode_candidate(FIELDS),
        )
        assert unavailable_update.returncode == 2
        assert unavailable_update.stderr == ""
        assert json.loads(unavailable_update.stdout)["status"] == "ERROR"


def check_guard_contract() -> None:
    deny = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "deny",
                "message": (
                    "Daqi checkpoint was not saved because the exact project-local "
                    "allow rule did not apply. NOW.md was not changed."
                ),
                "interrupt": False,
            },
        }
    }
    with tempfile.TemporaryDirectory(prefix="daqi-guard-") as temp:
        root = Path(temp).resolve()
        now = root / "NOW.md"
        settings = root / "settings.local.json"
        now.write_bytes(MANAGED)
        settings.write_text('{"canary":true}\n')

        def fingerprint(path: Path) -> tuple[str, int, int]:
            info = path.stat()
            return hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mtime_ns, info.st_mode

        before = (fingerprint(now), fingerprint(settings))
        helper = HELPER.resolve()
        direct_command = f"{shlex.join([str(helper)])} update --root {shlex.quote(str(root))}"
        direct = run_script(
            GUARD,
            "--helper",
            str(helper),
            "--root",
            str(root),
            stdin=json.dumps(
                {
                    "hook_event_name": "PermissionRequest",
                    "tool_name": "Bash",
                    "tool_input": {"command": direct_command},
                }
            ),
        )
        assert direct.returncode == 0
        assert json.loads(direct.stdout) == deny

        unrelated = run_script(
            GUARD,
            "--helper",
            str(helper),
            "--root",
            str(root),
            stdin=json.dumps(
                {
                    "hook_event_name": "PermissionRequest",
                    "tool_name": "Bash",
                    "tool_input": {"command": "echo unrelated"},
                }
            ),
        )
        assert unrelated.returncode == 0 and unrelated.stdout == ""
        assert before == (fingerprint(now), fingerprint(settings))
        guard_source = GUARD.read_text()
        assert "import checkpoint" not in guard_source
        assert "configure_claude" not in guard_source

        for argv, stdin in (
            (("--root", str(root), "--helper", str(helper)), "{}"),
            (("--helper", str(helper), "--root", str(root), "extra"), "{}"),
            (("--helper", str(helper), "--root", str(root)), "not-json"),
            (
                ("--helper", str(helper), "--root", str(root)),
                json.dumps(
                    {
                        "hook_event_name": "Stop",
                        "tool_name": "Bash",
                        "tool_input": {"command": direct_command},
                    }
                ),
            ),
        ):
            result = run_script(GUARD, *argv, stdin=stdin)
            assert result.returncode == 2, (argv, stdin, result)
        assert before == (fingerprint(now), fingerprint(settings))


def make_ready_project(
    parent: Path,
    *,
    now_raw: bytes = MANAGED,
    root_name: str = "project",
) -> tuple[Path, Path, dict[str, object]]:
    root = parent / root_name
    source = root / "src"
    source.mkdir(parents=True)
    claude_dir = root / ".claude"
    claude_dir.mkdir()
    helper, adapter, guard = checkpoint.installed_paths()
    entries = checkpoint.enrollment_entries(helper, adapter, guard, root.resolve())
    (claude_dir / "settings.local.json").write_text(
        json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    )
    (root / "NOW.md").write_bytes(now_raw)
    return root.resolve(), source.resolve(), entries


def run_read(
    root: Path,
    source: Path,
    *,
    project_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_script(
        HELPER,
        "read",
        "--root",
        str(root),
        "--project-root",
        str(root if project_root is None else project_root),
        stdin=json.dumps(
            {
                "hook_event_name": "SessionStart",
                "cwd": str(source),
                "source": "startup",
            }
        ),
    )


def run_update(
    root: Path,
    baseline: str,
    candidate: dict[str, str] | str,
) -> subprocess.CompletedProcess[str]:
    token = (
        checkpoint.encode_candidate(candidate)
        if isinstance(candidate, dict)
        else candidate
    )
    return run_script(
        HELPER,
        "update",
        "--root",
        str(root),
        baseline,
        token,
    )


def baseline_from_context(context: str) -> str:
    match = re.search(r"(?m)^baseline=([0-9a-f]{64})$", context)
    assert match is not None, context
    return match.group(1)


def check_update_noop_and_delta() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-update-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        baseline = baseline_from_context(
            json.loads(run_read(root, source).stdout)["hookSpecificOutput"][
                "additionalContext"
            ]
        )
        before = (now.read_bytes(), now.stat().st_mtime_ns, stat.S_IMODE(now.stat().st_mode))

        noop = run_update(root, baseline, FIELDS)
        assert noop.returncode == 0, noop
        assert noop.stderr == ""
        assert json.loads(noop.stdout) == {"status": "NOOP", "baseline": baseline}
        assert (now.read_bytes(), now.stat().st_mtime_ns, stat.S_IMODE(now.stat().st_mode)) == before

        candidate = {**FIELDS, "next": "Verify one atomic checkpoint update."}
        updated = run_update(root, baseline, candidate)
        assert updated.returncode == 0, updated
        assert updated.stderr == ""
        result = json.loads(updated.stdout)
        assert set(result) == {"status", "baseline"}
        assert result["status"] == "UPDATED"
        assert re.fullmatch(r"[0-9a-f]{64}", result["baseline"])
        assert now.read_bytes() == checkpoint.render_now(candidate, managed=True)
        assert stat.S_IMODE(now.stat().st_mode) == before[2]


def update_result(result: subprocess.CompletedProcess[str]) -> dict[str, str]:
    assert result.stderr == "", result.stderr
    assert result.stdout.count("\n") == 1, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def epoch_baseline(root: Path, source: Path) -> str:
    result = run_read(root, source)
    assert result.returncode == 0 and result.stdout, result
    return baseline_from_context(
        json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    )


def assert_conflict(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 3, result
    assert update_result(result) == {
        "status": "CONFLICT",
        "reason": "NOW or local authorization changed after read",
    }


def check_update_cas_and_priority() -> None:
    candidate = {**FIELDS, "next": "A different canonical next step."}

    for mutation in ("raw", "mode", "marker", "allow", "session", "guard"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-cas-{mutation}-") as temp:
            root, source, _entries = make_ready_project(Path(temp))
            baseline = epoch_baseline(root, source)
            now = root / "NOW.md"
            settings_path = root / ".claude" / "settings.local.json"
            if mutation == "raw":
                now.write_bytes(checkpoint.render_now({**FIELDS, "goal": "External canonical state."}, managed=True))
            elif mutation == "mode":
                now.chmod(stat.S_IMODE(now.stat().st_mode) ^ stat.S_IXUSR)
            elif mutation == "marker":
                now.write_bytes(MANAGED.replace(b"daqi: 1", b"daqi: 2", 1))
            else:
                settings = json.loads(settings_path.read_text())
                section, key = {
                    "allow": ("permissions", "allow"),
                    "session": ("hooks", "SessionStart"),
                    "guard": ("hooks", "PermissionRequest"),
                }[mutation]
                if mutation == "allow":
                    settings[section][key][0] += " "
                else:
                    settings[section][key][0]["external"] = True
                settings_path.write_text(json.dumps(settings, separators=(",", ":")))
            external = now.read_bytes()
            assert_conflict(run_update(root, baseline, "%"))
            assert now.read_bytes() == external

    with tempfile.TemporaryDirectory(prefix="daqi-priority-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        baseline = epoch_baseline(root, source)
        now = root / "NOW.md"
        now.write_bytes(checkpoint.render_now({**FIELDS, "goal": "New external epoch."}, managed=True))
        assert_conflict(run_update(root, baseline, "%"))
        current = epoch_baseline(root, source)
        for malformed in ("%", token_for("not-json"), token_for(b"\xff"), "A"):
            before = now.read_bytes()
            result = run_update(root, current, malformed)
            assert result.returncode == 2, result
            assert update_result(result)["status"] == "ERROR"
            assert now.read_bytes() == before

    with tempfile.TemporaryDirectory(prefix="daqi-git-cas-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        initialized = subprocess.run(
            ("git", "init", "-q", str(root)), capture_output=True, text=True, check=False
        )
        assert initialized.returncode == 0, initialized
        baseline = epoch_baseline(root, source)
        tracked = subprocess.run(
            ("git", "-C", str(root), "add", "-f", ".claude/settings.local.json"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert tracked.returncode == 0, tracked
        assert_conflict(run_update(root, baseline, "%"))

    if sys.platform == "darwin":
        for metadata in ("gid", "flags"):
            with tempfile.TemporaryDirectory(prefix=f"daqi-{metadata}-baseline-") as temp:
                root, source, _entries = make_ready_project(Path(temp))
                now = root / "NOW.md"
                baseline = epoch_baseline(root, source)
                if metadata == "gid":
                    os.chown(now, -1, 12)
                else:
                    os.chflags(now, stat.UF_HIDDEN, follow_symlinks=False)
                assert_conflict(run_update(root, baseline, "%"))
                info = os.lstat(now)
                assert info.st_gid == (12 if metadata == "gid" else os.getgid())
                assert info.st_flags == (
                    stat.UF_HIDDEN if metadata == "flags" else 0
                )
                if info.st_flags:
                    os.chflags(now, 0, follow_symlinks=False)


def check_update_baseline_chain_and_store_scope() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-chain-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        stores = {}
        for name in ("SHELF.md", "HANDOFF.md", "SELF.md", "POOL.md"):
            path = root / name
            path.write_text(f"{name} sentinel\n")
            stores[name] = (path.read_bytes(), path.stat().st_mtime_ns)

        baseline_0 = epoch_baseline(root, source)
        noop = run_update(root, baseline_0, FIELDS)
        assert update_result(noop) == {"status": "NOOP", "baseline": baseline_0}

        candidate_1 = {**FIELDS, "next": "Commit epoch one."}
        first = run_update(root, update_result(noop)["baseline"], candidate_1)
        first_payload = update_result(first)
        assert first.returncode == 0 and first_payload["status"] == "UPDATED"
        baseline_1 = first_payload["baseline"]
        assert baseline_1 != baseline_0

        candidate_2 = {**candidate_1, "done_when": "Epoch two is durable."}
        second = run_update(root, baseline_1, candidate_2)
        second_payload = update_result(second)
        assert second.returncode == 0 and second_payload["status"] == "UPDATED"
        baseline_2 = second_payload["baseline"]
        assert baseline_2 not in (baseline_0, baseline_1)
        assert_conflict(run_update(root, baseline_0, candidate_2))
        assert (root / "NOW.md").read_bytes() == checkpoint.render_now(candidate_2, managed=True)

        for name, fingerprint in stores.items():
            path = root / name
            assert (path.read_bytes(), path.stat().st_mtime_ns) == fingerprint


def check_staged_update_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-stage-") as temp:
        root, source, finalized = make_ready_project(Path(temp))
        helper, _adapter, guard = checkpoint.installed_paths()
        staged = checkpoint.staged_entries(helper, guard, root)
        staged["unrelated"] = {"theme": "dark"}
        settings_path = root / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps(staged, separators=(",", ":")))
        assert run_read(root, source).stdout == ""

        now = root / "NOW.md"
        before = (now.read_bytes(), now.stat().st_mtime_ns, stat.S_IMODE(now.stat().st_mode))
        baseline = checkpoint.stage_baseline_token(
            root,
            finalized,
            before[2],
            before[0],
            metadata=checkpoint.replaceable_metadata(now),
        )
        noop = run_update(root, baseline, FIELDS)
        payload = update_result(noop)
        assert noop.returncode == 0
        assert payload == {
            "status": "NOOP",
            "baseline": baseline,
            "probe_token": checkpoint.stage_probe_token(
                baseline, checkpoint.encode_candidate(FIELDS)
            ),
        }
        assert re.fullmatch(r"[0-9a-f]{64}", payload["probe_token"])
        assert (now.read_bytes(), now.stat().st_mtime_ns, stat.S_IMODE(now.stat().st_mode)) == before

        delta = run_update(root, baseline, {**FIELDS, "next": "Never stage this delta."})
        assert delta.returncode == 2
        assert update_result(delta)["status"] == "ERROR"
        assert (now.read_bytes(), now.stat().st_mtime_ns, stat.S_IMODE(now.stat().st_mode)) == before

        stale = run_update(root, "0" * 64, "%")
        assert_conflict(stale)

        normal = checkpoint.baseline_token(root, finalized, before[2], before[0])
        assert normal != baseline
        assert checkpoint.stage_probe_token(
            baseline, checkpoint.encode_candidate(FIELDS)
        ) != checkpoint.stage_probe_token(
            baseline, checkpoint.encode_candidate({**FIELDS, "goal": "Other goal."})
        )
        for public in ("stage_baseline_token", "stage_probe_token"):
            assert public in checkpoint.__all__

        unrelated_session = {"hooks": [{"type": "command", "command": "/bin/echo"}]}
        staged["hooks"]["SessionStart"] = [unrelated_session]
        settings_path.write_text(json.dumps(staged, separators=(",", ":")))
        allowed = run_update(root, baseline, FIELDS)
        assert allowed.returncode == 0 and update_result(allowed)["status"] == "NOOP"

        staged["hooks"]["SessionStart"].append(
            finalized["hooks"]["SessionStart"][0]
        )
        settings_path.write_text(json.dumps(staged, separators=(",", ":")))
        assert_conflict(run_update(root, baseline, "%"))


def call_update_in_process(
    root: Path, baseline: str, candidate: dict[str, str]
) -> tuple[int, dict[str, str]]:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = checkpoint._update_cli(
            str(root), baseline, checkpoint.encode_candidate(candidate)
        )
    assert stdout.getvalue().count("\n") == 1
    return code, json.loads(stdout.getvalue())


def check_root_lock_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-lock-") as temp:
        root = Path(temp) / "project"
        root.mkdir()
        alias = Path(temp) / "alias"
        alias.symlink_to(root, target_is_directory=True)
        expected = (
            Path(tempfile.gettempdir())
            / "daqi-now-locks"
            / f"{hashlib.sha256(str(root.resolve()).encode()).hexdigest()}.lock"
        )

        with checkpoint.root_lock(root):
            assert expected.is_file()
            assert expected.read_bytes() == b""
        first = expected.stat()
        with checkpoint.root_lock(alias):
            assert expected.stat().st_ino == first.st_ino

        directory = expected.parent.stat()
        lock = expected.stat()
        assert stat.S_IMODE(directory.st_mode) == 0o700
        assert stat.S_IMODE(lock.st_mode) == 0o600
        assert directory.st_uid == os.getuid() == lock.st_uid
        assert "root_lock" in checkpoint.__all__


def check_update_atomicity_and_concurrency() -> None:
    candidate_a = {**FIELDS, "next": "Concurrent candidate A."}
    candidate_b = {**FIELDS, "next": "Concurrent candidate B."}
    with tempfile.TemporaryDirectory(prefix="daqi-concurrent-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        baseline = epoch_baseline(root, source)
        commands = [
            (
                str(HELPER),
                "update",
                "--root",
                str(root),
                baseline,
                checkpoint.encode_candidate(candidate),
            )
            for candidate in (candidate_a, candidate_b)
        ]
        processes = [
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for command in commands
        ]
        completed = [process.communicate(timeout=10) for process in processes]
        codes = [process.returncode for process in processes]
        payloads = [json.loads(stdout) for stdout, stderr in completed if not stderr]
        assert sorted(codes) == [0, 3], (codes, completed)
        assert {payload["status"] for payload in payloads} == {"UPDATED", "CONFLICT"}
        assert checkpoint.parse_now((root / "NOW.md").read_bytes(), managed=True) in (
            candidate_a,
            candidate_b,
        )

    with tempfile.TemporaryDirectory(prefix="daqi-external-race-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        baseline = epoch_baseline(root, source)
        candidate = {**FIELDS, "next": "Do not overwrite an external race."}
        external = checkpoint.render_now(
            {**FIELDS, "goal": "External writer won during candidate decode."},
            managed=True,
        )
        real_decode = checkpoint.decode_candidate

        def mutate_during_decode(encoded: str) -> dict[str, str]:
            now.write_bytes(external)
            return real_decode(encoded)

        with mock.patch(
            "checkpoint.decode_candidate", side_effect=mutate_during_decode
        ):
            code, payload = call_update_in_process(root, baseline, candidate)
        assert code == 3
        assert payload == {
            "status": "CONFLICT",
            "reason": "NOW or local authorization changed after read",
        }
        assert now.read_bytes() == external

    for timing in ("before", "after"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-replace-{timing}-") as temp:
            root, source, _entries = make_ready_project(Path(temp))
            now = root / "NOW.md"
            baseline = epoch_baseline(root, source)
            candidate = {**FIELDS, "next": f"Complete {timing} replace fault."}
            old_raw = now.read_bytes()
            real_replace = os.replace

            def replace_fault(source_path: Path, target_path: Path) -> None:
                if timing == "after":
                    real_replace(source_path, target_path)
                raise OSError("injected replace fault")

            with mock.patch("checkpoint.os.replace", side_effect=replace_fault):
                code, payload = call_update_in_process(root, baseline, candidate)
            assert code == 2 and payload["status"] == "ERROR"
            expected = old_raw if timing == "before" else checkpoint.render_now(candidate, managed=True)
            assert now.read_bytes() == expected
            assert not list(root.glob(".daqi-NOW.*"))

    for fault in ("write", "file_fsync", "directory_fsync", "readback"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-io-{fault}-") as temp:
            root, source, _entries = make_ready_project(Path(temp))
            now = root / "NOW.md"
            baseline = epoch_baseline(root, source)
            candidate = {**FIELDS, "next": f"Complete {fault} fault."}
            old_raw = now.read_bytes()
            if fault == "write":
                patcher = mock.patch("checkpoint.os.write", side_effect=OSError("write fault"))
            elif fault in ("file_fsync", "directory_fsync"):
                real_fsync = os.fsync

                def fsync_fault(descriptor: int) -> None:
                    is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
                    if is_directory == (fault == "directory_fsync"):
                        raise OSError(errno.EIO, "fsync fault")
                    real_fsync(descriptor)

                patcher = mock.patch("checkpoint.os.fsync", side_effect=fsync_fault)
            else:
                real_read_now = checkpoint._read_now
                read_count = 0

                def readback_fault(project_root: Path) -> tuple[bytes, int, int, bytes | None]:
                    nonlocal read_count
                    read_count += 1
                    if read_count == 5:
                        raise ValueError("readback_fault")
                    return real_read_now(project_root)

                patcher = mock.patch("checkpoint._read_now", side_effect=readback_fault)
            with patcher:
                code, payload = call_update_in_process(root, baseline, candidate)
            assert code == 2 and payload["status"] == "ERROR"
            expected = (
                checkpoint.render_now(candidate, managed=True)
                if fault in ("directory_fsync", "readback")
                else old_raw
            )
            assert now.read_bytes() == expected
            assert not list(root.glob(".daqi-NOW.*"))

    for mismatch in ("temp", "final"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-metadata-{mismatch}-") as temp:
            root, source, _entries = make_ready_project(Path(temp))
            now = root / "NOW.md"
            baseline = epoch_baseline(root, source)
            candidate = {**FIELDS, "next": f"Reject {mismatch} metadata mismatch."}
            old_raw = now.read_bytes()
            real_metadata = checkpoint._replaceable_metadata
            def metadata_mismatch(path: Path) -> bytes | None:
                value = real_metadata(path)
                if path.name == "NOW.md":
                    if mismatch == "final" and path.read_bytes() != old_raw:
                        return b"different-final-provenance"
                elif mismatch == "temp":
                    return b"different-temp-provenance"
                return value

            with mock.patch(
                "checkpoint._replaceable_metadata", side_effect=metadata_mismatch
            ):
                code, payload = call_update_in_process(root, baseline, candidate)
            assert code == 2 and payload["status"] == "ERROR"
            expected = (
                checkpoint.render_now(candidate, managed=True)
                if mismatch == "final"
                else old_raw
            )
            assert now.read_bytes() == expected


def check_post_decode_revalidation() -> None:
    def run_race(
        root: Path,
        baseline: str,
        candidate: dict[str, str],
        mutate: Callable[[], None],
    ) -> tuple[int, dict[str, str]]:
        real_decode = checkpoint.decode_candidate
        mutated = False

        def mutate_once(encoded: str) -> dict[str, str]:
            nonlocal mutated
            if not mutated:
                mutate()
                mutated = True
            return real_decode(encoded)

        with mock.patch("checkpoint.decode_candidate", side_effect=mutate_once):
            return call_update_in_process(root, baseline, candidate)

    expected_conflict = {
        "status": "CONFLICT",
        "reason": "NOW or local authorization changed after read",
    }

    with tempfile.TemporaryDirectory(prefix="daqi-ready-noop-race-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        external = checkpoint.render_now(
            {**FIELDS, "goal": "External ready NOOP state."}, managed=True
        )
        code, payload = run_race(
            root,
            epoch_baseline(root, source),
            FIELDS,
            lambda: now.write_bytes(external),
        )
        assert code == 3 and payload == expected_conflict
        assert now.read_bytes() == external

    with tempfile.TemporaryDirectory(prefix="daqi-stage-noop-race-") as temp:
        root, _source, finalized = make_ready_project(Path(temp))
        helper, _adapter, guard = checkpoint.installed_paths()
        settings = checkpoint.staged_entries(helper, guard, root)
        (root / ".claude" / "settings.local.json").write_text(
            json.dumps(settings, separators=(",", ":"))
        )
        now = root / "NOW.md"
        mode = stat.S_IMODE(now.stat().st_mode)
        baseline = checkpoint.stage_baseline_token(
            root,
            finalized,
            mode,
            MANAGED,
            metadata=checkpoint.replaceable_metadata(now),
        )
        external = checkpoint.render_now(
            {**FIELDS, "goal": "External staged NOOP state."}, managed=True
        )
        code, payload = run_race(
            root, baseline, FIELDS, lambda: now.write_bytes(external)
        )
        assert code == 3 and payload == expected_conflict
        assert now.read_bytes() == external

    with tempfile.TemporaryDirectory(prefix="daqi-auth-race-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        settings_path = root / ".claude" / "settings.local.json"
        external_settings = json.loads(settings_path.read_text())
        external_settings["permissions"]["allow"][0] += " "
        external_raw = json.dumps(external_settings, separators=(",", ":"))
        code, payload = run_race(
            root,
            epoch_baseline(root, source),
            {**FIELDS, "next": "Never write after authorization changes."},
            lambda: settings_path.write_text(external_raw),
        )
        assert code == 3 and payload == expected_conflict
        assert settings_path.read_text() == external_raw
        assert now.read_bytes() == MANAGED

    with tempfile.TemporaryDirectory(prefix="daqi-git-race-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        initialized = subprocess.run(
            ("git", "init", "-q", str(root)), capture_output=True, text=True, check=False
        )
        assert initialized.returncode == 0, initialized
        baseline = epoch_baseline(root, source)
        git_result: subprocess.CompletedProcess[str] | None = None

        def track_settings() -> None:
            nonlocal git_result
            git_result = subprocess.run(
                ("git", "-C", str(root), "add", "-f", ".claude/settings.local.json"),
                capture_output=True,
                text=True,
                check=False,
            )

        code, payload = run_race(
            root,
            baseline,
            {**FIELDS, "next": "Never write after Git eligibility changes."},
            track_settings,
        )
        assert git_result is not None and git_result.returncode == 0, git_result
        assert code == 3 and payload == expected_conflict
        assert (root / "NOW.md").read_bytes() == MANAGED

    if sys.platform == "darwin":
        for metadata in ("gid", "flags"):
            with tempfile.TemporaryDirectory(prefix=f"daqi-{metadata}-cas-") as temp:
                root, source, _entries = make_ready_project(Path(temp))
                now = root / "NOW.md"
                original = os.lstat(now)

                def mutate_metadata() -> None:
                    if metadata == "gid":
                        os.chown(now, -1, 12)
                    else:
                        os.chflags(now, stat.UF_HIDDEN, follow_symlinks=False)

                code, payload = run_race(
                    root,
                    epoch_baseline(root, source),
                    FIELDS,
                    mutate_metadata,
                )
                assert code == 3 and payload == expected_conflict
                info = os.lstat(now)
                assert info.st_gid == (12 if metadata == "gid" else original.st_gid)
                assert info.st_flags == (
                    stat.UF_HIDDEN if metadata == "flags" else 0
                )
                if info.st_flags:
                    os.chflags(now, 0, follow_symlinks=False)

    for mutation in ("authorization", "git"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-pre-replace-{mutation}-") as temp:
            root, source, _entries = make_ready_project(Path(temp))
            now = root / "NOW.md"
            settings_path = root / ".claude" / "settings.local.json"
            external_settings = settings_path.read_text()
            if mutation == "git":
                initialized = subprocess.run(
                    ("git", "init", "-q", str(root)),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert initialized.returncode == 0, initialized
            else:
                settings = json.loads(external_settings)
                settings["hooks"]["PermissionRequest"][0]["external"] = True
                external_settings = json.dumps(settings, separators=(",", ":"))

            baseline = epoch_baseline(root, source)
            real_fsync = os.fsync
            mutated = False
            git_result: subprocess.CompletedProcess[str] | None = None

            def mutate_after_temp_fsync(descriptor: int) -> None:
                nonlocal mutated, git_result
                real_fsync(descriptor)
                if mutated or not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    return
                mutated = True
                if mutation == "git":
                    git_result = subprocess.run(
                        ("git", "-C", str(root), "add", "-f", ".claude/settings.local.json"),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                else:
                    settings_path.write_text(external_settings)

            with mock.patch(
                "checkpoint.os.fsync", side_effect=mutate_after_temp_fsync
            ):
                code, payload = call_update_in_process(
                    root,
                    baseline,
                    {**FIELDS, "next": f"Do not write after {mutation} changes."},
                )
            assert mutated
            if mutation == "git":
                assert git_result is not None and git_result.returncode == 0, git_result
            else:
                assert settings_path.read_text() == external_settings
            assert code == 3 and payload == expected_conflict
            assert now.read_bytes() == MANAGED
            assert not list(root.glob(".daqi-NOW.*"))


def check_update_file_and_metadata_safety() -> None:
    candidate = {**FIELDS, "next": "Never leave a partial checkpoint."}

    for kind in ("symlink", "fifo", "directory"):
        with tempfile.TemporaryDirectory(prefix=f"daqi-update-{kind}-") as temp:
            parent = Path(temp)
            root, source, _entries = make_ready_project(parent)
            baseline = epoch_baseline(root, source)
            now = root / "NOW.md"
            now.unlink()
            target = parent / "outside"
            if kind == "symlink":
                target.write_bytes(MANAGED)
                now.symlink_to(target)
            elif kind == "fifo":
                os.mkfifo(now)
            else:
                now.mkdir()
            result = run_update(root, baseline, candidate)
            assert result.returncode == 2, result
            assert update_result(result)["status"] == "ERROR"
            if kind == "symlink":
                assert target.read_bytes() == MANAGED

    with tempfile.TemporaryDirectory(prefix="daqi-read-only-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        now.chmod(0o400)
        baseline = epoch_baseline(root, source)
        result = run_update(root, baseline, candidate)
        assert result.returncode == 2
        assert update_result(result)["status"] == "ERROR"
        assert now.read_bytes() == MANAGED
        now.chmod(0o600)

    with tempfile.TemporaryDirectory(prefix="daqi-hard-link-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        now = root / "NOW.md"
        baseline = epoch_baseline(root, source)
        alias = root / "NOW.alias"
        os.link(now, alias)
        before = (now.read_bytes(), alias.read_bytes())
        assert run_read(root, source).stdout == ""
        result = run_update(root, baseline, candidate)
        assert result.returncode == 2
        assert update_result(result)["status"] == "ERROR"
        assert (now.read_bytes(), alias.read_bytes()) == before

    if sys.platform == "darwin":
        for metadata in ("gid", "flags"):
            with tempfile.TemporaryDirectory(prefix=f"daqi-preserve-{metadata}-") as temp:
                root, source, _entries = make_ready_project(Path(temp))
                now = root / "NOW.md"
                now.chmod(0o640)
                if metadata == "gid":
                    os.chown(now, -1, 12)
                else:
                    os.chflags(now, stat.UF_HIDDEN, follow_symlinks=False)
                before = os.lstat(now)
                baseline = epoch_baseline(root, source)
                result = run_update(root, baseline, candidate)
                assert result.returncode == 0, result
                assert update_result(result)["status"] == "UPDATED"
                after = os.lstat(now)
                assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
                assert after.st_gid == before.st_gid
                assert after.st_flags == before.st_flags
                if after.st_flags:
                    os.chflags(now, 0, follow_symlinks=False)

        with tempfile.TemporaryDirectory(prefix="daqi-immutable-") as temp:
            root, source, finalized = make_ready_project(Path(temp))
            now = root / "NOW.md"
            mode = stat.S_IMODE(now.stat().st_mode)
            clean_metadata = checkpoint.replaceable_metadata(now)
            os.chflags(now, stat.UF_IMMUTABLE, follow_symlinks=False)
            immutable_metadata = (
                clean_metadata[0],
                stat.UF_IMMUTABLE,
                clean_metadata[2],
            )
            before = (
                now.read_bytes(),
                now.stat().st_mtime_ns,
                mode,
                os.lstat(now).st_gid,
                os.lstat(now).st_flags,
            )
            try:
                try:
                    checkpoint.validate_replaceable_metadata(now)
                except ValueError as error:
                    assert str(error) == "unsupported_file_flags"
                else:
                    raise AssertionError("immutable NOW metadata was accepted")

                read = run_read(root, source)
                assert read.returncode == 0 and read.stdout == ""
                assert read.stderr == "daqi:now_invalid\n"

                ready_baseline = checkpoint.baseline_token(
                    root,
                    finalized,
                    mode,
                    MANAGED,
                    metadata=immutable_metadata,
                )
                ready_noop = run_update(root, ready_baseline, FIELDS)
                assert ready_noop.returncode == 2
                assert update_result(ready_noop) == {
                    "status": "ERROR",
                    "reason": "unsupported_file_flags",
                }

                helper, _adapter, guard = checkpoint.installed_paths()
                staged = checkpoint.staged_entries(helper, guard, root)
                (root / ".claude" / "settings.local.json").write_text(
                    json.dumps(staged, separators=(",", ":"))
                )
                stage_baseline = checkpoint.stage_baseline_token(
                    root,
                    finalized,
                    mode,
                    MANAGED,
                    metadata=immutable_metadata,
                )
                staged_noop = run_update(root, stage_baseline, FIELDS)
                assert staged_noop.returncode == 2
                assert update_result(staged_noop) == {
                    "status": "ERROR",
                    "reason": "unsupported_file_flags",
                }
                assert (
                    now.read_bytes(),
                    now.stat().st_mtime_ns,
                    stat.S_IMODE(now.stat().st_mode),
                    os.lstat(now).st_gid,
                    os.lstat(now).st_flags,
                ) == before
            finally:
                os.chflags(now, 0, follow_symlinks=False)

        for metadata in ("xattr", "acl"):
            with tempfile.TemporaryDirectory(prefix=f"daqi-{metadata}-") as temp:
                root, source, _entries = make_ready_project(Path(temp))
                now = root / "NOW.md"
                baseline = epoch_baseline(root, source)
                if metadata == "xattr":
                    command = ("/usr/bin/xattr", "-w", "com.daqi.test", "value", str(now))
                else:
                    command = ("/bin/chmod", "+a", f"{Path.home().owner()} allow read", str(now))
                injected = subprocess.run(command, capture_output=True, text=True, check=False)
                assert injected.returncode == 0, injected
                before = now.read_bytes()
                assert run_read(root, source).stdout == ""
                result = run_update(root, baseline, candidate)
                assert result.returncode == 2
                assert update_result(result)["status"] == "ERROR"
                assert now.read_bytes() == before

        with tempfile.TemporaryDirectory(prefix="daqi-metadata-tool-") as temp:
            root, _source, _entries = make_ready_project(Path(temp))
            real_run = subprocess.run

            def fail_acl(command: tuple[str, ...], *args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
                if command[0] == "/bin/ls":
                    raise OSError("injected ACL tool failure")
                return real_run(command, *args, **kwargs)

            with mock.patch("checkpoint.subprocess.run", side_effect=fail_acl):
                rejected(lambda: checkpoint.validate_replaceable_metadata(root / "NOW.md"))

    with tempfile.TemporaryDirectory(prefix="daqi-clean-temp-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        provenance_before = None
        if sys.platform == "darwin":
            provenance_before = subprocess.run(
                ("/usr/bin/xattr", "-px", "com.apple.provenance", str(root / "NOW.md")),
                capture_output=True,
                check=False,
            )
            assert provenance_before.returncode == 0 and not provenance_before.stderr
        baseline = epoch_baseline(root, source)
        result = run_update(root, baseline, candidate)
        assert result.returncode == 0 and update_result(result)["status"] == "UPDATED"
        checkpoint.validate_replaceable_metadata(root / "NOW.md")
        if sys.platform == "darwin":
            provenance_after = subprocess.run(
                ("/usr/bin/xattr", "-px", "com.apple.provenance", str(root / "NOW.md")),
                capture_output=True,
                check=False,
            )
            assert provenance_after.returncode == 0 and not provenance_after.stderr
            assert provenance_after.stdout == provenance_before.stdout


def assert_silent_read(root: Path, source: Path, canary: str = "CANARY_SECRET") -> None:
    result = run_read(root, source)
    assert result.returncode == 0, result
    assert result.stdout == "", result.stdout
    assert canary not in result.stderr


def check_ready_read_and_context() -> None:
    html_fields = {
        **FIELDS,
        "goal": "CANARY<&> exact-root state.",
        "verified_now": "Verified & bounded <data> only.",
    }
    now_raw = checkpoint.render_now(html_fields, managed=True)
    with tempfile.TemporaryDirectory(prefix="daqi-ready-") as temp:
        root, source, entries = make_ready_project(
            Path(temp), now_raw=now_raw, root_name="中文 project & 'ready space'"
        )
        result = run_read(root, source)
        assert result.returncode == 0, result
        assert result.stderr == "", result.stderr
        assert result.stdout and len(result.stdout.encode("utf-8")) <= 9500
        payload = json.loads(result.stdout)
        assert set(payload) == {"suppressOutput", "hookSpecificOutput"}
        assert payload["suppressOutput"] is True
        hook = payload["hookSpecificOutput"]
        assert set(hook) == {"hookEventName", "additionalContext"}
        assert hook["hookEventName"] == "SessionStart"
        context = hook["additionalContext"]

        assert checkpoint.MAX_HOOK_OUTPUT_BYTES == 9500
        assert "<daqi-state>" in context and "</daqi-state>" in context
        for key, value in html_fields.items():
            assert f"<{key}>{html.escape(value)}</{key}>" in context
        assert "CANARY<&>" not in context
        assert f"root={root}" in context
        assert f"root={html.escape(str(root))}" not in context
        helper, _adapter, _guard = checkpoint.installed_paths()
        prefix = checkpoint.canonical_update_prefix(helper, root)
        assert f"update_prefix={prefix}" in context
        assert f"update_prefix={html.escape(prefix)}" not in context
        baseline = baseline_from_context(context)
        assert baseline == checkpoint.baseline_token(
            root,
            entries,
            stat.S_IMODE((root / "NOW.md").stat().st_mode),
            now_raw,
            metadata=checkpoint.replaceable_metadata(root / "NOW.md"),
        )

        decisions = {"NO_DELTA", "PROPOSE_UPDATE", "NEEDS_DECISION"}
        outcomes = {"UPDATED", "NOOP", "CONFLICT", "ERROR", "NOT_DISPATCHED"}
        for word in decisions | outcomes:
            assert word in context
        assert "exactly one direct update command" in context
        assert "main session" in context and "subagents return evidence only" in context
        assert "NO_DELTA: zero helper calls" in context
        assert "NEEDS_DECISION: zero writes" in context
        assert "returned baseline" in context
        assert "do not rotate baseline and do not retry" in context
        for obsolete in ("SKIP", "OFFER", "WRITE", "CLARIFY"):
            assert obsolete not in context
        for forbidden in (
            "SELF.md",
            "SHELF.md",
            "POOL.md",
            "HANDOFF.md",
            "history",
            "status receipt",
        ):
            assert forbidden not in context

        settings_path = root / ".claude" / "settings.local.json"
        settings = json.loads(settings_path.read_text())
        settings["unrelated"] = {"theme": "dark"}
        settings_path.write_text(json.dumps(settings, separators=(",", ":")))
        os.utime(root / "NOW.md", None)
        second = run_read(root, source)
        assert second.returncode == 0 and second.stdout
        assert baseline_from_context(
            json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"]
        ) == baseline


def check_installed_trust() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-trust-") as temp:
        parent = Path(temp)
        root = parent / "project"
        root.mkdir()
        install = parent / "project-copy" / "skills" / "daqi" / "scripts"
        install.mkdir(parents=True)
        paths = tuple(install / name for name in ("checkpoint.py", "bootup-hook.sh", "permission_guard.py"))
        for path in paths:
            path.write_text("#!/bin/sh\n")
            path.chmod(0o755)
        assert checkpoint._trusted_installed_paths(root.resolve(), paths) == tuple(
            path.resolve() for path in paths
        )
        assert checkpoint._context_safe_path(Path("/tmp/space ' & 中文"))
        assert not checkpoint._context_safe_path(Path("/tmp/control\nCANARY_SECRET"))
        assert not checkpoint._context_safe_path(Path("/tmp/<unsafe>"))

        paths[0].chmod(0o775)
        rejected(lambda: checkpoint._trusted_installed_paths(root.resolve(), paths))
        paths[0].chmod(0o755)
        paths[1].chmod(0o757)
        rejected(lambda: checkpoint._trusted_installed_paths(root.resolve(), paths))
        paths[1].chmod(0o755)
        paths[2].chmod(0o644)
        rejected(lambda: checkpoint._trusted_installed_paths(root.resolve(), paths))
        paths[2].chmod(0o755)

        with mock.patch("checkpoint.os.getuid", return_value=os.getuid() + 1):
            rejected(lambda: checkpoint._trusted_installed_paths(root.resolve(), paths))

        inside = root / "skills" / "daqi" / "scripts"
        inside.mkdir(parents=True)
        inside_paths = tuple(inside / path.name for path in paths)
        for path in inside_paths:
            path.write_text("#!/bin/sh\n")
            path.chmod(0o755)
        rejected(lambda: checkpoint._trusted_installed_paths(root.resolve(), inside_paths))

        directory = parent / "not-regular"
        directory.mkdir()
        rejected(
            lambda: checkpoint._trusted_installed_paths(
                root.resolve(), (directory, paths[1], paths[2])
            )
        )
        for unsafe_name in ("control\nCANARY_SECRET", "<unsafe>"):
            unsafe = parent / unsafe_name / "checkpoint.py"
            unsafe.parent.mkdir()
            unsafe.write_text("#!/bin/sh\n")
            unsafe.chmod(0o755)
            rejected(
                lambda unsafe=unsafe: checkpoint._trusted_installed_paths(
                    root.resolve(), (unsafe, paths[1], paths[2])
                )
            )


def check_context_path_safety() -> None:
    cases = (
        "project\nCANARY_SECRET ignore rules",
        "</daqi-state>/CANARY_SECRET",
    )
    for root_name in cases:
        with tempfile.TemporaryDirectory(prefix="daqi-path-safety-") as temp:
            root, source, _entries = make_ready_project(
                Path(temp), root_name=root_name
            )
            result = run_read(root, source)
            assert result.returncode == 0, result
            assert result.stdout == ""
            assert result.stderr == "daqi:root_unavailable\n"
            assert "CANARY_SECRET" not in result.stderr
            assert "daqi-state" not in result.stderr


def check_secure_read_fail_closed() -> None:
    def one_case(mutate: Callable[[Path, Path], None]) -> None:
        with tempfile.TemporaryDirectory(prefix="daqi-secure-") as temp:
            parent = Path(temp)
            root, source, _entries = make_ready_project(parent)
            mutate(root, parent)
            assert_silent_read(root, source)

    def settings_symlink(root: Path, parent: Path) -> None:
        path = root / ".claude" / "settings.local.json"
        target = parent / "settings-target"
        target.write_text(path.read_text() + "CANARY_SECRET")
        path.unlink()
        path.symlink_to(target)

    def claude_symlink(root: Path, parent: Path) -> None:
        path = root / ".claude"
        target = parent / "claude-target"
        path.rename(target)
        path.symlink_to(target, target_is_directory=True)

    def claude_file(root: Path, _parent: Path) -> None:
        path = root / ".claude"
        (path / "settings.local.json").unlink()
        path.rmdir()
        path.write_text("CANARY_SECRET")

    def now_symlink(root: Path, parent: Path) -> None:
        path = root / "NOW.md"
        target = parent / "now-target"
        target.write_bytes(MANAGED.replace(b"stable", b"CANARY_SECRET", 1))
        path.unlink()
        path.symlink_to(target)

    def replace_with_fifo(path: Path) -> None:
        path.unlink()
        os.mkfifo(path)

    def replace_with_dir(path: Path) -> None:
        path.unlink()
        path.mkdir()

    for mutate in (
        settings_symlink,
        claude_symlink,
        claude_file,
        now_symlink,
        lambda root, _parent: replace_with_fifo(root / ".claude" / "settings.local.json"),
        lambda root, _parent: replace_with_fifo(root / "NOW.md"),
        lambda root, _parent: replace_with_dir(root / ".claude" / "settings.local.json"),
        lambda root, _parent: replace_with_dir(root / "NOW.md"),
        lambda root, _parent: (root / ".claude" / "settings.local.json").write_bytes(
            b"{" + b"x" * checkpoint.MAX_NOW_BYTES + b"}"
        ),
        lambda root, _parent: (root / "NOW.md").write_bytes(
            MANAGED + b"x" * checkpoint.MAX_NOW_BYTES
        ),
        lambda root, _parent: (root / "NOW.md").unlink(),
    ):
        one_case(mutate)

    invalid_settings = (
        b"not-json",
        b"[]",
        b'{"permissions":{},"permissions":{}}',
    )
    for raw in invalid_settings:
        one_case(
            lambda root, _parent, raw=raw: (
                root / ".claude" / "settings.local.json"
            ).write_bytes(raw)
        )

    invalid_now = (
        UNMANAGED,
        MANAGED.replace(b"daqi: 1", b"daqi: 2", 1),
        MANAGED.replace(b"## Goal", b"## Wrong", 1),
        b"\xff",
    )
    for raw in invalid_now:
        one_case(lambda root, _parent, raw=raw: (root / "NOW.md").write_bytes(raw))


def check_git_enrollment_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-git-") as temp:
        root, source, _entries = make_ready_project(Path(temp))
        initialized = subprocess.run(
            ("git", "init", "-q", str(root)), capture_output=True, text=True, check=False
        )
        assert initialized.returncode == 0, initialized
        untracked = run_read(root, source)
        assert untracked.returncode == 0 and untracked.stdout
        added = subprocess.run(
            ("git", "-C", str(root), "add", "-f", ".claude/settings.local.json"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert added.returncode == 0, added
        assert_silent_read(root, source)

    for kind in ("file", "symlink", "invalid-directory"):
        with tempfile.TemporaryDirectory(prefix="daqi-git-kind-") as temp:
            parent = Path(temp)
            root, source, _entries = make_ready_project(parent)
            git_path = root / ".git"
            if kind == "file":
                git_path.write_text("gitdir: elsewhere\n")
            elif kind == "symlink":
                target = parent / "git-target"
                target.mkdir()
                git_path.symlink_to(target, target_is_directory=True)
            else:
                git_path.mkdir()
            assert_silent_read(root, source)


def check_baseline_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="daqi-baseline-") as temp:
        parent = Path(temp)
        root, _source, entries = make_ready_project(parent)
        mode = stat.S_IMODE((root / "NOW.md").stat().st_mode)
        baseline = checkpoint.baseline_token(root, entries, mode, MANAGED)
        assert re.fullmatch(r"[0-9a-f]{64}", baseline)
        metadata = checkpoint.replaceable_metadata(root / "NOW.md")
        metadata_baseline = checkpoint.baseline_token(
            root, entries, mode, MANAGED, metadata=metadata
        )
        assert metadata_baseline != baseline
        assert checkpoint.baseline_token(
            root,
            entries,
            mode,
            MANAGED,
            metadata=(metadata[0] + 1, metadata[1], metadata[2]),
        ) != metadata_baseline
        assert checkpoint.baseline_token(
            root,
            entries,
            mode,
            MANAGED,
            metadata=(metadata[0], metadata[1] ^ 1, metadata[2]),
        ) != metadata_baseline

        other_root = parent / "other-project"
        other_root.mkdir()
        assert checkpoint.baseline_token(other_root, entries, mode, MANAGED) != baseline
        root_alias = parent / "project-alias"
        root_alias.symlink_to(root, target_is_directory=True)
        assert checkpoint.baseline_token(root_alias, entries, mode, MANAGED) == baseline
        assert checkpoint.baseline_token(root, entries, mode ^ stat.S_IWUSR, MANAGED) != baseline
        assert checkpoint.baseline_token(root, entries, mode, MANAGED + b"x") != baseline

        mutations = []
        allow = copy.deepcopy(entries)
        allow["permissions"]["allow"][0] += " "
        mutations.append(allow)
        session = copy.deepcopy(entries)
        session["hooks"]["SessionStart"][0]["hooks"][0]["args"][1] += "-other"
        mutations.append(session)
        guard = copy.deepcopy(entries)
        guard["hooks"]["PermissionRequest"][0]["hooks"][0]["args"][3] += "-other"
        mutations.append(guard)
        for mutated in mutations:
            assert checkpoint.baseline_token(root, mutated, mode, MANAGED) != baseline

        reordered = json.loads(
            json.dumps(entries, ensure_ascii=False, sort_keys=False), object_pairs_hook=dict
        )
        assert checkpoint.baseline_token(root, reordered, mode, MANAGED) == baseline


def check_host_neutral_seams() -> None:
    public = {
        "atomic_replace_regular",
        "read_bounded_regular",
        "read_managed_now",
        "trusted_installed_path",
        "host_baseline_token",
    }
    assert public <= set(checkpoint.__all__)

    with tempfile.TemporaryDirectory(prefix="daqi-host-core-") as temp:
        parent = Path(temp)
        root, _source, _entries = make_ready_project(parent)
        now = root / "NOW.md"

        bounded = checkpoint.read_bounded_regular(now, limit=checkpoint.MAX_NOW_BYTES)
        assert bounded is not None and bounded[0] == MANAGED
        assert checkpoint.read_bounded_regular(
            root / "missing", limit=1, missing_ok=True
        ) is None

        raw, mode, owner, metadata, fields = checkpoint.read_managed_now(root)
        assert raw == MANAGED
        assert mode == stat.S_IMODE(now.stat().st_mode)
        assert owner == os.getuid()
        assert metadata == checkpoint.replaceable_metadata(now)
        assert fields == FIELDS

        assert checkpoint.trusted_installed_path(root, HELPER) == HELPER.resolve()

        authorization = {
            "adapter": str(ADAPTER.resolve()),
            "events": ["SessionStart", "UserPromptSubmit", "Stop"],
        }
        baseline = checkpoint.host_baseline_token(
            "codex-v1",
            root,
            authorization,
            "default",
            mode,
            raw,
            metadata,
        )
        assert re.fullmatch(r"[0-9a-f]{64}", baseline)
        reordered = {
            "events": ["SessionStart", "UserPromptSubmit", "Stop"],
            "adapter": str(ADAPTER.resolve()),
        }
        assert checkpoint.host_baseline_token(
            "codex-v1", root, reordered, "default", mode, raw, metadata
        ) == baseline

        mutations = (
            ("codex-v2", root, authorization, "default", mode, raw, metadata),
            (
                "codex-v1",
                root,
                {**authorization, "adapter": str(HELPER.resolve())},
                "default",
                mode,
                raw,
                metadata,
            ),
            ("codex-v1", root, authorization, "plan", mode, raw, metadata),
            ("codex-v1", root, authorization, "default", mode ^ stat.S_IWUSR, raw, metadata),
            ("codex-v1", root, authorization, "default", mode, raw + b"x", metadata),
            (
                "codex-v1",
                root,
                authorization,
                "default",
                mode,
                raw,
                (metadata[0] + 1, metadata[1], metadata[2]),
            ),
            (
                "codex-v1",
                root,
                authorization,
                "default",
                mode,
                raw,
                (metadata[0], metadata[1] ^ 1, metadata[2]),
            ),
            (
                "codex-v1",
                root,
                authorization,
                "default",
                mode,
                raw,
                (metadata[0], metadata[1], b"different"),
            ),
        )
        for mutated in mutations:
            assert checkpoint.host_baseline_token(*mutated) != baseline

        alias = parent / "root-alias"
        alias.symlink_to(root, target_is_directory=True)
        assert checkpoint.host_baseline_token(
            "codex-v1", alias, authorization, "default", mode, raw, metadata
        ) == baseline


def check_hook_output_budget() -> None:
    base = checkpoint.render_now({**FIELDS, "goal": "g"}, managed=True)
    extra = checkpoint.MAX_NOW_BYTES - len(base)
    pathological = checkpoint.render_now(
        {**FIELDS, "goal": "g" + ("&<>" * ((extra + 2) // 3))[:extra]},
        managed=True,
    )
    assert len(pathological) == checkpoint.MAX_NOW_BYTES
    assert checkpoint.parse_now(pathological, managed=True)
    with tempfile.TemporaryDirectory(prefix="daqi-budget-") as temp:
        root, source, _entries = make_ready_project(Path(temp), now_raw=pathological)
        result = run_read(root, source)
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == "daqi:hook_output_too_large\n"


def check_source_security_contract() -> None:
    source = HELPER.read_text()
    assert "O_NOFOLLOW" in source
    assert "O_NONBLOCK" in source
    assert "os.fstat" in source
    assert "subprocess.run" in source
    assert "shell=True" not in source


def main() -> None:
    check_templates()
    check_schema()
    check_invalid_now()
    check_template_placeholders()
    check_size_boundary()
    check_candidate_codec()
    check_enrollment_contract()
    check_root_and_cli_contract()
    check_guard_contract()
    check_update_noop_and_delta()
    check_update_cas_and_priority()
    check_update_baseline_chain_and_store_scope()
    check_staged_update_contract()
    check_root_lock_contract()
    check_update_atomicity_and_concurrency()
    check_post_decode_revalidation()
    check_update_file_and_metadata_safety()
    check_ready_read_and_context()
    check_installed_trust()
    check_context_path_safety()
    check_secure_read_fail_closed()
    check_git_enrollment_gate()
    check_baseline_contract()
    check_host_neutral_seams()
    check_hook_output_budget()
    check_source_security_contract()
    print("PASS: checkpoint schema, enrollment, NOOP, update, conflict, and atomicity")


if __name__ == "__main__":
    main()
