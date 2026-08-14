#!/usr/bin/env python3
"""Agent-history scan with progress visualization (点子导入).

Phases: scan metadata -> select workspaces -> read context (shallow/deep) ->
propose intel/idea/project -> commit to POOL/SHELF after confirmation.

- Metadata only: session cwd + timestamps (+ DSH turn stats). Never reads
  transcripts.
- Deep read: project context files only (NOW.md / README.md / SKILL.md / docs),
  optionally distilled by the daqi brain (DeepSeek LLM, config in
  <store>/config.json or DAQI_LLM_* env). No key -> shallow heuristic mode.
- Progress: <store>/.scan-state.json is updated after every step and a
  self-refreshing <store>/scan.html is re-rendered (Grayscale Dither Archive).
- Stores are only written by `--commit <token>` after the proposals are shown.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import time
import datetime
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_shelf  # noqa: E402
from camp_status import parse_pool, parse_shelf  # noqa: E402

STATE_NAME = ".scan-state.json"
PROPOSALS_NAME = ".scan-proposals.json"
HTML_NAME = "scan.html"

MAX_FILES_PER_WORKSPACE = 6
SHALLOW_BYTES = 2400
DEEP_BYTES = 9000

# Grayscale Dither Archive palette
C_BG, C_BG2, C_CARD = "#F2F2EE", "#E5E5E0", "#FAFAF7"
C_TEXT, C_TEXT2, C_BORDER = "#111111", "#72726C", "#C9C9C2"
C_BLACK, C_REVERSE = "#050505", "#F5F5F2"

CSS = f"""
  body {{ background:{C_BG}; color:{C_TEXT}; font-family:-apple-system,"PingFang SC",sans-serif; line-height:1.55; }}
  .page {{ max-width:760px; margin:0 auto; padding:40px 24px 56px; }}
  .mono {{ font-family:ui-monospace,Menlo,monospace; letter-spacing:.02em; }}
  .sec {{ color:{C_TEXT2}; }}
  h1 {{ font-size:20px; letter-spacing:.12em; }}
  .meta {{ font-size:11px; color:{C_TEXT2}; margin-top:6px; }}
  .bar {{ height:26px; border:1px solid {C_TEXT}; background:{C_CARD}; margin-top:24px; position:relative; }}
  .bar .fill {{ height:100%; background:{C_TEXT};
                background-image:repeating-conic-gradient({C_REVERSE} 0 25%, transparent 0 50%);
                background-size:6px 6px; width:{{pct}}%; }}
  .bar .pct {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
               font-size:11px; mix-blend-mode:difference; color:{C_REVERSE}; }}
  .phases {{ display:grid; grid-template-columns:repeat(5,1fr); gap:6px; margin-top:18px; }}
  .phase {{ border:1px solid {C_BORDER}; background:{C_CARD}; padding:10px 12px; font-size:11px; }}
  .phase.on {{ background:{C_TEXT}; color:{C_CARD}; }}
  .phase.done {{ border-color:{C_TEXT}; }}
  .phase.done::after {{ content:" ✓"; }}
  .items {{ margin-top:28px; }}
  .item {{ display:flex; gap:10px; align-items:baseline; border:1px solid {C_BORDER};
          background:{C_CARD}; padding:9px 12px; }}
  .item + .item {{ margin-top:5px; }}
  .item .name {{ flex:1; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .chip {{ font-size:10px; padding:1px 6px; border:1px solid {C_TEXT}; white-space:nowrap; }}
  .chip.doing {{ background:{C_TEXT}; color:{C_CARD}; }}
  .chip.done {{ color:{C_TEXT2}; border-color:{C_BORDER}; }}
  .dots {{ width:12px; height:12px; display:inline-block;
           background-image:radial-gradient({C_TEXT} 1px, transparent 1px);
           background-size:6px 6px; }}
  footer {{ margin-top:36px; padding-top:14px; border-top:1px solid {C_BORDER};
            font-size:10px; color:{C_TEXT2}; letter-spacing:.08em; }}
"""


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


# ------------------------------------------------------------ configuration


def load_config(store: Path) -> dict:
    path = store / "config.json"
    cfg: dict = {"llm": {}}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                cfg = loaded
        except (OSError, json.JSONDecodeError) as error:
            print(f"warning: cannot read {path}: {error}", file=sys.stderr)
    llm = cfg.setdefault("llm", {})
    llm.setdefault("base_url", "https://api.deepseek.com")
    llm.setdefault("model", "DeepSeek-v4-flash0731")
    llm.setdefault("api_key", "")
    llm["base_url"] = os.environ.get("DAQI_LLM_BASE_URL") or llm["base_url"]
    llm["model"] = os.environ.get("DAQI_LLM_MODEL") or llm["model"]
    llm["api_key"] = os.environ.get("DAQI_LLM_API_KEY") or llm.get("api_key", "")
    return cfg


# ---------------------------------------------------------------- metadata


def dsh_sessions(projcache: Path) -> list[tuple[str, datetime.datetime]]:
    """cwd + createdAt from the DSH session projection cache (no transcripts)."""
    out: list[tuple[str, datetime.datetime]] = []
    if not projcache.is_file():
        print(f"warning: metadata not found: {projcache}", file=sys.stderr)
        return out
    try:
        data = json.loads(projcache.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"warning: cannot read {projcache}: {error}", file=sys.stderr)
        return out
    sessions = data.get("tables", {}).get("sessions", {})
    for session in sessions.values():
        identity = session.get("identity", {}) if isinstance(session, dict) else {}
        cwd = identity.get("cwd")
        created = identity.get("createdAt")
        if isinstance(cwd, str) and cwd and isinstance(created, (int, float)):
            out.append((cwd, datetime.datetime.fromtimestamp(created / 1000, datetime.timezone.utc)))
    return out


def scan_metadata(store: Path) -> list[dict]:
    merged: dict[str, dict] = {}
    sources = [
        (Path("~/.claude/projects").expanduser(), "Claude Code"),
        (Path("~/.codex/sessions").expanduser(), "Codex"),
    ]
    for root, agent in sources:
        for cwd, ts, _ in rebuild_shelf.iter_sessions(root, agent):
            if rebuild_shelf.default_excluded(cwd):
                continue
            row = merged.setdefault(
                cwd,
                {"path": cwd, "agents": set(), "last_active": datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), "sessions": 0},
            )
            row["agents"].add(agent)
            row["sessions"] += 1
            if ts is not None and (ts > row["last_active"] or row["sessions"] == 1):
                row["last_active"] = ts
    for cwd, ts in dsh_sessions(Path("~/.dsh/storages/session_projcache.json").expanduser()):
        if rebuild_shelf.default_excluded(cwd):
            continue
        row = merged.setdefault(
            cwd,
            {"path": cwd, "agents": set(), "last_active": datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), "sessions": 0},
        )
        row["agents"].add("DSH")
        row["sessions"] += 1
        if ts is not None:
            row["last_active"] = max(row["last_active"], ts)

    try:
        bands, _ = parse_shelf((store / "SHELF.md").read_text())
        shelf_paths = {p["path"] for rows in bands.values() for p in rows}
    except OSError:
        shelf_paths = set()

    candidates = []
    for row in merged.values():
        candidates.append(
            {
                "path": row["path"],
                "agents": sorted(row["agents"]),
                "last_active": row["last_active"].strftime("%Y-%m-%d %H:%M"),
                "sessions": row["sessions"],
                "in_shelf": row["path"] in shelf_paths,
            }
        )
    candidates.sort(key=lambda c: c["last_active"], reverse=True)
    return candidates


# ------------------------------------------------------------------ reading


CONTEXT_GLOB = ("NOW.md", "README.md", "README.zh-CN.md", "SKILL.md")


def read_context(root: Path, max_bytes: int) -> list[dict]:
    """Project context files only — never session transcripts."""
    files = []
    for name in CONTEXT_GLOB:
        p = root / name
        if p.is_file():
            files.append(p)
    docs = sorted((root / "20_Docs").glob("*.md")) if (root / "20_Docs").is_dir() else []
    files = files[:2] + docs[: MAX_FILES_PER_WORKSPACE - 2]
    out = []
    budget = max_bytes
    for p in files:
        if budget <= 0:
            break
        try:
            text = p.read_text(errors="replace")[:budget]
        except OSError as error:
            print(f"warning: cannot read {p}: {error}", file=sys.stderr)
            continue
        budget -= len(text)
        out.append({"file": str(p.relative_to(root)), "text": text})
    return out


def call_brain(cfg: dict, previews: list[dict]) -> list[dict]:
    llm = cfg["llm"]
    key = llm.get("api_key", "")
    if not key:
        return []
    body = {
        "model": llm["model"],
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是达奇的大脑，负责从项目工作区的上下文文件里提炼点子。"
                    "只输出 JSON：{\"items\":[{\"type\":\"intel|idea|project\","
                    "\"title\":\"…\",\"line\":\"一句话\",\"why_now\":\"…\","
                    "\"evidence\":\"…\",\"probe\":\"最小验证\"}]}。"
                    "intel=痛点或观察；idea=意图或方案假设；project=已成型的项目"
                    "（有根目录与可见交付物）。不发明；没有就返回空数组。"
                ),
            },
            {
                "role": "user",
                "content": "工作区文件摘录：\n" + "\n\n".join(
                    f"--- {p['file']} ---\n{p['text']}" for p in previews
                ),
            },
        ],
    }
    request = urllib.request.Request(
        llm["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # network / http / json — degrade to shallow
        print(f"warning: brain call failed ({error}); falling back to shallow", file=sys.stderr)
        return []
    try:
        content = payload["choices"][0]["message"]["content"]
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
        parsed = json.loads(text)
        return parsed.get("items", []) if isinstance(parsed, dict) else []
    except (KeyError, IndexError, json.JSONDecodeError) as error:
        print(f"warning: brain output unparsable ({error})", file=sys.stderr)
        return []


def heuristic(root: Path, previews: list[dict]) -> list[dict]:
    name = root.name
    first = previews[0] if previews else None
    title, line = name, f"工作区 {name} 有活跃会话记录"
    if first:
        m = re.search(r"^#\s+(.+)$", first["text"], re.M)
        if m:
            title = m.group(1).strip()
        body = re.sub(r"^#.*$", "", first["text"], flags=re.M).strip()
        line = (body.splitlines() or [line])[0][:120]
    if (root / "NOW.md").is_file():
        readme_title = None
        for p in previews:
            if Path(p["file"]).name.lower().startswith("readme"):
                m = re.search(r"^#\s+(.+)$", p["text"], re.M)
                if m:
                    readme_title = m.group(1).strip()
        if readme_title:
            title = readme_title
        else:
            title = name
        return [{"type": "project", "title": title, "line": line, "why_now": "已有 NOW 主线", "evidence": "NOW.md 存在", "probe": "确认是否入马厩"}]
    return [{"type": "idea", "title": title, "line": line, "why_now": "近期有 Agent 会话活动", "evidence": "上下文文件可读", "probe": "让达奇深读提炼"}]


# ------------------------------------------------------------------- state


def write_state(store: Path, state: dict) -> None:
    (store / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def render_html(state: dict) -> str:
    pct = int(state.get("percent", 0))
    phases = [("scan", "扫描"), ("select", "选择"), ("read", "读取"), ("brain", "提炼"), ("commit", "提交")]
    current = state.get("phase", "scan")
    phase_blocks = []
    seen_current = False
    for key, label in phases:
        cls = "phase done" if seen_current else "phase on" if key == current else "phase"
        if key == current:
            seen_current = True
        phase_blocks.append(f'<div class="{cls}">{label}<br><span class="mono">{key.upper()}</span></div>')
    items = ""
    for it in state.get("items", []):
        chip = "done" if it["status"] == "done" else "doing" if it["status"] == "reading" else ""
        mark = '<span class="dots"></span>' if it["status"] == "reading" else ""
        items += (
            f'<div class="item"><span class="chip {chip}">{esc(it["status"])}</span>'
            f'<span class="name" title="{esc(it["path"])}">{esc(Path(it["path"]).name)} · {esc(it["path"])}</span>'
            f"<span>{mark}</span></div>"
        )
    css = CSS.replace("{pct}", str(pct))
    return f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="1.5">
<title>扫描进程 · SCAN PROCESS</title>
<style>{css}</style>
</head>
<body>
<div class="page">
  <h1>扫描进程 <span class="sec mono">SCAN PROCESS</span></h1>
  <div class="meta mono">DAQI_CAMP_SCAN · {esc(state.get("started", ""))} · PHASE {current.upper()} · READ-ONLY UNTIL COMMIT</div>
  <div class="bar"><div class="fill"></div><div class="pct mono">{pct}%</div></div>
  <div class="phases">{''.join(phase_blocks)}</div>
  <div class="items">{items}</div>
  <footer class="mono">只读扫描：仅会话 cwd + 时间戳 + 项目上下文文件，不读对话记录 · 提交前不写任何 store · 自动刷新 1.5s</footer>
</div>
</body>
</html>
"""


def tick(store: Path, state: dict, **fields: object) -> None:
    state.update(fields)
    write_state(store, state)
    (store / HTML_NAME).write_text(render_html(state))
    print(f"[{state.get('percent', 0):>3}%] {fields.get('log', '')}")


# -------------------------------------------------------------------- main


def dedupe_against_stores(store: Path, proposals: list[dict]) -> list[dict]:
    try:
        pool_entries, _ = parse_pool((store / "POOL.md").read_text())
    except OSError:
        pool_entries = []
    try:
        bands, _ = parse_shelf((store / "SHELF.md").read_text())
        shelf_rows = [p for rows in bands.values() for p in rows]
    except OSError:
        shelf_rows = []
    known_titles = {e["text"][:40] for e in pool_entries} | {p["name"] for p in shelf_rows}
    fresh = []
    for p in proposals:
        if p.get("title", "")[:40] in known_titles:
            continue
        fresh.append(p)
    return fresh


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="扫描 Agent 历史，找点子和项目（带进度可视化）")
    ap.add_argument("--store", default=os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi"))
    ap.add_argument("--select", help="逗号分隔的工作区名或路径片段，单选/多选")
    ap.add_argument("--depth", choices=("shallow", "deep"), default="shallow")
    ap.add_argument("--commit", metavar="TOKEN", help="确认方案后提交（写 POOL/SHELF）")
    args = ap.parse_args(argv)

    store = Path(args.store)
    for required in ("POOL.md", "SHELF.md"):
        if not (store / required).is_file():
            print(f"营地不完整：需要 {store / required}", file=sys.stderr)
            return 2

    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    state = {"phase": "scan", "percent": 0, "started": started, "items": [], "log": "开始扫描 Agent 历史"}
    write_state(store, state)
    (store / HTML_NAME).write_text(render_html(state))
    print(f"[  0%] 开始扫描 Agent 历史 · 进度页：{store / HTML_NAME}")

    tick(store, state, percent=12, log="扫描 DSH / Claude Code / Codex 会话元数据（仅 cwd+时间戳，不读对话）")
    candidates = scan_metadata(store)
    state["candidates"] = candidates
    tick(store, state, percent=30, log=f"发现 {len(candidates)} 个工作区")

    if not args.select:
        print()
        for i, c in enumerate(candidates, 1):
            flag = " 已在马厩" if c["in_shelf"] else ""
            print(f"{i:>3}. {c['path']}  [{', '.join(c['agents'])}] {c['last_active']} · {c['sessions']} 会话{flag}")
        print()
        print("单选/多选示例：camp_scan.py --select 1,3  或  --select daqi.skill,IP-skill")
        state["phase"] = "select"
        write_state(store, state)
        (store / HTML_NAME).write_text(render_html(state))
        return 0

    picked = []
    for token in [t.strip() for t in args.select.split(",") if t.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(candidates):
            picked.append(candidates[int(token) - 1])
        else:
            matches = [c for c in candidates if token in c["path"]]
            picked.extend(matches)
    # dedupe, keep order
    deduped: list[dict] = []
    seen_paths: set[str] = set()
    for c in picked:
        if c["path"] in seen_paths:
            continue
        seen_paths.add(c["path"])
        deduped.append(c)
    picked = deduped

    if not picked:
        print("没有匹配的工作区。", file=sys.stderr)
        return 2

    state["phase"] = "read"
    items = [{"path": c["path"], "status": "pending"} for c in picked]
    state["items"] = items
    total = len(picked)
    read_bytes = DEEP_BYTES if args.depth == "deep" else SHALLOW_BYTES
    cfg = load_config(store)
    if args.depth == "deep" and not cfg["llm"].get("api_key"):
        print("注意：未配置 LLM API key，deep 自动降级为 shallow（启发式提炼）。", file=sys.stderr)
        args.depth = "shallow"

    proposals: list[dict] = []
    for index, cand in enumerate(picked):
        items[index]["status"] = "reading"
        tick(store, state, percent=30 + int(45 * index / max(total, 1)),
             log=f"读取 {cand['path']}（{args.depth}）")
        previews = read_context(Path(cand["path"]), read_bytes)
        findings: list[dict] = []
        if args.depth == "deep":
            tick(store, state, percent=30 + int(45 * (index + 0.5) / max(total, 1)),
                 log=f"大脑提炼 {cand['path']}（{cfg['llm']['model']}）")
            findings = call_brain(cfg, previews)
        if not findings:
            findings = heuristic(Path(cand["path"]), previews)
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
        items[index]["status"] = "done"
        tick(store, state, percent=30 + int(45 * (index + 1) / max(total, 1)),
             log=f"完成 {cand['path']}：{len(findings)} 条")

    state["phase"] = "brain" if args.depth == "deep" else "commit"
    proposals = dedupe_against_stores(store, proposals)
    state["proposals"] = proposals
    token = hashlib.sha256(json.dumps(proposals, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    state["token"] = token
    tick(store, state, percent=80, log=f"提炼完成：{len(proposals)} 条候选（已去重）")

    print()
    print("候选方案（确认后 --commit 才会写入账本/马厩）：")
    for p in proposals:
        print(f"  [{p['type']}] {p['title']} — {p['line'][:80]}")
    if not proposals:
        print("  （没有新发现）")
    print()
    print(f"token: {token}")

    if args.commit:
        if args.commit != token:
            print("token 不匹配：方案已变化，请重新确认。", file=sys.stderr)
            return 2
        if args.commit:  # apply
            state["phase"] = "commit"
            tick(store, state, percent=92, log="写入账本与马厩…")
            pool_lines = []
            now = datetime.date.today().isoformat()
            for p in proposals:
                if p["type"] == "project":
                    bands, _ = parse_shelf((store / "SHELF.md").read_text())
                    if any(row["path"] == p["source"] for rows in bands.values() for row in rows):
                        continue
                    shelf = (store / "SHELF.md").read_text()
                    row = f"| {p['title']} | {p['source']} | {now} | scan |"
                    shelf = shelf.replace("|---|---|---|---|\n", f"|---|---|---|---|\n{row}\n", 1)
                    (store / "SHELF.md").write_text(shelf)
                else:
                    stage = "情报" if p["type"] == "intel" else "点子"
                    pool_lines.append(
                        f"- 阶段：{stage}｜{p['title']}｜{p['why_now'] or '扫描发现'}｜"
                        f"{p['evidence'] or '—'}｜{p['probe'] or '—'}｜{now}"
                    )
            if pool_lines:
                pool = (store / "POOL.md").read_text()
                pool = pool.replace("<空>", "\n".join(pool_lines), 1)
                (store / "POOL.md").write_text(pool)
            state["applied"] = now
            tick(store, state, percent=100, log=f"已写入：{len(pool_lines)} 条入账本，项目入马厩")
        else:
            tick(store, state, percent=100, log="方案已确认，无待写入项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
