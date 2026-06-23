"""Pipeline configuration (paths). No external services, no paid APIs."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = two levels up from this file (src/market_elt/config.py).
ROOT = Path(__file__).resolve().parents[2]

DB_PATH = Path(os.environ.get("MARKET_ELT_DB", str(ROOT / "market_elt.duckdb")))
SAMPLE_CSV = ROOT / "data" / "sample" / "prices.csv"
