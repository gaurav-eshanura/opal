"""
Opal - package entry point
Plain English: Lets the app start with `python -m opal_studio` on any platform.
"""

import sys


def run() -> int:
    from opal_studio.main import main
    return main()


if __name__ == "__main__":
    sys.exit(run())
