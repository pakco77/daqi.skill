#!/usr/bin/env python3
"""daqi MCP server — one daqi brain for every MCP-capable host.

Stdio transport, newline-delimited JSON-RPC, standard library only.
Tools v1:
  daqi_record           记一笔情报/点子进账本（唯一写工具，用户显式调用）
  daqi_camp             渲染营地页并返回清点摘要（只读）
  daqi_status           马厩总览或某项目的 NOW 主线（只读）
  daqi_scan             扫描 Agent 历史：候选列表 / 选中深读提炼（只读，不提交）
  daqi_organize_preview 一键整理方案预览（只读，不执行）

Stores: --store 或 DAQI_HOME，默认 ~/.daqi。永不读对话记录。
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
import organize_stable  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "daqi"
SERVER_VERSION = "1.0.0"

TOOLS = [
    {
        "name": "daqi_record",
        "description": (
            "把一条情报（痛点/观察）或点子（意图/假设）记进营地账本 POOL。"
            "这是达奇唯一会写 store 的工具，只在用户明确要记时调用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "enum": ["intel", "idea"]},
                "text": {"type": "string", "description": "一句话痛点或意图"},
                "why_now": {"type": "string"},
                "evidence": {"type": "string"},
                "probe": {"type": "string"},
            },
            "required": ["stage", "text"],
        },
    },
    {
        "name": "daqi_camp",
        "description": "渲染只读营地页（~/.daqi/camp.html）并返回营地清点摘要。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "daqi_status",
        "description": "马厩总览；给 project 名时返回该项目的 NOW 主线（目标/已验证/下一步/完成条件）。",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
        },
    },
    {
        "name": "daqi_scan",
        "description": (
            "扫描 DSH/Claude Code/Codex 会话元数据（只读 cwd+时间戳，不读对话）。"
            "不给 select 返回候选列表；给 select（编号或路径片段，逗号分隔）则读取上下文并提炼"
            "候选方案，返回方案与 token，但绝不写 store——提交必须由用户在聊天里确认。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "select": {"type": "string"},
                "depth": {"type": "string", "enum": ["shallow", "deep"]},
            },
        },
    },
    {
        "name": "daqi_organize_preview",
        "description": (
            "从马厩定位项目，只读盘点并给出极简 move plan 与 token；不执行任何移动。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
            "required": ["project"],
        },
    },
]


def text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def tool_record(store: Path, args: dict) -> str:
    stage = args.get("stage")
    if stage not in ("intel", "idea"):
        raise ValueError("stage must be intel or idea")
    text = str(args.get("text", "")).strip()
    if not text:
        raise ValueError("text is required")
    pool_path = store / "POOL.md"
    if not pool_path.is_file():
        return f"营地不完整：缺少 {pool_path}"
    entries, _ = camp_status.parse_pool(pool_path.read_text())
    if any(e["text"][:40] == text[:40] for e in entries):
        return f"账本里已经有这条了（{text[:40]}…），不重复记。"
    label = "情报" if stage == "intel" else "点子"
    line = (
        f"- 阶段：{label}｜{text}｜{args.get('why_now') or '—'}｜"
        f"{args.get('evidence') or '—'}｜{args.get('probe') or '—'}｜"
        f"{datetime.date.today().isoformat()}"
    )
    pool = pool_path.read_text()
    if "<空>" in pool:
        pool = pool.replace("<空>", line, 1)
    else:
        pool = pool.rstrip("\n") + "\n" + line + "\n"
    pool_path.write_text(pool)
    return f"点子王，{label}记进账本了。{text[:60]}"


def tool_camp(store: Path, _args: dict) -> str:
    if not (store / "POOL.md").is_file() or not (store / "SHELF.md").is_file():
        return f"营地不完整：需要 {store / 'POOL.md'} 和 {store / 'SHELF.md'}"
    html = camp_status.build_page(store)
    (store / "camp.html").write_text(html)
    pool, _ = camp_status.parse_pool((store / "POOL.md").read_text())
    bands, _ = camp_status.parse_shelf((store / "SHELF.md").read_text())
    counts = {key: 0 for key, _ in camp_status.STAGE_ORDER}
    for e in pool:
        counts[e["stage"]] += 1
    band_counts = {key: len(bands[key]) for key, _ in camp_status.BANDS}
    return (
        f"营地清点完毕：账本 情报 {counts['intel']} · 点子 {counts['idea']} · 计划 {counts['plan']}（共 {sum(counts.values())}）；"
        f"马厩 在跑 {band_counts['riding']} · 松了 {band_counts['loose']} · 歇马 {band_counts['stabled']}（共 {sum(band_counts.values())}）。"
        f"档案：{store / 'camp.html'}"
    )


def tool_status(store: Path, args: dict) -> str:
    if not (store / "SHELF.md").is_file():
        return f"马厩不存在：{store / 'SHELF.md'}"
    bands, _ = camp_status.parse_shelf((store / "SHELF.md").read_text())
    project = str(args.get("project", "")).strip()
    if project:
        for key, label in camp_status.BANDS:
            for row in bands[key]:
                if row["name"] == project:
                    now_path = Path(row["path"]) / "00_Context" / "NOW.md"
                    if not now_path.is_file():
                        return f"{project}（{label}）没有 NOW 主线：{row['path']}"
                    now = camp_status.parse_now(now_path.read_text())
                    return (
                        f"{project} · {label} · {row['path']}\n"
                        f"目标：{now.get('goal', '—')}\n"
                        f"已验证：{now.get('verified', '—')}\n"
                        f"下一步：{now.get('next', '—')}\n"
                        f"完成条件：{now.get('done_when', '—')}"
                    )
        return f"马厩里没有「{project}」"
    lines = ["马厩："]
    for key, label in camp_status.BANDS:
        lines.append(f"{label} {len(bands[key])}：")
        for row in bands[key][:60]:
            lines.append(f"  - {row['name']} · {row['path']} · {row['last']}")
    return "\n".join(lines)


def tool_scan(store: Path, args: dict) -> str:
    candidates = camp_scan.scan_metadata(store)
    select = str(args.get("select", "")).strip()
    if not select:
        if not candidates:
            return "没有扫到工作区。"
        lines = [f"{i}. {c['path']}  [{', '.join(c['agents'])}] {c['last_active']} · {c['sessions']} 会话" + (" · 已在马厩" if c["in_shelf"] else "") for i, c in enumerate(candidates, 1)]
        return "工作区候选（用 daqi_scan select 指定编号或路径片段）：\n" + "\n".join(lines[:40])
    picked = []
    for token in [t.strip() for t in select.split(",") if t.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(candidates):
            picked.append(candidates[int(token) - 1])
        else:
            picked.extend(c for c in candidates if token in c["path"])
    seen: set[str] = set()
    picked = [c for c in picked if not (c["path"] in seen or seen.add(c["path"]))]
    if not picked:
        return "没有匹配的工作区。"
    depth = str(args.get("depth", "shallow"))
    cfg = camp_scan.load_config(store)
    if depth == "deep" and not cfg["llm"].get("api_key"):
        depth = "shallow"
    read_bytes = camp_scan.DEEP_BYTES if depth == "deep" else camp_scan.SHALLOW_BYTES
    proposals = []
    for cand in picked:
        previews = camp_scan.read_context(Path(cand["path"]), read_bytes)
        findings = camp_scan.call_brain(cfg, previews) if depth == "deep" else []
        if not findings:
            findings = camp_scan.heuristic(Path(cand["path"]), previews)
        for f in findings:
            if f.get("type") not in ("intel", "idea", "project"):
                f["type"] = "idea"
            f.setdefault("title", Path(cand["path"]).name)
            f.setdefault("line", "")
            f.setdefault("why_now", "")
            f.setdefault("evidence", "")
            f.setdefault("probe", "")
            f["source"] = cand["path"]
        proposals.extend(findings)
    proposals = camp_scan.dedupe_against_stores(store, proposals)
    token = hashlib.sha256(json.dumps(proposals, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    lines = [f"提炼完成：{len(proposals)} 条候选（{depth}，未写入任何 store）。"]
    for p in proposals:
        lines.append(f"[{p['type']}] {p['title']} — {p['line'][:80]}")
    lines.append(f"token: {token}（提交需用户在聊天里确认）")
    return "\n".join(lines)


def tool_organize_preview(store: Path, args: dict) -> str:
    project = str(args.get("project", "")).strip()
    if not project:
        raise ValueError("project is required")
    root = organize_stable.resolve_project(store, project)
    if not root:
        return f"马厩里没有「{project}」"
    plan = organize_stable.build_plan(Path(root), organize_stable.detect_language(Path(root)))
    lines = [f"项目根：{plan['root']}", f"目录语言：{plan['lang']}"]
    if plan["create"]:
        lines.append("[建] " + " ".join(f"{d}/" for d in plan["create"]))
    for m in plan["moves"]:
        lines.append(f"- {m['src']} -> {m['dst']}  [{m['conf']}] {m['why']}")
    for name, conf, why in plan["keep"]:
        lines.append(f"- 留原地：{name}（{conf}：{why}）")
    lines.append(f"token: {plan['token']}（执行需用户在聊天里确认）")
    return "\n".join(lines)


TOOL_HANDLERS = {
    "daqi_record": tool_record,
    "daqi_camp": tool_camp,
    "daqi_status": tool_status,
    "daqi_scan": tool_scan,
    "daqi_organize_preview": tool_organize_preview,
}


def handle_call(store: Path, params: dict) -> dict:
    name = params.get("name", "")
    if name not in TOOL_HANDLERS:
        return {"isError": True, **text_result(f"unknown tool: {name}")}
    try:
        text = TOOL_HANDLERS[name](store, params.get("arguments") or {})
        return text_result(text)
    except ValueError as error:
        return {"isError": True, **text_result(f"参数错误：{error}")}
    except Exception as error:  # keep the server alive; report the failure
        return {"isError": True, **text_result(f"工具失败：{error}")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="daqi MCP server (stdio)")
    ap.add_argument("--store", default=os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi"))
    args = ap.parse_args(argv)
    store = Path(args.store)
    out = sys.stdout
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        method = message.get("method", "")
        msg_id = message.get("id")
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = handle_call(store, message.get("params") or {})
        elif method == "ping":
            result = {}
        else:
            # notifications and unknown requests: stay silent or report errors only when id present
            if msg_id is not None:
                out.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"unknown method {method}"}}, ensure_ascii=False) + "\n")
                out.flush()
            continue
        if msg_id is not None:
            out.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}, ensure_ascii=False) + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
