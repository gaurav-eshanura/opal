#!/usr/bin/env bash
# Opal - Linux build
# Plain English: Builds a portable Linux app folder with PyInstaller.
set -e
cd "$(dirname "$0")"

if [ ! -f "assets/bin/ffmpeg" ]; then
  echo "NOTE: assets/bin/ffmpeg is missing - video tools will ask for the media engine."
fi

PYINSTALLER_ARGS=(-m PyInstaller --noconfirm --clean Tangerine.spec)
python3 "${PYINSTALLER_ARGS[@]}"

INTERNAL="dist/Opal/_internal"
if [ -d "$INTERNAL" ]; then
  rm -rf "$INTERNAL/PySide6/translations" \
         "$INTERNAL/PySide6/opengl32sw.dll" \
         "$INTERNAL/PySide6/Qt6Quick.dll" \
         "$INTERNAL/PySide6/Qt6Qml.dll" || true
  echo "Trimmed unused Qt payload."
fi

echo
echo "Built: dist/Opal/Opal"
echo "chmod +x dist/Opal/Opal and run it - no install needed."
