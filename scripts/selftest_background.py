"""Known-truth broad-mottling checks, distinct from narrow-halo tests."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from background_mottle import smooth_background

def main():
    p=argparse.ArgumentParser();p.add_argument('--font',required=True);p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    args.output_dir.mkdir(exist_ok=False,parents=True)
    w,h,s=640,160,4;y,x=np.mgrid[0:h,0:w]
    mask=Image.new('L',(w*s,h*s));ImageDraw.Draw(mask).text((30*s,45*s),'Background test',font=ImageFont.truetype(args.font,55*s),fill=255)
    alpha=np.asarray(mask.resize((w,h),Image.Resampling.LANCZOS))/255
    box=Image.fromarray((alpha>.05).astype('uint8')*255).getbbox();boxes=[{'box':list(box),'confidence':1}]
    rows=[]
    for name in ['linear','curved']:
        t=x/(w-1) if name=='linear' else .5+.5*np.sin(x/(w-1)*np.pi*1.5)
        bg=np.stack([240+8*t,160+45*t,190+25*t],axis=-1)
        truth=np.rint(bg*(1-alpha[...,None])+4*alpha[...,None]).astype('uint8')
        wave=5*np.sin(x/35*2*np.pi)*np.cos(y/29*2*np.pi)+4*np.cos((x+y)/60*2*np.pi)
        noisy=np.rint(np.clip(truth+wave[...,None]*(alpha<.01)[...,None],0,255)).astype('uint8')
        out,_,_,support=smooth_background(noisy,boxes,scale='mild')
        clean_out,_,_,_=smooth_background(truth,boxes,scale='mild')
        selected=(support>.9)&(alpha<.01)
        before=float(np.sqrt(np.mean((noisy[selected].astype(float)-truth[selected])**2)))
        after=float(np.sqrt(np.mean((out[selected].astype(float)-truth[selected])**2)))
        drift=float(np.mean(np.abs(clean_out[selected].astype(float)-truth[selected])))
        assert after<before*.7,(name,before,after)
        assert drift<2,(name,drift)
        core=noisy.max(axis=2)<=80;assert np.array_equal(out[core],noisy[core])
        rows.append({'case':name,'background_rmse_before':before,'background_rmse_after':after,'clean_background_mae':drift,'core_identical':True})
        sheet=Image.new('RGB',(w,h*3))
        for i,a in enumerate([truth,noisy,out]):sheet.paste(Image.fromarray(a),(0,i*h))
        sheet.save(args.output_dir/(name+'.png'))
    (args.output_dir/'metrics.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
