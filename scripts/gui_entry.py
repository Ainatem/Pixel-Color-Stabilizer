"""Absolute import entry for PyInstaller."""
from pixel_color_stabilizer.gui import main

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from pixel_color_stabilizer.selftest import run
        run(sys.argv[2])
    else:
        main()
