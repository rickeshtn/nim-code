#!/usr/bin/env bash
# Remove nim-code files. Does NOT uninstall the opencode CLI itself
# (run `npm rm -g opencode-ai` for that).
set -euo pipefail
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nim-code"
LAUNCHER="$HOME/.local/bin/nimcode"

rm -rf "$CONFIG_DIR"
rm -f  "$LAUNCHER"
echo "removed $CONFIG_DIR and $LAUNCHER"
echo "opencode CLI left in place. To remove it:  npm rm -g opencode-ai"
