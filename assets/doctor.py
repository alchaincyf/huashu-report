#!/usr/bin/env python3
"""Check the local dependencies required by huashu-report's PDF pipeline."""
import importlib.util
import shutil
import sys

def main():
    checks = []
    py_ok = sys.version_info >= (3, 11)
    checks.append((f"Python {sys.version_info.major}.{sys.version_info.minor}", py_ok))
    if sys.version_info >= (3, 14):
        print("WARNING Python 3.14+ is outside the documented 3.11 baseline; prefer a dedicated 3.11 venv for reproducibility.")
    checks.append(("playwright Python package", importlib.util.find_spec("playwright") is not None))
    for name in ("pdfinfo", "pdftotext", "pdftoppm"):
        checks.append((name, shutil.which(name) is not None))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'OK' if ok else 'MISSING':7} {name}")
    if failed:
        print("\nWindows: install Poppler (pdfinfo/pdftotext/pdftoppm), then set HUASHU_PDFINFO, HUASHU_PDFTOTEXT or HUASHU_PDFTOPPM when they are not on PATH.")
        print("Install Python dependencies with: python -m pip install playwright && python -m playwright install chromium")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
