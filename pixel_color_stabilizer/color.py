"""D65 color distance used for deterministic singleton tie breaking."""
import numpy as np

def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert uint8/float RGB (..., 3) to CIE Lab (D65)."""
    x = np.asarray(rgb, dtype=np.float64)
    if x.shape[-1] != 3:
        raise ValueError("RGB 数组最后一维必须是 3")
    if x.size and x.max() > 1.0:
        x = x / 255.0
    x = np.clip(x, 0.0, 1.0)
    linear = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    r, g, b = linear[..., 0], linear[..., 1], linear[..., 2]
    px = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    py = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    pz = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    px /= 0.95047
    pz /= 1.08883
    delta = 6.0 / 29.0
    fx = np.where(px > delta ** 3, np.cbrt(px), px / (3 * delta ** 2) + 4.0 / 29.0)
    fy = np.where(py > delta ** 3, np.cbrt(py), py / (3 * delta ** 2) + 4.0 / 29.0)
    fz = np.where(pz > delta ** 3, np.cbrt(pz), pz / (3 * delta ** 2) + 4.0 / 29.0)
    lab = np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=-1)
    return lab
