#!/usr/bin/env bash
# Opal - macOS build
# Plain English: Builds a portable macOS app bundle with PyInstaller.
set -e
cd "$(dirname "$0")"

if [ ! -f "assets/bin/ffmpeg" ]; then
  echo "NOTE: assets/bin/ffmpeg is missing - video tools will ask for the media engine."
fi

PYINSTALLER_ARGS=(-m PyInstaller --noconfirm --clean Tangerine.spec)
python3 "${PYINSTALLER_ARGS[@]}"

# Trim what macOS never needs.
INTERNAL="dist/Opal/_internal"
if [ -d "$INTERNAL" ]; then
  rm -rf "$INTERNAL/PySide6/translations" \
         "$INTERNAL/PySide6/opengl32sw.dll" \
         "$INTERNAL/PySide6/Qt6Quick.dll" \
         "$INTERNAL/PySide6/Qt6Qml.dll" || true
  echo "Trimmed unused Qt payload."
fi

echo
echo "Built: dist/Opal/Opal.app"
echo "Copy that folder anywhere and open it - no install needed."
