@echo off
cd /d "%~dp0"
python -m pixel_color_stabilizer --gui
if errorlevel 1 (
  echo Install Python 3.10+ with Tcl/Tk, then run: python -m pip install .
  pause
)
