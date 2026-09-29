"""PyInstaller entry point for the self-contained native build."""
import multiprocessing
import sys

from fmpoc.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
