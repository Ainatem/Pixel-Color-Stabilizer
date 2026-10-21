# Pixel Color Stabilizer

[中文](README.md)

A local desktop editor, CLI and Python library for coordinate-wise temporal color stabilization in selected regions and frame ranges. Extracted from Pixel Studio. No Aseprite, Blender, GPU, AI weights, account or server required. The current desktop UI is Chinese with English labels on primary actions.

## Run

Windows portable: unzip the complete folder and run `PixelColorStabilizer.exe`. Keep `_internal` beside it. No Python installation is needed.

From source, use Python 3.10+ with Tk:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install .
python -m pixel_color_stabilizer --gui
```

Linux may require `python3-tk`. Windows is locally verified; the core and media tests have a cross-platform CI matrix.

Open a PNG sequence/folder, GIF, APNG, or uniform PNG sheet. Sheet import asks for cell dimensions and effective frame count, in row-major order. PNG sequences use natural filename sorting and a configurable default duration (100 ms). GIF/APNG retain their durations. Drag a rectangle on the left, set an inclusive 1-based frame range, preview, inspect playback, and apply. Repeat or undo, then export into a new folder. Coordinates are 0-based.

Changing parameters invalidates the pending preview. Export requires applying or discarding a pending preview. Preview is non-destructive; source files and existing exports are never overwritten. Export before closing; there is no autosave. Reopen an export folder to restore frames, timings and operation reports; the in-memory undo stack starts empty on reopen. Native `.aseprite` files are not read or written; export universal image formats from your editor first.

## Rules and limitations

- `preserve`: vote opaque RGB at each selected coordinate; preserve each frame's alpha and hidden transparent RGB. Color ties choose first occurrence. This is the Python/CLI default.
- `majority`: empty wins only when more than half of frames are transparent; otherwise fill every selected frame with the opaque RGB mode. Coverage ties fill; RGB ties choose first occurrence. This intentionally changes the silhouette and is the GUI default.
- Optional cleanup merges only original eight-neighbor color singletons, preserving alpha and existing connected color pairs. An explicit 1 px halo may extend cleanup outside the selection. Neighbor support, connected region size and Lab distance determine ties, as in the original algorithm.
- Fixed-coordinate voting can flatten moving boundaries. It does not track objects. Select stationary parts and short intervals; inspect playback.
- Binary alpha (0/255) and matching canvases are required. Partial alpha is rejected rather than silently thresholded. Durations must be integer milliseconds from 1 to 65535. Very large selections are rejected by a work estimate; split them into shorter intervals.

## Output

Each new export folder contains `frames/*.png`, a lossless APNG `animation.png`, `animation.json` with durations and operation reports, and `spritesheet.png` plus Aseprite-style JSON array metadata `spritesheet.json`. The JSON is not a native Aseprite project. APNG preserves duplicate frames, RGBA including hidden RGB, frame count and timing without palette quantization. Some viewers display only its first frame. PNG frames and JSON are the primary exchange data. GIF export is intentionally omitted because it can quantize colors and timing; importing GIF cannot recover already-lost information.

## CLI and API

Create `params.json`:

```json
{"start":1,"end":8,"rectangles":[{"x":4,"y":6,"width":12,"height":16}],"alpha_mode":"preserve","cleanup_isolated":false,"cleanup_halo":0}
```

```sh
python -m pixel_color_stabilizer --input input_frames --params params.json --output result
python -m pixel_color_stabilizer --input sheet.png --cell 64 64 --frames 12 --duration 100 --params params.json --output result_sheet
```

The API supports a union of 1–64 rectangles. Overlap is counted once. `min_ratio` optionally filters uncertain modes in `preserve`; it must be zero in `majority`.

```python
from pixel_color_stabilizer import temporal_mode
from pixel_color_stabilizer.media import Animation, load_animation, export_bundle

a = load_animation("input_frames")
frames, report = temporal_mode(a.frames, 1, 8,
    [{"x": 4, "y": 6, "width": 12, "height": 16}], alpha_mode="preserve")
export_bundle("result", Animation(frames, a.durations, [report]))
```

## Develop and package

```sh
python -m pip install '.[build]'
python -m unittest discover -s tests -v
python -m build
```

On Windows, run `scripts/build_windows.ps1` from an activated clean virtual environment. Output: `dist/PixelColorStabilizer-windows-x64.zip`. `.github/workflow-templates/` contains cross-platform test and Windows packaging templates. The initial publishing token lacked the `workflow` scope, so Actions is not enabled; a maintainer can copy these templates into `.github/workflows/` through GitHub's web editor. The Windows workflow supports manual or `v*` tag triggers and uploads an artifact without automatically publishing a public release. Commit source and docs; omit `.venv`, `build`, `dist`, private assets and caches. Upload the portable ZIP separately as a Release asset. Repository: [Ainatem/Pixel-Color-Stabilizer](https://github.com/Ainatem/Pixel-Color-Stabilizer). Download portable builds from its Releases page.

Project code is [MIT licensed](LICENSE). Core algorithms were extracted from the local Pixel Studio source with original voting semantics. No commercial editor, model weights or user assets are included. Runtime dependencies retain their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).
