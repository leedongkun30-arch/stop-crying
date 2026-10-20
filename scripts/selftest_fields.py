#!/usr/bin/env python3
"""Synthetic flat-field regression and anonymous visual example generator."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from flatten_fields import flatten_fields, validate_fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    width, height = 640, 480
    source = np.full((height, width, 4), 255, np.uint8)
    fields, masks = [], []
    colors = [(15, 52, 80), (0, 134, 147), (255, 232, 70), (202, 233, 249), (255, 255, 255)]
    font = ImageFont.truetype(args.font, 30)
    for i, color in enumerate(colors):
        y0, y1 = 8 + i * 94, 94 + i * 94
        yy, xx = np.mgrid[0:y1-y0, 0:624]
        noise = 12 * np.sin(xx / 29) * np.cos(yy / 17) + 4 * np.sin(xx / 7 + yy / 13)
        source[y0:y1, 8:632, :3] = np.clip(np.array(color) + noise[..., None], 0, 255)
        mask = Image.new('L', (width, height))
        ImageDraw.Draw(mask).text((30, y0 + 23), 'Example text 0123', font=font, fill=255)
        coverage = np.asarray(mask).astype(float) / 255
        masks.append(coverage == 1)
        foreground = (245, 248, 250) if i < 2 else ((180, 20, 20) if i == 2 else (20, 30, 45))
        source[..., :3] = np.rint(source[..., :3] * (1-coverage[..., None])
                                  + np.array(foreground) * coverage[..., None]).astype(np.uint8)
        # A long internal table rule must survive the fill.
        source[y0 + 73:y0 + 75, 20:620, :3] = (235, 240, 245) if i < 2 else (100, 110, 120)
        fields.append({'rect': [8, y0, 632, y1], 'color': color})
    source[10:17, 570:580, 3] = 100
    original = source.copy()
    result, support, _ = flatten_fields(source, fields)
    assert np.array_equal(source, original), 'Input mutated'
    assert np.array_equal(source[..., 3], result[..., 3]), 'Alpha changed'
    assert np.array_equal(source[source[..., 3] < 255], result[source[..., 3] < 255]), 'Transparent pixels changed'
    assert np.array_equal(source[~support], result[~support]), 'Outside support changed'
    assert np.array_equal(source[np.logical_or.reduce(masks)], result[np.logical_or.reduce(masks)]), 'Ink cores changed'
    reductions = []
    for field in fields:
        x0, y0, x1, y1 = field['rect']
        assert np.array_equal(source[y0+73:y0+75, 20:620], result[y0+73:y0+75, 20:620]), 'Rule changed'
        before = source[y0+6:y0+16, 50:500, :3].astype(float)
        after = result[y0+6:y0+16, 50:500, :3].astype(float)
        target = np.array(field['color'])
        a, b = np.mean((before-target)**2), np.mean((after-target)**2)
        assert b < a * .05, (a, b)
        reductions.append({'before_mse': round(a, 4), 'after_mse': round(b, 4)})
    for bad in ([{'rect': [-1, 0, 2, 2], 'color': [0, 0, 0]}],
                [{'rect': [0, 0, 2, 2], 'color': [0, 0, 256]}]):
        try:
            validate_fields({'width': width, 'height': height, 'fields': bad}, (width, height))
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid field accepted')
    overlapping = fields + [fields[0]]
    assert np.array_equal(flatten_fields(source, overlapping)[0], result), 'Repeated field accumulates changes'
    Image.fromarray(source).save(args.output_dir / 'before.png')
    payload = {'width': width, 'height': height, 'fields': fields}
    (args.output_dir / 'fields.json').write_text(json.dumps(payload, indent=2) + '\n')
    command = [sys.executable, str(Path(__file__).with_name('flatten_fields.py')),
               str(args.output_dir/'before.png'), str(args.output_dir/'after.png'),
               '--fields', str(args.output_dir/'fields.json')]
    subprocess.run(command, check=True, capture_output=True)
    assert np.array_equal(np.asarray(Image.open(args.output_dir/'after.png')), result)
    assert subprocess.run(command, capture_output=True).returncode != 0, 'Existing output overwritten'
    comparison = Image.new('RGB', (width*2, height))
    comparison.paste(Image.fromarray(source).convert('RGB'), (0, 0))
    comparison.paste(Image.fromarray(result).convert('RGB'), (width, 0))
    comparison.save(args.output_dir / 'comparison.png')
    print(json.dumps({'checks': 'PASS', 'synthetic_background_error': reductions}))


if __name__ == '__main__':
    main()
