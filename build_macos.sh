#!/usr/bin/env bash
# Opal - macOS build
# Plain English: Builds the portable macOS app bundle with PyInstaller.
#
#   ./build_macos.sh          full build (everything included)
#   ./build_macos.sh --core   core build (engines fetched on demand)
set -e
cd "$(dirname "$0")"

VARIANT="full"
DIST="Opal-Full"
if [ "${1:-}" = "--core" ]; then
  VARIANT="core"
  DIST="Opal"
fi

if [ ! -f "assets/bin/ffmpeg" ]; then
  echo "NOTE: assets/bin/ffmpeg is missing - the video and audio tools will use"
  echo "      the ffmpeg on this machine instead of a bundled one."
fi

# One build pipeline for every platform: it runs PyInstaller, trims the payload
# the app never loads, packs the release archive and stages it where the
# website's download button expects it.
python3 build_release.py ${1:-}

# The app is a bundle, so people drag the whole .app across.
chmod +x "dist/${DIST}.app/Contents/MacOS/${DIST}" 2>/dev/null || true

echo
echo "Built ($VARIANT): dist/${DIST}.app"
echo "Copy that .app anywhere, open it and it works - no install needed."
