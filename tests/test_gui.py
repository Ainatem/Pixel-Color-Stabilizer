"""Widget-level workflow smoke test; run locally with a desktop or Xvfb."""
import time
import unittest

import numpy as np


class GuiTests(unittest.TestCase):
    def test_selection_preview_invalidation_apply_undo_playback(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('Tk is not installed')
        from pixel_color_stabilizer.gui import Editor
        from pixel_color_stabilizer.media import Animation
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('Desktop display unavailable')
        root.withdraw()
        editor = Editor(root)
        try:
            a = np.full((12, 16, 4), [10, 20, 30, 255], np.uint8)
            b = a.copy(); b[3, 4] = [200, 90, 80, 255]
            editor.loaded(Animation([a, b, a.copy()], [60, 70, 80]))
            editor.update_controls()
            for k, v in dict(x=4, y=3, width=1, height=1).items():
                editor.vars[k].set(str(v))
            editor.preview()
            deadline = time.monotonic()+10
            while editor.busy and time.monotonic() < deadline:
                root.update(); time.sleep(.01)
            self.assertFalse(editor.busy)
            self.assertEqual(editor.session.report['changed_pixels'], 1)
            self.assertFalse(editor.apply_button.instate(['disabled']))
            editor.vars['end'].set('2')
            self.assertIsNone(editor.session.preview)
            self.assertTrue(editor.apply_button.instate(['disabled']))
            editor.vars['end'].set('3')
            editor.preview()
            while editor.busy and time.monotonic() < deadline:
                root.update(); time.sleep(.01)
            editor.apply()
            self.assertEqual(editor.session.current.frames[1][3, 4].tolist(), [10, 20, 30, 255])
            editor.undo()
            np.testing.assert_array_equal(editor.session.current.frames[1], b)
            editor.toggle_play(); root.update(); editor.stop()
            self.assertIsNone(editor.timer)
        finally:
            editor.stop()
            if editor.poll_id is not None: root.after_cancel(editor.poll_id)
            root.destroy()
