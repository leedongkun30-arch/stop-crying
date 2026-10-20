#!/usr/bin/env python3
"""Known-truth checks for gradient retention and near-text artifact suppression."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from clean_text import clean, distance_band
from filter_methods import rolling_estimator


def run_clean(rgb, boxes):
    return clean(rgb, boxes, background_estimator=rolling_estimator(), refine_fringe=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    w, h, scale = 640, 150, 4
    text_mask = Image.new('L', (w*scale, h*scale))
    ImageDraw.Draw(text_mask).text((28*scale, 35*scale), 'Stop crying',
        font=ImageFont.truetype(str(args.font), 70*scale), fill=255)
    alpha = np.asarray(text_mask.resize((w,h), Image.Resampling.LANCZOS))/255
    bounds = Image.fromarray((alpha>0.05).astype(np.uint8)*255).getbbox()
    boxes = [{'box': list(bounds), 'confidence': 1}]
    y,x = np.mgrid[0:h,0:w]; x=x/(w-1); y=y/(h-1)
    cases = {
        'pink-linear': np.stack([245-10*x, 160+45*x+8*y, 190+30*x],axis=-1),
        'blue-quadratic': np.stack([140+32*x+10*y*y, 205+17*x, 240-15*x*x],axis=-1),
        'white-flat': np.full((h,w,3), 250.0),
    }
    results=[]
    for name,bg in cases.items():
        truth = np.rint(bg*(1-alpha[...,None])+4*alpha[...,None]).astype(np.uint8)
        core = truth.max(axis=2)<=80
        distance = distance_band(core, 9)
        ring = (distance>0)&(distance<=6)&(alpha<0.01)
        # Intentional smooth background is known; add a bright local halo plus oscillation.
        envelope = np.maximum(0,1-distance/7)*(alpha<0.01)
        artifact = (11+6*np.sin(x*140)*np.cos(y*33))*envelope
        noisy = np.clip(np.rint(truth+artifact[...,None]),0,255).astype(np.uint8)
        fixed,_,_,_=run_clean(noisy,boxes)
        clean_fixed,_,_,_=run_clean(truth,boxes)
        before=float(np.sqrt(np.mean((noisy[ring].astype(float)-truth[ring])**2)))
        after=float(np.sqrt(np.mean((fixed[ring].astype(float)-truth[ring])**2)))
        drift=float(np.mean(np.abs(clean_fixed[ring].astype(float)-truth[ring])))
        assert after < before*0.6, (name,before,after)
        assert drift < 1, (name,drift)
        assert np.array_equal(fixed[core],noisy[core])
        results.append({'case':name,'near_text_background_rmse_before_8bit':before,
                        'near_text_background_rmse_after_8bit':after,
                        'clean_gradient_mae_8bit':drift,'core_unchanged':True})
        strip=Image.new('RGB',(w,h*3))
        for row,arr in enumerate([truth,noisy,fixed]):
            strip.paste(Image.fromarray(arr),(0,h*row))
        strip.save(args.output_dir/f'{name}.png')
    boundary_bg = np.full((h,w,3),255.0)
    border_y = bounds[3]+1
    boundary_bg[border_y:] = [255,223,235]
    boundary_image = np.rint(boundary_bg*(1-alpha[...,None])+4*alpha[...,None]).astype(np.uint8)
    boundary_fixed,_,_,_=run_clean(boundary_image,boxes)
    assert np.array_equal(boundary_fixed[border_y:],boundary_image[border_y:])
    results.append({'case':'white-card-pink-neighbor','neighbor_pixels_unchanged':True})
    (args.output_dir/'metrics.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
