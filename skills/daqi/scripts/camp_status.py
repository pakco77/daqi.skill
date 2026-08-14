#!/usr/bin/env python3
"""Render the read-only, self-contained Mono Dither camp scene.

POOL, SHELF, optional SELF, and exact project NOW files are inputs. The only
write is the derived HTML at --out (default <store>/camp.html), and output/input
identity collisions are rejected before rendering.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import datetime
from pathlib import Path

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
BAND_TOKENS = {
    "在跑": "riding",
    "松了": "loose",
    "歇马": "stabled",
    "Riding": "riding",
    "Loose rein": "loose",
    "Stabled": "stabled",
}

SCENE_CSS = r"""
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  html, body { width: 100%; height: 100%; margin: 0; }
  body {
    overflow: hidden;
    background: #050505;
    color: #111111;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  button { font: inherit; }
  .camp-mono {
    font-family: ui-monospace, "SF Mono", Menlo, Monaco, Consolas, monospace;
    font-variant-numeric: tabular-nums;
  }
  .camp-app {
    position: relative;
    width: 100vw;
    height: 100vh;
    min-width: 960px;
    min-height: 640px;
    overflow: hidden;
    isolation: isolate;
    background: #050505;
  }
  .camp-world {
    position: absolute;
    inset: 0;
    transform-origin: 50% 62%;
    transform: translate(0, 0) scale(1);
    transition: transform 620ms steps(7, end);
    will-change: transform;
  }
  .camp-scene-image {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    image-rendering: pixelated;
    transition: opacity 360ms steps(5, end);
  }
  .camp-scene-day { opacity: 0; }
  .camp-app[data-time="day"] .camp-scene-day { opacity: 1; }
  .camp-app[data-time="day"] .camp-scene-night { opacity: 0; }
  .camp-app[data-view="ledger"] .camp-world { transform: translate(18%, 1%) scale(1.48); }
  .camp-app[data-view="stable"] .camp-world { transform: translate(-18%, 1%) scale(1.48); }
  .camp-app[data-view="self"] .camp-world { transform: translate(0, -9%) scale(1.44); }

  .camp-topbar {
    position: absolute;
    z-index: 8;
    top: 24px;
    left: 28px;
    right: 28px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    pointer-events: none;
  }
  .camp-brand {
    color: #F5F5F2;
    text-shadow: 0 1px #050505;
  }
  .camp-app[data-time="day"] .camp-brand { color: #111111; text-shadow: none; }
  .camp-brand strong {
    display: block;
    font-size: 17px;
    font-weight: 680;
    letter-spacing: .16em;
  }
  .camp-brand span {
    display: block;
    margin-top: 5px;
    font-size: 10px;
    letter-spacing: .12em;
    opacity: .72;
  }
  .camp-timebox {
    pointer-events: auto;
    display: flex;
    align-items: stretch;
    border: 1px solid #111111;
    background: #FAFAF7;
  }
  .camp-timebox button {
    min-width: 48px;
    min-height: 34px;
    padding: 0 10px;
    border: 0;
    border-right: 1px solid #C9C9C2;
    background: #FAFAF7;
    color: #111111;
    cursor: pointer;
    font-size: 10px;
    letter-spacing: .08em;
  }
  .camp-timebox button:hover,
  .camp-timebox button[aria-pressed="true"] {
    background: #111111;
    color: #F5F5F2;
  }
  .camp-local-time {
    display: grid;
    min-width: 82px;
    place-items: center;
    padding: 0 10px;
    color: #72726C;
    font-size: 10px;
    letter-spacing: .08em;
  }

  .camp-feature {
    position: absolute;
    z-index: 5;
    display: grid;
    gap: 2px;
    min-width: 146px;
    padding: 10px 12px;
    border: 1px solid #C9C9C2;
    border-radius: 1px;
    background: #FAFAF7;
    color: #111111;
    text-align: left;
    cursor: pointer;
    transition: opacity 180ms steps(3, end), background-color 0ms, color 0ms;
  }
  .camp-feature:hover,
  .camp-feature:focus-visible {
    outline: none;
    border-color: #111111;
    background: #111111;
    color: #F5F5F2;
  }
  .camp-feature strong { font-size: 14px; font-weight: 700; letter-spacing: .04em; }
  .camp-feature span { font-size: 10px; letter-spacing: .1em; opacity: .72; }
  .camp-feature-ledger { left: 8%; top: 62%; }
  .camp-feature-self { left: 45%; top: 73%; }
  .camp-feature-stable { right: 7%; top: 61%; }
  .camp-app:not([data-view="overview"]) .camp-feature { opacity: 0; pointer-events: none; }

  .camp-fire {
    position: absolute;
    z-index: 4;
    left: 50%;
    top: 73.5%;
    width: 34px;
    height: 48px;
    transform: translate(-50%, -100%);
    pointer-events: none;
    mix-blend-mode: screen;
  }
  .camp-flame {
    position: absolute;
    bottom: 0;
    left: 50%;
    background: #D9BC72;
    clip-path: polygon(50% 0, 76% 39%, 66% 100%, 34% 100%, 20% 48%);
    transform: translateX(-50%);
    transform-origin: 50% 100%;
    animation: camp-burn 680ms steps(5, end) infinite alternate;
  }
  .camp-flame-a { width: 18px; height: 40px; opacity: .72; }
  .camp-flame-b { width: 10px; height: 27px; opacity: .95; animation-delay: -240ms; }
  @keyframes camp-burn {
    0% { transform: translateX(-50%) scale(.82, .9) skewX(-4deg); }
    45% { transform: translateX(-50%) scale(1, 1.08) skewX(3deg); }
    100% { transform: translateX(-50%) scale(.9, .96) skewX(-2deg); }
  }

  .camp-back {
    position: absolute;
    z-index: 10;
    left: 28px;
    bottom: 26px;
    min-height: 36px;
    padding: 0 13px;
    border: 1px solid #111111;
    border-radius: 1px;
    background: #FAFAF7;
    color: #111111;
    cursor: pointer;
    font-size: 11px;
  }
  .camp-back:hover { background: #111111; color: #F5F5F2; }
  .camp-back[hidden] { display: none; }

  .camp-panel {
    position: absolute;
    z-index: 9;
    top: 15%;
    width: clamp(420px, 39vw, 560px);
    max-height: 72vh;
    overflow: hidden;
    border: 1px solid #111111;
    border-radius: 1px;
    background: #FAFAF7;
    color: #111111;
    opacity: 1;
    transform: translateY(0);
    animation: camp-panel-in 300ms steps(5, end) both;
  }
  .camp-panel[hidden] { display: none; }
  .camp-panel:focus { outline: none; }
  .camp-panel-ledger, .camp-panel-self { right: 5%; }
  .camp-panel-stable { left: 5%; }
  @keyframes camp-panel-in {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .camp-panel-head {
    padding: 20px 22px 16px;
    border-bottom: 1px solid #C9C9C2;
  }
  .camp-panel-head h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: .04em; }
  .camp-panel-head p { margin: 5px 0 0; color: #72726C; font-size: 11px; letter-spacing: .08em; }
  .camp-panel-body { padding: 16px 22px 20px; }
  .camp-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
  .camp-tag {
    position: relative;
    min-height: 30px;
    padding: 0 10px;
    border: 1px solid #C9C9C2;
    border-radius: 1px;
    background: #FAFAF7;
    color: #111111;
    cursor: pointer;
    font-size: 11px;
  }
  .camp-tag:hover { border-color: #111111; }
  .camp-tag[aria-pressed="true"] {
    border-color: #111111;
    padding-left: 25px;
    background: #111111;
    color: #FAFAF7;
  }
  .camp-tag[aria-pressed="true"]::before {
    content: "";
    position: absolute;
    left: 7px;
    top: 50%;
    width: 10px;
    height: 10px;
    transform: translateY(-50%);
    background-color: #FAFAF7;
    background-image: repeating-conic-gradient(#111111 0 25%, transparent 0 50%);
    background-size: 4px 4px;
  }
  .camp-list { display: grid; gap: 6px; }
  .camp-entry,
  .camp-project {
    width: 100%;
    min-height: 54px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid #C9C9C2;
    border-radius: 1px;
    background: #FAFAF7;
    color: #111111;
    text-align: left;
  }
  .camp-project { cursor: pointer; }
  .camp-project:hover, .camp-project:focus-visible {
    outline: none;
    border-color: #111111;
    background: #111111;
    color: #F5F5F2;
  }
  .camp-item-title { overflow: hidden; font-size: 13px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
  .camp-item-meta { margin-top: 3px; color: #72726C; font-size: 10px; }
  .camp-project:hover .camp-item-meta { color: #C9C9C2; }
  .camp-item-time { color: #72726C; font-size: 10px; white-space: nowrap; }
  .camp-empty {
    padding: 26px 16px;
    border: 1px dashed #C9C9C2;
    color: #72726C;
    text-align: center;
    font-size: 12px;
  }
  .camp-pages { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 12px; }
  .camp-pages button {
    min-height: 28px;
    padding: 0 9px;
    border: 1px solid #C9C9C2;
    background: #FAFAF7;
    cursor: pointer;
    font-size: 10px;
  }
  .camp-pages button:hover:not(:disabled) { background: #111111; color: #F5F5F2; }
  .camp-pages button:disabled { opacity: .4; cursor: default; }
  .camp-pages span { color: #72726C; font-size: 10px; }
  .camp-now { display: grid; gap: 12px; }
  .camp-now section { padding-bottom: 11px; border-bottom: 1px solid #C9C9C2; }
  .camp-now section:last-child { border-bottom: 0; padding-bottom: 0; }
  .camp-now h3 { margin: 0 0 5px; color: #72726C; font-size: 10px; font-weight: 600; letter-spacing: .12em; }
  .camp-now p { margin: 0; font-size: 13px; line-height: 1.55; }
  .camp-profile { display: grid; gap: 8px; }
  .camp-trait { display: grid; grid-template-columns: 92px 1fr; gap: 14px; padding: 9px 0; border-bottom: 1px solid #C9C9C2; }
  .camp-trait dt { color: #72726C; font-size: 11px; }
  .camp-trait dd { margin: 0; font-size: 13px; }
  .camp-goals { margin: 14px 0 0; padding: 14px 0 0 18px; border-top: 1px solid #C9C9C2; }
  .camp-goals li { margin-top: 6px; font-size: 13px; }
  .camp-notice { margin-top: 14px; color: #72726C; font-size: 10px; }
  .camp-a11y { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }

  @media (max-width: 959px) {
    body { overflow: auto; }
    .camp-app { min-width: 0; min-height: 820px; height: auto; }
    .camp-world { height: 62vw; min-height: 430px; position: relative; }
    .camp-topbar { position: absolute; top: 14px; left: 14px; right: 14px; }
    .camp-brand span { display: none; }
    .camp-feature { min-width: 118px; padding: 8px; }
    .camp-feature-ledger { left: 3%; top: 43%; }
    .camp-feature-self { left: 39%; top: 55%; }
    .camp-feature-stable { right: 3%; top: 43%; }
    .camp-panel, .camp-panel-ledger, .camp-panel-stable, .camp-panel-self {
      position: relative;
      inset: auto;
      width: calc(100% - 28px);
      max-height: none;
      margin: 14px;
    }
    .camp-back { position: fixed; left: 14px; bottom: 14px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .camp-world, .camp-scene-image { transition: none; }
    .camp-panel { animation: none; }
    .camp-flame { animation: none; }
  }
"""


SCENE_JS = r"""
(() => {
  const camp = document.querySelector('.camp-app');
  const payload = JSON.parse(document.getElementById('camp-data').textContent);
  const panel = camp.querySelector('.camp-panel');
  const panelTitle = camp.querySelector('.camp-panel-title');
  const panelSub = camp.querySelector('.camp-panel-sub');
  const panelBody = camp.querySelector('.camp-panel-body');
  const backButton = camp.querySelector('[data-action="back"]');
  const live = camp.querySelector('[aria-live]');
  const PAGE_SIZE = 5;
  const storageKey = 'daqi.camp.timeMode';
  const state = {
    view: 'overview',
    stableDepth: 'list',
    ledgerTag: 'intel',
    stableTag: 'riding',
    ledgerPage: 0,
    stablePage: 0,
    timeMode: 'auto',
  };
  let selectedProject = null;

  try {
    const saved = localStorage.getItem(storageKey);
    if (['auto', 'day', 'night'].includes(saved)) state.timeMode = saved;
  } catch (_) {}

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function resolvedTime() {
    if (state.timeMode !== 'auto') return state.timeMode;
    const hour = new Date().getHours();
    return hour >= 6 && hour < 18 ? 'day' : 'night';
  }

  function renderClock() {
    camp.querySelector('.camp-local-time').textContent = new Intl.DateTimeFormat([], {
      hour: '2-digit', minute: '2-digit'
    }).format(new Date());
  }

  function addTags(items, selected, onSelect) {
    const wrap = make('div', 'camp-tags');
    items.forEach((item) => {
      const button = make('button', 'camp-tag', `${item.label} ${item.count}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(item.key === selected));
      button.addEventListener('click', () => onSelect(item.key));
      wrap.append(button);
    });
    panelBody.append(wrap);
  }

  function addEmpty(text) {
    panelBody.append(make('div', 'camp-empty', text));
  }

  function addPages(total, page, onPage) {
    const pages = Math.ceil(total / PAGE_SIZE);
    if (pages <= 1) return;
    const wrap = make('div', 'camp-pages');
    const previous = make('button', '', '上一页');
    const next = make('button', '', '下一页');
    previous.type = next.type = 'button';
    previous.disabled = page <= 0;
    next.disabled = page >= pages - 1;
    previous.addEventListener('click', () => onPage(page - 1));
    next.addEventListener('click', () => onPage(page + 1));
    wrap.append(previous, make('span', 'camp-mono', `${page + 1} / ${pages}`), next);
    panelBody.append(wrap);
  }

  function addNotice() {
    if (!payload.warnings.length) return;
    panelBody.append(make('div', 'camp-notice', `有 ${payload.warnings.length} 条记录暂时无法读取`));
  }

  function renderLedger() {
    panelTitle.textContent = '营地账本';
    panelSub.textContent = '情报 · 点子 · 计划';
    const labels = {intel: '情报', idea: '点子', plan: '计划'};
    const tags = Object.entries(labels).map(([key, label]) => ({
      key, label, count: payload.ledger.filter((item) => item.stage === key).length
    }));
    addTags(tags, state.ledgerTag, (key) => {
      state.ledgerTag = key;
      state.ledgerPage = 0;
      renderState();
    });
    const items = payload.ledger.filter((item) => item.stage === state.ledgerTag);
    if (!items.length) {
      addEmpty('这个阶段还没有条目');
      return;
    }
    const list = make('div', 'camp-list');
    items.slice(state.ledgerPage * PAGE_SIZE, (state.ledgerPage + 1) * PAGE_SIZE).forEach((item) => {
      const row = make('div', 'camp-entry');
      row.append(make('div', 'camp-item-title', item.text || '未命名条目'));
      row.append(make('div', 'camp-item-time camp-mono', item.last_seen || '时间未知'));
      list.append(row);
    });
    panelBody.append(list);
    addPages(items.length, state.ledgerPage, (page) => { state.ledgerPage = page; renderState(); });
  }

  function renderProjectNow() {
    panelTitle.textContent = '这票到哪了';
    panelSub.textContent = selectedProject ? selectedProject.name : '马厩';
    if (!selectedProject || !selectedProject.now) {
      addEmpty('还没有可确认的当前进度');
      return;
    }
    const wrap = make('div', 'camp-now');
    [
      ['目标', selectedProject.now.goal],
      ['已验证', selectedProject.now.verified],
      ['下一步', selectedProject.now.next],
      ['完成条件', selectedProject.now.done_when],
    ].forEach(([label, value]) => {
      const section = make('section');
      section.append(make('h3', 'camp-mono', label), make('p', '', value));
      wrap.append(section);
    });
    panelBody.append(wrap);
  }

  function renderStable() {
    if (state.stableDepth === 'now') {
      renderProjectNow();
      return;
    }
    panelTitle.textContent = '马厩';
    panelSub.textContent = '干一票';
    const definitions = [
      ['riding', '在跑'], ['week', '7 天没动'], ['month', '30 天没动']
    ];
    if (payload.projects.some((item) => item.display_band === 'unknown')) {
      definitions.push(['unknown', '时间未知']);
    }
    const tags = definitions.map(([key, label]) => ({
      key, label, count: payload.projects.filter((item) => item.display_band === key).length
    }));
    addTags(tags, state.stableTag, (key) => {
      state.stableTag = key;
      state.stablePage = 0;
      renderState();
    });
    const projects = payload.projects.filter((item) => item.display_band === state.stableTag);
    if (!projects.length) {
      addEmpty('这个时间段没有项目');
      addNotice();
      return;
    }
    const list = make('div', 'camp-list');
    projects.slice(state.stablePage * PAGE_SIZE, (state.stablePage + 1) * PAGE_SIZE).forEach((project) => {
      const row = make('button', 'camp-project');
      row.type = 'button';
      const main = make('div');
      main.append(make('div', 'camp-item-title', project.name || '未命名项目'));
      main.append(make('div', 'camp-item-meta camp-mono', `Agent · ${project.agent || '未知'}`));
      row.append(main, make('div', 'camp-item-time camp-mono', project.last || '时间未知'));
      row.addEventListener('click', () => {
        selectedProject = project;
        state.stableDepth = 'now';
        renderState();
      });
      list.append(row);
    });
    panelBody.append(list);
    addPages(projects.length, state.stablePage, (page) => { state.stablePage = page; renderState(); });
    addNotice();
  }

  function renderProfile() {
    panelTitle.textContent = '达奇对你的认知';
    panelSub.textContent = '';
    if (!payload.profile.traits.length && !payload.profile.goals.length) {
      addEmpty('现在还认不出你');
      return;
    }
    if (payload.profile.traits.length) {
      const list = make('dl', 'camp-profile');
      payload.profile.traits.forEach((item) => {
        const row = make('div', 'camp-trait');
        row.append(make('dt', '', item.label), make('dd', '', item.value));
        list.append(row);
      });
      panelBody.append(list);
    }
    if (payload.profile.goals.length) {
      const goals = make('ul', 'camp-goals');
      payload.profile.goals.forEach((goal) => goals.append(make('li', '', goal)));
      panelBody.append(goals);
    }
  }

  function renderPanel() {
    panelBody.replaceChildren();
    panel.className = `camp-panel camp-panel-${state.view}`;
    if (state.view === 'ledger') renderLedger();
    if (state.view === 'stable') renderStable();
    if (state.view === 'self') renderProfile();
  }

  function renderState() {
    camp.dataset.view = state.view;
    camp.dataset.time = resolvedTime();
    backButton.hidden = state.view === 'overview';
    panel.hidden = state.view === 'overview';
    camp.querySelectorAll('.camp-feature').forEach((button) => {
      const available = state.view === 'overview';
      button.setAttribute('aria-expanded', String(button.dataset.view === state.view));
      button.setAttribute('aria-hidden', String(!available));
      button.tabIndex = available ? 0 : -1;
    });
    camp.querySelectorAll('[data-time-mode]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.timeMode === state.timeMode));
    });
    if (state.view !== 'overview') renderPanel();
    live.textContent = state.view === 'overview' ? '营地全景' : panelTitle.textContent;
    renderClock();
  }

  function openView(view) {
    state.view = view;
    state.stableDepth = 'list';
    selectedProject = null;
    renderState();
    requestAnimationFrame(() => panel.focus({preventScroll: true}));
  }

  function goBackOneLevel() {
    if (state.view === 'stable' && state.stableDepth === 'now') {
      state.stableDepth = 'list';
      selectedProject = null;
    } else if (state.view !== 'overview') {
      state.view = 'overview';
    }
    renderState();
  }

  camp.querySelectorAll('.camp-feature').forEach((button) => {
    button.addEventListener('click', () => openView(button.dataset.view));
  });
  backButton.addEventListener('click', goBackOneLevel);
  camp.querySelectorAll('[data-time-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      state.timeMode = button.dataset.timeMode;
      try { localStorage.setItem(storageKey, state.timeMode); } catch (_) {}
      renderState();
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.view !== 'overview') goBackOneLevel();
  });

  let wheelTotal = 0;
  let wheelLocked = false;
  let wheelTimer;
  camp.addEventListener('wheel', (event) => {
    if (event.deltaY <= 0 || state.view === 'overview') return;
    event.preventDefault();
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(() => { wheelTotal = 0; wheelLocked = false; }, 220);
    if (wheelLocked) return;
    wheelTotal += event.deltaY;
    if (wheelTotal >= 48) {
      wheelLocked = true;
      goBackOneLevel();
    }
  }, {passive: false});

  setInterval(() => {
    if (state.timeMode === 'auto') camp.dataset.time = resolvedTime();
    renderClock();
  }, 60000);
  renderState();
})();
"""


# ------------------------------------------------------------------ assets


def asset_data_uri(name: str) -> str:
    path = Path(__file__).resolve().parent.parent / "assets" / name
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


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
                "goals" if title in {"长期目标", "long-term goals", "durable goals"} else None
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


def classify_activity(value: str, now: datetime.date | datetime.datetime) -> str:
    value = (value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            active_date = datetime.date.fromisoformat(value)
        except ValueError:
            return "unknown"
        current_date = now.date() if isinstance(now, datetime.datetime) else now
        days = (current_date - active_date).days
    else:
        try:
            active_at = datetime.datetime.fromisoformat(
                value[:-1] + "+00:00" if value.endswith("Z") else value
            )
        except ValueError:
            return "unknown"
        if (
            not isinstance(now, datetime.datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
            or active_at.tzinfo is None
            or active_at.utcoffset() is None
        ):
            return "unknown"
        elapsed_seconds = (
            now.astimezone(datetime.timezone.utc) - active_at.astimezone(datetime.timezone.utc)
        ).total_seconds()
        if elapsed_seconds < 0:
            return "unknown"
        days = int(elapsed_seconds // 86400)

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


def enrich_projects(projects: list[dict], now: datetime.date | datetime.datetime) -> tuple[list[dict], list[str]]:
    enriched = []
    warnings = []
    for project in projects:
        item = dict(project)
        item["display_band"] = classify_activity(item.get("last", ""), now)
        item["now"] = None
        path = item.get("path", "")
        if path:
            now_path = Path(path) / "00_Context" / "NOW.md"
            try:
                if now_path.is_file():
                    checkpoint = parse_now(now_path.read_text(encoding="utf-8"))
                    if all(checkpoint.values()):
                        item["now"] = checkpoint
                    else:
                        warnings.append(
                            f"NOW has no complete checkpoint for {item.get('name', '(未命名)')}"
                        )
            except (OSError, UnicodeError) as exc:
                warnings.append(f"NOW unavailable for {item.get('name', '(未命名)')}: {exc}")
        enriched.append(item)
    return enriched, warnings


def paths_share_identity(left: Path, right: Path) -> bool:
    try:
        if left.resolve(strict=False) == right.resolve(strict=False):
            return True
    except (OSError, RuntimeError):
        if left.absolute() == right.absolute():
            return True
    try:
        return left.samefile(right)
    except OSError:
        return False


# ------------------------------------------------------------------ render


def render_html(store: Path, pool: list[dict], projects: list[dict], profile: dict,
                      warnings: list[str], gen_ts: datetime.datetime) -> str:
    """Render one self-contained scene; all user data stays in inert JSON."""
    payload = {
        "ledger": pool,
        "projects": projects,
        "profile": profile,
        "warnings": warnings,
        "generated_at": gen_ts.isoformat(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    night = asset_data_uri("camp-night.png")
    day = asset_data_uri("camp-day.png")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>达奇营地</title>
<style>{SCENE_CSS}</style>
</head>
<body>
<main class="camp-app" data-view="overview" data-time="night">
  <div class="camp-world" aria-hidden="true">
    <img class="camp-scene-image camp-scene-night" src="{night}" alt="">
    <img class="camp-scene-image camp-scene-day" src="{day}" alt="">
    <div class="camp-fire">
      <i class="camp-flame camp-flame-a"></i>
      <i class="camp-flame camp-flame-b"></i>
    </div>
  </div>

  <header class="camp-topbar">
    <div class="camp-brand">
      <strong>达奇营地</strong>
      <span class="camp-mono">MONO DITHER ARCHIVE</span>
    </div>
    <div class="camp-timebox" aria-label="场景时间">
      <button type="button" data-action="time-auto" data-time-mode="auto">自动</button>
      <button type="button" data-action="time-day" data-time-mode="day">白天</button>
      <button type="button" data-action="time-night" data-time-mode="night">夜晚</button>
      <span class="camp-local-time camp-mono" aria-label="你的本地时间"></span>
    </div>
  </header>

  <button type="button" class="camp-feature camp-feature-ledger" data-view="ledger" aria-expanded="false">
    <strong>营地账本</strong><span>情报 · 点子 · 计划</span>
  </button>
  <button type="button" class="camp-feature camp-feature-self" data-view="self" aria-expanded="false">
    <strong>火</strong><span>你是谁？</span>
  </button>
  <button type="button" class="camp-feature camp-feature-stable" data-view="stable" aria-expanded="false">
    <strong>马厩</strong><span>干一票</span>
  </button>

  <button type="button" class="camp-back" data-action="back" hidden>返回上一层 ↓</button>
  <section class="camp-panel" tabindex="-1" aria-labelledby="camp-panel-title" hidden>
    <header class="camp-panel-head">
      <h2 class="camp-panel-title" id="camp-panel-title"></h2>
      <p class="camp-panel-sub"></p>
    </header>
    <div class="camp-panel-body"></div>
  </section>
  <div class="camp-a11y" aria-live="polite"></div>
</main>
<script type="application/json" id="camp-data">{payload_json}</script>
<script>{SCENE_JS}</script>
</body>
</html>
"""


# ------------------------------------------------------------------- main


def summarize(store: Path, pool: list[dict], projects: list[dict], out: Path,
              warnings: list[str]) -> str:
    counts = {key: 0 for key, _ in STAGE_ORDER}
    for e in pool:
        counts[e["stage"]] += 1
    total_ideas = sum(counts.values())
    band_counts = {key: 0 for key, _ in BANDS}
    legacy_band = {"riding": "riding", "week": "loose", "month": "stabled", "unknown": "stabled"}
    for project in projects:
        band_counts[legacy_band[project["display_band"]]] += 1
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

    gen_ts = datetime.datetime.now().astimezone()
    pool, warn_pool = parse_pool(pool_path.read_text())
    bands, warn_shelf = parse_shelf(shelf_path.read_text())
    flat_projects = flatten_projects(bands)
    self_path = store / "SELF.md"
    readonly_inputs = [pool_path, shelf_path, self_path]
    readonly_inputs.extend(
        Path(project["path"]) / "00_Context" / "NOW.md"
        for project in flat_projects
        if project.get("path")
    )
    conflict = next((path for path in readonly_inputs if paths_share_identity(out, path)), None)
    if conflict is not None:
        print(f"输出路径与只读输入冲突：{out} -> {conflict}", file=sys.stderr)
        return 2

    profile = parse_self(self_path.read_text()) if self_path.is_file() else {"traits": [], "goals": []}
    projects, warn_now = enrich_projects(flat_projects, gen_ts)
    warnings = warn_pool + warn_shelf + warn_now

    html_text = render_html(store, pool, projects, profile, warnings, gen_ts)
    out.write_text(html_text)

    print(summarize(store, pool, projects, out, warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
