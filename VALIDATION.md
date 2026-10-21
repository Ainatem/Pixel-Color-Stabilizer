# Validation — 2026-10-21

Locally verified on Windows x64, Python 3.10.11, NumPy 2.2.6,
Pillow 12.3.0, SciPy 1.15.3, PyInstaller 6.22.3.

- 28 unit / integration tests passed, including the Tk widget workflow.
- The extracted temporal voting and singleton code retains the original Pixel
  Studio algorithm, including coverage ties, RGB ties and explicit cleanup halo.
- PNG/APNG round trips preserve RGBA (including hidden RGB), duplicate frame
  count, order and variable durations. Sheet data and frame rectangles checked.
- GIF compositing, APNG default-poster exclusion, PNG natural order and invalid
  input handling tested.
- Output creation refuses existing destinations; simulated disk failure leaves
  no partial export. Manifest frame paths cannot escape the bundle directory.
- Portable executable self-test passed from a separate temporary working
  directory with PATH limited to Windows System32 and PYTHONPATH, PYTHONHOME,
  TCL_LIBRARY and TK_LIBRARY removed. Checks: Tk creation, threaded preview,
  apply, SciPy cleanup, PNG/APNG export and readback, undo and playback.
- Wheel and source distribution successfully built.

No Aseprite, Blender, GPU, model weights, server or original Pixel Studio
installation is used by the standalone tool. macOS/Linux desktop behavior has
not been locally verified; CI templates are included but remote CI is not enabled
because the publishing token lacks the workflow scope. Unsaved undo history is
in memory; export is required before closing.
