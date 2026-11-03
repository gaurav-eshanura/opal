#!/usr/bin/env bash
# Opal - Linux build
# Plain English: Builds a portable Linux app folder with PyInstaller.
#
#   ./build_linux.sh          full build (everything included)
#   ./build_linux.sh --core   core build (engines fetched on demand)
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

# The folder has to stay runnable after it is copied to another machine.
chmod +x "dist/${DIST}/${DIST}" 2>/dev/null || true

echo
echo "Built ($VARIANT): dist/${DIST}/${DIST}"
echo "Copy that folder anywhere and run it - no install needed."
