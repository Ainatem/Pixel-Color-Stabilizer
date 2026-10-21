"""Merge color singletons into adjacent opaque color regions, without erosion.

Only pixels isolated in the ORIGINAL eight-neighborhood may change. Existing
two-pixel (including diagonal) clusters, alpha, framing and timing are retained.
"""
from collections import Counter
import numpy as np
from scipy.ndimage import label
from .color import srgb_to_lab

NEIGHBORS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]


def isolated_color_mask(rgba):
    a = np.asarray(rgba)
    if a.ndim != 3 or a.shape[-1] != 4:
        raise ValueError('Expected H,W,4 RGBA frame')
    opaque = a[..., 3] > 0
    h, w = opaque.shape
    same = np.zeros((h, w), bool)
    for dy, dx in NEIGHBORS:
        ys = slice(max(0, dy), h + min(0, dy))
        xs = slice(max(0, dx), w + min(0, dx))
        yn = slice(max(0, -dy), h + min(0, -dy))
        xn = slice(max(0, -dx), w + min(0, -dx))
        same[ys, xs] |= (opaque[yn, xn] & np.all(a[ys, xs, :3] == a[yn, xn, :3], axis=-1))
    return opaque & ~same


def merge_isolated_colors(rgba):
    source = np.asarray(rgba, dtype=np.uint8)
    out = source.copy()
    original = isolated_color_mask(source)
    opaque = source[..., 3] > 0
    h, w = opaque.shape
    # Labels are exact RGB colors, not quantization or approximate color matches.
    rgb = source[..., :3].astype(np.int32)
    ids = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    current = ids.copy()
    part_size = np.zeros((h, w), np.int32)
    colors = np.unique(ids[opaque])
    labs = {int(c): srgb_to_lab(np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255], np.uint8)) for c in colors}
    for c in colors:
        parts, _ = label((ids == c) & opaque, structure=np.ones((3, 3), bool))
        sizes = np.bincount(parts.ravel())
        region = parts > 0
        part_size[region] = sizes[parts[region]]
    stable = opaque & ~original
    pending = original.copy()
    waves = 0
    while pending.any():
        changes = []
        for y, x in np.argwhere(pending):
            adjacent = [(y + dy, x + dx) for dy, dx in NEIGHBORS
                        if 0 <= y + dy < h and 0 <= x + dx < w and stable[y + dy, x + dx]]
            if not adjacent:
                continue
            counts = Counter(int(current[ny, nx]) for ny, nx in adjacent)
            region_size = {c: max(int(part_size[ny, nx]) for ny, nx in adjacent if current[ny, nx] == c) for c in counts}
            old = int(ids[y, x])
            # Neighbor majority first, then supporting connected region size;
            # color distance and RGB order only break remaining deterministic ties.
            chosen = min(counts, key=lambda c: (-counts[c], -region_size[c], float(np.sum((labs[c] - labs[old]) ** 2)), c))
            changes.append((int(y), int(x), chosen, region_size[chosen]))
        if not changes:
            break  # No adjacent opaque region: do not invent a bridge across alpha.
        for y, x, c, size in changes:
            current[y, x] = c
            part_size[y, x] = size
            out[y, x, :3] = [(c >> 16) & 255, (c >> 8) & 255, c & 255]
            pending[y, x] = False
            stable[y, x] = True
        waves += 1
    changed = np.any(out[..., :3] != source[..., :3], axis=-1)
    assert not (changed & ~original).any()
    assert np.array_equal(out[..., 3], source[..., 3])
    patches = [{'x': int(x), 'y': int(y), 'from': source[y, x, :3].tolist(), 'to': out[y, x, :3].tolist()}
               for y, x in np.argwhere(changed)]
    return out, {'candidates': int(original.sum()), 'merged': int(changed.sum()),
                 'remaining': int(isolated_color_mask(out).sum()), 'unattached_no_region': int(pending.sum()),
                 'waves_over_original_candidates_only': waves, 'alpha_changed': False,
                 'patches': patches}
