# Camp view (read-only) / 营地盘点（只读）

Load this reference when the user asks for `营地` / `盘点` / `清点` (`camp` / `count` / `camp view`), or wants a read-only picture of the camp.

## Contract

- Run `scripts/camp_status.py --store <STORE_ROOT>` (optionally `--out <path>`). Default output: `<STORE_ROOT>/camp.html`.
- The script reads `POOL.md`, `SHELF.md`, optional `SELF.md`, and only `<exact-project-path>/00_Context/NOW.md` for projects recorded in SHELF. It never searches siblings or alternate roots.
- It writes only the derived HTML artifact. It never modifies SELF/SHELF/POOL/NOW/HANDOFF. If `--out` aliases any input path directly, through a symlink, or through a hardlink, exit with code 2 before writing.
- Print the script's stdout summary verbatim and give the HTML path. Do not hand-count the stores.
- If the store is incomplete (missing `POOL.md` or `SHELF.md`), report the script's error and stop. Do not substitute another store.
- The HTML is a snapshot: re-run to refresh after the ledger or stables change.

## Scene and data contents

- Overview: one scene with three object-bound buttons: `营地账本 / 情报 · 点子 · 计划`, `马厩 / 干一票`, and `火 / 你是谁？`.
- Ledger panel: switchable 情报/点子/计划 Tags; entry text and `last_seen` only. Never show Agent here.
- Stable panel: switchable 在跑 (`<7` full days), 7 天没动 (`7–29`), 30 天没动 (`>=30`), and conditional 时间未知 Tags. Every row shows project, last active, and Agent.
- Project depth: clicking a Stable row opens `这票到哪了` with Goal, Verified now, Next, and Done when. Missing, malformed, template-only, or unreadable NOW degrades to an honest unavailable state.
- Fire panel: `达奇对你的认知` renders only confirmed SELF traits and durable goals. A missing or template-only SELF shows `现在还认不出你`; never infer a profile from chat.
- Compact warning copy appears only when source data could not be rendered. All panels have meaningful empty states.

## Interaction contract

- Initial state is the overview. Clicking an object moves the scene closer and raises a detached paper panel; never use a full-height side drawer.
- Down-wheel and `Esc` call the same one-level-back behavior. Stable NOW returns to the Stable list first, then the overview. One continuous wheel gesture may navigate only once.
- Ledger and Stable lists use five-row pages rather than scroll-heavy panels.
- `自动` resolves from browser local time: day from 06:00 inclusive to 18:00 exclusive, night otherwise. Manual `白天` / `夜晚` persists in localStorage across reloads.
- Buttons, Tags, focus order, `aria-pressed`, `aria-expanded`, and the polite live region remain keyboard and screen-reader operable.

## Visual contract — Grayscale Dither Archive / 灰阶点阵档案

- Palette: background `#F2F2EE`, secondary `#E5E5E0`, paper `#FAFAF7`, text `#111111`, secondary text `#72726C`, border `#C9C9C2`, black `#050505`, reverse text `#F5F5F2`. Only the animated flame may use muted yellow `#D9BC72`.
- Typography: modern sans-serif for headings and body; monospace for numbers, labels, timestamps, and IDs. No pixel font — monospace carries the terminal detail; readability always wins.
- Imagery: paired, geometry-aligned `1600×900` scenes embedded into the output: 1-bit Floyd–Steinberg night and four-level Bayer 4×4 day. Keep visible grain and hard tonal steps. No runtime network images.
- Components: compact 36–42% paper panels, 1px solid borders, radius 0–2px, no drop shadow or blur; hover = black/white inversion; selected Tag = black inverse plus a small checker mark; disabled ≈ 40% gray; generous whitespace.
- Motion: scene focus, panel entrance, image switching, and flame use short `steps()` transitions. `prefers-reduced-motion` removes camera interpolation and ambient flame motion. No CRT scanlines, glitch, RGB split, or soft cinematic gradients.
- If the HTML is extended, keep it self-contained: no external assets, no network, no runtime JS dependency, and keep every store file untouched.
