#!/usr/bin/env python
# --------------------------------------------------------------------------
# Thin wrapper around `python -m src.cli create-admin`.
#
# Run from the repository root so that `src` is importable:
#   BIDAR_ADMIN_PASSWORD=... uv run python scripts/create_admin.py \
#       --username admin --email admin@example.com
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["create-admin", *sys.argv[1:]]))
