#!/usr/bin/env python3
"""Read-only camp view.

Parse the camp stores (POOL.md ledger + SHELF.md stables) and render one
self-contained HTML report in the "Grayscale Dither Archive / 灰阶点阵档案"
style. The stores are opened read-only and never modified; the only write is
the derived HTML artifact at --out (default <store>/camp.html).

Style contract (Grayscale Dither Archive):
  - 70% modern editorial design, 20% grayscale dither imagery, 10% terminal detail
  - palette: bg #F2F2EE, secondary #E5E5E0, card #FAFAF7, text #111111,
    secondary text #72726C, border #C9C9C2, black #050505, reverse #F5F5F2
  - 1px solid borders, 0-2px radius, no soft shadows; hover = black/white invert;
    selected = checker/dither fill; disabled = 35-45% gray
  - modern sans for body/headings, monospace for numbers/labels/times/ids
  - dither: 1-bit Floyd-Steinberg for the hero image, 4-level Bayer 4x4 for
    thumbnails; visible pixel grain, no gradients, no soft blur
  - motion is frame-like: discrete steps(), image develops from sparse dots
  - no CRT scanlines, no glitch, no RGB split
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import os
import re
import sys
import datetime
from pathlib import Path

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:  # pragma: no cover - degrade gracefully without images
    HAS_PIL = False

STAGE_ORDER = [("intel", "情报"), ("idea", "点子"), ("plan", "计划")]
STAGE_TOKENS = {
    "情报": "intel",
    "点子": "idea",
    "计划": "plan",
    "intel": "intel",
    "idea": "idea",
    "plan": "plan",
}
BANDS = [("riding", "在跑"), ("loose", "松了"), ("stabled", "歇马")]
DISPLAY_BANDS = [
    ("riding", "在跑"),
    ("week", "7 天没动"),
    ("month", "30 天没动"),
    ("unknown", "时间未知"),
]
BAND_TOKENS = {
    "在跑": "riding",
    "松了": "loose",
    "歇马": "stabled",
    "Riding": "riding",
    "Loose rein": "loose",
    "Stabled": "stabled",
}

# Grayscale Dither Archive palette
C_BG = "#F2F2EE"
C_BG2 = "#E5E5E0"
C_CARD = "#FAFAF7"
C_TEXT = "#111111"
C_TEXT2 = "#72726C"
C_BORDER = "#C9C9C2"
C_BLACK = "#050505"
C_REVERSE = "#F5F5F2"

PAGE_CSS = """
  :root { color-scheme: light; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: %(bg)s; color: %(text)s;
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", sans-serif;
    line-height: 1.55; -webkit-font-smoothing: antialiased;
  }
  .page { max-width: 880px; margin: 0 auto; padding: 40px 24px 56px; }
  .mono { font-family: ui-monospace, "SF Mono", Menlo, "JetBrains Mono", monospace; letter-spacing: .02em; }
  .sec { color: %(text2)s; }
  img.dither { image-rendering: pixelated; display: block; }

  /* --- header --- */
  .top { display: flex; align-items: center; gap: 16px; padding-bottom: 24px; border-bottom: 1px solid %(border)s; }
  .top h1 { font-size: 20px; font-weight: 650; letter-spacing: .12em; }
  .top .meta { font-size: 11px; color: %(text2)s; margin-top: 6px; }
  .top .mark { width: 56px; height: 56px; border: 1px solid %(border)s; background: %(card)s; }

  /* --- hero: the 10%% black block --- */
  .hero { display: grid; grid-template-columns: 132px 1fr auto; gap: 28px; align-items: center;
          background: %(black)s; color: %(reverse)s; padding: 32px 28px; margin-top: 32px; }
  .hero .kicker { font-size: 10px; letter-spacing: .28em; color: #b9b9b2; margin-bottom: 10px; }
  .hero h2 { font-size: 40px; font-weight: 700; letter-spacing: .08em; }
  .hero .sub { color: #d6d6cf; font-size: 13px; margin-top: 8px; }
  .hero .num { text-align: right; padding-left: 28px; }
  .hero .num + .num { border-left: 1px solid #3a3a35; }
  .hero .n { display: block; font-size: 44px; font-weight: 600; line-height: 1; }
  .hero .l { display: block; font-size: 10px; letter-spacing: .2em; color: #b9b9b2; margin-top: 8px; }

  /* --- sections --- */
  section { margin-top: 40px; }
  .sec-head { display: flex; align-items: baseline; justify-content: space-between;
              border-bottom: 1px solid %(border)s; padding-bottom: 10px; margin-bottom: 20px; }
  .sec-head h3 { font-size: 15px; font-weight: 650; letter-spacing: .1em; }
  .sec-head .counts { font-size: 11px; color: %(text2)s; }

  /* --- stage / band counters --- */
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .cell { border: 1px solid %(border)s; background: %(card)s; padding: 16px 18px; }
  .cell .big { font-size: 34px; font-weight: 600; line-height: 1.05; }
  .cell .lab { font-size: 11px; letter-spacing: .18em; color: %(text2)s; margin-top: 8px; }
  .cell .note { font-size: 11px; color: %(text2)s; margin-top: 4px; }

  /* --- entries --- */
  .rows { list-style: none; margin-top: 20px; }
  .row { display: flex; align-items: baseline; gap: 12px; border: 1px solid %(border)s;
         background: %(card)s; padding: 12px 14px; }
  .row + .row { margin-top: 6px; }
  .row .txt { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row .when { font-size: 11px; color: %(text2)s; white-space: nowrap; }
  .badge { font-size: 10px; letter-spacing: .14em; padding: 2px 7px; border: 1px solid %(text)s; white-space: nowrap; }
  .badge.intel  { background: transparent; }
  .badge.idea   { color: %(text)s;
                  background-image: repeating-conic-gradient(%(text)s 0 25%%, transparent 0 50%%);
                  background-size: 12px 12px; }
  .badge.plan   { background: %(text)s; color: %(card)s; }

  /* --- stables --- */
  .proj { display: grid; grid-template-columns: 48px 1fr auto; gap: 14px; align-items: center;
          border: 1px solid %(border)s; background: %(card)s; padding: 10px 14px; }
  .proj + .proj { margin-top: 6px; }
  .proj .thumb { width: 48px; height: 48px; border: 1px solid %(border)s; background: %(bg2)s; }
  .proj .name { font-size: 13px; font-weight: 600; }
  .proj .path { font-size: 11px; color: %(text2)s; margin-top: 2px; overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap; }
  .proj .meta { text-align: right; font-size: 10px; color: %(text2)s; white-space: nowrap; }
  .proj .agent { font-size: 11px; color: %(text2)s; margin-top: 4px; }

  /* --- interaction: inversion, checker, disabled --- */
  button, .hover-inv { transition: none; }
  .hover-inv:hover { background: %(text)s; color: %(card)s; }
  .hover-inv:hover .sec { color: #c9c9c2; }
  .checker { background-image: repeating-conic-gradient(%(text)s 0 25%%, transparent 0 50%%);
             background-size: 8px 8px; }
  .off { opacity: .42; }
  .press:active { color: %(card)s;
                  background-image: repeating-conic-gradient(%(text)s 0 25%%, transparent 0 50%%);
                  background-size: 6px 6px; }

  /* --- frame-like motion: outline first, then details; dots develop --- */
  @keyframes framein { 0%% { opacity: 0; } 20%% { opacity: .2; } 100%% { opacity: 1; } }
  @keyframes develop { from { opacity: 0; } to { opacity: 1; } }
  .frame { animation: framein .45s steps(6, end) both; }
  .frame.d1 { animation-delay: .06s; }
  .frame.d2 { animation-delay: .14s; }
  .frame.d3 { animation-delay: .22s; }
  .reveal { background-color: %(bg2)s;
            background-image: radial-gradient(%(text)s 1px, transparent 1px);
            background-size: 14px 14px; }
  .reveal img { animation: develop .5s steps(8, end) both; }
  @keyframes dots { 0%% { background-size: 24px 24px; opacity: .35; } 100%% { background-size: 14px 14px; opacity: 1; } }

  /* --- empty state --- */
  .empty { border: 1px dashed %(border)s; background: %(card)s; padding: 28px 20px;
           text-align: center; color: %(text2)s; font-size: 13px; }

  footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid %(border)s;
           font-size: 10px; color: %(text2)s; letter-spacing: .08em; }

  @media (max-width: 640px) {
    .hero { grid-template-columns: 1fr; }
    .hero .num { text-align: left; padding-left: 0; }
    .hero .num + .num { border-left: 0; padding-top: 14px; }
    .proj { grid-template-columns: 40px 1fr; }
    .proj .meta { text-align: left; grid-column: 2; }
  }
""" % {
    "bg": C_BG,
    "bg2": C_BG2,
    "card": C_CARD,
    "text": C_TEXT,
    "text2": C_TEXT2,
    "border": C_BORDER,
    "black": C_BLACK,
    "reverse": C_REVERSE,
}


# ---------------------------------------------------------------- dithering


def dither_1bit(img: "Image.Image", size: int | None = None) -> "Image.Image":
    g = img.convert("L")
    if size:
        g = g.resize((size, size), Image.LANCZOS)
    return g.convert("1", dither=Image.FLOYDSTEINBERG)


def dither_4gray_bayer(img: "Image.Image", size: int | None = None) -> "Image.Image":
    g = img.convert("L")
    if size:
        g = g.resize((size, size), Image.LANCZOS)
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    out = Image.new("L", g.size)
    gp, op = g.load(), out.load()
    for y in range(g.height):
        for x in range(g.width):
            v = gp[x, y] * (3.0 / 255.0) + bayer[y % 4][x % 4] / 16.0
            op[x, y] = min(3, int(v)) * 85
    return out


def png_data_uri(img: "Image.Image") -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def load_icon() -> "Image.Image | None":
    if not HAS_PIL:
        return None
    here = Path(__file__).resolve().parent.parent
    candidates = (here / "assets" / "daqi-icon.png", here.parent / "assets" / "daqi-icon.png")
    path = next((c for c in candidates if c.is_file()), None)
    if path is None:
        return None
    try:
        return Image.open(path)
    except OSError:
        return None


# ------------------------------------------------------------------ parsing


def is_placeholder(value: str) -> bool:
    value = value.strip()
    return not value or value in {"—", "-", "<空>"} or (
        value.startswith("<") and value.endswith(">")
    )


def parse_self(text: str) -> dict:
    result = {"traits": [], "goals": []}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            title = line[3:].strip().lower()
            section = "traits" if title.startswith(("你的档案", "your profile")) else (
                "goals" if title in {"长期目标", "long-term goals"} else None
            )
            continue
        if section == "traits" and line.startswith("-"):
            body = line[1:].strip()
            parts = re.split(r"[:：]", body, maxsplit=1)
            if len(parts) == 2 and not is_placeholder(parts[1]):
                result["traits"].append({"label": parts[0].strip(), "value": parts[1].strip()})
        elif section == "goals" and line and not line.startswith(">"):
            value = line.removeprefix("- ").strip()
            if not is_placeholder(value):
                result["goals"].append(value)
    return result


NOW_SECTIONS = {
    "goal": "goal",
    "verified now": "verified",
    "next": "next",
    "done when": "done_when",
}


def parse_now(text: str) -> dict:
    chunks = {key: [] for key in NOW_SECTIONS.values()}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = NOW_SECTIONS.get(line[3:].strip().lower())
            continue
        if current and line and not line.startswith("---"):
            chunks[current].append(line.removeprefix("- ").strip())
    return {
        key: " ".join(value) if value and not is_placeholder(" ".join(value)) else ""
        for key, value in chunks.items()
    }


def classify_activity(value: str, today: datetime.date) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value or "")
    if not match:
        return "unknown"
    try:
        days = (today - datetime.date.fromisoformat(match.group())).days
    except ValueError:
        return "unknown"
    if days < 0:
        return "unknown"
    if days < 7:
        return "riding"
    if days < 30:
        return "week"
    return "month"


def parse_pool(text: str) -> tuple[list[dict], list[str]]:
    """Return ledger entries plus parse warnings. Stores are only read here."""
    entries, warnings = [], []
    zh = re.compile(r"^\s*-\s*阶段[:：]\s*([^｜|]+?)\s*[｜|](.*)$")
    en = re.compile(r"^\s*-\s*stage:\s*([^|]+?)\s*\|(.*)$")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        m = zh.match(line) or en.match(line)
        if not m:
            continue
        token = m.group(1).strip()
        stage = STAGE_TOKENS.get(token)
        if stage is None:
            warnings.append(f"POOL line {lineno}: unknown stage {token!r}")
            stage = "idea"
        rest = m.group(2).strip()
        parts = [p.strip() for p in re.split(r"[｜|]", rest)]
        text_part = parts[0] if parts else ""
        last_seen = parts[-1] if len(parts) > 1 else ""
        entries.append({"stage": stage, "text": text_part, "last_seen": last_seen})
    return entries, warnings


def parse_shelf(text: str) -> tuple[dict[str, list[dict]], list[str]]:
    bands: dict[str, list[dict]] = {key: [] for key, _ in BANDS}
    warnings: list[str] = []
    current = "riding"
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^##\s*(?:[🟢🟡🔴]\s*)?(.+)$", line)
        if m:
            token = m.group(1).strip()
            if token in BAND_TOKENS:
                current = BAND_TOKENS[token]
            elif token.lower() in ("stables", "马厩"):
                continue
            else:
                warnings.append(f"SHELF: unknown band header {token!r}")
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        first = cells[0]
        if first in ("项目", "Project") or re.match(r"^\s*-{2,}\s*$", first):
            continue
        name = first or "(未命名)"
        path = cells[1] if len(cells) > 1 else ""
        last = cells[2] if len(cells) > 2 else ""
        agent = cells[3] if len(cells) > 3 else ""
        bands[current].append({"name": name, "path": path, "last": last, "agent": agent})
    return bands, warnings


def flatten_projects(bands: dict[str, list[dict]]) -> list[dict]:
    return [dict(project) for key, _ in BANDS for project in bands[key]]


def enrich_projects(projects: list[dict], today: datetime.date) -> tuple[list[dict], list[str]]:
    enriched = []
    warnings = []
    for project in projects:
        item = dict(project)
        item["display_band"] = classify_activity(item.get("last", ""), today)
        item["now"] = None
        path = item.get("path", "")
        if path:
            now_path = Path(path) / "00_Context" / "NOW.md"
            try:
                if now_path.is_file():
                    item["now"] = parse_now(now_path.read_text())
            except OSError as exc:
                warnings.append(f"NOW unavailable for {item.get('name', '(未命名)')}: {exc}")
        enriched.append(item)
    return enriched, warnings


# ------------------------------------------------------------------ render


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def badge_html(stage: str) -> str:
    return f'<span class="badge {esc(stage)}">{esc(stage)}</span>'


def render_html(store: Path, pool: list[dict], bands: dict[str, list[dict]],
                warnings: list[str], gen_ts: datetime.datetime) -> str:
    counts = {key: 0 for key, _ in STAGE_ORDER}
    for e in pool:
        counts[e["stage"]] += 1
    total_ideas = sum(counts.values())
    band_counts = {key: len(bands[key]) for key, _ in BANDS}
    total_projects = sum(band_counts.values())
    archive_id = "ARCHIVE_" + hashlib.sha1(str(store).encode()).hexdigest()[:4].upper()

    icon = load_icon()
    if icon is not None:
        hero_img = png_data_uri(dither_1bit(icon, 96))
        thumb_img = png_data_uri(dither_4gray_bayer(icon, 40))
        mark_img = png_data_uri(dither_1bit(icon, 48))
    else:
        hero_img = thumb_img = mark_img = None

    updated = max(
        (p.stat().st_mtime for p in (store / "POOL.md", store / "SHELF.md") if p.is_file()),
        default=gen_ts.timestamp(),
    )
    updated_s = datetime.datetime.fromtimestamp(updated).strftime("%Y.%m.%d %H:%M")

    hero = (
        f'<div class="reveal">{hero_img and f"<img class=\"dither\" width=\"96\" height=\"96\" src=\"{hero_img}\" alt=\"dither mark\">"}</div>'
        if hero_img
        else f'<div class="checker" style="width:96px;height:96px"></div>'
    )

    # stage counters
    stage_cells = []
    stage_descs = {"intel": "痛点 · 观察 · 先盯着", "idea": "意图 · 假设 · 待养成", "plan": "证据齐了 · 等出发"}
    for key, label in STAGE_ORDER:
        stage_cells.append(
            f'<div class="cell hover-inv press">'
            f'<div class="big mono">{counts[key]}</div>'
            f'<div class="lab mono">{esc(label)} / {key.upper()}</div>'
            f'<div class="note">{stage_descs[key]}</div></div>'
        )

    # ledger rows
    pool_rows = ""
    for e in pool:
        label = dict(STAGE_ORDER)[e["stage"]]
        pool_rows += (
            f'<li class="row"><span class="badge {esc(e["stage"])}">{esc(label)}</span>'
            f'<span class="txt" title="{esc(e["text"])}">{esc(e["text"])}</span>'
            f'<span class="when mono">{esc(e["last_seen"]) or "—"}</span></li>'
        )
    pool_block = (
        f'<ul class="rows">{"".join(pool_rows)}</ul>'
        if pool
        else '<div class="empty">账本还是空的。说「我发现……」记情报，说「我想做……」记点子。</div>'
    )

    # band counters + rows
    band_cells = []
    band_descs = {"riding": "<3 天活跃", "loose": "3–14 天", "stabled": ">14 天"}
    for key, label in BANDS:
        band_cells.append(
            f'<div class="cell hover-inv press">'
            f'<div class="big mono">{band_counts[key]}</div>'
            f'<div class="lab mono">{esc(label)} / {key.upper()}</div>'
            f'<div class="note">{band_descs[key]}</div></div>'
        )

    proj_rows = ""
    for key, label in BANDS:
        for p in bands[key]:
            thumb = (
                f'<div class="thumb"><img class="dither" width="40" height="40" src="{thumb_img}" alt=""></div>'
                if thumb_img
                else f'<div class="thumb checker"></div>'
            )
            proj_rows += (
                f'<div class="proj hover-inv">{thumb}'
                f'<div><div class="name">{esc(p["name"])}</div>'
                f'<div class="path mono" title="{esc(p["path"])}">{esc(p["path"]) or "—"}</div></div>'
                f'<div class="meta"><div class="mono">{esc(label)}</div>'
                f'<div class="agent mono">{esc(p["last"]) or "—"} · {esc(p["agent"]) or "—"}</div></div></div>'
            )
    shelf_block = (
        f'<div style="margin-top:20px">{"".join(proj_rows)}</div>'
        if proj_rows
        else '<div class="empty">马厩还是空的。计划成熟后，你说「出发」才会立项目。</div>'
    )

    warn_block = ""
    if warnings:
        warn_block = (
            '<div class="empty" style="margin-top:20px;text-align:left">'
            + "".join(f'<div class="mono">{esc(w)}</div>' for w in warnings)
            + "</div>"
        )

    mark = mark_img and f'<img class="dither" width="48" height="48" src="{mark_img}" alt="">'
    return f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>营地档案 · CAMP ARCHIVE</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<div class="page">
  <header class="top frame">
    <div class="mark">{mark or ''}</div>
    <div>
      <h1>营地档案 <span class="sec mono">CAMP ARCHIVE</span></h1>
      <div class="meta mono">{archive_id} · UPDATED {updated_s} · STATUS / ACTIVE · READ-ONLY</div>
    </div>
  </header>

  <section class="hero frame d1">
    <div>{hero}</div>
    <div>
      <div class="kicker mono">GRAYSCALE DITHER ARCHIVE — 灰阶点阵档案</div>
      <h2>点子王</h2>
      <p class="sub">痛点记成情报，点子养出计划。达奇不会背叛你。</p>
    </div>
    <div style="display:flex">
      <div class="num"><span class="n mono">{total_ideas}</span><span class="l mono">IDEAS / 点子</span></div>
      <div class="num"><span class="n mono">{total_projects}</span><span class="l mono">PROJECTS / 项目</span></div>
    </div>
  </section>

  <section class="frame d1">
    <div class="sec-head">
      <h3>账本 <span class="sec mono">POOL</span></h3>
      <div class="counts mono">情报 {counts["intel"]} · 点子 {counts["idea"]} · 计划 {counts["plan"]} / 共 {total_ideas}</div>
    </div>
    <div class="grid">{''.join(stage_cells)}</div>
    {pool_block}
  </section>

  <section class="frame d2">
    <div class="sec-head">
      <h3>马厩 <span class="sec mono">SHELF</span></h3>
      <div class="counts mono">在跑 {band_counts["riding"]} · 松了 {band_counts["loose"]} · 歇马 {band_counts["stabled"]} / 共 {total_projects}</div>
    </div>
    <div class="grid">{''.join(band_cells)}</div>
    {shelf_block}
    {warn_block}
  </section>

  <footer class="mono frame d3">READ-ONLY · 数据来自 {esc(str(store / "POOL.md"))} 与 {esc(str(store / "SHELF.md"))} · 生成于 {gen_ts.strftime("%Y.%m.%d %H:%M:%S")} · 未写入任何 store</footer>
</div>
</body>
</html>
"""


# ------------------------------------------------------------------- main


def summarize(store: Path, pool: list[dict], bands: dict[str, list[dict]], out: Path,
              warnings: list[str]) -> str:
    counts = {key: 0 for key, _ in STAGE_ORDER}
    for e in pool:
        counts[e["stage"]] += 1
    total_ideas = sum(counts.values())
    band_counts = {key: len(bands[key]) for key, _ in BANDS}
    total_projects = sum(band_counts.values())
    lines = ["点子王，营地清点完毕："]
    lines.append(
        f"账本 — 情报 {counts['intel']} · 点子 {counts['idea']} · 计划 {counts['plan']}（共 {total_ideas}）"
    )
    lines.append(
        f"马厩 — 在跑 {band_counts['riding']} · 松了 {band_counts['loose']} · 歇马 {band_counts['stabled']}（共 {total_projects}）"
    )
    if total_ideas == 0 and total_projects == 0:
        lines.append("账本和马厩还是空的。说「我发现……」记情报，「我想做……」记点子。")
    if warnings:
        lines.append("解析提示：")
        lines.extend(f"  - {w}" for w in warnings)
    lines.append(f"档案：{out}（只读，未写入任何 store）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the read-only camp archive view.")
    default_store = os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi")
    parser.add_argument("--store", default=default_store, help=f"camp store dir (default {default_store})")
    parser.add_argument("--out", default=None, help="output HTML path (default <store>/camp.html)")
    args = parser.parse_args(argv)

    store = Path(args.store)
    out = Path(args.out) if args.out else store / "camp.html"

    pool_path, shelf_path = store / "POOL.md", store / "SHELF.md"
    if not pool_path.is_file() or not shelf_path.is_file():
        print(f"营地不完整：需要 {pool_path} 和 {shelf_path}", file=sys.stderr)
        return 2

    pool, warn_pool = parse_pool(pool_path.read_text())
    bands, warn_shelf = parse_shelf(shelf_path.read_text())
    warnings = warn_pool + warn_shelf

    gen_ts = datetime.datetime.now()
    html_text = render_html(store, pool, bands, warnings, gen_ts)
    out.write_text(html_text)

    print(summarize(store, pool, bands, out, warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
