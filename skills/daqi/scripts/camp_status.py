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
    transform: translate3d(0, 0, 0) scale(1);
    transition: transform 520ms cubic-bezier(.2, .72, .22, 1);
    will-change: transform;
    backface-visibility: hidden;
    contain: layout paint;
  }
  .camp-zoom-layer {
    --camp-wheel-zoom: 1;
    --camp-zoom-x: 50%;
    --camp-zoom-y: 62%;
    position: absolute;
    inset: 0;
    transform: translateZ(0) scale(var(--camp-wheel-zoom));
    transform-origin: var(--camp-zoom-x) var(--camp-zoom-y);
    transition: transform 180ms cubic-bezier(.2, .72, .22, 1);
    will-change: transform;
    backface-visibility: hidden;
  }
  .camp-scene-image {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    image-rendering: pixelated;
    transition: opacity 260ms linear;
    backface-visibility: hidden;
  }
  .camp-scene-night { filter: brightness(.34) contrast(1.2); }
  .camp-scene-day { opacity: 0; }
  .camp-app[data-time="day"] .camp-scene-day { opacity: 1; }
  .camp-app[data-time="day"] .camp-scene-night { opacity: 0; }
  .camp-app[data-view="ledger"] .camp-world { transform: translate3d(18%, 1%, 0) scale(1.48); }
  .camp-app[data-view="stable"] .camp-world { transform: translate3d(-18%, 1%, 0) scale(1.48); }
  .camp-app[data-view="self"] .camp-world { transform: translate3d(0, -9%, 0) scale(1.44); }

  .camp-motion-rig {
    --camp-rig-ink: rgba(242, 242, 238, .5);
    --camp-rig-dim: rgba(114, 114, 108, .42);
    position: absolute;
    z-index: 3;
    pointer-events: none;
  }
  .camp-app[data-time="day"] .camp-motion-rig {
    --camp-rig-ink: rgba(17, 17, 17, .58);
    --camp-rig-dim: rgba(114, 114, 108, .34);
  }
  .camp-treetop-rig {
    top: 0;
    width: 15%;
    height: 47%;
    transform-origin: 50% 100%;
    animation: camp-treetop-sway 4.8s steps(6, end) infinite alternate;
  }
  .camp-treetop-left { left: 0; }
  .camp-treetop-right { right: 0; animation-duration: 5.6s; animation-delay: -1.7s; }
  .camp-treetop-rig i {
    position: absolute;
    bottom: 0;
    width: 56%;
    height: 86%;
    background-color: var(--camp-rig-dim);
    background-image: repeating-conic-gradient(var(--camp-rig-ink) 0 25%, transparent 0 50%);
    background-size: 5px 5px;
    clip-path: polygon(50% 0, 62% 24%, 57% 24%, 78% 48%, 65% 48%, 96% 75%, 62% 73%, 62% 100%, 39% 100%, 39% 73%, 4% 77%, 34% 48%, 21% 49%, 43% 24%, 37% 24%);
    opacity: .14;
  }
  .camp-treetop-rig i:nth-child(1) { left: -8%; height: 96%; }
  .camp-treetop-rig i:nth-child(2) { left: 34%; height: 72%; bottom: -3%; }
  .camp-treetop-right i:nth-child(1) { left: 42%; }
  .camp-treetop-right i:nth-child(2) { left: 2%; height: 78%; }
  @keyframes camp-treetop-sway {
    from { transform: rotate(-.35deg) translate3d(-1px, 0, 0); }
    to { transform: rotate(.55deg) translate3d(2px, 0, 0); }
  }

  .camp-horse-rig {
    left: 76.5%;
    top: 49%;
    width: 16.5%;
    height: 28%;
    animation: camp-horse-breathe 5.2s steps(6, end) infinite;
  }
  @keyframes camp-horse-breathe {
    0%, 100% { transform: translate3d(0, 0, 0); }
    35% { transform: translate3d(1px, 2px, 0); }
    70% { transform: translate3d(-1px, 1px, 0); }
  }
  .camp-horse-head {
    position: absolute;
    left: 11%;
    top: 10%;
    width: 28px;
    height: 48px;
    transform-origin: 78% 18%;
    background-color: var(--camp-rig-dim);
    background-image: repeating-conic-gradient(var(--camp-rig-ink) 0 25%, transparent 0 50%);
    background-size: 7px 7px;
    clip-path: polygon(57% 0, 83% 13%, 100% 39%, 82% 75%, 54% 100%, 11% 85%, 0 58%, 27% 43%, 34% 15%);
    opacity: .28;
    animation: camp-horse-head-dip 7.4s steps(8, end) infinite;
  }
  .camp-horse-head::before,
  .camp-horse-head::after {
    content: "";
    position: absolute;
    top: -6px;
    width: 6px;
    height: 12px;
    background: var(--camp-rig-ink);
    clip-path: polygon(50% 0, 100% 100%, 0 82%);
  }
  .camp-horse-head::before { left: 9px; animation: camp-horse-ear-l 9.4s steps(8, end) infinite; }
  .camp-horse-head::after { left: 17px; animation: camp-horse-ear-r 11.2s steps(8, end) infinite; }
  @keyframes camp-horse-ear-l {
    0%, 88%, 100% { transform: rotate(-8deg); }
    91% { transform: rotate(-16deg); }
    95% { transform: rotate(-5deg); }
  }
  @keyframes camp-horse-ear-r {
    0%, 90%, 100% { transform: rotate(12deg); }
    93% { transform: rotate(20deg); }
    96% { transform: rotate(9deg); }
  }
  @keyframes camp-horse-head-dip {
    0%, 45%, 100% { transform: rotate(-3deg) translate3d(0, 0, 0); }
    58%, 78% { transform: rotate(12deg) translate3d(1px, 5px, 0); }
    86% { transform: rotate(4deg) translate3d(0, 2px, 0); }
  }
  .camp-horse-hoof {
    position: absolute;
    right: 27%;
    bottom: 1%;
    width: 8px;
    height: 54px;
    transform-origin: 50% 8%;
    border: 1px solid var(--camp-rig-ink);
    background: var(--camp-rig-dim);
    clip-path: polygon(18% 0, 88% 0, 72% 78%, 100% 87%, 87% 100%, 8% 100%, 0 86%, 26% 76%);
    opacity: .66;
    animation: camp-horse-hoof-lift 6.2s steps(7, end) infinite;
  }
  @keyframes camp-horse-hoof-lift {
    0%, 58%, 100% { transform: rotate(0) translate3d(0, 0, 0); }
    67%, 76% { transform: rotate(-12deg) translate3d(-2px, -7px, 0); }
    84% { transform: rotate(-4deg) translate3d(-1px, -2px, 0); }
  }
  .camp-horse-dust {
    position: absolute;
    right: 19%;
    bottom: -2%;
    width: 46px;
    height: 22px;
  }
  .camp-horse-dust i,
  .camp-wind-dust i {
    position: absolute;
    width: 5px;
    height: 5px;
    background: var(--camp-rig-ink);
    opacity: 0;
  }
  .camp-horse-dust i { bottom: 2px; animation: camp-horse-dust-rise 6.2s steps(6, end) infinite; }
  .camp-horse-dust i:nth-child(2) { left: 12px; animation-delay: 80ms; }
  .camp-horse-dust i:nth-child(3) { left: 25px; animation-delay: 160ms; }
  @keyframes camp-horse-dust-rise {
    0%, 72%, 100% { opacity: 0; transform: translate3d(0, 0, 0); }
    78% { opacity: .55; }
    92% { opacity: 0; transform: translate3d(14px, -12px, 0) scale(.6); }
  }
  .camp-wind-dust {
    left: 9%;
    bottom: 6%;
    width: 72%;
    height: 18%;
  }
  .camp-wind-dust i { bottom: 0; animation: camp-wind-dust-cross 9s steps(12, end) infinite; }
  .camp-wind-dust i:nth-child(2) { bottom: 24%; animation-delay: -2.2s; }
  .camp-wind-dust i:nth-child(3) { bottom: 9%; animation-delay: -4.6s; }
  .camp-wind-dust i:nth-child(4) { bottom: 38%; animation-delay: -6.7s; }
  .camp-wind-dust i:nth-child(5) { bottom: 56%; animation-delay: -3.3s; animation-duration: 12s; }
  .camp-wind-dust i:nth-child(6) { bottom: 72%; animation-delay: -7.1s; animation-duration: 14s; }
  @keyframes camp-wind-dust-cross {
    0% { opacity: 0; transform: translate3d(0, 0, 0); }
    12%, 68% { opacity: .32; }
    100% { opacity: 0; transform: translate3d(520px, -16px, 0); }
  }
  /* 风掠过地面：断续风线横扫 + 空气浮尘 */
  .camp-wind-streaks {
    left: 0;
    right: 0;
    bottom: 3%;
    height: 8%;
  }
  .camp-wind-streaks i {
    position: absolute;
    height: 2px;
    width: 12%;
    background-image: repeating-linear-gradient(90deg, var(--camp-rig-ink) 0 6px, transparent 6px 14px);
    opacity: 0;
    animation: camp-wind-streak 7.4s steps(14, end) infinite;
  }
  .camp-wind-streaks i:nth-child(1) { bottom: 10%; animation-delay: -1.2s; }
  .camp-wind-streaks i:nth-child(2) { bottom: 46%; width: 8%; animation-delay: -3.8s; animation-duration: 8.6s; }
  .camp-wind-streaks i:nth-child(3) { bottom: 0; width: 15%; animation-delay: -5.4s; }
  @keyframes camp-wind-streak {
    0% { opacity: 0; transform: translate3d(-12vw, 0, 0); }
    10%, 60% { opacity: .4; }
    100% { opacity: 0; transform: translate3d(105vw, 0, 0); }
  }

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
  .camp-feature-self { left: calc(50% + 58px); top: 70%; }
  .camp-feature-stable { right: 7%; top: 61%; }
  .camp-feature-scan { left: 8%; top: 33%; }
  .camp-app:not([data-view="overview"]) .camp-feature { opacity: 0; pointer-events: none; }

  /* --- scan panel --- */
  .camp-scan-bar { position: relative; height: 24px; border: 1px solid #111111; background: #FAFAF7; margin-bottom: 14px; }
  .camp-scan-fill { height: 100%; background: #111111;
                    background-image: repeating-conic-gradient(#F5F5F2 0 25%, transparent 0 50%);
                    background-size: 6px 6px; }
  .camp-scan-bar span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                        font-size: 11px; mix-blend-mode: difference; color: #F5F5F2; }
  .camp-scan-phases { display: flex; gap: 6px; margin-bottom: 16px; }
  .camp-scan-phase { flex: 1; border: 1px solid #C9C9C2; background: #FAFAF7; font-size: 10px;
                     letter-spacing: .1em; padding: 6px 4px; text-align: center; }
  .camp-scan-phase.on { background: #111111; color: #F5F5F2; border-color: #111111; }
  .camp-scan-phase.done { border-color: #111111; }
  .camp-scan-phase.done::after { content: " ✓"; }
  .camp-scan-head { font-size: 11px; letter-spacing: .08em; color: #72726C; margin: 14px 0 8px; }
  .camp-scan-row { display: flex; gap: 10px; align-items: flex-start; border: 1px solid #C9C9C2;
                   background: #FAFAF7; padding: 9px 12px; }
  .camp-scan-row + .camp-scan-row { margin-top: 5px; }
  .camp-scan-row input { margin-top: 4px; accent-color: #111111; }
  .camp-scan-cmd { display: flex; gap: 8px; margin-top: 10px; }
  .camp-scan-cmd input { flex: 1; min-width: 0; border: 1px solid #C9C9C2; background: #FAFAF7;
                         padding: 8px 10px; font-size: 12px; color: #111111; }
  .camp-scan-cmd button { border: 1px solid #111111; background: #FAFAF7; color: #111111;
                          padding: 0 14px; cursor: pointer; font-size: 11px; }
  .camp-scan-cmd button:hover { background: #111111; color: #F5F5F2; }

  .camp-fire {
    position: absolute;
    z-index: 4;
    left: 50%;
    top: 73.5%;
    width: 64px;
    height: 108px;
    transform: translate(-50%, -100%);
    pointer-events: none;
  }
  .camp-flame {
    position: absolute;
    bottom: 0;
    left: 50%;
    clip-path: polygon(50% 0, 76% 39%, 66% 100%, 34% 100%, 20% 48%);
    transform: translateX(-50%);
    transform-origin: 50% 100%;
    animation: camp-burn 680ms steps(5, end) infinite alternate;
  }
  .camp-flame-a { z-index: 2; width: 24px; height: 52px; background: #E4B95F; opacity: .94; }
  .camp-flame-b { z-index: 3; width: 12px; height: 34px; background: #FFF0B0; opacity: .98; animation-delay: -240ms; }
  .camp-flame-c { z-index: 1; width: 34px; height: 29px; background: #B96E32; opacity: .86; animation-delay: -410ms; }
  .camp-ember-light {
    position: absolute;
    z-index: 0;
    left: 50%;
    bottom: -8px;
    width: 92px;
    height: 38px;
    transform: translateX(-50%);
    background-color: rgba(228, 185, 95, .2);
    background-image: repeating-conic-gradient(rgba(255, 240, 176, .4) 0 25%, transparent 0 50%);
    background-size: 6px 6px;
    clip-path: polygon(8% 42%, 25% 17%, 70% 6%, 95% 38%, 78% 83%, 31% 96%);
    animation: camp-ember-pulse 920ms steps(4, end) infinite alternate;
  }
  @keyframes camp-burn {
    0% { transform: translateX(-50%) scale(.82, .9) skewX(-4deg); }
    45% { transform: translateX(-50%) scale(1, 1.08) skewX(3deg); }
    100% { transform: translateX(-50%) scale(.9, .96) skewX(-2deg); }
  }
  @keyframes camp-ember-pulse {
    from { opacity: .48; transform: translateX(-50%) scale(.94); }
    to { opacity: .82; transform: translateX(-50%) scale(1.04); }
  }
  /* 特别大的炊烟：宽烟柱 + 五缕错峰上升 */
  .camp-smoke {
    position: absolute;
    left: 50%;
    bottom: 40px;
    width: 150px;
    height: 240px;
    transform: translateX(-50%);
  }
  .camp-smoke i {
    position: absolute;
    left: 50%;
    bottom: 0;
    width: 34px;
    height: 52px;
    border: 2px solid rgba(242, 242, 238, .62);
    background-color: rgba(201, 201, 194, .5);
    background-image: repeating-conic-gradient(rgba(242, 242, 238, .75) 0 25%, transparent 0 50%);
    background-size: 7px 7px;
    clip-path: polygon(22% 0, 84% 10%, 100% 64%, 68% 100%, 10% 86%, 0 34%);
    opacity: 0;
    animation: camp-smoke-rise 3.4s steps(10, end) infinite;
  }
  .camp-smoke i:nth-child(1) { animation-delay: 0s; transform-origin: 50% 100%; }
  .camp-smoke i:nth-child(2) { width: 44px; height: 66px; animation-delay: -1.1s; }
  .camp-smoke i:nth-child(3) { animation-delay: -2.2s; }
  .camp-smoke i:nth-child(4) { width: 40px; height: 60px; animation-delay: -.5s; }
  .camp-smoke i:nth-child(5) { width: 48px; height: 72px; animation-delay: -1.7s; }
  @keyframes camp-smoke-rise {
    0% { opacity: 0; transform: translate3d(-50%, 4px, 0) scale(.55); }
    16% { opacity: .62; }
    62% { opacity: .32; }
    100% { opacity: 0; transform: translate3d(calc(-50% + 26px), -190px, 0) scale(2.2); }
  }

  /* --- 颗粒火焰：CSS 点阵颗粒位移 + 火星上升，模拟燃烧 --- */
  .camp-fire-grain {
    position: absolute;
    z-index: 5;
    left: 50%;
    bottom: 0;
    width: 46px;
    height: 76px;
    transform: translateX(-50%);
    background-image: repeating-conic-gradient(rgba(255, 240, 176, .9) 0 25%, transparent 0 50%);
    background-size: 5px 5px;
    clip-path: polygon(50% 0, 76% 39%, 66% 100%, 34% 100%, 20% 48%);
    animation: camp-grain-shift 340ms steps(3, end) infinite;
    opacity: .78;
  }
  @keyframes camp-grain-shift {
    0%   { background-position: 0 0;       transform: translateX(-50%) scale(1, .96); }
    33%  { background-position: 3px 2px;   transform: translateX(calc(-50% + 2px)) scale(.94, 1.02); }
    66%  { background-position: -2px 4px;  transform: translateX(calc(-50% - 2px)) scale(1.04, .98); }
    100% { background-position: 1px -3px;  transform: translateX(-50%) scale(.98, 1.05); }
  }
  .camp-sparks { position: absolute; inset: 0; z-index: 6; }
  .camp-sparks i {
    position: absolute;
    left: 50%;
    bottom: 30px;
    width: 4px;
    height: 4px;
    background: #FFF0B0;
    background-image: repeating-conic-gradient(#FFF0B0 0 25%, transparent 0 50%);
    background-size: 2px 2px;
    opacity: 0;
    animation: camp-spark-rise 1.9s steps(7, end) infinite;
  }
  .camp-sparks i:nth-child(2) { animation-delay: -.6s; }
  .camp-sparks i:nth-child(3) { animation-delay: -1.1s; }
  .camp-sparks i:nth-child(4) { animation-delay: -1.5s; }
  .camp-sparks i:nth-child(5) { animation-delay: -.9s; animation-duration: 2.4s; }
  @keyframes camp-spark-rise {
    0%   { opacity: 0; transform: translate(-50%, 0) scale(.6); }
    14%  { opacity: .9; }
    55%  { opacity: .5; transform: translate(calc(-50% - 5px), -30px) scale(1); }
    100% { opacity: 0; transform: translate(calc(-50% + 6px), -66px) scale(.4); }
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
  .camp-panel-ledger { right: 5%; }
  .camp-panel-self { left: 4%; right: auto; top: 13%; width: clamp(380px, 34vw, 500px); }
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

  /* --- Pixel UI 组件层：单色硬边框 + 硬投影；全营只有火有色 --- */
  .camp-app {
    --ui-bg: #FAFAF7;
    --ui-ink: #111111;
    --ui-soft: #72726C;
    --ui-border: #C9C9C2;
    --ui-shadow: #9A9A94;
    --camp-px-font: "PS2P", "Zpix", ui-monospace, Menlo, monospace;
  }
  .camp-app[data-time="night"] {
    --ui-bg: #0A0A09;
    --ui-ink: #F5F5F2;
    --ui-soft: #9A9A94;
    --ui-border: #3A3A35;
    --ui-shadow: #1F1F1B;
  }
  .camp-panel { border: 3px solid var(--ui-ink); border-radius: 0;
                background: var(--ui-bg); color: var(--ui-ink);
                box-shadow: 4px 4px 0 0 var(--ui-shadow); }
  .camp-panel-head { display: flex; align-items: flex-start; gap: 10px; border-bottom: 2px solid var(--ui-border); }
  .camp-panel-head-text { min-width: 0; }
  .camp-panel-head p { color: var(--ui-soft); }
  .camp-panel-back {
    flex: none; margin-top: 2px; padding: 4px 10px; cursor: pointer;
    border: 3px solid var(--ui-ink); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    font-family: var(--camp-px-font); font-size: 11px;
    box-shadow: 3px 3px 0 0 var(--ui-shadow);
  }
  .camp-panel-back:hover { transform: translate(1px, 1px); box-shadow: -3px -3px 0 0 var(--ui-shadow); }
  .camp-panel-back:active { transform: translate(3px, 3px); box-shadow: none; }
  .camp-panel-back[hidden] { display: none; }
  .camp-panel-body { overflow-y: auto; max-height: calc(72vh - 92px);
                     scrollbar-width: thin; scrollbar-color: var(--ui-ink) var(--ui-bg); }
  .camp-panel-body::-webkit-scrollbar { width: 8px; }
  .camp-panel-body::-webkit-scrollbar-track { background: var(--ui-bg); }
  .camp-panel-body::-webkit-scrollbar-thumb { background: var(--ui-ink); border: 2px solid var(--ui-bg); }
  .camp-tag {
    border: 3px solid var(--ui-border); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    box-shadow: 3px 3px 0 0 var(--ui-shadow);
    font-family: var(--camp-px-font);
  }
  .camp-tag:hover { border-color: var(--ui-ink); }
  .camp-tag[aria-pressed="true"] {
    background: var(--ui-ink); color: var(--ui-bg); border-color: var(--ui-ink);
    box-shadow: -3px -3px 0 0 var(--ui-shadow);
  }
  .camp-tag[aria-pressed="true"]::before {
    background-color: var(--ui-bg);
    background-image: repeating-conic-gradient(var(--ui-ink) 0 25%, transparent 0 50%);
  }
  .camp-entry, .camp-project {
    border: 2px solid var(--ui-border); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
  }
  .camp-project:hover, .camp-project:focus-visible { border-color: var(--ui-ink); background: var(--ui-ink); color: var(--ui-bg); }
  .camp-item-meta, .camp-item-time { color: var(--ui-soft); }
  .camp-project:hover .camp-item-meta { color: var(--ui-border); }
  .camp-empty { border: 2px dashed var(--ui-border); color: var(--ui-soft); background: transparent; }
  .camp-pages button {
    border: 3px solid var(--ui-border); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    box-shadow: 2px 2px 0 0 var(--ui-shadow);
    font-family: var(--camp-px-font);
  }
  .camp-pages button:hover:not(:disabled) { background: var(--ui-ink); color: var(--ui-bg); border-color: var(--ui-ink); }
  .camp-pages span { color: var(--ui-soft); }
  .camp-now section { border-bottom-color: var(--ui-border); }
  .camp-now h3 { color: var(--ui-soft); }
  .camp-trait { border-bottom-color: var(--ui-border); }
  .camp-notice { border: 2px solid var(--ui-ink); background: var(--ui-bg); color: var(--ui-ink); }
  .camp-scan-bar { border: 2px solid var(--ui-ink); background: var(--ui-bg); }
  .camp-scan-fill { background: var(--ui-ink);
                    background-image: repeating-conic-gradient(var(--ui-bg) 0 25%, transparent 0 50%); }
  .camp-scan-phase { border: 2px solid var(--ui-border); background: var(--ui-bg); color: var(--ui-ink);
                     font-family: var(--camp-px-font); }
  .camp-scan-phase.on { background: var(--ui-ink); color: var(--ui-bg); border-color: var(--ui-ink); }
  .camp-scan-phase.done { border-color: var(--ui-ink); }
  .camp-scan-head { color: var(--ui-soft); }
  .camp-scan-row { border: 2px solid var(--ui-border); background: var(--ui-bg); }
  .camp-scan-cmd input { border: 2px solid var(--ui-border); background: var(--ui-bg); color: var(--ui-ink); }
  .camp-scan-cmd button {
    border: 3px solid var(--ui-ink); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    box-shadow: 3px 3px 0 0 var(--ui-shadow);
    font-family: var(--camp-px-font);
  }
  .camp-scan-cmd button:hover { background: var(--ui-ink); color: var(--ui-bg); box-shadow: -3px -3px 0 0 var(--ui-shadow); }
  .camp-scan-mini { margin-top: 6px; height: 10px; border: 1px solid var(--ui-ink); background: var(--ui-bg); max-width: 340px; }
  .camp-scan-mini-fill { height: 100%; background: var(--ui-ink);
                         background-image: repeating-conic-gradient(var(--ui-bg) 0 25%, transparent 0 50%);
                         background-size: 4px 4px; }
  .camp-scan-chip { font-family: var(--camp-px-font); font-size: 10px; padding: 1px 7px;
                    border: 2px solid var(--ui-border); white-space: nowrap; }
  .camp-scan-chip.doing { background: var(--ui-ink); color: var(--ui-bg); border-color: var(--ui-ink); }
  .camp-scan-chip.done { color: var(--ui-soft); border-color: var(--ui-border); }
  .camp-scan-cmd button.loading {
    background-image: repeating-conic-gradient(var(--ui-ink) 0 25%, transparent 0 50%);
    background-size: 6px 6px;
    animation: camp-loading-shift .6s steps(4, end) infinite;
  }
  @keyframes camp-loading-shift {
    0% { background-position: 0 0; }
    100% { background-position: 12px 12px; }
  }
  .camp-panel { width: clamp(520px, 46vw, 660px); }
  .camp-entry { position: relative; display: block; padding: 12px 46px 12px 14px; min-height: 64px; }
  .camp-project { position: relative; min-height: 64px; }
  .camp-entry-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .camp-entry-line { margin-top: 5px; color: var(--ui-soft); font-size: 11px; line-height: 1.5;
                     overflow-wrap: anywhere; }
  .camp-entry-line::before { content: "▸ "; color: var(--ui-border); }
  .camp-item-progress { margin-top: 4px; color: var(--ui-soft); font-size: 10px;
                        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 420px; }
  .camp-item-progress.has-now { color: var(--ui-ink); }
  .camp-del {
    position: absolute; top: 6px; right: 6px; z-index: 2;
    min-width: 20px; height: 20px; padding: 0 4px; line-height: 16px;
    border: 2px solid var(--ui-border); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    font-family: var(--camp-px-font); font-size: 11px; cursor: pointer;
  }
  .camp-del:hover { border-color: var(--ui-ink); }
  .camp-del.off { opacity: .42; cursor: default; }
  .camp-scan-pages { display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap; }
  .camp-scan-page {
    min-width: 30px; height: 26px;
    border: 3px solid var(--ui-border); border-radius: 0;
    background: var(--ui-bg); color: var(--ui-ink);
    font-family: var(--camp-px-font); font-size: 11px; cursor: pointer;
    box-shadow: 2px 2px 0 0 var(--ui-shadow);
  }
  .camp-scan-page.on { background: var(--ui-ink); color: var(--ui-bg); border-color: var(--ui-ink); }
  .camp-modal { position: fixed; inset: 0; z-index: 30; display: flex; align-items: center; justify-content: center;
                background: rgba(5, 5, 5, .55); }
  .camp-modal[hidden] { display: none; }
  .camp-modal-box { width: min(340px, 86vw); border: 3px solid var(--ui-ink); border-radius: 0;
                    background: var(--ui-bg); color: var(--ui-ink);
                    box-shadow: 5px 5px 0 0 var(--ui-shadow); padding: 18px 20px; }
  .camp-modal-title { font-size: 13px; line-height: 1.5; margin-bottom: 16px; }
  .camp-modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
  .camp-modal-actions button { border: 3px solid var(--ui-ink); border-radius: 0; background: var(--ui-bg);
                               color: var(--ui-ink); font-family: var(--camp-px-font); font-size: 11px;
                               padding: 6px 12px; cursor: pointer; box-shadow: 2px 2px 0 0 var(--ui-shadow); }
  .camp-modal-actions button:hover { box-shadow: -2px -2px 0 0 var(--ui-shadow); transform: translate(1px, 1px); }
  .camp-modal-actions .camp-modal-confirm { background: var(--ui-ink); color: var(--ui-bg); }
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
    .camp-feature-self { left: 54%; top: 55%; }
    .camp-feature-stable { right: 3%; top: 43%; }
    .camp-feature-scan { left: 3%; top: 26%; }
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
    .camp-world, .camp-zoom-layer, .camp-scene-image { transition: none; }
    .camp-panel { animation: none; }
    .camp-flame, .camp-ember-light, .camp-smoke i { animation: none; }
    .camp-fire-grain, .camp-sparks i { animation: none; opacity: .55; }
    .camp-motion-rig { display: none; }
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
  const panelBack = camp.querySelector('[data-action="panel-back"]');
  const live = camp.querySelector('[aria-live]');
  const zoomLayer = camp.querySelector('.camp-zoom-layer');
  const PAGE_SIZE = 5;
  const SCAN_PAGE_SIZE = 10;
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
  let sceneZoom = 1;
  let scanPage = 0;

  function setSceneZoom(next, origin) {
    sceneZoom = Math.round(Math.min(1.2, Math.max(1, next)) * 100) / 100;
    if (origin) {
      zoomLayer.style.setProperty('--camp-zoom-x', `${origin.x}%`);
      zoomLayer.style.setProperty('--camp-zoom-y', `${origin.y}%`);
    }
    zoomLayer.style.setProperty('--camp-wheel-zoom', sceneZoom);
    camp.dataset.sceneZoom = sceneZoom.toFixed(2);
  }

  function resetSceneZoom() {
    setSceneZoom(1, {x: 50, y: 62});
  }

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

  const modal = camp.querySelector('.camp-modal');
  let closeDeleteModal = () => {};
  function openDeleteModal(label, run) {
    modal.querySelector('.camp-modal-title').textContent = `删掉「${label}」? 这一条不会进回收站。`;
    modal.hidden = false;
    closeDeleteModal = () => { modal.hidden = true; };
    modal.querySelector('[data-action="modal-cancel"]').onclick = () => closeDeleteModal();
    modal.querySelector('[data-action="modal-confirm"]').onclick = () => { closeDeleteModal(); run(); };
  }
  modal.addEventListener('click', (event) => { if (event.target === modal) closeDeleteModal(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) closeDeleteModal();
  });

  function deleteRow(file, line, button) {
    fetch('http://127.0.0.1:8799/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file, line })
    }).then((r) => r.json()).then((d) => {
      if (d && d.ok) { location.reload(); }
      else { button.textContent = '删除失败'; }
    }).catch(() => { button.textContent = '桥未启动'; });
  }

  function renderLedger() {
    panelTitle.textContent = '营地账本';
    panelSub.textContent = '情报 · 点子 · 计划';
    const scanBtn = make('button', 'camp-panel-back camp-scan-open', '扫描 · 找点子 / 找项目');
    scanBtn.type = 'button';
    scanBtn.style.marginBottom = '12px';
    scanBtn.addEventListener('click', () => openView('scan'));
    panelBody.append(scanBtn);
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
      const head = make('div', 'camp-entry-head');
      head.append(make('div', 'camp-item-title', item.text || '未命名条目'));
      head.append(make('div', 'camp-item-time camp-mono', item.last_seen || '时间未知'));
      row.append(head);
      const meta = [['为什么现在出现', item.why_now], ['证据', item.evidence], ['最小验证', item.probe]];
      meta.forEach(([label, value]) => {
        if (!value || value === '—') return;
        row.append(make('div', 'camp-entry-line', `${label}：${value}`));
      });
      const del = make('button', 'camp-del', '×');
      del.title = '删除';
      del.type = 'button';
      if (item.raw) {
        del.addEventListener('click', () => openDeleteModal((item.text || '这条').slice(0, 14), () => deleteRow('POOL.md', item.raw, del)));
      } else {
        del.disabled = true;
        del.classList.add('off');
      }
      row.append(del);
      list.append(row);
    });
    panelBody.append(list);
    addPages(items.length, state.ledgerPage, (page) => { state.ledgerPage = page; renderState(); });
  }

  function deepDive(project, button, resultBox) {
    button.disabled = true;
    button.classList.add('loading');
    button.textContent = '深挖中…';
    fetch('http://127.0.0.1:8799/deep-dive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: project.path })
    }).then((r) => r.json()).then((d) => {
      button.disabled = false;
      button.classList.remove('loading');
      button.textContent = '深挖';
      if (d && d.ok) {
        resultBox.replaceChildren(make('div', 'camp-item-time camp-mono', d.text));
      } else {
        resultBox.replaceChildren(make('div', 'camp-item-time camp-mono', (d && d.error) || '深挖失败'));
      }
    }).catch(() => {
      button.disabled = false;
      button.classList.remove('loading');
      button.textContent = '深挖';
      resultBox.replaceChildren(make('div', 'camp-item-time camp-mono', '桥未启动 — 对达奇说「开桥」'));
    });
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
    const diveRow = make('div', 'camp-scan-cmd');
    const diveBtn = make('button', '', '深挖');
    diveBtn.type = 'button';
    const diveResult = make('div', 'camp-scan-head');
    diveBtn.addEventListener('click', () => deepDive(selectedProject, diveBtn, diveResult));
    diveRow.append(diveBtn, make('span', 'camp-item-time camp-mono', '读更深一层上下文，只显示、不写账本'));
    panelBody.append(diveRow);
    panelBody.append(diveResult);
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
      const row = make('div', 'camp-project');
      row.tabIndex = 0;
      const main = make('div');
      main.append(make('div', 'camp-item-title', project.name || '未命名项目'));
      main.append(make('div', 'camp-item-meta camp-mono', `Agent · ${project.agent || '未知'}`));
      const progress = project.now
        ? (project.now.next || project.now.goal || '有 NOW 主线')
        : '无 NOW 主线 — 点开看详情';
      const progressLine = make('div', `camp-item-progress camp-mono${project.now ? ' has-now' : ''}`, progress);
      main.append(progressLine);
      row.append(main, make('div', 'camp-item-time camp-mono', project.last || '时间未知'));
      const del = make('button', 'camp-del', '×');
      del.title = '删除';
      del.type = 'button';
      del.addEventListener('click', (event) => {
        event.stopPropagation();
        if (project.raw) del.addEventListener('click', () => openDeleteModal((project.name || '这个项目').slice(0, 14), () => deleteRow('SHELF.md', project.raw, del)));
      });
      row.append(del);
      const openNow = () => {
        selectedProject = project;
        state.stableDepth = 'now';
        renderState();
      };
      row.addEventListener('click', openNow);
      row.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openNow(); }
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

  function copyText(text, button) {
    const done = () => {
      const old = button.textContent;
      button.textContent = '已复制';
      setTimeout(() => { button.textContent = old; }, 1200);
    };
    const fallback = () => {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.append(area);
      area.select();
      try { document.execCommand('copy'); done(); } catch (_) {}
      area.remove();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else fallback();
  }

  function scanSelection() {
    try { return JSON.parse(localStorage.getItem('daqi.camp.scanSelection') || '[]'); } catch (_) { return []; }
  }

  function renderScan() {
    panelTitle.textContent = '扫描';
    panelSub.textContent = '找点子 · 找项目';
    const scan = payload.scan;
    if (!scan) {
      addEmpty('还没有扫描记录。对达奇说：扫描');
      return;
    }
    const pct = Number(scan.percent || 0);
    const barWrap = make('div', 'camp-scan-bar');
    const fill = make('div', 'camp-scan-fill');
    fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    barWrap.append(fill, make('span', 'camp-mono', `${pct}%`));
    panelBody.append(barWrap);

    const phaseRow = make('div', 'camp-scan-phases');
    let passed = false;
    [['scan', '扫描'], ['select', '选择'], ['read', '读取'], ['brain', '提炼'], ['commit', '提交']].forEach(([key, label]) => {
      const chip = make('span', 'camp-scan-phase', label);
      if (scan.phase === key) { chip.classList.add('on'); passed = true; }
      else if (passed) {}
      else chip.classList.add('done');
      phaseRow.append(chip);
    });
    panelBody.append(phaseRow);

    if (Array.isArray(scan.candidates) && scan.candidates.length) {
      panelBody.append(make('div', 'camp-scan-head', `工作区候选 — 每页 ${SCAN_PAGE_SIZE} 条，勾选后点「提交」`));
      const list = make('div', 'camp-list');
      const saved = scanSelection();
      let commandInput = null;
      const refreshCommand = () => {
        const pagePaths = scan.candidates
          .slice(scanPage * SCAN_PAGE_SIZE, (scanPage + 1) * SCAN_PAGE_SIZE)
          .map((c) => c.path);
        const savedPaths = scanSelection().filter((p) => !pagePaths.includes(p));
        Array.from(list.querySelectorAll('input:checked')).forEach((i) => savedPaths.push(i.value));
        try { localStorage.setItem('daqi.camp.scanSelection', JSON.stringify(savedPaths)); } catch (_) {}
        const nums = savedPaths.map((p) => {
          const idx = scan.candidates.findIndex((c) => c.path === p);
          return idx >= 0 ? String(idx + 1) : null;
        }).filter(Boolean);
        if (commandInput) commandInput.value = nums.length ? `达奇：扫描 ${nums.join(',')}` : '';
      };
      const pageStart = scanPage * SCAN_PAGE_SIZE;
      scan.candidates.slice(pageStart, pageStart + SCAN_PAGE_SIZE).forEach((c) => {
        const num = scan.candidates.findIndex((x) => x.path === c.path) + 1;
        const item = (Array.isArray(scan.items) && scan.items.find((it) => it.path === c.path)) || {};
        const row = make('label', 'camp-scan-row');
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.value = c.path;
        box.checked = saved.includes(c.path);
        box.addEventListener('change', refreshCommand);
        row.append(box);
        const info = make('div', '');
        const head = make('div', 'camp-scan-head-line');
        head.append(make('span', 'camp-item-title', `${num}. ${c.path}`));
        if (item.status === 'reading') head.append(make('span', 'camp-scan-chip doing', '读取中'));
        if (item.status === 'done') head.append(make('span', 'camp-scan-chip done', '完成'));
        info.append(head);
        info.append(make('div', 'camp-item-time camp-mono',
          `${(c.agents || []).join(' · ')} · ${c.last_active || ''} · ${c.sessions || 0} 会话${c.in_shelf ? ' · 已在马厩' : ''}`));
        const pct = Number(item.percent || 0);
        if (item.status === 'reading' && pct > 0) {
          const mini = make('div', 'camp-scan-mini');
          const fill = make('div', 'camp-scan-mini-fill');
          fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
          mini.append(fill);
          info.append(mini);
        }
        row.append(info);
        list.append(row);
      });
      const pages = Math.ceil(scan.candidates.length / SCAN_PAGE_SIZE);
      if (pages > 1) {
        const pager = make('div', 'camp-scan-pages');
        for (let p = 0; p < pages; p += 1) {
          const btn = make('button', `camp-scan-page${p === scanPage ? ' on' : ''}`, String(p + 1));
          btn.type = 'button';
          btn.addEventListener('click', () => { scanPage = p; renderScan(); });
          pager.append(btn);
        }
        panelBody.append(pager);
      }
      panelBody.append(list);
      const cmdRow = make('div', 'camp-scan-cmd');
      commandInput = document.createElement('input');
      commandInput.className = 'camp-mono';
      commandInput.readOnly = true;
      commandInput.placeholder = '勾选后点「提交」';
      const submitBtn = make('button', '', '提交');
      submitBtn.type = 'button';
      submitBtn.addEventListener('click', () => {
        if (!commandInput.value) return;
        copyText(commandInput.value, submitBtn);
      });
      cmdRow.append(commandInput, submitBtn);
      panelBody.append(cmdRow);
      refreshCommand();
    }

    if (Array.isArray(scan.proposals) && scan.proposals.length) {
      panelBody.append(make('div', 'camp-scan-head', '提炼候选 — 确认后才会写入账本/马厩'));
      const list = make('div', 'camp-list');
      scan.proposals.forEach((p) => {
        const row = make('div', 'camp-entry');
        row.append(make('div', 'camp-item-title', `[${p.type}] ${p.title}`));
        row.append(make('div', 'camp-item-time camp-mono', (p.line || '').slice(0, 90)));
        list.append(row);
      });
      panelBody.append(list);
      if (scan.token) {
        const sel = scanSelection();
        const tokRow = make('div', 'camp-scan-cmd');
        const tokInput = document.createElement('input');
        tokInput.className = 'camp-mono';
        tokInput.readOnly = true;
        tokInput.value = `camp_scan.py --select ${sel.join(',')} --commit ${scan.token}`;
        const tokBtn = make('button', '', '提交到账本 / 马厩');
        tokBtn.type = 'button';
        tokBtn.addEventListener('click', () => copyText(tokInput.value, tokBtn));
        tokRow.append(tokInput, tokBtn);
        panelBody.append(tokRow);
      }
    }

    if (scan.applied) panelBody.append(make('div', 'camp-notice', `已于 ${scan.applied} 写入账本与马厩`));
  }

  function renderSettings() {
    panelTitle.textContent = '设置';
    panelSub.textContent = '达奇的大脑';
    const s = payload.settings || {};
    panelBody.append(make('div', 'camp-scan-head',
      `模型 ${s.model || '—'} · 接口 ${s.base_url || '—'} · ${s.has_key ? '已配置 key' : '未配置 key'}`));
    panelBody.append(make('div', 'camp-scan-head', 'API Key — 只写本机 ~/.daqi/config.json，不进聊天'));
    const row = make('div', 'camp-scan-cmd');
    const input = document.createElement('input');
    input.type = 'password';
    input.placeholder = 'sk-…';
    const saveBtn = make('button', '', '保存');
    saveBtn.type = 'button';
    saveBtn.addEventListener('click', async () => {
      const flash = (t) => { saveBtn.textContent = t; setTimeout(() => { saveBtn.textContent = '保存'; }, 1500); };
      try {
        const res = await fetch('http://127.0.0.1:8799/set-key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: input.value })
        });
        const data = await res.json();
        if (data && data.ok) { flash('已保存'); input.value = ''; }
        else flash('保存失败');
      } catch (_) { flash('桥未启动'); }
    });
    row.append(input, saveBtn);
    panelBody.append(row);
    panelBody.append(make('div', 'camp-item-time camp-mono', '桥未启动时，对达奇说「开桥」。深读（deep）由达奇用此模型提炼点子。'));
  }

  function renderPanel() {
    panelBody.replaceChildren();
    panel.className = `camp-panel camp-panel-${state.view}`;
    if (state.view === 'ledger') renderLedger();
    if (state.view === 'stable') renderStable();
    if (state.view === 'self') renderProfile();
    if (state.view === 'scan') renderScan();
    if (state.view === 'settings') renderSettings();
  }

  function renderState() {
    camp.dataset.view = state.view;
    camp.dataset.time = resolvedTime();
    backButton.hidden = state.view === 'overview';
    panelBack.hidden = state.view === 'overview';
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
    scanPage = 0;
    resetSceneZoom();
    renderState();
    requestAnimationFrame(() => panel.focus({preventScroll: true}));
  }

  function goBackOneLevel() {
    if (state.view === 'scan') {
      state.view = 'ledger';
    } else if (state.view === 'stable' && state.stableDepth === 'now') {
      state.stableDepth = 'list';
      selectedProject = null;
    } else if (state.view !== 'overview') {
      state.view = 'overview';
    }
    resetSceneZoom();
    renderState();
  }

  camp.querySelectorAll('.camp-feature').forEach((button) => {
    button.addEventListener('click', () => openView(button.dataset.view));
  });
  backButton.addEventListener('click', goBackOneLevel);
  panelBack.addEventListener('click', goBackOneLevel);
  camp.querySelector('[data-action="settings"]').addEventListener('click', () => openView('settings'));
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
  function zoomOrigin(event) {
    const fixed = {
      ledger: {x: 20, y: 64},
      stable: {x: 84, y: 61},
      self: {x: 50, y: 72},
    };
    if (fixed[state.view]) return fixed[state.view];
    const bounds = camp.getBoundingClientRect();
    return {
      x: Math.min(100, Math.max(0, (event.clientX - bounds.left) / bounds.width * 100)),
      y: Math.min(100, Math.max(0, (event.clientY - bounds.top) / bounds.height * 100)),
    };
  }
  camp.addEventListener('wheel', (event) => {
    if (event.target.closest && event.target.closest('.camp-panel')) return; // 框内只上下滚动
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(() => { wheelTotal = 0; wheelLocked = false; }, 220);
    if (event.deltaY < 0) {
      event.preventDefault();
      wheelTotal = 0;
      wheelLocked = false;
      const step = Math.min(.04, Math.max(.008, Math.abs(event.deltaY) / 800));
      setSceneZoom(sceneZoom + step, zoomOrigin(event));
      return;
    }
    if (event.deltaY === 0) return;
    if (sceneZoom > 1) {
      event.preventDefault();
      setSceneZoom(sceneZoom - Math.min(.04, Math.max(.008, Math.abs(event.deltaY) / 800)));
      return;
    }
    if (state.view === 'overview') return;
    event.preventDefault();
    if (wheelLocked) return;
    wheelTotal += event.deltaY;
    if (wheelTotal >= 48) {
      wheelLocked = true;
      goBackOneLevel();
    }
  }, {passive: false});

  setInterval(() => {
    if (state.timeMode === 'auto') {
      camp.dataset.time = resolvedTime();
    }
    renderClock();
  }, 60000);
  resetSceneZoom();
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
            section = "traits" if title.startswith(("你的画像", "你的档案", "your portrait", "your profile")) else (
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
        mids = parts[1:-1] if len(parts) > 2 else []
        last_seen = parts[-1] if len(parts) > 1 else ""
        entries.append({
            "stage": stage,
            "text": text_part,
            "why_now": mids[0] if mids else "",
            "evidence": mids[1] if len(mids) > 1 else "",
            "probe": mids[2] if len(mids) > 2 else "",
            "last_seen": last_seen,
            "raw": line,
        })
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
        bands[current].append({"name": name, "path": path, "last": last, "agent": agent, "raw": line})
    return bands, warnings


def flatten_projects(bands: dict[str, list[dict]]) -> list[dict]:
    return [dict(project) for key, _ in BANDS for project in bands[key]]


def find_now_file(path: str) -> Path | None:
    """Locate a project's NOW main line at common positions (00_Context/, root, one level deep)."""
    root = Path(path)
    candidates = [root / "00_Context" / "NOW.md", root / "NOW.md"]
    try:
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            candidates.append(child / "NOW.md")
            candidates.append(child / "00_Context" / "NOW.md")
    except OSError:
        pass
    return next((c for c in candidates if c.is_file()), None)


def enrich_projects(projects: list[dict], now: datetime.date | datetime.datetime) -> tuple[list[dict], list[str]]:
    enriched = []
    warnings = []
    for project in projects:
        item = dict(project)
        item["display_band"] = classify_activity(item.get("last", ""), now)
        item["now"] = None
        path = item.get("path", "")
        if path:
            now_path = find_now_file(path)
            try:
                if now_path is not None and now_path.is_file():
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
    scan_state = None
    scan_path = store / ".scan-state.json"
    if scan_path.is_file():
        try:
            scan_state = json.loads(scan_path.read_text())
        except (OSError, json.JSONDecodeError):
            scan_state = None
    # settings expose model/base_url/has_key only — never the key itself
    settings = {"model": "DeepSeek-v4-flash0731", "base_url": "https://api.deepseek.com", "has_key": False}
    cfg_path = store / "config.json"
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text())
            llm = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
            settings["model"] = str(llm.get("model", settings["model"]))
            settings["base_url"] = str(llm.get("base_url", settings["base_url"]))
            settings["has_key"] = bool(str(llm.get("api_key", "")).strip())
        except (OSError, json.JSONDecodeError):
            pass
    payload = {
        "ledger": pool,
        "projects": projects,
        "profile": profile,
        "warnings": warnings,
        "scan": scan_state,
        "settings": settings,
        "generated_at": gen_ts.isoformat(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    night = asset_data_uri("camp-night.png")
    day = asset_data_uri("camp-day.png")
    scan_active = bool(scan_state and scan_state.get("phase") in ("read", "brain") and not scan_state.get("applied"))
    refresh_meta = '<meta http-equiv="refresh" content="1.5">' if scan_active else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh_meta}
<title>马掌望台</title>
<style>{SCENE_CSS}</style>
</head>
<body>
<main class="camp-app" data-view="overview" data-time="night">
  <div class="camp-world" aria-hidden="true">
    <div class="camp-zoom-layer">
      <img class="camp-scene-image camp-scene-night" src="{night}" alt="">
      <img class="camp-scene-image camp-scene-day" src="{day}" alt="">

      <div class="camp-motion-rig camp-treetop-rig camp-treetop-left"><i></i><i></i></div>
      <div class="camp-motion-rig camp-treetop-rig camp-treetop-right"><i></i><i></i></div>
      <div class="camp-motion-rig camp-wind-dust"><i></i><i></i><i></i><i></i><i></i><i></i></div>
      <div class="camp-motion-rig camp-wind-streaks"><i></i><i></i><i></i></div>
      <div class="camp-motion-rig camp-horse-rig">
        <i class="camp-horse-head"></i>
        <i class="camp-horse-hoof"></i>
        <span class="camp-horse-dust"><i></i><i></i><i></i></span>
      </div>

      <div class="camp-fire">
        <div class="camp-smoke"><i></i><i></i><i></i><i></i><i></i></div>
        <i class="camp-ember-light"></i>
        <i class="camp-flame camp-flame-c"></i>
        <i class="camp-flame camp-flame-a"></i>
        <i class="camp-flame camp-flame-b"></i>
        <i class="camp-fire-grain"></i>
        <span class="camp-sparks"><i></i><i></i><i></i><i></i><i></i></span>
      </div>
    </div>
  </div>

  <header class="camp-topbar">
    <div class="camp-brand">
      <strong>马掌望台</strong>
      <span class="camp-mono">MONO DITHER ARCHIVE</span>
    </div>
    <div class="camp-timebox" aria-label="场景时间">
      <button type="button" data-action="time-auto" data-time-mode="auto">自动</button>
      <button type="button" data-action="time-day" data-time-mode="day">白天</button>
      <button type="button" data-action="time-night" data-time-mode="night">夜晚</button>
      <button type="button" data-action="settings">设置</button>
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
      <button type="button" class="camp-panel-back" data-action="panel-back">← 返回</button>
      <div class="camp-panel-head-text">
        <h2 class="camp-panel-title" id="camp-panel-title"></h2>
        <p class="camp-panel-sub"></p>
      </div>
    </header>
    <div class="camp-panel-body"></div>
  </section>
  <div class="camp-modal" hidden>
    <div class="camp-modal-box">
      <div class="camp-modal-title"></div>
      <div class="camp-modal-actions">
        <button type="button" data-action="modal-cancel">取消</button>
        <button type="button" class="camp-modal-confirm" data-action="modal-confirm">确认删除</button>
      </div>
    </div>
  </div>
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
    lines = ["营地清点完毕："]
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


def build_page(store: Path, gen_ts: datetime.datetime | None = None) -> str:
    """Parse the stores read-only and render the full camp page."""
    gen_ts = gen_ts or datetime.datetime.now().astimezone()
    pool, warn_pool = parse_pool((store / "POOL.md").read_text())
    bands, warn_shelf = parse_shelf((store / "SHELF.md").read_text())
    flat_projects = flatten_projects(bands)
    self_path = store / "SELF.md"
    profile = parse_self(self_path.read_text()) if self_path.is_file() else {"traits": [], "goals": []}
    projects, warn_now = enrich_projects(flat_projects, gen_ts)
    warnings = warn_pool + warn_shelf + warn_now
    return render_html(store, pool, projects, profile, warnings, gen_ts)


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

    html_text = build_page(store, gen_ts)
    out.write_text(html_text)

    pool, _ = parse_pool(pool_path.read_text())
    bands, _ = parse_shelf(shelf_path.read_text())
    flat = flatten_projects(bands)
    projects, warn_now = enrich_projects(flat, gen_ts)
    print(summarize(store, pool, projects, out, warn_pool + warn_shelf + warn_now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
