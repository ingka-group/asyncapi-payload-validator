"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Command-line interface for AsyncAPI Payload Validator."""

import sys
import io
from pathlib import Path

# Import the main function from validator module
from .validator import main

def cli():
    """CLI entry point wrapper."""
    # Fix Windows console encoding issues with Unicode characters
    if sys.platform == 'win32':
        # Reconfigure stdout/stderr to use UTF-8 encoding
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nValidation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    cli()
