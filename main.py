#!/usr/bin/env python3
"""Simple entry file for command-line use."""

import sys

from src.cli import main as cli_main

if __name__ == "__main__":
    # Start the CLI and return its exit code to the shell.
    sys.exit(cli_main())
