"""Local PyInstaller override for pycparser.

The upstream contrib hook still assumes ``pycparser.lextab`` and
``pycparser.yacctab`` are generated modules that must be bundled to avoid
runtime writes to the current working directory.

That assumption is outdated for the pycparser version used here: the parser
keeps those names only for backward-compatible constructor parameters and does
not require the generated modules. Overriding the upstream hook avoids noisy
false-positive hidden import warnings during the Windows desktop build.
"""

hiddenimports = []