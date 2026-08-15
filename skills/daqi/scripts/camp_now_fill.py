#!/usr/bin/env python3
"""补主线：为马厩里没有 NOW 的项目生成候选四字段，确认后写入 00_Context/NOW.md。

流程与扫描一致：
  --list                列出缺少 NOW 主线的项目（只读）
  --previews-only --select 名字片段  打印上下文摘录，供 agent 大脑提炼
  --proposals FILE      采用 agent 提炼的四字段候选，铸 token（不写任何文件）
  --commit TOKEN        确认后写入；已存在 NOW 的一律跳过，绝不覆盖
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camp_status  # noqa: E402
import camp_scan  # noqa: E402
import checkpoint  # noqa: E402


def missing_now(store: Path) -> list[dict]:
    if not (store / "SHELF.md").is_file():
        return []
    bands, _ = camp_status.parse_shelf((store / "SHELF.md").read_text())
    out = []
    for key, label in camp_status.BANDS:
        for row in bands[key]:
            if not camp_status.find_now_file(row["path"]):
                out.append({"name": row["name"], "path": row["path"], "band": label})
    return out


def render_now_bytes(candidate: dict) -> bytes:
    fields = {
        "goal": str(candidate.get("goal", "")).strip() or "—",
        "verified_now": str(candidate.get("verified_now", "")).strip() or "—",
        "next": str(candidate.get("next", "")).strip() or "—",
        "done_when": str(candidate.get("done_when", "")).strip() or "—",
    }
    return checkpoint.render_now(fields, managed=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="补主线：给没 NOW 的马写候选主线（确认后写入）")
    ap.add_argument("--store", default=os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--select", help="逗号分隔的项目名片段（配合 --previews-only）")
    ap.add_argument("--previews-only", action="store_true", help="打印上下文摘录，不写任何 store")
    ap.add_argument("--max-bytes", type=int, default=2600)
    ap.add_argument("--proposals", metavar="FILE", help="采用给定候选 JSON（agent 大脑产物）")
    ap.add_argument("--commit", metavar="TOKEN", help="确认后写入候选 NOW")
    args = ap.parse_args(argv)

    store = Path(args.store)
    missing = missing_now(store)

    if args.list:
        if not missing:
            print("马厩里每一匹都有 NOW 主线了。")
        else:
            print(f"缺少 NOW 主线的项目（{len(missing)}）：")
            for m in missing:
                print(f"  - {m['name']}  {m['path']}  [{m['band']}]")
        return 0

    if args.previews_only:
        if not args.select:
            print("--previews-only 需要 --select（项目名片段，逗号分隔）", file=sys.stderr)
            return 2
        picked = [m for m in missing for token in args.select.split(",")
                  if token.strip() and token.strip() in m["name"]]
        payload = [{"name": m["name"], "path": m["path"],
                    "files": camp_scan.read_context(Path(m["path"]), args.max_bytes)}
                   for m in picked]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.proposals:
        try:
            candidates = json.loads(Path(args.proposals).read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(f"无法读取候选 JSON：{error}", file=sys.stderr)
            return 2
        if not isinstance(candidates, list):
            print("候选 JSON 必须是数组", file=sys.stderr)
            return 2
        token = hashlib.sha256(json.dumps(candidates, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        if not args.commit:
            print(f"候选主线（{len(candidates)} 条，确认后 --commit 才会写入）：")
            for c in candidates:
                skip = "（跳过）" if c.get("skip") else ""
                print(f"  [{c.get('name', '?')}] 目标：{c.get('goal', '—')[:60]}{skip}")
            print()
            print(f"token: {token}")
            return 0
        if args.commit != token:
            print("token 不匹配：方案已变化，请重新确认。", file=sys.stderr)
            return 2
        written, skipped = [], []
        for c in candidates:
            if c.get("skip") or not c.get("path"):
                skipped.append(c.get("name", "?"))
                continue
            root = Path(c["path"])
            now_path = root / "00_Context" / "NOW.md"
            if camp_status.find_now_file(str(root)):
                skipped.append(f"{c.get('name', '?')}（已有 NOW，不覆盖）")
                continue
            now_path.parent.mkdir(parents=True, exist_ok=True)
            now_path.write_bytes(render_now_bytes(c))
            written.append(c.get("name", "?"))
        print(f"已写入 {len(written)} 条主线：{'、'.join(written) or '—'}")
        if skipped:
            print(f"跳过 {len(skipped)} 条：{'、'.join(skipped)}")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
