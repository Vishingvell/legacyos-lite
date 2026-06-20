# Copyright (c) 2026 Vishalan Karunanithi.
# All Rights Reserved.
# This repository is published for hackathon review only. No permission is granted to copy,
# modify, distribute, sublicense, or commercially use this software without written permission.

"""Vercel function entrypoint for LegacyOS Lite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("LEGACYOSLITE_DB_PATH", "/tmp/legacyoslite.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# Keep demo visibility aligned with preview URL while remaining local-safe.
os.environ.setdefault("LEGACYOSLITE_ALLOWED_ORIGINS", "")

from legacyos_lite.main import app  # noqa: E402
