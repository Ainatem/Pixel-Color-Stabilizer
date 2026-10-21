"""Portable RGBA import and lossless, non-overwriting export bundles."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import shutil
import struct
import tempfile
import zlib

import numpy as np
from PIL import Image


def natural_key(path):
    return tuple((0, int(s)) if s.isdigit() else (1, s.casefold())
                 for s in re.split(r'(\d+)', Path(path).name))


@dataclass
class Animation:
    frames: list
    durations: list
    operations: list = field(default_factory=list)

    def __post_init__(self):
        if not self.frames or len(self.frames) != len(self.durations):
            raise ValueError('Frames and durations must be non-empty and have matching lengths.')
        shape = self.frames[0].shape
        if len(shape) != 3 or shape[2] != 4 or any(a.shape != shape or a.dtype != np.uint8 for a in self.frames):
            raise ValueError('All frames must have the same RGBA canvas.')
        if any(np.any((a[..., 3] != 0) & (a[..., 3] != 255)) for a in self.frames):
            raise ValueError('Only binary alpha (0 / 255) pixel art is supported. Export without antialiasing first.')
        if any(isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 65535 for d in self.durations):
            raise ValueError('Frame durations must be integer milliseconds in 1..65535.')


def load_animation(source, duration=100, cell=None, frame_count=None):
    """Directory, naturally sorted PNG list, GIF/APNG, or uniform row-major sheet.

    GIF/APNG frames use Pillow's composited logical canvas. An APNG default
    poster is excluded. Existing export bundles restore per-frame timing.
    """
    if isinstance(source, (list, tuple)):
        paths = sorted(map(Path, source), key=natural_key)
        if not paths:
            raise ValueError('No PNG files selected.')
        frames = []
        for p in paths:
            with Image.open(p) as im:
                if im.format != 'PNG' or getattr(im, 'n_frames', 1) != 1:
                    raise ValueError('Sequence input must contain static PNG files.')
                frames.append(np.array(im.convert('RGBA')))
        return Animation(frames, [duration] * len(frames))
    source = Path(source)
    if source.is_dir():
        manifest = source / 'animation.json'
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if data.get('format') != 'pixel-color-stabilizer-v1':
                raise ValueError('Unsupported animation.json format.')
            frames, durations = [], []
            for item in data['frames']:
                p = (source / item['file']).resolve()
                if not p.is_relative_to(source.resolve()):
                    raise ValueError('Invalid frame path in manifest.')
                with Image.open(p) as im:
                    frames.append(np.array(im.convert('RGBA')))
                durations.append(item['duration'])
            return Animation(frames, durations, data.get('operations', []))
        return load_animation(list(source.glob('*.png')), duration)
    with Image.open(source) as im:
        if im.format not in ('PNG', 'GIF'):
            raise ValueError('Use PNG, GIF or APNG input. Export .aseprite as PNG frames or a sheet first.')
        if cell:
            w, h = cell
            if w < 1 or h < 1 or im.width % w or im.height % h or getattr(im, 'n_frames', 1) != 1:
                raise ValueError('A static sheet must divide exactly into the chosen cell size.')
            capacity = (im.width // w) * (im.height // h)
            count = capacity if frame_count is None else frame_count
            if not 1 <= count <= capacity:
                raise ValueError('Sheet frame count is out of range.')
            rgba = im.convert('RGBA')
            frames = [np.array(rgba.crop(((i % (im.width//w))*w, (i // (im.width//w))*h,
                                           (i % (im.width//w))*w+w, (i // (im.width//w))*h+h)))
                      for i in range(count)]
            return Animation(frames, [duration] * count)
        frames, durations = [], []
        first = 1 if im.info.get('default_image') else 0
        for i in range(first, getattr(im, 'n_frames', 1)):
            im.seek(i)
            frames.append(np.array(im.convert('RGBA')))
            durations.append(max(1, round(im.info.get('duration', duration) or duration)))
        return Animation(frames, durations)


def _chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def write_apng(path, animation):
    """Full RGBA SOURCE frames; retain duplicate frames, hidden RGB and timing."""
    height, width = animation.frames[0].shape[:2]
    with Path(path).open('wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)))
        f.write(_chunk(b'acTL', struct.pack('>II', len(animation.frames), 0)))
        seq = 0
        for i, (a, ms) in enumerate(zip(animation.frames, animation.durations)):
            f.write(_chunk(b'fcTL', struct.pack('>IIIIIHHBB', seq, width, height, 0, 0, ms, 1000, 0, 0)))
            seq += 1
            raw = b''.join(b'\0' + row.tobytes() for row in a)
            compressed = zlib.compress(raw)
            if i == 0:
                f.write(_chunk(b'IDAT', compressed))
            else:
                f.write(_chunk(b'fdAT', struct.pack('>I', seq) + compressed))
                seq += 1
        f.write(_chunk(b'IEND', b''))


def export_bundle(destination, animation, columns=8):
    """Create a new directory atomically. Never replace input or an old export."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Output already exists. Choose a new folder name.')
    if isinstance(columns, bool) or not isinstance(columns, int) or columns < 1:
        raise ValueError('Sheet columns must be a positive integer.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.stabilizer-', dir=destination.parent))
    try:
        (stage / 'frames').mkdir()
        h, w = animation.frames[0].shape[:2]
        cols = min(columns, len(animation.frames))
        sheet = Image.new('RGBA', (cols * w, ((len(animation.frames)+cols-1)//cols) * h))
        entries = []
        for i, (a, ms) in enumerate(zip(animation.frames, animation.durations)):
            name = f'frames/frame_{i+1:06d}.png'
            image = Image.fromarray(a)
            image.save(stage / name)
            sheet.paste(image, ((i % cols)*w, (i // cols)*h))
            entries.append({'file': name, 'duration': ms, 'frame': {'x': (i % cols)*w, 'y': (i // cols)*h, 'w': w, 'h': h}})
        sheet.save(stage / 'spritesheet.png')
        write_apng(stage / 'animation.png', animation)
        data = {'format': 'pixel-color-stabilizer-v1', 'width': w, 'height': h,
                'frames': entries, 'operations': animation.operations}
        (stage / 'animation.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        # Common Aseprite-style sheet metadata; usable by other editors/engines too.
        metadata = {'frames': [{'filename': Path(e['file']).name, 'frame': e['frame'],
                    'rotated': False, 'trimmed': False, 'spriteSourceSize': {'x': 0, 'y': 0, 'w': w, 'h': h},
                    'sourceSize': {'w': w, 'h': h}, 'duration': e['duration']} for e in entries],
                    'meta': {'app': 'Pixel Color Stabilizer', 'version': '0.1.0', 'image': 'spritesheet.png',
                             'format': 'RGBA8888', 'size': {'w': sheet.width, 'h': sheet.height}, 'scale': '1'}}
        (stage / 'spritesheet.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination
