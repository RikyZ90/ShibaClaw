"""PyInstaller hook for cffi.cparser.

The cffi parser contains a never-called workaround function with delayed
imports for ``pycparser.lextab`` and ``pycparser.yacctab``. Recent pycparser
releases used by this project do not ship those generated modules, so excluding
them removes false positives from PyInstaller's warn report.
"""

excludedimports = ["pycparser.lextab", "pycparser.yacctab"]