#!/usr/bin/env python3
"""Backward-compatible wrapper for the RP migration config converter."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target_script = (
        Path(__file__).resolve().parents[1]
        / "rp_migration_config"
        / "scripts"
        / "rp_migration_config_to_env.py"
    )
    runpy.run_path(str(target_script), run_name="__main__")
