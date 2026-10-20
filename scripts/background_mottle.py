"""Broad colored-background filtering, independent of a polygon fit."""
import numpy as np


def smooth_background(rgb, boxes, strength=1.0, scale='strong'):
    import cv2
    if not hasattr(cv2, 'ximgproc') or not hasattr(cv2.ximgproc, 'dtFilter'):
        raise ImportError('OpenCV contrib ximgproc.dtFilter is required')
    settings={'mild':(15,20), 'medium':(35,25), 'strong':(70,30)}
    space,color_sigma=settings[scale]
    source=rgb.astype(np.float32)
    # Estimate a background without ink. This does not erase ink in the output.
    ink=(rgb.max(axis=2)<145).astype(np.uint8)
    excluded=cv2.dilate(ink,np.ones((7,7),np.uint8))*255
    bg=cv2.inpaint(rgb,excluded,5,cv2.INPAINT_TELEA).astype(np.float32)
    opacity=np.clip(np.sum((bg-source)*bg,axis=2)/np.maximum(np.sum(bg*bg,axis=2),1),0,1)
    chroma=np.clip((np.ptp(bg,axis=2)-8)/12,0,1)
    light=np.clip((bg.min(axis=2)-110)/40,0,1)
    proposal=np.zeros(rgb.shape[:2],np.uint8)
    records=[]
    for index,entry in enumerate(boxes):
        if float(entry.get('confidence',1))<.3:
            records.append({'index':index,'status':'low-confidence'});continue
        x0,y0,x1,y1=entry['box']
        proposal[int(y0):int(np.ceil(y1)),int(x0):int(np.ceil(x1))]=1
        records.append({'index':index,'status':'processed'})
    if not proposal.any():
        return rgb.copy(),np.zeros(rgb.shape[:2],bool),records,np.zeros(rgb.shape[:2])
    distance=cv2.distanceTransform(1-proposal,cv2.DIST_L2,5)
    scope=np.clip((20-distance)/12,0,1)
    scope=scope*scope*(3-2*scope)
    weights=strength*(1-opacity)*chroma*light*scope
    core=rgb.max(axis=2)<=80
    weights[core]=0
    filtered=cv2.ximgproc.dtFilter(bg,bg,sigmaSpatial=space,sigmaColor=color_sigma,
                                  mode=cv2.ximgproc.DTF_NC,numIters=3)
    result=np.clip(np.rint(source+(filtered-bg)*weights[...,None]),0,255).astype(np.uint8)
    assert np.array_equal(result[core],rgb[core])
    assert np.array_equal(result[weights==0],rgb[weights==0])
    return result,np.any(result!=rgb,axis=2),records,weights
