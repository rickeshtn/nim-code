#!/usr/bin/env bash
# Build dist/nimcode-installer.sh — a single-file installer with
# opencode.json + nim_proxy.py embedded inline. The output is one bash
# script users can download from a GitHub Release and run directly.
#
# Usage:  ./tools/build_installer.sh
# Output: dist/nimcode-installer.sh
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="dist/nimcode-installer.sh"
mkdir -p dist

# Sanity checks
[ -f install.sh ]        || { echo "install.sh missing" >&2; exit 1; }
[ -f opencode.json ]     || { echo "opencode.json missing" >&2; exit 1; }
[ -f tools/nim_proxy.py ] || { echo "tools/nim_proxy.py missing" >&2; exit 1; }
python3 -c "import json; json.load(open('opencode.json'))"          # validate JSON
python3 -m py_compile tools/nim_proxy.py                            # validate python

VERSION="$(grep -E '^NIMCODE_VERSION=' install.sh | head -1 | cut -d'"' -f2)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# Unique heredoc tags that cannot appear in the embedded files
TAG_JSON="__NIMCODE_OPENCODE_JSON_END__"
TAG_PROXY="__NIMCODE_PROXY_PY_END__"
if grep -q "$TAG_JSON" opencode.json; then
  echo "heredoc tag '$TAG_JSON' clashes with opencode.json" >&2; exit 1
fi
if grep -q "$TAG_PROXY" tools/nim_proxy.py; then
  echo "heredoc tag '$TAG_PROXY' clashes with nim_proxy.py" >&2; exit 1
fi

{
  echo '#!/usr/bin/env bash'
  echo "# nimcode-installer.sh v${VERSION} (build ${GIT_SHA})"
  echo "# Self-contained installer — opencode.json + nim_proxy.py embedded inline."
  echo "# Source: https://github.com/natkal-coder/nim-code"
  echo "#"
  echo "# Usage:  chmod +x nimcode-installer.sh && ./nimcode-installer.sh"
  echo
  echo "set -e"
  echo
  echo "# --- extract embedded payloads ---"
  echo 'NIMCODE_SRC_DIR_OVERRIDE="$(mktemp -d -t nimcode-XXXXXX)"'
  echo 'mkdir -p "$NIMCODE_SRC_DIR_OVERRIDE/tools"'
  echo 'trap '"'"'rm -rf "$NIMCODE_SRC_DIR_OVERRIDE"'"'"' EXIT'
  echo
  echo "# opencode.json"
  echo "cat > \"\$NIMCODE_SRC_DIR_OVERRIDE/opencode.json\" <<'$TAG_JSON'"
  cat opencode.json
  echo "$TAG_JSON"
  echo
  echo "# nim_proxy.py (also exported as EMBEDDED_NIM_PROXY for install.sh)"
  echo "cat > \"\$NIMCODE_SRC_DIR_OVERRIDE/tools/nim_proxy.py\" <<'$TAG_PROXY'"
  cat tools/nim_proxy.py
  echo "$TAG_PROXY"
  echo "export NIMCODE_SRC_DIR_OVERRIDE"
  echo 'export EMBEDDED_NIM_PROXY="$NIMCODE_SRC_DIR_OVERRIDE/tools/nim_proxy.py"'
  echo
  echo "# --- install.sh body (verbatim, minus its own shebang) ---"
  tail -n +2 install.sh
} > "$OUT"

chmod +x "$OUT"
bash -n "$OUT"

bytes=$(wc -c < "$OUT")
echo "built: $OUT  (${bytes} bytes, version ${VERSION}, sha ${GIT_SHA})"
