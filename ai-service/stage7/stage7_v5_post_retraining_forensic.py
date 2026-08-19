"""Entry point for V5 post-retraining forensic investigation.

Delegates to the canonical implementation in experiment_v5/post_retraining_forensic.py.
Read-only: no production changes, no retraining, no deployment.
"""
from __future__ import annotations

import runpy
from pathlib import Path

_IMPL = Path(__file__).resolve().parent / "experiment_v5" / "post_retraining_forensic.py"

if __name__ == "__main__":
    runpy.run_path(str(_IMPL), run_name="__main__")
