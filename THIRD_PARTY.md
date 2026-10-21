# Third-party components

The project source is MIT licensed. Dependencies and their bundled notices remain under their own terms:

| Component | Role | License family |
| --- | --- | --- |
| Python | Runtime | PSF license and bundled notices |
| Tcl/Tk | Desktop widgets | Tcl/Tk license |
| NumPy | Array operations | BSD-3-Clause and bundled notices |
| SciPy | Connected-component labeling | BSD-3-Clause and bundled notices, including native libraries |
| Pillow | PNG/GIF/APNG import and PNG export | MIT-CMU / HPND and bundled codec notices |
| PyInstaller | Portable packaging and bootloader | GPL with bootloader exception; see installed package license |

The packaging script copies installed distribution notices, including the Python,
Tcl/Tk and PyInstaller license files when available, into `third_party_licenses/`.
Dependency metadata and bundled library license files are also retained by
PyInstaller. Refer to those version-specific texts for the complete terms.

No Aseprite binary or assets, Blender binary, AI models, local project data,
API tokens, downloaded references or generated private artwork are distributed.
