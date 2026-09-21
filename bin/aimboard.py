#!/usr/bin/env python3
"""Entry point for the aim dashboard.

The dashboard is a package (`aimboard/`) beside this file, one module per
concern, with views that register themselves as plugins. This script exists so
that `bin/aimboard.py render ...` keeps working; everything it does is in the
package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aimboard.cli import main  # noqa: E402  (path first)

if __name__ == "__main__":
    sys.exit(main())
