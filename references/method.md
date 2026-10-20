# Optional narrow-fringe methods

Use these modes for a narrow bright text fringe or a simple local fill. Background mode handles wider color mottling.

## Optional rolling pipeline

1. OCR proposes text regions. Pixel darkness identifies the core; low-confidence proposals and regions without enough support are skipped.
2. Exclude dark structure (maximum RGB below 145) and five pixels around it from the background estimate. Excluding only the core leaves a bright halo in the samples and recreates it in the result.
3. Telea inpainting with radius 5 fills the excluded area. Apply OpenCV rolling guidance to the filled background with sigma-space 6, sigma-color 20, and four iterations. The estimated background can follow local curved gradients without one polynomial covering the entire label.
4. Preserve the dark core (maximum RGB <=80) exactly. Within two pixels, project edge colors onto the local ink/background color segment. Desaturated bright fringes inside the text proposal receive more complete correction; dissimilar colors remain gated.
5. Taper the changes by distance, restrict writes to the text proposal plus one pixel, and blend. This prevents local fill estimates from spreading past the detected text bounds into nearby cards. It can leave a halo outside those bounds; changing the bounds requires visual inspection.

Inpainting and guidance remain estimates. Wide, dense lettering, multiple background materials, and insufficient clean samples can bias them. Encoded RGB is used as an empirical diagram-cleanup model, not a calibrated linear-light matte. Square-neighborhood distance is used by the mask operations. No guarantee is made for arbitrary textures or intentional outlines.

## Retained polynomial mode

`--method polynomial` retains the original robust per-channel quadratic fit:

`B(x,y) = c0+c1*x+c2*y+c3*x*x+c4*x*y+c5*y*y`

It needs only NumPy and Pillow. This mode has six background coefficients per channel and can preserve linear/quadratic gradients particularly well. Complex local curvature or multiple fills can violate the model. Its original, more conservative edge gates and neighborhood support are retained for reproducibility.

## Sources

- [OpenCV edge-aware filters](https://docs.opencv.org/4.x/da/d17/group__ximgproc__filters.html)
- [Rolling Guidance Filter](https://www.cse.cuhk.edu.hk/leojia/projects/rollguidance/)
- [Apple text bounding boxes](https://developer.apple.com/documentation/vision/vnrecognizedtext/boundingbox(for:))
