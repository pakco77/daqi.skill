# Camp view (read-only) / 营地盘点（只读）

Load this reference when the user asks for `营地` / `盘点` / `清点` (`camp` / `count` / `camp view`), or wants a read-only picture of the camp.

## Contract

- Run `scripts/camp_status.py --store <STORE_ROOT>` (optionally `--out <path>`). Default output: `<STORE_ROOT>/camp.html`.
- The script reads only `POOL.md` and `SHELF.md`, without modifying them, and writes only the derived HTML artifact. It never touches SELF/SHELF/POOL/NOW/HANDOFF.
- Print the script's stdout summary verbatim and give the HTML path. Do not hand-count the stores.
- If the store is incomplete (missing `POOL.md` or `SHELF.md`), report the script's error and stop. Do not substitute another store.
- The HTML is a snapshot: re-run to refresh after the ledger or stables change.

## Report contents

- Ledger: 情报/点子/计划 counts plus total; one row per entry with stage badge, text, and `last_seen`.
- Stables: 在跑/松了/歇马 counts plus rows (name, path, last active, Agent).
- Empty-state messaging when the camp has no entries; parse warnings appended below.

## Visual contract — Grayscale Dither Archive / 灰阶点阵档案

- Palette: bg `#F2F2EE`, secondary `#E5E5E0`, card `#FAFAF7`, text `#111111`, secondary text `#72726C`, border `#C9C9C2`, black `#050505`, reverse text `#F5F5F2`. Page ratio ≈ 65% cream / 20% light gray / 10% black / 5% dither texture.
- Typography: modern sans-serif for headings and body; monospace for numbers, labels, timestamps, and IDs. No pixel font — monospace carries the terminal detail; readability always wins.
- Imagery: 1-bit Floyd–Steinberg dither for the hero, 4-level Bayer 4×4 dither for thumbnails, `image-rendering: pixelated`, visible grain. No gradients, no soft shadows.
- Components: 1px solid borders, radius 0–2px, no drop shadows; hover = black/white inversion; selected = checker/dither fill; disabled ≈ 40% gray; 8px grid; generous whitespace. Stage badges encode maturity by dither density: 情报 outline-only, 点子 sparse checker, 计划 black inverse.
- Motion: frame-like — `steps()` fades, sparse-dot to image development, short discrete transitions. No CRT scanlines, no glitch, no RGB split.
- If the HTML is extended, keep it self-contained: no external assets, no network, no runtime JS dependency, and keep every store file untouched.
