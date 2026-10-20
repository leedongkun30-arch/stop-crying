---
name: stop-crying
description: Reduce broad color mottling around text in raster diagrams using text-protected background filtering. Use for AI-generated background blotches and stop crying cleanup. Includes explicit flat-field cleanup for persistent mottling on dark, light, or neutral fills, and a separate narrow-halo mode; not for spelling correction, glyph reshaping, intentional texture removal, or photographic restoration.
---

# Stop Crying

Preserve the original and produce a separate PNG using deterministic image processing. Determine whether the defect is **broad background-color mottling**, a narrow bright fringe, or irregular glyph geometry before choosing a treatment. Do not assume that every complaint of background artifacts means a text halo. If a prior result is rejected, align on the visible defect before tuning further.

## Choose the target

- **Broad color mottling around text:** default `--method background`. Exclude dark ink from a temporary background estimate, filter the colored background over a wider spatial scale, then apply background-color changes while preserving ink. This does not fit or fill polygons.
- **Persistent mottling on an intended solid fill:** use `scripts/flatten_fields.py` with explicitly selected surface rectangles and target colors. This includes dark and neutral backgrounds excluded by the default filter. Read [flat-field cleanup](references/flat-fields.md) for geometry, preservation limits, and validation.
- **Narrow bright fringe attached to text:** `--method rolling`, with text/fringe exclusion and local antialias recomposition. This is a different task; its six-pixel neighborhood cannot remove broad mottling.
- **Simple flat or quadratic fill near text:** `--method polynomial`, the earlier local estimator. Use only when visual comparison supports it.
- Glyph shape, spelling, deliberate outlines, and textured paper need another treatment. Light lettering on dark solid fills can use explicit flat fields after inspection. Do not silently smooth them away.

A `strong` preset is not evidence that broad mottling has been removed. The default transfers only part of a filtered background change and excludes dark/neutral fills. When the visible defect remains, inspect matching crops and choose a different treatment rather than repeatedly applying the same preset. Synthetic fringe scores do not measure broad mottling removal.

## Run

Requires NumPy and Pillow. Flat fields require OpenCV; background/rolling modes also require `opencv-contrib-python-headless` with `ximgproc`; ordinary `opencv-python` may not suffice. Use a suitable existing runtime or isolated dependency directory/venv, not an unsolicited modification to a shared runtime. The Codex desktop dependency loader can locate a Python runtime. Do not hard-code another user's paths.

`detect_text.swift` uses on-device macOS Vision and Swift. It may need a permitted local execution context. Other OCR can supply the same box format. Reuse OCR for identical source pixels.

```sh
swiftc -module-cache-path <work>/swift-cache <skill>/scripts/detect_text.swift -o <work>/detect_text
<work>/detect_text INPUT.png <work>/text-boxes.json
<python> <skill>/scripts/clean_text.py INPUT.png <work>/cleaned.png --boxes <work>/text-boxes.json --background-scale strong
```

Use absolute paths and fresh outputs. Input must be upright RGB/RGBA. Existing outputs and mismatched box dimensions are refused. JSON uses top-left source pixels:

```json
{"width":640,"height":150,"boxes":[{"box":[25,40,430,115],"confidence":1.0}]}
```

OCR supplies proposals, not glyph masks. Review the `.regions.png` overlay. Remove/split proposals that encompass unrelated artwork or multiple incompatible surfaces. Manually supplied boxes must not be reported as detected.

## Background mode

`--background-scale mild|medium|strong` defaults to **strong**. Medium is a lower-intensity option. The presets increase spatial/color smoothing; stronger settings can flatten intended gradients and marker texture. `--strength` (above zero through 1) scales the change. `--radius` applies only to narrow-fringe/polynomial modes, not this mode.

Background mode estimates a temporary ink-free background, applies a domain-transform edge-aware filter at full resolution, and transfers the background change back with a soft ink-opacity weight. It acts on light chromatic fills near text, tapering to zero within 20 source pixels of the OCR proposals. Dark cores remain identical. It is not a global recoloring or a guarantee that every intentional gradient survives.

Read [background filtering details](references/background.md) when adapting scale, inspecting boundary spill, or discussing preservation. For the optional narrow-fringe methods, read [local methods](references/method.md).

## Inspect and report

Compare the same source-coordinate crops at 3×–5× nearest-neighbor enlargement and at normal size. For background mottling, inspect the **spaces between letters and the wider fill above/below them**, not only the one-pixel fringe. Show original/mild/medium/strong when the strength tradeoff matters.

Check small text, fill boundaries, gradient shape, dark cores, and transparency. Core equality alone does not establish preserved glyph appearance. Both stronger flattening and leftover mottling should be visible in the comparison, rather than hidden by a favorable crop.

Use the saved PNG and `.report.json` to verify dimensions, core equality, alpha, and unchanged pixels outside support. Reports and masks are diagnostics, not artwork. Do not call synthetic RMSE a perceptual success score or infer user acceptance from it. Actual-image comparisons are the primary evidence for this task.

For changes to the default background filter, run:

```sh
<python> <skill>/scripts/selftest_background.py --font PATH_TO_BOLD_TTF --output-dir FRESH_TEST_DIRECTORY
```

`selftest.py` separately checks narrow-fringe rolling behavior. It does not validate broad mottling removal.

Deliver the new PNG and visible before/after or strength comparison. State which defect was treated and the observed tradeoff. Do not declare a universally best method from one image or claim a complaint is resolved solely because metrics improved.
