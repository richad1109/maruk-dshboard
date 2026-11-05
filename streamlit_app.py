"""Streamlit deployment entrypoint for Maruk Terminal."""
import sys
from pathlib import Path

# Pastikan direktori root repository selalu ada di posisi pertama sys.path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from maruk_ui import main

if __name__ == "__main__":
    main()
