# Explicit flat fields

Use `scripts/flatten_fields.py` when a surface should be one solid color and broad mottling remains after background filtering. It handles dark fields with light lettering and light/neutral fields with dark or red lettering. It intentionally replaces gradients inside the selected fields.

```sh
python scripts/flatten_fields.py input.png output/flat.png --fields fields.json
```

No OCR is required. Inspect the source and select each field separately; these rectangles describe surfaces, not text boxes. Coordinates are integer source pixels, top-left origin, with exclusive right/bottom edges. Exclude outer borders and unrelated artwork. Split a rectangle if it crosses multiple colors. White areas must also be explicitly selected; there is no automatic whole-image whitening.

```json
{
  "width": 640,
  "height": 160,
  "fields": [
    {"rect": [10, 10, 630, 70], "color": [15, 52, 80]},
    {"rect": [10, 80, 630, 150], "color": [255, 255, 255]}
  ]
}
```

Choose each target RGB from the intended design or a representative clean patch. Background pixels must occupy most of each field for the median estimate to work. Later fields override earlier ones using the original pixels, so overlaps do not accumulate corrections. `--strength` in `(0, 1]` blends the correction.

The algorithm estimates the median opaque background in each field. Pixels close to it are flattened to the target; distant foreground colors receive less or no correction. White cores on dark fields and dark/red cores on light fields are protected. Long horizontal/vertical rules are detected separately. Protecting every detected edge would preserve edges caused by mottling itself, leaving visible blotches behind.

This is a heuristic for flat diagrams, not semantic segmentation. Low-contrast text or artwork can resemble background; short, faint or diagonal rules may not be protected. Keep such elements outside fields and inspect antialiasing and small lettering. Do not use this mode for photographs, deliberate texture, multicolor artwork, or gradients that should remain.

Outputs: a new PNG, `.mask.png`, `.regions.png`, and `.report.json`. Reports contain settings and geometry, without input/output paths. Dimensions and alpha are preserved; partly/fully transparent pixels remain identical. Existing output or diagnostic files are refused.

Compare original and output at normal size and matching 3×–5× nearest-neighbor crops. Include light and dark surfaces, inter-letter gaps, small text, and boundaries. Changed-pixel counts and synthetic error reductions are diagnostics, not proof of visual success. If a result is rejected, inspect the remaining defect and change treatment rather than repeatedly increasing the same ineffective filter.

Regression check and synthetic example generation:

```sh
python scripts/selftest_fields.py --font /path/to/bold.ttf --output-dir output/fields-test
```

The test checks known-background restoration, contrasting ink cores, long rules, transparent pixels, unchanged outside-support pixels, repeated fields, invalid rectangles/colors, PNG round-trip, and overwrite refusal. It does not establish preservation for arbitrary artwork.
