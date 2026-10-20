"""Optional OpenCV background estimators for controlled dehalo comparisons."""
import numpy as np
from clean_text import clean


def rolling_estimator(sigma_space=6.0, sigma_color=20.0):
    import cv2
    if not hasattr(cv2, "ximgproc") or not hasattr(cv2.ximgproc, "rollingGuidanceFilter"):
        raise ImportError("OpenCV contrib ximgproc is required")
    def estimate(patch, distance):
        # Remove text and its immediate fringe before constructing the guidance.
        excluded = (distance <= 5).astype(np.uint8) * 255
        known = excluded == 0
        if known.sum() < 60 or np.median(patch[known].min(axis=1)) < 105:
            return None
        source = np.rint(patch).astype(np.uint8)
        filled = cv2.inpaint(source, excluded, 5, cv2.INPAINT_TELEA)
        background = cv2.ximgproc.rollingGuidanceFilter(
            filled, d=0, sigmaColor=sigma_color, sigmaSpace=sigma_space, numOfIter=4)
        error = float(np.median(np.linalg.norm(background[known].astype(float)-patch[known],axis=1)))
        return background.astype(float), error, int(known.sum())
    return estimate


def apply_method(rgb, boxes, method, parameter=None):
    import cv2
    if method == 'original':
        return rgb.copy()
    if method == 'median':
        return cv2.medianBlur(rgb, parameter or 3)
    if method == 'bilateral':
        return cv2.bilateralFilter(rgb, 13, parameter or 40, 3)
    if method == 'current':
        return clean(rgb, boxes)[0]
    if method in ('rolling', 'rolling-refined'):
        space,color = parameter or (3,25)
        return clean(rgb, boxes, background_estimator=rolling_estimator(space,color), refine_fringe=method == 'rolling-refined')[0]
    raise ValueError(method)
