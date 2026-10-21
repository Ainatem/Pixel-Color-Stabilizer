"""Create a GitHub-ready source ZIP without environments or private assets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
out = root/'dist/PixelColorStabilizer-source.zip'
out.parent.mkdir(exist_ok=True)
files = [root/name for name in ('pyproject.toml', 'MANIFEST.in', '.gitignore', 'LICENSE',
    'README.md', 'README.en.md', 'THIRD_PARTY.md', 'VALIDATION.md', 'Start.cmd')]
for directory, pattern in (('pixel_color_stabilizer', '*.py'), ('tests', '*.py'),
                           ('scripts', '*.py'), ('scripts', '*.ps1'), ('.github', '*.yml')):
    files.extend((root/directory).rglob(pattern))
with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        if '__pycache__' not in path.parts:
            archive.write(path, Path('Pixel-Color-Stabilizer')/path.relative_to(root))
print(out)
