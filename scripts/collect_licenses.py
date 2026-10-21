"""Collect actual installed dependency notices into a portable distribution."""
from importlib import metadata
from pathlib import Path
import shutil
import sys
import tkinter
from urllib.request import urlopen


def collect(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('numpy', 'scipy', 'Pillow', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'packaging', 'pefile', 'pywin32-ctypes'):
        distribution = metadata.distribution(name)
        copied = []
        for item in distribution.files or []:
            if any('license' in part.lower() or 'copying' in part.lower() or 'copyright' in part.lower() for part in item.parts):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = destination / name / str(item).replace('..', '_parent_')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target); copied.append(str(target.relative_to(destination)))
        (destination/f'{name}-version.txt').write_text(f'{name} {distribution.version}\n'+'\n'.join(copied), encoding='utf-8')
    base = Path(sys.base_prefix)
    license_file = base / 'LICENSE.txt'
    if not license_file.exists():
        raise RuntimeError('Python LICENSE.txt missing; add its runtime license before distribution.')
    shutil.copy2(license_file, destination/'Python-LICENSE.txt')
    for name in ('tcl8.6', 'tk8.6', 'tix8.4.3'):
        path = base / 'tcl' / name / 'license.terms'
        if path.exists():
            shutil.copy2(path, destination/f'{name}-license.terms')
    if not (destination/'tcl8.6-license.terms').exists():
        # Some official Windows Python installs omit Tcl's license file.
        # Obtain the exact runtime tag's notice from Tcl's upstream source.
        version = tkinter.Tcl().eval('info patchlevel')
        tag = 'core-' + version.replace('.', '-')
        url = f'https://raw.githubusercontent.com/tcltk/tcl/{tag}/license.terms'
        with urlopen(url, timeout=30) as response:
            notice = response.read()
        if b'Copyright' not in notice and b'copyright' not in notice:
            raise RuntimeError('Unexpected Tcl license response')
        (destination/'tcl8.6-license.terms').write_bytes(notice)
        (destination/'tcl-notice-source.txt').write_text(f'Tcl {version}\n{url}\n', encoding='utf-8')
    if not (destination/'tcl8.6-license.terms').exists() or not (destination/'tk8.6-license.terms').exists():
        raise RuntimeError('Tcl/Tk license.terms missing; add the GUI runtime licenses before distribution.')


if __name__ == '__main__':
    collect(sys.argv[1])
