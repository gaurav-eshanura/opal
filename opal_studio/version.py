"""The one place the Opal version number is written down.

The About box, the build (which names the release zip) and the website all
read it from here, so they can never drift apart.
"""

__version__ = "2.3.0"

# The name of the release archives the build produces, e.g.
# "Opal-v2.2.0-Windows-x64.zip".
RELEASE_TAG = f"v{__version__}"
