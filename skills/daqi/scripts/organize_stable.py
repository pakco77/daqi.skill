#!/usr/bin/env python3
"""One-click stable organization (马厩一键整理).

Resolve a project's real path from SHELF, inventory its root read-only, and
produce a minimal move plan following the project-fold rules:
  - preview mode (default): print the plan + a plan token; no writes
  - apply mode: re-derive the plan, verify the token, then create missing
    skeleton dirs and execute High-confidence moves only
  - every move is logged (原路径 -> 新路径 + confidence) for reversal;
    nothing is ever deleted; Medium/Low items stay in place and are listed
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import datetime
from pathlib import Path

# import sibling parser from the same scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from camp_status import parse_shelf  # noqa: E402

SCHEMA_EN = {
    "00_Context", "10_Source", "20_Docs", "30_Assets", "40_Builds",
    "50_Data", "60_Run-Release", "70_References", "90_History", "99_Delete-Review",
}
SCHEMA_ZH = {
    "00_上下文", "10_源码", "20_文档", "30_素材", "40_构建",
    "50_数据", "60_运行发布", "70_参考", "90_历史", "99_待删除复核",
}
ZH2EN = {
    "00_上下文": "00_Context", "10_源码": "10_Source", "20_文档": "20_Docs",
    "30_素材": "30_Assets", "40_构建": "40_Builds", "50_数据": "50_Data",
    "60_运行发布": "60_Run-Release", "70_参考": "70_References",
    "90_历史": "90_History", "99_待删除复核": "99_Delete-Review",
}
MACHINE_FILES = {"NOW.md", "HANDOFF.md", "SKILL.md", "README.md", ".gitignore"}
SKELETON = ["00_Context", "10_Source", "20_Docs", "90_History"]

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4", ".mov", ".m4v", ".mp3"}
ARCHIVE_EXT = {".zip", ".tar", ".gz", ".tgz", ".dmg", ".7z", ".rar"}
DOC_EXT = {".md", ".txt", ".docx", ".pdf", ".xlsx", ".pptx"}
DATA_EXT = {".csv", ".json", ".jsonl", ".sqlite", ".db", ".parquet"}
BACKUP_PAT = re.compile(r"(v\d|backup|old|_bak|备份|副本|前备份|旧)", re.I)


def detect_language(root: Path) -> str:
    """en if any English schema dir exists, zh if any Chinese one exists, else en."""
    names = {p.name for p in root.iterdir() if p.is_dir()}
    if names & SCHEMA_ZH:
        return "zh"
    return "en"


def tgt(name_en: str, lang: str) -> str:
    if lang == "zh":
        for zh, en in ZH2EN.items():
            if en == name_en:
                return zh
    return name_en


def classify(name: str, is_dir: bool, has_git: bool, lang: str) -> tuple[str | None, str, str]:
    """Return (target_dir_en, confidence, reason). None target = keep in place."""
    if is_dir:
        if name in SCHEMA_EN or name in SCHEMA_ZH:
            return None, "high", "标准目录，保持原位"
        if has_git:
            return "10_Source", "medium", "git 仓库：建议按身份命名后移入 10_Source（需确认）"
        return None, "low", "目录归属无法判断"
    if name in MACHINE_FILES:
        if name in ("NOW.md", "HANDOFF.md"):
            return "00_Context", "high", "机器契约热文件，当前必读"
        return None, "high", "机器契约文件，保持原位"
    ext = Path(name).suffix.lower()
    if ext in IMG_EXT:
        return "30_Assets", "high", "素材"
    if ext in ARCHIVE_EXT and BACKUP_PAT.search(name):
        return "90_History", "high", "旧版本/备份"
    if ext in DOC_EXT:
        return "20_Docs", "high", "文档"
    if ext in DATA_EXT:
        return "50_Data", "high", "数据"
    return None, "low", "无法判断归属"


def build_plan(root: Path, lang: str) -> dict:
    """Read-only inventory + plan. Returns {root, lang, create[], moves[], keep[], token}."""
    create, moves, keep = [], [], []
    existing = {p.name for p in root.iterdir() if p.is_dir()}
    for schema in SKELETON:
        if tgt(schema, lang) not in existing:
            create.append(tgt(schema, lang))
    for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if p.name.startswith("."):
            continue
        is_dir = p.is_dir()
        has_git = is_dir and (p / ".git").exists()
        target_en, conf, reason = classify(p.name, is_dir, has_git, lang)
        if target_en is None:
            if conf != "high" or reason.startswith("机器契约"):
                keep.append((p.name, conf, reason))
            continue
        target = tgt(target_en, lang)
        moves.append({"src": p.name, "dst": f"{target}/{p.name}", "conf": conf, "why": reason})
    lines = [f"create:{d}" for d in create] + [
        f"move:{m['src']}->{m['dst']}[{m['conf']}]" for m in moves
    ]
    token = hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()[:16]
    return {"root": root, "lang": lang, "create": create, "moves": moves,
            "keep": keep, "token": token}


def print_plan(plan: dict) -> None:
    root = plan["root"]
    print(f"项目根：{root}")
    print(f"目录语言：{plan['lang']}")
    print()
    if plan["create"]:
        print("[建] " + " ".join(f"{d}/" for d in plan["create"]))
    else:
        print("[建] 无（骨架已齐）")
    if plan["moves"]:
        print()
        print("待移动：")
        for m in plan["moves"]:
            print(f"  - {m['src']} -> {m['dst']}  [{m['conf']}] {m['why']}")
    if plan["keep"]:
        print()
        print("待判断（保持原位）：")
        for name, conf, why in plan["keep"]:
            print(f"  - {name}  ({conf}：{why})")
    print()
    log_name = tgt("90_History", plan["lang"]) + "/" + ("搬运日志.md" if plan["lang"] == "zh" else "cleanup-log.md")
    print(f"搬运日志：{root / log_name}")
    print(f"token: {plan['token']}")


def apply_plan(plan: dict, expect_token: str) -> int:
    if expect_token != plan["token"]:
        print("token 不匹配：方案已变化，请重新 preview。", file=sys.stderr)
        return 2
    root = plan["root"]
    lang = plan["lang"]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    log_dir = root / tgt("90_History", lang)
    log_path = log_dir / ("搬运日志.md" if lang == "zh" else "cleanup-log.md")
    log_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"## {now} 一键整理 — {root}", f"- 目录语言：{lang}", f"- token: {expect_token}"]
    for d in plan["create"]:
        (root / d).mkdir(parents=True, exist_ok=True)
        lines.append(f"- [建] {d}/")
    for m in plan["moves"]:
        if m["conf"] != "high":
            lines.append(f"- [留] {m['src']}（{m['conf']}：{m['why']}）")
            continue
        src, dst = root / m["src"], root / m["dst"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            lines.append(f"- [冲突] {m['src']} -> {m['dst']}（目标已存在，未动）")
            continue
        shutil.move(str(src), str(dst))
        lines.append(f"- [移] {m['src']} -> {m['dst']} [{m['conf']}]")
    with log_path.open("a") as f:
        f.write("\n".join(lines) + "\n\n")
    print("\n".join(lines))
    print(f"\n完成。搬运日志：{log_path}")
    return 0


def resolve_project(store: Path, name: str) -> str:
    shelf = store / "SHELF.md"
    if not shelf.is_file():
        print(f"马厩不存在：{shelf}", file=sys.stderr)
        return ""
    bands, _ = parse_shelf(shelf.read_text())
    hits = [p["path"] for rows in bands.values() for p in rows if p["name"] == name]
    if not hits:
        print(f"马厩里没有叫「{name}」的项目。", file=sys.stderr)
        return ""
    if len(hits) > 1:
        print(f"「{name}」在马厩里出现 {len(hits)} 次：\n" + "\n".join(hits), file=sys.stderr)
        return ""
    return hits[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="马厩项目一键整理（project-fold 桥）")
    ap.add_argument("--store", default=os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi"))
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", metavar="TOKEN", help="执行 preview 给出的 token（无此参数即只读 preview）")
    args = ap.parse_args(argv)

    root = resolve_project(Path(args.store), args.project)
    if not root:
        return 2
    root = Path(root).expanduser()
    if not root.is_dir():
        print(f"项目根不存在或不可读：{root}", file=sys.stderr)
        return 2

    plan = build_plan(root, detect_language(root))
    if args.apply:
        return apply_plan(plan, args.apply)
    print_plan(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
