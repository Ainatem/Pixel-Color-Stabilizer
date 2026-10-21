"""Deterministic smoke test for the frozen Windows application."""
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk

import numpy as np

from .gui import Editor
from .isolated_color import merge_isolated_colors
from .media import Animation, export_bundle, load_animation


def run(report_path):
    root = tk.Tk(); root.withdraw()
    editor = Editor(root)
    try:
        a = np.full((8, 10, 4), [40, 60, 80, 255], np.uint8)
        a[0, 0] = [11, 22, 33, 0]
        b = a.copy(); b[4, 4] = [200, 30, 50, 255]
        animation = Animation([a, b, a.copy()], [70, 110, 130])
        editor.loaded(animation); editor.update_controls()
        editor.mode.set('preserve')
        editor.preview()
        deadline = time.monotonic()+15
        while editor.busy and time.monotonic() < deadline:
            root.update(); time.sleep(.01)
        assert not editor.busy and editor.session.report['changed_pixels'] == 1
        editor.apply()
        cleaned, report = merge_isolated_colors(b)
        assert report['merged'] == 1
        np.testing.assert_array_equal(cleaned, a)
        with tempfile.TemporaryDirectory(prefix='pixel portable test ') as tmp:
            output = Path(tmp)/'导出 animation'
            export_bundle(output, editor.session.current)
            imported = load_animation(output/'animation.png')
            assert imported.durations == animation.durations
            assert len(imported.frames) == 3
            for frame in imported.frames:
                np.testing.assert_array_equal(frame, a)
        editor.undo()
        np.testing.assert_array_equal(editor.session.current.frames[1], b)
        editor.toggle_play(); root.update(); editor.stop()
        Path(report_path).write_text(json.dumps({'ok': True, 'checks': [
            'Tk editor creation', 'threaded preview', 'apply', 'SciPy singleton cleanup',
            'PNG bundle export', 'APNG RGBA and timing roundtrip', 'undo', 'playback']}, indent=2), encoding='utf-8')
    finally:
        editor.stop()
        root.after_cancel(editor.poll_id)
        root.destroy()
