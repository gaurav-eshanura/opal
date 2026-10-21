"""
Opal - File manager integration ("Open with Opal")
Plain English: Adds a right-click entry so a customer can send any file
straight to the studio. Windows uses the per-user shell key, Linux writes a
shared-mime handler, and macOS - which has no equivalent for all files -
reports that plainly instead of failing.
"""

import sys
from pathlib import Path

from opal_studio.platform_compat import (install_context_menu as _install,
                                         uninstall_context_menu as _uninstall,
                                         context_menu_supported, platform_name)


def install_context_menu() -> bool:
    """Adds the entry to the system file manager."""
    return _install()


def uninstall_context_menu() -> bool:
    """Removes the entry from the system file manager."""
    return _uninstall()


def describe_support() -> str:
    if context_menu_supported():
        return f"Right-click integration is available on {platform_name()}."
    return ("Right-click integration is not available on macOS - "
            "drag a file onto the app instead.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        print("Removed from the file manager." if uninstall_context_menu()
              else "Could not remove the entry.")
    else:
        print("Added to the file manager." if install_context_menu() else describe_support())
