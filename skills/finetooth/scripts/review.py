#!/usr/bin/env python3
"""The review tool's command: `python3 <skill>/scripts/review.py <subcommand>`.

The code lives in the `finetooth` package next to this file, one module per concern;
`finetooth/cli.py` holds the subcommands. Standard library only, no dependencies.
"""

import sys

from finetooth.cli import main

if __name__ == "__main__":
    sys.exit(main())
