import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from pixel_color_stabilizer.media import Animation, load_animation, export_bundle
from pixel_color_stabilizer.session import Session


class PortableTests(unittest.TestCase):
    def animation(self):
        a = np.full((4, 6, 4), [50, 80, 90, 255], np.uint8)
        a[0, 0] = [11, 22, 33, 0]
        b = a.copy(); b[1, 1] = [200, 0, 0, 255]
        return Animation([a, a.copy(), b, a.copy()], [60, 140, 90, 230])

    def assert_frames(self, a, b):
        self.assertEqual(a.durations, b.durations)
        self.assertEqual(len(a.frames), len(b.frames))
        for x, y in zip(a.frames, b.frames):
            np.testing.assert_array_equal(x, y)

    def test_lossless_export_bundle_apng_duplicates_and_hidden_rgb(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.animation(); out = Path(tmp)/'out'
            export_bundle(out, a, columns=3)
            self.assert_frames(a, load_animation(out))
            self.assert_frames(a, load_animation(out/'animation.png'))
            sheet = load_animation(out/'spritesheet.png', cell=(6, 4), frame_count=4)
            for x, y in zip(a.frames, sheet.frames):
                np.testing.assert_array_equal(x, y)
            metadata = json.loads((out/'spritesheet.json').read_text())
            self.assertEqual([e['duration'] for e in metadata['frames']], a.durations)
            with self.assertRaises(ValueError): export_bundle(out, a)

    def test_single_frame_apng_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.animation(); a = Animation(a.frames[:1], [100])
            export_bundle(Path(tmp)/'out', a)
            self.assert_frames(a, load_animation(Path(tmp)/'out/animation.png'))

    def test_png_natural_order_and_default_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for number in (10, 2, 1):
                Image.fromarray(np.full((2, 2, 4), [number, 0, 0, 255], np.uint8)).save(Path(tmp)/f'f{number}.png')
            a = load_animation(tmp, 77)
            self.assertEqual([int(f[0, 0, 0]) for f in a.frames], [1, 2, 10])
            self.assertEqual(a.durations, [77]*3)

    def test_gif_composited_frames_and_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Image.new('RGBA', (8, 8), (0, 0, 0, 0)); first.putpixel((2, 2), (255, 0, 0, 255))
            second = first.copy(); second.putpixel((4, 4), (0, 255, 0, 255))
            path = Path(tmp)/'input.gif'
            first.save(path, save_all=True, append_images=[second], duration=[80, 120], loop=0, disposal=2)
            animation = load_animation(path)
            self.assertEqual(animation.durations, [80, 120])
            self.assertEqual(animation.frames[1][4, 4].tolist(), [0, 255, 0, 255])

    def test_apng_default_poster_is_not_an_animation_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            poster = Image.new('RGBA', (3, 3), 'blue')
            first = Image.new('RGBA', (3, 3), 'red'); second = Image.new('RGBA', (3, 3), 'green')
            path = Path(tmp)/'poster.png'
            poster.save(path, save_all=True, append_images=[first, second], default_image=True, duration=[80, 120], loop=0)
            animation = load_animation(path)
            self.assertEqual(animation.durations, [80, 120])
            self.assertEqual(len(animation.frames), 2)
            self.assertEqual(animation.frames[0][0, 0].tolist(), [255, 0, 0, 255])

    def test_invalid_alpha_sizes_timing_and_sheet_are_rejected(self):
        a = self.animation()
        with self.assertRaises(ValueError): Animation(a.frames, [0]*4)
        with self.assertRaises(ValueError): Animation([a.frames[0], a.frames[1][:2]], [100, 100])
        b = a.frames[0].copy(); b[2, 2, 3] = 128
        with self.assertRaises(ValueError): Animation([b], [100])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'sheet.png'; Image.fromarray(a.frames[0]).save(path)
            with self.assertRaises(ValueError): load_animation(path, cell=(4, 3))
            with self.assertRaises(ValueError): load_animation(path, cell=(2, 2), frame_count=7)

    def test_preview_apply_multiple_regions_undo_and_export_history(self):
        session = Session(self.animation()); original = session.current
        params = dict(start=1, end=4, rectangles=[dict(x=1, y=1, width=1, height=1)])
        session.make_preview(**params)
        self.assertIs(session.current, original)
        session.apply(); first = session.current
        self.assertEqual(first.frames[2][1, 1, 0], 50)
        session.make_preview(start=1, end=2, rectangles=[dict(x=0, y=0, width=1, height=1)], alpha_mode='majority')
        session.apply(); session.undo(); self.assertIs(session.current, first)
        session.undo(); self.assertIs(session.current, original)
        session.make_preview(**params); session.invalidate()
        with self.assertRaises(ValueError): session.apply()
        session.make_preview(**params); session.apply()
        with tempfile.TemporaryDirectory() as tmp:
            export_bundle(Path(tmp)/'out', session.current)
            loaded = load_animation(Path(tmp)/'out')
            self.assertEqual(len(loaded.operations), 1)
            self.assert_frames(session.current, loaded)

    def test_failed_export_leaves_no_partial_destination(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'out'
            with patch('pixel_color_stabilizer.media.write_apng', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): export_bundle(out, self.animation())
            self.assertFalse(out.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_manifest_cannot_read_outside_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'out'; out.mkdir()
            (out/'animation.json').write_text(json.dumps({'format': 'pixel-color-stabilizer-v1',
                'frames': [{'file': '../outside.png', 'duration': 100}]}))
            with self.assertRaises(ValueError): load_animation(out)
