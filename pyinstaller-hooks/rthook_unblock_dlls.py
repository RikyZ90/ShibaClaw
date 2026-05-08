"""PyInstaller runtime hook: remove Windows Zone.Identifier from bundled DLLs.

When a user downloads the portable ZIP from GitHub Releases, Windows adds an
NTFS alternate data stream (Zone.Identifier) to every extracted file.  The .NET
Framework CLR refuses to load assemblies that carry this mark, which causes
pythonnet to crash with:

    RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize

This hook runs before any application code and silently strips the stream from
all .dll and .exe files inside the PyInstaller bundle directory.
"""

import os
import sys

def _unblock_bundle_dir() -> None:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir is None or sys.platform != "win32":
        return

    for dirpath, _dirs, filenames in os.walk(bundle_dir):
        for fn in filenames:
            if not fn.lower().endswith((".dll", ".exe")):
                continue
            ads_path = os.path.join(dirpath, fn) + ":Zone.Identifier"
            try:
                os.remove(ads_path)
            except (OSError, FileNotFoundError):
                pass

_unblock_bundle_dir()
