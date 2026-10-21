"""Coordinate-wise temporal mode, extracted from Pixel Studio. No editor dependency."""
import numpy as np

def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{name} 必须是整数')
    return value

def temporal_mode(arrays, start, end, rectangles, min_ratio=0.0, cleanup_isolated=False, cleanup_halo=0,
                  alpha_mode='preserve'):
    """1-based inclusive frames; rectangles are native x,y,width,height, half-open.

    preserve: vote opaque RGB and retain each frame's alpha/hidden RGB.
    majority: empty wins only with >50% of all frames; otherwise fill every frame
    with the modal opaque RGB. Color ties choose first occurrence, coverage ties fill.
    """
    start = _integer(start, 'start'); end = _integer(end, 'end')
    if not arrays or not 1 <= start <= end <= len(arrays):
        raise ValueError('起止帧超出范围（从1开始，含结束帧）')
    shape = arrays[0].shape
    if len(shape) != 3 or shape[2] != 4 or any(a.shape != shape or a.dtype != np.uint8 for a in arrays):
        raise ValueError('需要相同画布的 uint8 RGBA 序列')
    if any(np.any((a[..., 3] != 0) & (a[..., 3] != 255)) for a in arrays):
        raise ValueError('此工具只处理真像素帧，alpha必须为0或255')
    if isinstance(min_ratio, bool) or not isinstance(min_ratio, (int, float)) or not 0 <= min_ratio <= 1:
        raise ValueError('min_ratio 必须在0到1之间')
    if alpha_mode not in ('preserve', 'majority'):
        raise ValueError('alpha_mode 必须是preserve或majority')
    if alpha_mode == 'majority' and min_ratio != 0:
        raise ValueError('含透明投票使用完整众数规则，min_ratio须为0')
    if not isinstance(cleanup_isolated, bool):
        raise ValueError('cleanup_isolated 必须是布尔值')
    if isinstance(cleanup_halo, bool) or not isinstance(cleanup_halo, int) or cleanup_halo not in (0, 1):
        raise ValueError('cleanup_halo 必须是0或1')
    if not isinstance(rectangles, list) or not 1 <= len(rectangles) <= 64:
        raise ValueError('需要1到64个矩形选区')
    height, width = shape[:2]; selected = np.zeros((height, width), dtype=bool)
    clean_rects = []
    for rectangle in rectangles:
        if not isinstance(rectangle, dict):
            raise ValueError('矩形必须包含x,y,width,height')
        x, y, w, h = [_integer(rectangle.get(key), key) for key in ('x', 'y', 'width', 'height')]
        if x < 0 or y < 0 or w < 1 or h < 1 or x+w > width or y+h > height:
            raise ValueError('矩形超出原生画布，或宽高小于1')
        selected[y:y+h, x:x+w] = True
        clean_rects.append({'x': x, 'y': y, 'width': w, 'height': h})
    indices = np.flatnonzero(selected); count = end-start+1
    if count*count*len(indices) > 400_000_000:
        raise ValueError('所选时段与区域过大，请缩短帧段或缩小选区')
    output = [a.copy() for a in arrays]
    changed = np.zeros(len(arrays), dtype=int); positions = 0; mixed_alpha = 0
    filled_pixels = 0; cleared_pixels = 0
    for offset in range(0, len(indices), 2048):
        coords = indices[offset:offset+2048]
        samples = np.stack([a.reshape(-1, 4)[coords] for a in arrays[start-1:end]])
        opaque = samples[..., 3] == 255
        rgb = samples[..., :3].astype(np.uint32)
        packed = rgb[..., 0] | (rgb[..., 1] << 8) | (rgb[..., 2] << 16)
        packed[~opaque] = 0x1000000
        best = np.full(len(coords), 0x1000000, dtype=np.uint32)
        best_count = np.zeros(len(coords), dtype=int)
        for frame in range(count):
            hits = (packed == packed[frame]).sum(axis=0)
            better = opaque[frame] & (hits > best_count)
            best[better] = packed[frame, better]; best_count[better] = hits[better]
        valid = (best_count > 0) & (best_count >= opaque.sum(axis=0)*min_ratio)
        target = np.stack([best & 255, (best >> 8) & 255, (best >> 16) & 255], axis=1).astype(np.uint8)
        any_change = np.zeros(len(coords), dtype=bool)
        empty_wins = (~opaque).sum(axis=0)*2 > count
        for frame in range(count):
            destination = output[start-1+frame].reshape(-1, 4)
            if alpha_mode == 'majority':
                destination[coords[empty_wins]] = 0
                destination[coords[~empty_wins], :3] = target[~empty_wins]
                destination[coords[~empty_wins], 3] = 255
                mask = np.any(destination[coords] != samples[frame], axis=1)
                filled_pixels += int((~empty_wins & ~opaque[frame]).sum())
                cleared_pixels += int((empty_wins & opaque[frame]).sum())
            else:
                mask = valid & opaque[frame] & (packed[frame] != best)
                destination[coords[mask], :3] = target[mask]
            changed[start-1+frame] += int(mask.sum()); any_change |= mask
        positions += int(any_change.sum())
        mixed_alpha += int((opaque.any(axis=0) & ~opaque.all(axis=0)).sum())
    mode_changed_pixels = int(changed.sum()); cleanup_changed = 0
    if cleanup_isolated:
        from .isolated_color import merge_isolated_colors
        permitted = selected.copy()
        if cleanup_halo:
            padded = np.pad(selected, 1)
            permitted = np.logical_or.reduce([padded[dy:dy+height, dx:dx+width]
                                              for dy in range(3) for dx in range(3)])
        all_changes = np.zeros((height, width), dtype=bool)
        shared_cleanup = None
        if alpha_mode == 'majority':
            # A common cleanup result keeps a selected coordinate identical across
            # time even when neighbors outside the rectangle move between frames.
            shared_cleanup, _ = merge_isolated_colors(output[start-1])
        for frame in range(start-1, end):
            if shared_cleanup is not None:
                replace = selected & np.any(shared_cleanup != output[frame], axis=2)
                cleanup_changed += int(replace.sum()); output[frame][replace] = shared_cleanup[replace]
                cleaned, _ = merge_isolated_colors(output[frame])
                replace = permitted & ~selected & np.any(cleaned != output[frame], axis=2)
            else:
                cleaned, _ = merge_isolated_colors(output[frame])
                replace = permitted & np.any(cleaned != output[frame], axis=2)
            cleanup_changed += int(replace.sum()); output[frame][replace] = cleaned[replace]
            actual = np.any(output[frame] != arrays[frame], axis=2)
            changed[frame] = int(actual.sum()); all_changes |= actual
        positions = int(all_changes.sum())
    return output, {'schema_version': 2, 'algorithm': ('coverage-majority-then-opaque-rgb-mode'
                                                     if alpha_mode == 'majority' else 'opaque-rgb-coordinate-mode'),
                    'start': start, 'end': end, 'rectangles': clean_rects, 'min_ratio': min_ratio,
                    'alpha_mode': alpha_mode, 'empty_majority_rule': 'strictly-more-than-half',
                    'coverage_tie_break': 'opaque', 'filled_pixels': filled_pixels,
                    'cleared_pixels': cleared_pixels,
                    'cleanup_isolated': cleanup_isolated, 'cleanup_halo': cleanup_halo,
                    'mode_changed_pixels_before_cleanup': mode_changed_pixels,
                    'cleanup_changed_pixels': cleanup_changed,
                    'tie_break': 'first-occurrence', 'alpha_changed': bool(filled_pixels or cleared_pixels),
                    'selected_pixels': len(indices), 'changed_positions': positions,
                    'changed_pixels': int(changed.sum()), 'changed_per_frame': changed.tolist(),
                    'mixed_alpha_positions': mixed_alpha}
