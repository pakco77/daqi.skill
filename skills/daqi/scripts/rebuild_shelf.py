#!/usr/bin/env python3
"""Build a read-only SHELF candidate from Claude Code and Codex metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class Project:
    cwd: str
    last_active: datetime
    agents: set[str] = field(default_factory=set)


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def metadata_from_jsonl(path: Path) -> tuple[str | None, datetime | None]:
    """Find a session cwd and its latest timestamp without using message content."""
    cwd: str | None = None
    latest: datetime | None = None
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                payload = record.get("payload")
                payload = payload if isinstance(payload, dict) else {}
                found_cwd = record.get("cwd") or payload.get("cwd")
                if cwd is None and isinstance(found_cwd, str) and found_cwd:
                    cwd = found_cwd
                timestamp = parse_time(record.get("timestamp")) or parse_time(
                    payload.get("timestamp")
                )
                if timestamp is not None:
                    latest = timestamp if latest is None else max(latest, timestamp)
        if cwd is not None:
            return cwd, latest or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except (OSError, UnicodeError) as error:
        print(f"warning: cannot read {path}: {error}", file=sys.stderr)
    return None, None


def default_excluded(cwd: str) -> bool:
    normalized = cwd.replace("\\", "/").rstrip("/")
    if normalized in {"", "/", str(Path.home())}:
        return True
    if normalized.startswith(("/tmp/", "/private/tmp/", "/var/tmp/")):
        return True
    return bool(re.search(r"/Documents/Codex/\d{4}-\d{2}-\d{2}/", normalized))


def iter_sessions(root: Path, agent: str) -> Iterable[tuple[str, datetime, str]]:
    if not root.exists():
        print(f"warning: metadata root not found: {root}", file=sys.stderr)
        return
    try:
        files = root.rglob("*.jsonl")
        for path in files:
            cwd, timestamp = metadata_from_jsonl(path)
            if cwd and timestamp:
                yield cwd, timestamp, agent
    except OSError as error:
        print(f"warning: cannot scan {root}: {error}", file=sys.stderr)


def collect(args: argparse.Namespace) -> list[Project]:
    merged: dict[str, Project] = {}
    sources = [
        (Path(args.claude_root).expanduser(), "C"),
        (Path(args.codex_root).expanduser(), "X"),
        (Path(args.codex_archive_root).expanduser(), "X"),
    ]
    extra_exclusions = [re.compile(pattern) for pattern in args.exclude_pattern]

    for root, agent in sources:
        for cwd, timestamp, found_agent in iter_sessions(root, agent):
            if not args.include_temporary and default_excluded(cwd):
                continue
            if any(pattern.search(cwd) for pattern in extra_exclusions):
                continue
            project = merged.get(cwd)
            if project is None:
                project = Project(cwd=cwd, last_active=timestamp)
                merged[cwd] = project
            project.last_active = max(project.last_active, timestamp)
            project.agents.add(found_agent)

    return sorted(merged.values(), key=lambda item: (-item.last_active.timestamp(), item.cwd))


def project_status(project: Project, now: datetime, drift_days: int, sleep_days: int) -> str:
    age_days = max(0.0, (now - project.last_active).total_seconds() / 86400)
    if age_days < drift_days:
        return "active"
    if age_days <= sleep_days:
        return "drifting"
    return "sleeping"


def as_records(projects: list[Project], args: argparse.Namespace) -> list[dict[str, object]]:
    now = parse_time(args.as_of) if args.as_of else datetime.now(timezone.utc)
    assert now is not None
    records = []
    for project in projects:
        records.append(
            {
                "project": Path(project.cwd).name or project.cwd,
                "cwd": project.cwd,
                "last_active": project.last_active.isoformat().replace("+00:00", "Z"),
                "agents": "/".join(sorted(project.agents)),
                "status": project_status(project, now, args.drift_days, args.sleep_days),
            }
        )
    return records


def markdown(records: list[dict[str, object]], language: str) -> str:
    labels = {
        "zh": {
            "title": "# SHELF 候选（确认后再写入）",
            "active": "## 🟢 在推",
            "drifting": "## 🟡 漂了",
            "sleeping": "## 🔴 休眠",
            "header": "| 项目 | 地址 | 最后活跃 | Agent |",
            "empty": "_无_",
        },
        "en": {
            "title": "# SHELF candidate (confirm before writing)",
            "active": "## 🟢 Active",
            "drifting": "## 🟡 Drifting",
            "sleeping": "## 🔴 Sleeping",
            "header": "| Project | Path | Last active | Agent |",
            "empty": "_None_",
        },
    }[language]

    def escape(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    output = [labels["title"], ""]
    for status in ("active", "drifting", "sleeping"):
        output.extend([labels[status], "", labels["header"], "|---|---|---|---|"])
        rows = [record for record in records if record["status"] == status]
        if rows:
            for record in rows:
                output.append(
                    "| {project} | {cwd} | {last_active} | {agents} |".format(
                        **{key: escape(value) for key, value in record.items()}
                    )
                )
        else:
            output.append(f"| {labels['empty']} |  |  |  |")
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Build a read-only daqi SHELF candidate from session metadata."
    )
    result.add_argument("--claude-root", default="~/.claude/projects")
    result.add_argument("--codex-root", default="~/.codex/sessions")
    result.add_argument("--codex-archive-root", default="~/.codex/archived_sessions")
    result.add_argument("--language", choices=("zh", "en"), default="zh")
    result.add_argument("--format", choices=("markdown", "json"), default="markdown")
    result.add_argument("--as-of", help="ISO-8601 clock for deterministic replay")
    result.add_argument("--drift-days", type=int, default=3)
    result.add_argument("--sleep-days", type=int, default=14)
    result.add_argument("--exclude-pattern", action="append", default=[])
    result.add_argument("--include-temporary", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.drift_days < 0 or args.sleep_days < args.drift_days:
        print("error: require 0 <= drift-days <= sleep-days", file=sys.stderr)
        return 2
    if args.as_of and parse_time(args.as_of) is None:
        print("error: --as-of must be ISO-8601", file=sys.stderr)
        return 2
    try:
        records = as_records(collect(args), args)
    except re.error as error:
        print(f"error: invalid --exclude-pattern: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        print(markdown(records, args.language), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
