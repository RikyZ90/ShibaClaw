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
    if sys.platform != "win32":
        return
    
    # Determina la directory da cui cercare i file.
    # Se siamo in un bundle PyInstaller, usa _MEIPASS.
    # Altrimenti, usa la directory dell'eseguibile (caso onedir o estrazione ZIP).
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir is None:
        # Directory dell'eseguibile
        bundle_dir = os.path.dirname(sys.executable)

    # Try to use ctypes to delete the ADS more reliably on Windows
    try:
        import ctypes
        from ctypes.wintypes import LPCWSTR

        # Define DeleteFileW for removing ADS
        delete_file = ctypes.windll.kernel32.DeleteFileW
        delete_file.argtypes = [LPCWSTR]
        delete_file.restype = bool

        def remove_ads(path: str) -> None:
            # Remove the Zone.Identifier ADS
            ads_path = path + ":Zone.Identifier"
            if not delete_file(ads_path):
                # If deletion fails, it might not exist, ignore
                pass
    except (ImportError, AttributeError):
        # Fallback to os.remove if ctypes is not available
        def remove_ads(path: str) -> None:
            ads_path = path + ":Zone.Identifier"
            try:
                os.remove(ads_path)
            except (OSError, FileNotFoundError):
                pass

    for dirpath, _dirs, filenames in os.walk(bundle_dir):
        for fn in filenames:
            if not fn.lower().endswith((".dll", ".exe", ".pyd")):
                continue
            full_path = os.path.join(dirpath, fn)
            remove_ads(full_path)

_unblock_bundle_dir()
