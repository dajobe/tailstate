"""Allow imports of ``tailstate`` when tests run without an editable install."""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parents[1] / "src"
if _src.is_dir():
    sys.path.insert(0, str(_src))
