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
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import datetime
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_shelf  # noqa: E402
from camp_status import build_page, parse_pool, parse_shelf  # noqa: E402

STATE_NAME = ".scan-state.json"

MAX_FILES_PER_WORKSPACE = 6
SHALLOW_BYTES = 2400
DEEP_BYTES = 9000

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
    """Project context files only — never session transcripts.

    Looks at root contract files, one level of containers, and nested repo
    roots (e.g. 00_Context/NOW.md, 10_Source/<repo>/README.md), skipping
    dependency caches. Budget is shared across at most 8 files.
    """
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build",
            "90_History", "90_历史"}
    files: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        if p.is_file() and p not in seen:
            seen.add(p)
            files.append(p)

    def scan_docs(d: Path) -> None:
        for sub in ("00_Context", "20_Docs", "docs", "20_文档"):
            sd = d / sub
            if sd.is_dir():
                for p in sorted(sd.rglob("*.md"))[:3]:
                    add(p)

    def safe_iter(d: Path) -> list[Path]:
        try:
            return sorted(d.iterdir())
        except OSError:
            return []

    for name in CONTEXT_GLOB:
        add(root / name)
    level1 = [d for d in safe_iter(root)
              if d.is_dir() and d.name not in skip and not d.name.startswith(".")]
    for d in level1:
        for name in CONTEXT_GLOB:
            add(d / name)
        scan_docs(d)
    for d in level1:
        for g in safe_iter(d):
            if not g.is_dir() or g.name in skip or g.name.startswith("."):
                continue
            for name in CONTEXT_GLOB:
                add(g / name)
            scan_docs(g)
    out = []
    budget = max_bytes
    for p in files[:8]:
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


def agent_command() -> str | None:
    for c in ("codex", "claude"):
        found = shutil.which(c)
        if found:
            return found
    local_bin = Path.home() / ".local" / "bin"
    for c in ("codex", "claude"):
        candidate = local_bin / c
        if candidate.is_file():
            return str(candidate)
    return None


def call_agent_brain(cfg: dict, previews: list[dict]) -> list[dict]:
    """No API key? Use the installed local agent as the brain."""
    agent = cfg.get("agent", {}) if isinstance(cfg, dict) else {}
    command = str(agent.get("command", "") or agent_command() or "")
    if not command:
        return []
    prompt = (
        "你是达奇的大脑，负责从项目工作区的上下文文件里提炼点子。"
        "只输出一个 JSON 数组（不要多余文字）："
        '[{"type":"intel|idea|project","title":"…","line":"一句话","why_now":"…",'
        '"evidence":"…","probe":"最小验证"}]。'
        "intel=痛点或观察；idea=意图或方案假设；project=已成型的项目（有根目录与可见交付物）。"
        "不发明；没有就输出 []。\n\n工作区文件摘录：\n"
        + "\n\n".join(f"--- {p['file']} ---\n{p['text']}" for p in previews)
    )
    if command.endswith("codex"):
        full = [command, "exec", "--skip-git-repo-check", prompt]
    elif command.endswith("claude"):
        full = [command, "-p", prompt]
    else:
        full = [command] + list(agent.get("args", [])) + [prompt]
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=600, cwd=str(Path.home()))
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"warning: agent brain failed ({error})", file=sys.stderr)
        return []
    text = result.stdout.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
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


def render_camp_page(store: Path) -> None:
    """Regenerate camp.html so its 扫描 panel mirrors the current state."""
    try:
        (store / "camp.html").write_text(build_page(store))
    except Exception as error:
        print(f"warning: camp page refresh failed: {error}", file=sys.stderr)


def write_state(store: Path, state: dict) -> None:
    (store / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def tick(store: Path, state: dict, **fields: object) -> None:
    state.update(fields)
    write_state(store, state)
    render_camp_page(store)
    print(f"[{state.get('percent', 0):>3}%] {fields.get('log', '')}")


# -------------------------------------------------------------------- main


def resolve_selection(candidates: list[dict], select: str) -> list[dict]:
    picked = []
    for token in [t.strip() for t in select.split(",") if t.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(candidates):
            picked.append(candidates[int(token) - 1])
        else:
            picked.extend(c for c in candidates if token in c["path"])
    seen: set[str] = set()
    return [c for c in picked if not (c["path"] in seen or seen.add(c["path"]))]


def scan_flow(store: Path, select: str, depth: str = "shallow") -> tuple[list[dict], str]:
    """Run the scan pipeline with live state/camp-page ticks; returns (proposals, token)."""
    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    candidates = scan_metadata(store)
    picked = resolve_selection(candidates, select)
    items = [{"path": c["path"], "status": "pending", "percent": 0} for c in picked]
    state = {"phase": "read", "percent": 30, "started": started,
             "items": items, "candidates": candidates}
    write_state(store, state)
    render_camp_page(store)
    cfg = load_config(store)
    proposals: list[dict] = []
    total = max(len(picked), 1)
    read_bytes = DEEP_BYTES if depth == "deep" else SHALLOW_BYTES
    for index, cand in enumerate(picked):
        items[index]["status"] = "reading"
        items[index]["percent"] = 8
        state["percent"] = 30 + int(45 * index / total)
        write_state(store, state)
        render_camp_page(store)
        previews = read_context(Path(cand["path"]), read_bytes)
        findings: list[dict] = []
        if depth == "deep":
            items[index]["percent"] = 55
            state["percent"] = 30 + int(45 * (index + 0.5) / total)
            write_state(store, state)
            render_camp_page(store)
            if cfg["llm"].get("api_key"):
                findings = call_brain(cfg, previews)
            else:
                findings = call_agent_brain(cfg, previews)
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
        items[index]["percent"] = 100
        state["percent"] = 30 + int(45 * (index + 1) / total)
        write_state(store, state)
        render_camp_page(store)
    proposals = dedupe_against_stores(store, proposals)
    token = hashlib.sha256(json.dumps(proposals, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    state.update({"phase": "commit", "percent": 80, "proposals": proposals, "token": token})
    write_state(store, state)
    render_camp_page(store)
    return proposals, token


def commit_scan(store: Path, token: str) -> tuple[int, int]:
    """Write the state-held proposals into POOL/SHELF after token check."""
    state_path = store / STATE_NAME
    if not state_path.is_file():
        return -1, -1
    try:
        state = json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return -1, -1
    if state.get("token") != token:
        return -1, -1
    proposals = state.get("proposals", [])
    pool_lines = []
    shelf_added = 0
    now = datetime.date.today().isoformat()
    for p in proposals:
        if p.get("type") == "project":
            shelf = (store / "SHELF.md").read_text()
            if p.get("source") and f"| {p.get('source')} " not in shelf:
                shelf = shelf.replace("|---|---|---|---|\n", f"|---|---|---|---|\n| {p.get('title')} | {p.get('source')} | {now} | scan |\n", 1)
                (store / "SHELF.md").write_text(shelf)
                shelf_added += 1
        else:
            stage = "情报" if p.get("type") == "intel" else "点子"
            pool_lines.append(
                f"- 阶段：{stage}｜{p.get('title')}｜{p.get('why_now') or '扫描发现'}｜"
                f"{p.get('evidence') or '—'}｜{p.get('probe') or '—'}｜{now}"
            )
    if pool_lines:
        pool = (store / "POOL.md").read_text()
        if "<空>" in pool:
            pool = pool.replace("<空>", "\n".join(pool_lines), 1)
        else:
            pool = pool.rstrip("\n") + "\n" + "\n".join(pool_lines) + "\n"
        (store / "POOL.md").write_text(pool)
    state["applied"] = now
    state["applied_pool"] = len(pool_lines)
    state["applied_shelf"] = shelf_added
    state["phase"] = "commit"
    state["percent"] = 100
    write_state(store, state)
    render_camp_page(store)
    return len(pool_lines), shelf_added


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
    ap.add_argument("--proposals", metavar="FILE", help="跳过读取/提炼，直接采用给定候选 JSON（agent 大脑产物）")
    ap.add_argument("--previews-only", action="store_true", help="只打印所选工作区的上下文摘录（供 agent 大脑提炼），不写任何 store")
    ap.add_argument("--max-bytes", type=int, default=DEEP_BYTES, help="previews-only 时每个工作区的字符预算")
    args = ap.parse_args(argv)

    store = Path(args.store)
    for required in ("POOL.md", "SHELF.md"):
        if not (store / required).is_file():
            print(f"营地不完整：需要 {store / required}", file=sys.stderr)
            return 2

    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    state = {"phase": "scan", "percent": 0, "started": started, "items": [], "log": "开始扫描 Agent 历史"}
    write_state(store, state)
    render_camp_page(store)
    print(f"[  0%] 开始扫描 Agent 历史 · 进度：{store / 'camp.html'} 的扫描面板")

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
        render_camp_page(store)
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

    if args.previews_only:
        payload = []
        for cand in picked:
            payload.append({"path": cand["path"], "files": read_context(Path(cand["path"]), args.max_bytes)})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

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
    if args.proposals:
        try:
            injected = json.loads(Path(args.proposals).read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(f"无法读取候选 JSON：{error}", file=sys.stderr)
            return 2
        if not isinstance(injected, list):
            print("候选 JSON 必须是数组", file=sys.stderr)
            return 2
        for f in injected:
            if not isinstance(f, dict):
                continue
            if f.get("type") not in ("intel", "idea", "project"):
                f["type"] = "idea"
            f.setdefault("title", "")
            f.setdefault("line", "")
            f.setdefault("why_now", "")
            f.setdefault("evidence", "")
            f.setdefault("probe", "")
            proposals.append(f)
        for item in items:
            item["status"] = "done"
            item["percent"] = 100
        tick(store, state, percent=80, log=f"采用 agent 大脑候选：{len(proposals)} 条")
    else:
        for index, cand in enumerate(picked):
            items[index]["status"] = "reading"
            items[index]["percent"] = 8
            tick(store, state, percent=30 + int(45 * index / max(total, 1)),
                 log=f"读取 {cand['path']}（{args.depth}）")
            previews = read_context(Path(cand["path"]), read_bytes)
            findings: list[dict] = []
            if args.depth == "deep":
                items[index]["percent"] = 55
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
            items[index]["percent"] = 100
            tick(store, state, percent=30 + int(45 * (index + 1) / max(total, 1)),
                 log=f"完成 {cand['path']}：{len(findings)} 条")

    state["phase"] = "brain" if args.depth == "deep" else "commit"
    proposals = dedupe_against_stores(store, proposals)
    state["proposals"] = proposals
    token = hashlib.sha256(json.dumps(proposals, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    state["token"] = token
    tick(store, state, percent=80, log=f"这波扫完，挖到 {len(proposals)} 条新的（去重过了）")

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
                if "<空>" in pool:
                    pool = pool.replace("<空>", "\n".join(pool_lines), 1)
                else:
                    pool = pool.rstrip("\n") + "\n" + "\n".join(pool_lines) + "\n"
                (store / "POOL.md").write_text(pool)
            state["applied"] = now
            tick(store, state, percent=100, log=f"已写入：{len(pool_lines)} 条入账本，项目入马厩")
        else:
            tick(store, state, percent=100, log="方案已确认，无待写入项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
