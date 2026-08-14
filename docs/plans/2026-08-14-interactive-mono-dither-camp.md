# Interactive Mono Dither Camp Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the current vertical camp report with the approved read-only, desktop-first Mono Dither camp whose archive desk, stable, and fire reveal real POOL, SHELF/NOW, and SELF data.

**Architecture:** Keep `camp_status.py` as the only runtime entry point and keep the output as one self-contained HTML file. Extend its pure parsing layer for SELF, NOW, and display-time bands; enrich parsed SHELF rows from the exact project roots; then replace the report renderer with a namespaced scene, compact floating panels, embedded day/night assets, and a small deterministic JavaScript state machine. Add no framework, package manager, server, or runtime network request.

**Tech Stack:** Python 3 standard library, existing optional Pillow helpers, embedded HTML/CSS/vanilla JavaScript, two checked-in dithered PNG assets, assert-based Python tests.

**Design source:** `docs/superpowers/specs/2026-08-14-interactive-mono-dither-camp-design.md`

---

## Execution rules

- Work in the repository root `10_Source/daqi.skill`.
- Do not stage or commit `.superpowers/`; it contains brainstorming prototypes only.
- Before the two image-generation calls in Task 5, request explicit approval because they may consume an external generation quota. If approval is not given, stop at that task instead of substituting a generic landscape.
- Preserve the exact bytes of every input store and project NOW file in tests.
- Use exact project roots from `SHELF.md`. Never search siblings or fall back to another store.
- Every implementation commit must stage only the files named by its task.

### Task 1: Lock the new parser contracts with failing tests

**Objective:** Define the exact SELF, NOW, activity-band, and missing-data behavior before changing production code.

**Files:**

- Modify: `tests/test_camp_status.py`
- Test: `tests/test_camp_status.py`

**Step 1: Add a direct module loader to the test file**

Add this after the `SCRIPT` constant so pure functions can be tested without introducing pytest:

```python
import importlib.util

SPEC = importlib.util.spec_from_file_location("camp_status", SCRIPT)
camp_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(camp_status)
```

**Step 2: Add representative SELF and NOW fixtures**

Use fixtures that distinguish real entries from template placeholders:

```python
SELF_PROFILE = """---
management_language: zh
---

# SELF —— 你的档案

## 你的档案（热区，均为可选）

- 决策方式：先看真实材料，再定一个主方向
- 质量标准：必须有可观察的完成证据
- 沟通偏好：结论先说，过程保持紧凑
- 授权边界：发布和外部写入必须先确认

## 长期目标

- 把点子养到能被真实使用

## 记录规则

- 这段政策文字不能成为用户档案
"""

SELF_TEMPLATE_ONLY = """## 你的档案（热区，均为可选）

- 行业：<用户明确提供且影响协作时才写>
- 职业：<用户明确提供且影响协作时才写>

## 长期目标

<只有用户希望跨项目持续携带时才写>
"""

NOW_ZH = """---
daqi: 1
---

# NOW —— 这票到哪了

## Goal

交付一个可运行营地。

## Verified now

- 只读解析已经通过。

## Next

完成场景交互。

## Done when

浏览器验收通过。
"""
```

**Step 3: Add pure parser checks**

```python
def check_profile_and_now_parsing() -> None:
    profile = camp_status.parse_self(SELF_PROFILE)
    assert [item["label"] for item in profile["traits"]] == [
        "决策方式", "质量标准", "沟通偏好", "授权边界"
    ]
    assert profile["goals"] == ["把点子养到能被真实使用"]
    assert camp_status.parse_self(SELF_TEMPLATE_ONLY) == {"traits": [], "goals": []}

    now = camp_status.parse_now(NOW_ZH)
    assert now["goal"] == "交付一个可运行营地。"
    assert "只读解析已经通过" in now["verified"]
    assert now["next"] == "完成场景交互。"
    assert now["done_when"] == "浏览器验收通过。"
```

**Step 4: Add deterministic activity-band checks**

```python
def check_activity_bands() -> None:
    today = datetime.date(2026, 8, 14)
    assert camp_status.classify_activity("2026-08-14", today) == "riding"
    assert camp_status.classify_activity("2026-08-08", today) == "riding"
    assert camp_status.classify_activity("2026-08-07", today) == "week"
    assert camp_status.classify_activity("2026-07-16", today) == "week"
    assert camp_status.classify_activity("2026-07-15", today) == "month"
    assert camp_status.classify_activity("unknown", today) == "unknown"
    assert camp_status.classify_activity("", today) == "unknown"
```

Also import `datetime` and call both new checks from `main()`.

**Step 5: Run the test and verify the intended failure**

Run:

```bash
python3 tests/test_camp_status.py
```

Expected: FAIL with `AttributeError: module 'camp_status' has no attribute 'parse_self'`.

**Step 6: Commit the failing contract tests**

```bash
git add tests/test_camp_status.py
git commit -m "test: define interactive camp data contracts"
```

### Task 2: Implement SELF, NOW, and time-band parsing

**Objective:** Make the new pure parser tests pass with the smallest standard-library implementation.

**Files:**

- Modify: `skills/daqi/scripts/camp_status.py:22-291`
- Test: `tests/test_camp_status.py`

**Step 1: Add the activity display constants**

Keep source SHELF headers compatible, but define separate display bands:

```python
DISPLAY_BANDS = [
    ("riding", "在跑"),
    ("week", "7 天没动"),
    ("month", "30 天没动"),
    ("unknown", "时间未知"),
]
```

Do not replace `BANDS` or `BAND_TOKENS`; they still parse legacy/source SHELF sections.

**Step 2: Implement placeholder rejection once**

```python
def is_placeholder(value: str) -> bool:
    value = value.strip()
    return not value or value in {"—", "-", "<空>"} or (value.startswith("<") and value.endswith(">"))
```

**Step 3: Implement `parse_self`**

```python
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
```

**Step 4: Implement `parse_now`**

Use one section collector so Markdown bullets remain readable without inventing a Markdown dependency:

```python
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
```

**Step 5: Implement `classify_activity`**

```python
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
```

**Step 6: Run the parser contract tests**

Run:

```bash
python3 tests/test_camp_status.py
```

Expected: the new parser checks pass; later integration assertions may still describe the old HTML.

**Step 7: Commit the parser implementation**

```bash
git add skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "feat: parse camp profile checkpoints and activity"
```

### Task 3: Enrich exact SHELF projects from NOW without writes

**Objective:** Attach one safe checkpoint result and a computed display band to each parsed project.

**Files:**

- Modify: `skills/daqi/scripts/camp_status.py:262-306`
- Modify: `tests/test_camp_status.py`

**Step 1: Extend the test store helper to create exact project roots**

Add:

```python
def make_project(now_text: str | None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="daqi-project-"))
    if now_text is not None:
        context = root / "00_Context"
        context.mkdir()
        (context / "NOW.md").write_text(now_text)
    return root
```

Build a SHELF fixture with three valid dates and one invalid date using these temporary paths.

**Step 2: Add the failing enrichment check**

```python
def check_project_enrichment_and_readonly() -> None:
    with_now = make_project(NOW_ZH)
    without_now = make_project(None)
    projects = [
        {"name": "A", "path": str(with_now), "last": "2026-08-14", "agent": "Codex"},
        {"name": "B", "path": str(without_now), "last": "bad-date", "agent": "Claude Code"},
    ]
    now_bytes = (with_now / "00_Context" / "NOW.md").read_bytes()
    result, warnings = camp_status.enrich_projects(projects, datetime.date(2026, 8, 14))
    assert result[0]["display_band"] == "riding"
    assert result[0]["now"]["next"] == "完成场景交互。"
    assert result[1]["display_band"] == "unknown"
    assert result[1]["now"] is None
    assert warnings == []
    assert (with_now / "00_Context" / "NOW.md").read_bytes() == now_bytes
```

**Step 3: Run and verify failure**

Run `python3 tests/test_camp_status.py`.

Expected: FAIL because `enrich_projects` does not exist.

**Step 4: Implement flattening and exact enrichment**

```python
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
```

Do not call `resolve()`, glob, `rglob`, or sibling search. The SHELF path is the trust boundary.

**Step 5: Run the tests and commit**

Run `python3 tests/test_camp_status.py`.

Expected: PASS for parser and enrichment checks.

```bash
git add skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "feat: read exact project checkpoints for camp"
```

### Task 4: Integrate SELF and enriched projects in the command path

**Objective:** Pass complete read-only camp data into the renderer while preserving required-store failure behavior.

**Files:**

- Modify: `skills/daqi/scripts/camp_status.py:462-510`
- Modify: `tests/test_camp_status.py`

**Step 1: Expand `make_store` without making SELF required**

```python
def make_store(pool: str, shelf: str, self_text: str | None = None) -> Path:
    store = Path(tempfile.mkdtemp(prefix="daqi-camp-"))
    (store / "POOL.md").write_text(pool)
    (store / "SHELF.md").write_text(shelf)
    if self_text is not None:
        (store / "SELF.md").write_text(self_text)
    return store
```

**Step 2: Add integration assertions**

- A store with `SELF_PROFILE` must render its confirmed traits.
- A store without SELF must still generate successfully and include `现在还认不出你`.
- A template-only SELF must produce the same honest empty profile.
- Input bytes for POOL, SHELF, SELF, and project NOW must remain identical.
- `main()` must still return 2 and write no HTML when POOL or SHELF is absent.

**Step 3: Run and verify the failing integration test**

Run `python3 tests/test_camp_status.py`.

Expected: FAIL because `main()` does not yet read SELF or enrich projects.

**Step 4: Update `main()` with optional SELF and exact NOW enrichment**

Use this data flow:

```python
self_path = store / "SELF.md"
profile = parse_self(self_path.read_text()) if self_path.is_file() else {"traits": [], "goals": []}
projects, warn_now = enrich_projects(flatten_projects(bands), gen_ts.date())
warnings = warn_pool + warn_shelf + warn_now
html_text = render_html(store, pool, projects, profile, warnings, gen_ts)
```

The required-file check for POOL and SHELF stays before all optional reads.

**Step 5: Update `render_html` and `summarize` signatures only enough to keep the file runnable**

Temporarily accept `projects` and `profile` even though Task 6 replaces the old markup. Do not duplicate enrichment inside the renderer.

**Step 6: Run all existing tests and commit**

Run `python3 tests/test_camp_status.py`.

Expected: all parser, integration, missing-store, warning, and byte-preservation checks pass.

```bash
git add skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "feat: assemble read-only interactive camp data"
```

### Task 5: Create and approve the paired camp scene assets

**Objective:** Produce an original day/night pair with shared geometry and committed dither treatment, without runtime network access.

**Files:**

- Create: `skills/daqi/assets/camp-night.png`
- Create: `skills/daqi/assets/camp-day.png`
- Create: `skills/daqi/assets/camp-scene.prompt.md`

**Step 1: Request explicit image-generation approval**

Ask once before calling image generation. State that the plan uses one original night generation and one geometry-preserving day edit, then local dither processing. Do not call the service until approved.

**Step 2: Generate the original night composition**

Use the approved reference only as style direction. The prompt must require an original 16:9 composition with:

- large left tent and archive desk/crate;
- central campfire with free UI space around it;
- right stable/hitching post and horse silhouette;
- lake, mountain ridge, dense trees, and star field;
- no text, no UI, no characters, no color except neutral source tones;
- high-contrast engraving/halftone structure suitable for 1-bit Floyd–Steinberg conversion.

**Step 3: Create the day edit from the generated night asset**

Lock camera, object positions, and silhouettes. Replace the night sky and star exposure with overcast daylight, preserve the same hotspot geometry, and keep grayscale tonal separation. Do not create a simple inversion.

**Step 4: Apply final local dither treatment**

- Night: 1600×900, high-contrast grayscale, 1-bit Floyd–Steinberg.
- Day: 1600×900, four gray levels using the existing Bayer 4×4 matrix or an equivalent hard ordered dither.
- Optimize PNGs without changing dimensions.

Record the generation prompts, source/output dimensions, and processing commands in `camp-scene.prompt.md`. Do not include private temporary paths.

**Step 5: Inspect the assets side by side**

Verify:

- archive desk, fire, and stable occupy matching coordinates;
- UI panels have open negative space on the opposite side of each focus;
- the fire remains visible in both modes but is not baked in as the only animation;
- no text, watermark, soft blur, or chromatic accent is present in the scene assets.

**Step 6: Commit only the approved assets and provenance note**

```bash
git add skills/daqi/assets/camp-night.png skills/daqi/assets/camp-day.png skills/daqi/assets/camp-scene.prompt.md
git commit -m "feat: add paired dither camp scenes"
```

### Task 6: Replace the vertical report with the scene-first HTML shell

**Objective:** Render the approved three-function camp and meaningful compact panels from real parsed data.

**Files:**

- Modify: `skills/daqi/scripts/camp_status.py:61-456`
- Modify: `tests/test_camp_status.py`

**Step 1: Replace old HTML assertions with the approved UI contract**

Add assertions for:

```python
assert "营地账本" in html
assert "情报 · 点子 · 计划" in html
assert "马厩" in html and "干一票" in html
assert "火" in html and "你是谁？" in html
assert "7 天没动" in html and "30 天没动" in html
assert "达奇对你的认知" in html
assert "这票到哪了" in html
assert "data:image/png;base64," in html
assert "POOL / CAMP LEDGER" not in html
assert "LAST_SEEN · NO AGENT" not in html
assert "READ-ONLY" not in html
```

Add one POOL-only sentinel Agent string and assert it is absent from ledger markup. Assert SHELF Agent values are present.

**Step 2: Run and verify failure**

Run `python3 tests/test_camp_status.py`.

Expected: FAIL on the approved scene labels and removed engineering labels.

**Step 3: Add a standard-library asset loader**

```python
def asset_data_uri(name: str) -> str:
    path = Path(__file__).resolve().parent.parent / "assets" / name
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
```

Missing approved scene assets should be a clear renderer error during development, not a silent icon fallback.

**Step 4: Replace `PAGE_CSS` with the approved namespaced visual system**

Use one prefix such as `camp-` for every scene object, state, panel, and control. In particular, physical stable and stable panel must be distinct names such as:

```css
.camp-stable-object { /* scene geometry only */ }
.camp-panel-stable { /* paper panel only */ }
```

Required CSS contracts:

- full-viewport scene-first layout;
- detached 36–42% paper panels;
- palette and typography from the design spec;
- 1px borders, 0–2px radius, no ordinary shadow;
- selected Tags use hard monochrome checker/Bayer texture;
- no soft gradient, blur, scanline, glitch, or RGB split;
- scene focus transforms use 6–8-step motion;
- `prefers-reduced-motion` removes camera interpolation and ambient loops;
- a readable stacked fallback below the supported desktop width.

**Step 5: Render the three overview buttons beside their real scene objects**

Use semantic buttons with exact visible copy and stable `data-view` values:

```html
<button class="camp-feature camp-feature-ledger" data-view="ledger">
  <strong>营地账本</strong><span>情报 · 点子 · 计划</span>
</button>
<button class="camp-feature camp-feature-self" data-view="self">
  <strong>火</strong><span>你是谁？</span>
</button>
<button class="camp-feature camp-feature-stable" data-view="stable">
  <strong>马厩</strong><span>干一票</span>
</button>
```

**Step 6: Render data as JSON once, then let the embedded UI filter it**

Avoid duplicate Python markup for every Tag. Serialize escaped structured data into an application JSON script:

```python
payload = {
    "ledger": pool,
    "projects": projects,
    "profile": profile,
    "generated_at": gen_ts.isoformat(),
}
payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
```

Add `import json`. Embed as:

```html
<script type="application/json" id="camp-data">{payload_json}</script>
```

All user-controlled text inserted into `innerHTML` must pass through a JavaScript escaping helper, or be assigned with `textContent`. Prefer DOM creation and `textContent` at trust boundaries.

**Step 7: Render meaningful empty and error states**

- Empty ledger Tag: no items in this stage.
- Empty time Tag: no projects in this band.
- Invalid date: conditional `时间未知` Tag.
- Missing NOW: no current checkpoint available.
- Empty profile: approved “现在还认不出你” copy.
- Parse warning: compact notice only when it affects visible data.

**Step 8: Run tests and commit the shell**

Run `python3 tests/test_camp_status.py`.

Expected: all structural, data-source, empty-state, missing-store, and read-only assertions pass.

```bash
git add skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "feat: render scene-first mono dither camp"
```

### Task 7: Implement the deterministic interaction and time state machine

**Objective:** Make click, Tags, NOW depth, one-level back, pagination, day/night, and accessibility behavior match the approved contract.

**Files:**

- Modify: `skills/daqi/scripts/camp_status.py` (`PAGE_JS` and generated markup)
- Modify: `tests/test_camp_status.py`

**Step 1: Add structural JavaScript assertions before implementation**

Assert generated HTML contains stable hooks rather than implementation prose:

```python
for hook in (
    'data-view="ledger"',
    'data-view="stable"',
    'data-view="self"',
    'data-action="back"',
    'data-action="time-auto"',
    'data-action="time-day"',
    'data-action="time-night"',
):
    assert hook in html
assert "prefers-reduced-motion" in html
assert "localStorage" in html
```

**Step 2: Run and verify failure**

Run `python3 tests/test_camp_status.py`.

Expected: FAIL on missing state hooks.

**Step 3: Implement one explicit view model**

Use these states only:

```javascript
const state = {
  view: 'overview',       // overview | ledger | stable | self
  stableDepth: 'list',    // list | now
  ledgerTag: 'intel',
  stableTag: 'riding',
  ledgerPage: 0,
  stablePage: 0,
  timeMode: 'auto',       // auto | day | night
};
```

Do not create a router or generic state framework.

**Step 4: Implement one-level parent navigation**

```javascript
function goBackOneLevel() {
  if (state.view === 'stable' && state.stableDepth === 'now') {
    state.stableDepth = 'list';
  } else if (state.view !== 'overview') {
    state.view = 'overview';
  }
  renderState();
}
```

Wire the explicit back button and Escape to this function.

**Step 5: Implement the downward-wheel gesture guard**

Accumulate positive `deltaY` only inside the camp. Navigate once after a threshold, then require a quiet interval before another navigation:

```javascript
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
```

At overview, prevent document movement only while pointer focus is inside the full-viewport camp.

**Step 6: Implement day/night selection and persistence**

- `AUTO`: local hour `>= 6 && < 18` means day.
- Store only manual `day` or `night` under a namespaced key such as `daqi.camp.timeMode`.
- Choosing auto removes that key.
- Re-evaluate automatic time on a short minute interval.
- Keep all three controls keyboard reachable and expose selected state with `aria-pressed`.

**Step 7: Implement Tag filtering and five-row pagination**

- Changing a Tag resets its page to zero.
- Pagination never uses vertical wheel.
- Conditional `unknown` stable Tag appears only when at least one project needs it.
- Project selection stores the selected project index and switches `stableDepth` to `now`.
- Returning preserves stable Tag and page.

**Step 8: Implement fire animation and reduced motion**

- Add a stepped 6–8-frame micro-yellow flame layer independent of the grayscale raster scene.
- Day reduces flame emphasis and increases smoke legibility.
- Reduced motion shows a static flame and immediate scene/panel state changes.

**Step 9: Run tests and commit interactions**

Run `python3 tests/test_camp_status.py`.

Expected: all tests pass.

```bash
git add skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "feat: add camp focus tags and time controls"
```

### Task 8: Update the command summary and public documentation

**Objective:** Make CLI and README language accurately describe the new read sources, display bands, and interaction without overstating proof.

**Files:**

- Modify: `skills/daqi/references/camp-view.md`
- Modify: `README.zh-CN.md:228-237`
- Modify: `README.md:229-237`
- Modify: `skills/daqi/scripts/camp_status.py:462-483`
- Modify: `tests/test_camp_status.py`

**Step 1: Update the failing stdout assertions**

Replace old `松了 / 歇马` expectations with render-time display bands:

```python
assert "在跑 1 · 7 天没动 0 · 30 天没动 1" in result.stdout
```

Add `时间未知` only when the fixture contains an invalid date.

**Step 2: Run and verify failure**

Run `python3 tests/test_camp_status.py`.

Expected: FAIL because `summarize()` still reports source SHELF sections.

**Step 3: Update `summarize()`**

Count enriched projects by `display_band`. Keep the exact read-only receipt and output path. Do not mention removed engineering UI labels.

**Step 4: Update the camp reference contract**

Document:

- reads POOL, SHELF, optional SELF, and exact project `00_Context/NOW.md`;
- only derived HTML is written;
- three scene functions and their real data owners;
- 7/30-day display bands do not rewrite SHELF source status;
- local-time day/night plus browser-only override;
- one-level downward-wheel back behavior;
- missing SELF/NOW and invalid-date handling.

**Step 5: Update Chinese and English README sections**

Replace the old vertical-report and 65%-cream page description. Keep claims bounded to local generated HTML and browser-verified interaction; do not claim all Agent hosts were tested.

**Step 6: Run tests and commit documentation**

Run `python3 tests/test_camp_status.py`.

Expected: PASS with updated CLI summary.

```bash
git add skills/daqi/references/camp-view.md README.zh-CN.md README.md skills/daqi/scripts/camp_status.py tests/test_camp_status.py
git commit -m "docs: describe interactive read-only camp"
```

### Task 9: Run full automated and read-only verification

**Objective:** Prove repository behavior and source-file immutability before visual QA.

**Files:**

- Modify only if a verification failure reveals a bug in files already listed above.

**Step 1: Run the focused camp test**

```bash
python3 tests/test_camp_status.py
```

Expected final line:

```text
PASS: interactive camp data, states, empty cases, missing store, readonly sources
```

**Step 2: Run all repository tests**

```bash
python3 tests/test_rebuild_shelf.py
python3 tests/test_checkpoint.py
python3 tests/test_codex_continuity.py
python3 tests/test_camp_status.py
```

Expected: all four scripts print PASS and exit 0.

**Step 3: Generate a fixture-backed final HTML**

Use the test helper or an explicit temporary fixture store; do not modify the user's real store for automated checks. Confirm the output is a single HTML file and contains no `http://`, `https://`, external `<script src>`, or stylesheet link.

**Step 4: Verify byte preservation**

The focused test must compare bytes for POOL, SHELF, optional SELF, and project NOW before and after generation. Treat any mismatch as a release blocker.

**Step 5: Verify repository diff scope**

Run:

```bash
git status --short
git diff --check
git diff --stat
```

Expected: only planned files differ; `.superpowers/` remains untracked and unstaged unless separately ignored later.

No commit is needed if verification passes without changes. If a bug is fixed, rerun the focused and full suites, then commit the exact fix files with `fix: ...`.

### Task 10: Perform local browser interaction and screenshot QA

**Objective:** Verify the actual generated page at approved desktop sizes in both time modes, without confusing browser proof with external/live proof.

**Files:**

- Modify only if QA identifies a concrete bug.
- Temporary screenshots: `/tmp/daqi-camp-*.png` (never commit).

**Step 1: Generate the page from a fixture with all states**

The fixture must include:

- at least one intel, idea, and plan;
- projects in riding, 7-day, 30-day, and unknown bands;
- one project with complete NOW and one without NOW;
- a populated SELF profile;
- enough rows to exercise pagination.

**Step 2: Inspect at the three target viewports**

- 1280×800
- 1440×900
- 1728×1117

Check both forced day and forced night. Confirm labels remain attached to their objects and the focused object remains visible beside its detached panel.

**Step 3: Exercise the complete interaction flow**

- Overview → ledger → every Tag → pagination → down-wheel back.
- Overview → stable → every time Tag → project → NOW detail → one down-wheel to stable list → second down-wheel to overview.
- Overview → fire → populated profile; repeat with empty-profile fixture.
- Auto/day/night controls, persistence after reload, and return to auto.
- Tab order, Enter/Space, Escape, visible focus, and reduced motion.

**Step 4: Inspect visual compliance**

Confirm:

- no full-height side drawer;
- no ordinary shadow, soft gradient, blur, CRT scanline, glitch, or RGB split;
- paper panels use warm grayscale, 1px rules, and no decorative terminal copy;
- selected Tags use monochrome dither texture;
- fire is the only chromatic element and remains restrained;
- day/night geometry is identical;
- no text clipping at longest real labels and time values.

**Step 5: Capture evidence screenshots**

Capture at minimum:

- night overview;
- day overview;
- ledger with selected Tag;
- stable project list with Agent/time;
- NOW detail;
- profile populated or honest empty state.

**Step 6: Re-run automated tests after any visual fix**

Run all four repository test scripts again. Expected: PASS.

**Step 7: Commit exact QA fixes if needed**

Stage only the production/test/docs files actually changed. Never commit `/tmp` screenshots or `.superpowers/` prototypes.

---

## Final handoff evidence

The implementation handoff must separately report:

- **Implemented:** exact files and interactions now present.
- **Automated verification:** commands and PASS counts.
- **Local browser verification:** tested viewport/mode/flow evidence and screenshots.
- **Read-only proof:** confirmed unchanged input bytes.
- **Not proved:** behavior in every Agent host, real external publishing, or any write action from the HTML.
