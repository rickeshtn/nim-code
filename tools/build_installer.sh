#!/usr/bin/env bash
# Build dist/nimcode-installer.sh — a single-file installer with
# opencode.json embedded inline. The output is one bash script users can
# download from a GitHub Release and run directly.
#
# Usage:  ./tools/build_installer.sh
# Output: dist/nimcode-installer.sh
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="dist/nimcode-installer.sh"
mkdir -p dist

# Sanity checks
[ -f install.sh ] || { echo "install.sh missing" >&2; exit 1; }
[ -f opencode.json ] || { echo "opencode.json missing" >&2; exit 1; }
python3 -c "import json; json.load(open('opencode.json'))"   # validate JSON

VERSION="$(grep -E '^NIMCODE_VERSION=' install.sh | head -1 | cut -d'"' -f2)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# Pick a unique heredoc tag that cannot appear in opencode.json
HEREDOC_TAG="__NIMCODE_OPENCODE_JSON_END__"
if grep -q "$HEREDOC_TAG" opencode.json; then
  echo "heredoc tag '$HEREDOC_TAG' clashes with opencode.json contents" >&2
  exit 1
fi

{
  echo '#!/usr/bin/env bash'
  echo "# nimcode-installer.sh v${VERSION} (build ${GIT_SHA})"
  echo "# Self-contained installer — opencode.json is embedded inline."
  echo "# Source: https://github.com/natkal-coder/nim-code"
  echo "#"
  echo "# Usage:  chmod +x nimcode-installer.sh && ./nimcode-installer.sh"
  echo
  echo "set -e"
  echo
  echo "# --- extract embedded opencode.json ---"
  echo 'NIMCODE_SRC_DIR_OVERRIDE="$(mktemp -d -t nimcode-XXXXXX)"'
  echo 'trap '"'"'rm -rf "$NIMCODE_SRC_DIR_OVERRIDE"'"'"' EXIT'
  echo "cat > \"\$NIMCODE_SRC_DIR_OVERRIDE/opencode.json\" <<'$HEREDOC_TAG'"
  cat opencode.json
  echo "$HEREDOC_TAG"
  echo "export NIMCODE_SRC_DIR_OVERRIDE"
  echo
  echo "# --- install.sh body (verbatim, minus its own shebang) ---"
  # Strip the shebang line from install.sh; everything else is included verbatim.
  tail -n +2 install.sh
} > "$OUT"

chmod +x "$OUT"

# Syntax-check the produced file
bash -n "$OUT"

bytes=$(wc -c < "$OUT")
echo "built: $OUT  (${bytes} bytes, version ${VERSION}, sha ${GIT_SHA})"
