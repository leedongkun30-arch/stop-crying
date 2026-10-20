# Broad color-background filtering

The target is color fluctuation across the area surrounding text, including gaps between letters. A six-pixel text-edge mask addresses a different spatial scale and leaves most of this fluctuation unchanged.

## Implementation

1. Detect dark pixels (maximum RGB below 145), expand by three pixels, and inpaint a temporary background using Telea radius 5. The original ink is not replaced by this estimate.
2. Filter the temporary background with OpenCV domain-transform normalized-convolution mode (`DTF_NC`, three iterations). The mild/medium/strong spatial and color sigmas are (15,20), (35,25), and (70,30), in source pixels and 8-bit RGB units.
3. Estimate ink opacity by projecting the observed pixel against the temporary background. Transfer the filtered-minus-original background delta with an opacity-dependent weight.
4. Restrict the transfer to bright chromatic fills: color range ramps from 8 to 20, minimum channel ramps from 110 to 150. Pixels at maximum RGB <=80 are fixed exactly.
5. Scope the transfer around OCR proposals: full scope inside and for eight pixels outside, then a smooth taper to zero at 20 pixels. This keeps distant illustrations outside the operation. Artwork close to a proposal can still be affected; inspect it.

No closed polygons are located or painted. Broad illumination trends can survive local filtering, but no spatial filter can perfectly distinguish intended texture from similarly scaled artifacts. Strong mode can flatten some fills while leaving broad fluctuation elsewhere. For intended solid colors that remain mottled, use [explicit flat fields](flat-fields.md). Strong is the default; medium and mild provide lower-intensity settings.

## Verification

The broad-background self-test explicitly uses mild to retain its original regression conditions and adds spatially correlated color fluctuation across linear and curved synthetic gradients. It measures background RMSE against known truth and separately measures drift after processing a clean gradient, over strongly affected non-text pixels. These tests check the mechanism; they do not establish perceptual success on a user's image.

Keep dark-core, exterior-support, alpha, and non-opaque pixel preservation separate from aesthetic assessment. Inspect marker boundaries and nearby icons; inpainting can mix colors at adjacent materials. Text-edge halos may remain because this mode transfers background change rather than rebuilding the entire text matte.

Narrow-halo benchmark scores do not establish broad-mottling removal.

[OpenCV domain-transform filtering API](https://docs.opencv.org/4.x/da/d17/group__ximgproc__filters.html)
