#!/usr/bin/env bash
# Install Toma Timer .desktop entry + icon for the current user.
# After running, rofi (drun mode) and app menus will show "Toma Timer".
#
# Usage:  ./install.sh           # install
#         ./install.sh --uninstall
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
ICON_DIR="$DATA/icons"

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Removing Toma Timer desktop entry + icon..."
  rm -f "$APPS/toma-timer.desktop"
  find "$ICON_DIR/hicolor" -name "toma-timer.png" -delete 2>/dev/null || true
  (command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS") || true
  (command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$ICON_DIR/hicolor") || true
  echo "Done. Toma Timer removed from launcher."
  exit 0
fi

echo "Installing Toma Timer icon (all sizes)..."
for src in "$DIR"/assets/icons/hicolor/*/apps/toma-timer.png; do
  size_dir="$(basename "$(dirname "$(dirname "$src")")")"   # e.g. 48x48
  dst="$ICON_DIR/hicolor/$size_dir/apps"
  mkdir -p "$dst"
  cp -f "$src" "$dst/toma-timer.png"
done

# Also drop a 512px master for icon-name lookups
mkdir -p "$ICON_DIR/hicolor/512x512/apps"
cp -f "$DIR/assets/icons/hicolor/512x512/apps/toma-timer.png" "$ICON_DIR/hicolor/512x512/apps/toma-timer.png"

echo "Installing .desktop entry..."
mkdir -p "$APPS"
cp -f "$DIR/assets/toma-timer.desktop" "$APPS/toma-timer.desktop"

# Make the venv python path portable: rewrite Exec to point at this checkout.
VENV_PY="$DIR/.venv/bin/python"
MAIN_PY="$DIR/src/main.py"
if [[ -x "$VENV_PY" ]]; then
  sed -i "s|^Exec=.*|Exec=$VENV_PY $MAIN_PY|" "$APPS/toma-timer.desktop"
fi

echo "Updating caches..."
(command -v desktop-file-validate >/dev/null && desktop-file-validate "$APPS/toma-timer.desktop") || echo "  (validate skipped)"
(command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS") || true
(command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$ICON_DIR/hicolor") || true

echo
echo "Done. Toma Timer installed."
echo "  Desktop entry : $APPS/toma-timer.desktop"
echo "  Icon          : $ICON_DIR/hicolor/*/apps/toma-timer.png"
echo
echo "Open rofi (drun mode) and type 'toma' to launch."
