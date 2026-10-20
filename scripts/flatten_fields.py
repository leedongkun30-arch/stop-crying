#!/usr/bin/env python3
"""Flatten explicitly selected solid-color fields without re-rendering lettering."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def validate_fields(payload, size):
    if (payload.get('width'), payload.get('height')) != size:
        raise ValueError('Field dimensions must match the source image')
    fields = payload.get('fields')
    if not isinstance(fields, list) or not fields:
        raise ValueError('Provide at least one explicit field')
    for field in fields:
        rect, color = field.get('rect', []), field.get('color', [])
        if (len(rect) != 4 or any(type(v) is not int for v in rect)
                or not (0 <= rect[0] < rect[2] <= size[0]
                        and 0 <= rect[1] < rect[3] <= size[1])):
            raise ValueError('Field rectangles must be integer, in-bounds source coordinates')
        if len(color) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in color):
            raise ValueError('Field color must contain three integer RGB values in 0..255')
    return fields


def flatten_fields(original, fields, strength=1.0):
    if not 0 < strength <= 1:
        raise ValueError('Strength must be >0 and <=1')
    if original.dtype != np.uint8 or original.ndim != 3 or original.shape[2] not in (3, 4):
        raise ValueError('Expected uint8 RGB/RGBA pixels')
    height, width = original.shape[:2]
    validate_fields({'width': width, 'height': height, 'fields': fields}, (width, height))
    rgb = original[..., :3]
    opaque = original[..., 3] == 255 if original.shape[2] == 4 else np.ones((height, width), bool)
    edge_source = rgb.copy()
    edge_source[~opaque] = 0
    edges = cv2.Canny(edge_source, 35, 100)
    # Protect long rules, not every edge: mottling itself can produce Canny edges.
    horizontal = cv2.morphologyEx(edges, cv2.MORPH_OPEN, np.ones((1, 35), np.uint8))
    vertical = cv2.morphologyEx(edges, cv2.MORPH_OPEN, np.ones((25, 1), np.uint8))
    rules = cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8)) > 0
    result = original.copy()
    support = np.zeros((height, width), bool)
    records = []
    for field in fields:
        x0, y0, x1, y1 = field['rect']
        tile = rgb[y0:y1, x0:x1].astype(float)
        visible = opaque[y0:y1, x0:x1]
        if not visible.any():
            records.append({'status': 'no-opaque-pixels'})
            continue
        base = np.median(tile[visible], axis=0)
        target = np.asarray(field['color'], float)
        distance = np.linalg.norm(tile - base, axis=2)
        dark_field = target.max() < 200
        edge = 120 if dark_field else 105
        alpha = np.clip((edge - distance) / (edge - 65), 0, 1)
        alpha = strength * alpha * alpha * (3 - 2 * alpha)
        if dark_field:
            ink = tile.min(axis=2) > 190
        else:
            ink = ((tile.max(axis=2) < 135)
                   | ((tile[..., 0] > 150) & (tile[..., 1] < 115) & (tile[..., 2] < 115)))
        alpha[ink | rules[y0:y1, x0:x1] | ~visible] = 0
        patch = np.clip(np.rint(tile * (1 - alpha[..., None]) + target * alpha[..., None]), 0, 255)
        # Later fields override earlier fields, always using original source pixels.
        result[y0:y1, x0:x1, :3] = patch.astype(np.uint8)
        support[y0:y1, x0:x1] = alpha > 0
        records.append({'status': 'processed', 'rect': field['rect'], 'color': field['color'],
                        'estimated_background': base.tolist(), 'candidate_pixels': int((alpha > 0).sum())})
    assert np.array_equal(result[~support], original[~support])
    return result, support, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--fields', type=Path, required=True)
    parser.add_argument('--strength', type=float, default=1.0)
    args = parser.parse_args()
    paths = [args.output, args.output.with_suffix('.report.json'),
             args.output.with_suffix('.mask.png'), args.output.with_suffix('.regions.png')]
    if args.output.suffix.lower() != '.png' or any(p.exists() for p in paths):
        parser.error('Use a fresh PNG output and fresh report/mask/overlay paths')
    source = Image.open(args.input)
    if source.mode not in ('RGB', 'RGBA') or source.getexif().get(274, 1) != 1:
        parser.error('Normalize input to upright RGB/RGBA first')
    try:
        fields = validate_fields(json.loads(args.fields.read_text()), source.size)
        original = np.asarray(source)
        result, support, records = flatten_fields(original, fields, args.strength)
    except (ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result).save(paths[0], icc_profile=source.info.get('icc_profile'))
    changed = np.any(original != result, axis=2)
    Image.fromarray(changed.astype(np.uint8) * 255).save(paths[2])
    overlay = source.convert('RGB')
    draw = ImageDraw.Draw(overlay)
    for field in fields:
        x0, y0, x1, y1 = field['rect']
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 0, 255))
    overlay.save(paths[3])
    saved = np.asarray(Image.open(paths[0]))
    report = {'method': 'explicit-flat-fields', 'dimensions': list(source.size),
              'strength': args.strength, 'changed_pixels': int(changed.sum()),
              'outside_support_identical': bool(np.array_equal(saved[~support], original[~support])),
              'alpha_identical': source.mode != 'RGBA' or bool(np.array_equal(saved[..., 3], original[..., 3])),
              'regions': records,
              'limitation': 'Intended flat fills only; low-contrast artwork can be mistaken for background.'}
    paths[1].write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'regions'}, indent=2))


if __name__ == '__main__':
    main()
