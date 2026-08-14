# Camp scene asset provenance

Generated on 2026-08-14 with the built-in `imagegen` tool. The reference supplied during design was used only as style direction; the scene composition is original.

## Night generation

Use case: `stylized-concept`

Prompt summary:

> Create an original 16:9 night wilderness camp for a desktop interactive UI in a contemporary Grayscale Dither Archive style. Arrange three readable zones in one fixed wide scene: a large canvas tent and archive desk on the left, an unobstructed campfire in the center, and a rustic stable or hitching rail with one horse on the right. Place a lake, mountain ridge, pine forest, stars, and a subtle Milky Way behind them. Use high-contrast monochrome engraving, visible stipple, etched lines, and low-bit grayscale structure. Preserve detail in dark areas and leave restrained negative space around the three zones. No people, text, UI, logos, watermark, blur, glossy 3D, retro-game sprites, ASCII, CRT, glitch, RGB split, or cyberpunk color.

The generation prompt also locked the intended hotspot centers near 22%, 51%, and 80% of the image width, and allowed only a tiny muted fire accent in the generated source. The final checked-in asset removes that color during 1-bit conversion.

Source dimensions: `1672 x 941`, RGB PNG.

## Day edit

Use case: `lighting-weather`

Prompt summary:

> Treat the generated night image as the edit target and geometry master. Change only the time of day and environmental illumination to calm soft daytime. Keep the exact camera, crop, perspective, horizon, mountains, lake geometry, trees, rocks, tent, archive desk, fire ring, stable, hitching rail, horse identity and pose, and all object spacing unchanged. Preserve the monochrome engraving, stipple, low-bit grayscale, and hard tonal steps. Do not add, remove, move, resize, redesign, or reinterpret objects. No text, UI, saturated sky, sunset wash, sepia, blur, retro-game styling, ASCII, CRT, glitch, or geometry drift.

Source dimensions: `1672 x 941`, RGB PNG.

## Local processing

Both generated sources were resized to exactly `1600 x 900` with Pillow Lanczos resampling and grayscale autocontrast (`cutoff=1`).

- `camp-night.png`: converted to mode `1` with Pillow Floyd-Steinberg dithering, then PNG optimized.
- `camp-day.png`: converted to grayscale and quantized to four values (`0`, `85`, `170`, `255`) with a hard Bayer 4x4 ordered-dither matrix, then PNG optimized.

The scene assets are intentionally achromatic. The small warm fire color and flame motion are rendered separately by the generated HTML so they remain interactive and can honor reduced-motion preferences.

Final dimensions:

- `camp-night.png`: `1600 x 900`, 1-bit grayscale.
- `camp-day.png`: `1600 x 900`, four used grayscale levels stored in an 8-bit grayscale PNG.
