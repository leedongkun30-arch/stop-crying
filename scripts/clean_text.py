#!/usr/bin/env python3
"""Conservative local dehalo for dark text on light, smooth backgrounds.
Dependencies: numpy, Pillow. OCR boxes only propose regions; no text is re-rendered.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def dilate(mask, radius):
    if radius <= 0:
        return mask.copy()
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(
        ImageFilter.MaxFilter(radius * 2 + 1))) > 0


def distance_band(mask, radius):
    distance = np.full(mask.shape, radius + 1, dtype=np.float64)
    distance[mask] = 0
    expanded = mask.copy()
    for r in range(1, radius + 1):
        expanded = dilate(expanded, 1)
        distance[expanded & (distance > r)] = r
    return distance


def design(height, width):
    y, x = np.mgrid[-1:1:complex(height), -1:1:complex(width)]
    return np.stack([np.ones_like(x), x, y, x*x, x*y, y*y], axis=-1)


def fit_background(rgb, distance):
    bright = (rgb.min(axis=2) > 105) & (distance > 3)
    if bright.sum() < 60:
        return None
    values = rgb[bright]
    center = np.median(values, axis=0)
    # Reject a second fill/white card border before fitting a smooth color field.
    selected = bright & (np.linalg.norm(rgb - center, axis=2) < 45)
    if selected.sum() < 60:
        return None
    basis = design(*rgb.shape[:2])
    a, b = basis[selected], rgb[selected]
    # Deterministic subsampling bounds the fit cost on large images.
    step = max(1, len(a) // 12000)
    a, b = a[::step], b[::step]
    weight = np.ones(len(a))
    for _ in range(5):
        root = np.sqrt(weight)
        coeff = np.linalg.lstsq(a * root[:, None], b * root[:, None], rcond=None)[0]
        error = np.linalg.norm(a @ coeff - b, axis=1)
        scale = max(1.0, float(np.median(error)) * 1.5)
        weight = np.minimum(1, scale / np.maximum(error, 1e-6))
    median_error = float(np.median(error))
    if median_error > 12:
        return None
    model = np.clip(basis @ coeff, 0, 255)
    # Extrapolation from a thin strip is unsafe; do not accept extreme fields.
    if np.max(np.ptp(model, axis=(0, 1))) > 90:
        return None
    return model, median_error, int(selected.sum())


def clean(rgb_u8, boxes, radius=6, strength=1.0, core_level=80, background_estimator=None, refine_fringe=False):
    rgb = rgb_u8.astype(np.float64)
    height, width = rgb.shape[:2]
    accum = np.zeros_like(rgb)
    weights = np.zeros((height, width))
    records = []
    for index, entry in enumerate(boxes):
        if float(entry.get('confidence', 1)) < 0.3:
            records.append({'index': index, 'status': 'low-confidence'})
            continue
        bx0, by0, bx1, by1 = entry['box']
        x0, y0 = max(0, int(np.floor(bx0)) - radius), max(0, int(np.floor(by0)) - radius)
        x1, y1 = min(width, int(np.ceil(bx1)) + radius), min(height, int(np.ceil(by1)) + radius)
        patch = rgb[y0:y1, x0:x1]
        if min(patch.shape[:2]) < 3:
            continue
        seed = patch.max(axis=2) <= core_level
        # Only dark pixels inside the OCR proposal seed text neighborhoods.
        proposal = np.zeros(seed.shape, dtype=bool)
        px0, py0 = max(0, int(bx0)-x0-1), max(0, int(by0)-y0-1)
        px1, py1 = min(x1-x0, int(np.ceil(bx1))-x0+1), min(y1-y0, int(np.ceil(by1))-y0+1)
        proposal[py0:py1, px0:px1] = True
        text = seed & proposal
        if text.sum() < 10:
            records.append({'index': index, 'status': 'no-dark-text'})
            continue
        distance = distance_band(text, radius + 2)
        all_dark_distance = distance_band(patch.max(axis=2) < 145, 5)
        fitted = (background_estimator or fit_background)(patch, all_dark_distance)
        if fitted is None:
            records.append({'index': index, 'status': 'uncertain-background'})
            continue
        background, error, samples = fitted
        ink = np.median(patch[text], axis=0)
        direction = background - ink
        # Project antialias pixels onto the local ink/background color segment.
        # Pixels farther from the core cannot create new gray glyph outlines.
        opacity = np.clip(np.sum((background-patch)*direction, axis=2) /
                          np.maximum(np.sum(direction*direction, axis=2), 1), 0, 1)
        opacity[distance > 2] = 0
        target = background * (1-opacity[..., None]) + ink * opacity[..., None]
        # Reject other fills, colored decorations and strong boundaries.
        residual = np.linalg.norm(patch-target, axis=2)
        # Bright halos desaturate a fill; a more saturated neighboring fill
        # must not be painted over by a white-card background estimate.
        chroma = np.linalg.norm(np.minimum(
            patch / np.maximum(patch.max(axis=2, keepdims=True), 1) -
            background / np.maximum(background.max(axis=2, keepdims=True), 1), 0), axis=2) * 255
        gate = np.clip((26-residual)/10, 0, 1) * np.clip((26-chroma)/10, 0, 1)
        if refine_fringe:
            fringe = (distance > 0) & (distance <= 2) & proposal
            fringe &= (chroma < 16) & (residual < 80)
            gate[fringe] = 1
        radial = np.clip((radius+1-distance)/max(1, radius/2), 0, 1)
        radial = radial*radial*(3-2*radial)
        weight = strength * radial * gate
        weight[seed | (distance > radius)] = 0
        if refine_fringe:
            # Keep locally inpainted colors from spilling outside the text proposal.
            weight[~proposal] = 0
        accum[y0:y1, x0:x1] += target * weight[..., None]
        weights[y0:y1, x0:x1] += weight
        records.append({'index': index, 'status': 'processed',
                        'background_median_sample_rgb_l2': error, 'background_samples': samples,
                        'candidate_pixels': int((weight > 0).sum())})
    target = accum / np.maximum(weights[..., None], 1e-12)
    mix = np.minimum(weights, strength)
    result = np.rint(rgb*(1-mix[..., None]) + target*mix[..., None]).clip(0,255).astype(np.uint8)
    core = rgb_u8.max(axis=2) <= core_level
    result[core] = rgb_u8[core]
    changed = np.any(result != rgb_u8, axis=2)
    assert np.array_equal(result[core], rgb_u8[core])
    assert np.array_equal(result[weights == 0], rgb_u8[weights == 0])
    return result, changed, records, weights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--boxes', type=Path, required=True,
                        help='JSON: width, height, boxes [{box:[x0,y0,x1,y1],confidence:...}]')
    parser.add_argument('--radius', type=int, default=6, help='Halo neighborhood in source pixels')
    parser.add_argument('--strength', type=float, default=1)
    parser.add_argument('--method', choices=['background', 'rolling', 'polynomial'], default='background',
                        help='background: broad color mottling; rolling: narrow bright fringe; polynomial: quadratic fill')
    parser.add_argument('--background-scale', choices=['mild','medium','strong'], default='strong')
    args = parser.parse_args()
    if not 2 <= args.radius <= 30 or not 0 < args.strength <= 1:
        parser.error('radius must be 2..30; strength must be >0 and <=1')
    if args.output.suffix.lower() != '.png':
        parser.error('output must be PNG')
    report_path = args.output.with_suffix('.report.json')
    mask_path = args.output.with_suffix('.mask.png')
    overlay_path = args.output.with_suffix('.regions.png')
    for path in [args.output, report_path, mask_path, overlay_path]:
        if path.exists():
            parser.error(f'Refusing to overwrite {path}')
    start = time.perf_counter()
    source = Image.open(args.input)
    if source.mode not in ('RGB', 'RGBA'):
        parser.error('Expected RGB/RGBA image; explicitly convert other image modes first')
    if source.getexif().get(274, 1) != 1:
        parser.error('Normalize EXIF orientation before detection and cleanup')
    payload = json.loads(args.boxes.read_text())
    if (payload['width'], payload['height']) != source.size:
        parser.error('Box coordinates do not match the input dimensions')
    boxes = payload['boxes']
    for entry in boxes:
        box = entry.get('box', [])
        if len(box) != 4 or not np.isfinite(box).all() or not (0 <= box[0] < box[2] <= source.width and 0 <= box[1] < box[3] <= source.height):
            parser.error('Invalid or out-of-bounds text box')
    original = np.asarray(source)
    rgb = original[..., :3]
    estimator = None
    if args.method == 'rolling':
        try:
            from filter_methods import rolling_estimator
            estimator = rolling_estimator(6, 20)
        except (ImportError, AttributeError) as exc:
            parser.error('Rolling mode needs opencv-contrib-python-headless with ximgproc; '
                         'install it in the selected runtime or explicitly choose --method polynomial. '
                         + str(exc))
    if args.method == 'background':
        try:
            from background_mottle import smooth_background
            result, changed, records, weights = smooth_background(
                rgb, boxes, args.strength, args.background_scale)
        except (ImportError, AttributeError) as exc:
            parser.error('Background mode requires opencv-contrib-python-headless: ' + str(exc))
    else:
        result, changed, records, weights = clean(
            rgb, boxes, args.radius, args.strength, background_estimator=estimator,
            refine_fringe=args.method == 'rolling')
    if source.mode == 'RGBA':
        # Fully/partly transparent pixels require a different matte model.
        opaque = original[..., 3] == 255
        result[~opaque] = rgb[~opaque]
        result = np.dstack([result, original[..., 3]])
        changed &= opaque
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result).save(args.output, icc_profile=source.info.get('icc_profile'))
    Image.fromarray(changed.astype(np.uint8)*255).save(mask_path)
    overlay = source.convert('RGB')
    draw = ImageDraw.Draw(overlay)
    for entry in boxes:
        draw.rectangle(entry['box'], outline=(0,180,50), width=1)
    overlay.save(overlay_path)
    saved = np.asarray(Image.open(args.output))
    core = rgb.max(axis=2) <= 80
    report = {'input': str(args.input.resolve()), 'output': str(args.output.resolve()),
              'dimensions': list(source.size), 'radius': args.radius if args.method!='background' else None, 'method': args.method,
              'background_scale': args.background_scale if args.method=='background' else None,
              'strength': args.strength, 'ocr_regions': len(boxes),
              'processed_regions': sum(r['status']=='processed' for r in records),
              'changed_pixels': int(changed.sum()), 'changed_percent': float(changed.mean()*100),
              'core_pixels_identical': bool(np.array_equal(saved[core], original[core])),
              'outside_support_identical': bool(np.array_equal(saved[weights==0], original[weights==0])),
              'alpha_identical': source.mode != 'RGBA' or bool(np.array_equal(saved[...,3],original[...,3])),
              'seconds': time.perf_counter()-start, 'regions': records,
              'limitation': 'Smooth-background prior; cannot identify artistic intent from a single raster.'}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='regions'}, indent=2))


if __name__ == '__main__':
    main()
