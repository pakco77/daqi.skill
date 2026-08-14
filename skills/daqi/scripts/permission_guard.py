#!/usr/bin/env python3
"""Deny direct Daqi helper commands when Claude's local allow did not apply."""

from __future__ import annotations

import json
import os
import shlex
import stat
import sys
from pathlib import Path
from typing import Any


DENIAL = {
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


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _real_helper(raw: str) -> Path:
    if not raw or "\x00" in raw:
        raise ValueError("invalid helper")
    supplied = Path(raw)
    if not supplied.is_absolute():
        raise ValueError("invalid helper")
    try:
        helper = supplied.resolve(strict=True)
        info = helper.stat()
    except (OSError, RuntimeError) as error:
        raise ValueError("invalid helper") from error
    if helper != supplied or not stat.S_ISREG(info.st_mode) or not os.access(helper, os.X_OK):
        raise ValueError("invalid helper")
    return helper


def _real_root(raw: str) -> Path:
    if not raw or "\x00" in raw:
        raise ValueError("invalid root")
    supplied = Path(raw)
    if not supplied.is_absolute():
        raise ValueError("invalid root")
    try:
        root = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("invalid root") from error
    if root != supplied or not root.is_dir():
        raise ValueError("invalid root")
    return root


def _event() -> str:
    try:
        event = json.loads(sys.stdin.read(), object_pairs_hook=_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("invalid PermissionRequest event") from error
    if not isinstance(event, dict):
        raise ValueError("invalid PermissionRequest event")
    tool_input = event.get("tool_input")
    if (
        event.get("hook_event_name") != "PermissionRequest"
        or event.get("tool_name") != "Bash"
        or not isinstance(tool_input, dict)
        or not isinstance(tool_input.get("command"), str)
    ):
        raise ValueError("invalid PermissionRequest event")
    return tool_input["command"]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if (
        len(args) != 4
        or args[0] != "--helper"
        or args[2] != "--root"
    ):
        print("invalid_guard_cli", file=sys.stderr)
        return 2
    try:
        helper = _real_helper(args[1])
        _real_root(args[3])
        command = _event()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if command.startswith(shlex.join([str(helper)]) + " "):
        print(json.dumps(DENIAL, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
