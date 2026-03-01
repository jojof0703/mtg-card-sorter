#!/usr/bin/env python3
"""MTG Card Sorter - entry point."""

import sys

from src.cli import main as cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
