import argparse
import json
from pathlib import Path

from .media import load_animation, export_bundle, Animation
from .core import temporal_mode


def main():
    parser = argparse.ArgumentParser(description='Pixel Color Stabilizer — no Aseprite required')
    parser.add_argument('--gui', action='store_true', help='Open desktop editor (also the default with no arguments)')
    parser.add_argument('--input', type=Path, help='PNG folder, GIF/APNG, or PNG sheet')
    parser.add_argument('--output', type=Path, help='New output directory')
    parser.add_argument('--params', type=Path, help='JSON with start, end, rectangles and optional mode/cleanup settings')
    parser.add_argument('--duration', type=int, default=100, help='Default PNG frame duration in milliseconds')
    parser.add_argument('--cell', type=int, nargs=2, metavar=('WIDTH', 'HEIGHT'), help='Uniform sheet cell size')
    parser.add_argument('--frames', type=int, help='Sheet frame count, excluding trailing empty cells')
    args = parser.parse_args()
    if args.gui or not any((args.input, args.output, args.params)):
        from .gui import main as gui_main
        gui_main()
        return
    if not all((args.input, args.output, args.params)):
        parser.error('--input, --output and --params are required for batch mode')
    try:
        animation = load_animation(args.input, args.duration, args.cell, args.frames)
        params = json.loads(args.params.read_text(encoding='utf-8-sig'))
        arrays, report = temporal_mode(animation.frames, **params)
        export_bundle(args.output, Animation(arrays, animation.durations, animation.operations + [report]))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
