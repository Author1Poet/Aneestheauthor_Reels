import numpy as np, cv2
from PIL import Image


def _warp(im, M, size):
    a = np.asarray(im)
    if a.shape[2] == 4:
        al = a[..., 3:4].astype(np.uint16)
        pm = np.concatenate([(a[..., :3].astype(np.uint16) * al // 255).astype(np.uint8), a[..., 3:4]], axis=2)
        w = cv2.warpAffine(pm, M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        wa = w[..., 3:4].astype(np.float32)
        rgb = np.where(wa > 0, w[..., :3].astype(np.float32) * 255.0 / np.maximum(wa, 1), 0)
        out = np.concatenate([np.clip(rgb, 0, 255).astype(np.uint8), w[..., 3:4]], axis=2)
        return Image.fromarray(out, "RGBA")
    w = cv2.warpAffine(a, M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(w)


def rot(im, angle, center):
    M = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), float(angle), 1.0)
    return _warp(im, M, im.size)


def zoom(im, z, px, py, dx=0.0, dy=0.0):
    M = np.array([[z, 0, px - z * px + dx], [0, z, py - z * py + dy]], np.float32)
    return _warp(im, M, im.size)
