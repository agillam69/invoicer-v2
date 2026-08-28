"""``python -m invoice_manager``."""

from __future__ import annotations

import sys

from invoice_manager.app import main

if __name__ == "__main__":
    sys.exit(main())
