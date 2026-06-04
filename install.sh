#!/usr/bin/env bash
# nim-code installer
# Installs the opencode CLI, drops a NIM-preconfigured opencode.json into
# ~/.config/nim-code/, picks up your NVIDIA build.nvidia.com API key (from
# $HOME/.nvidia_api_key, $NVIDIA_API_KEY, or an interactive prompt),
# validates it live, and installs a `nimcode` launcher into ~/.local/bin.
#
# Works two ways:
#   1. Clone-and-run:   git clone ... && ./install.sh
#   2. One-line install: curl -fsSL https://raw.githubusercontent.com/natkal-coder/nim-code/main/install.sh | bash
#
# Re-running is safe (idempotent). Pass --reset to wipe stored key.
set -euo pipefail
trap 'rc=$?; printf "\033[31mxx\033[0m install.sh failed at line %d (exit %d)\n" "${LINENO}" "$rc" >&2' ERR

# ---------- paths ----------
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nim-code"
ENV_FILE="$CONFIG_DIR/env"
CFG_FILE="$CONFIG_DIR/opencode.json"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/nimcode"

# Resolve where opencode.json lives.
#   1. NIMCODE_SRC_DIR_OVERRIDE — used by the single-file installer (embedded copy)
#   2. directory of this script — used when cloned
#   3. empty -> download from upstream on the fly (curl|bash mode)
if [ -n "${NIMCODE_SRC_DIR_OVERRIDE:-}" ] && [ -f "$NIMCODE_SRC_DIR_OVERRIDE/opencode.json" ]; then
  SRC_DIR="$NIMCODE_SRC_DIR_OVERRIDE"
elif [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)/opencode.json" ]; then
  SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SRC_DIR=""
fi

# Canonical user-visible key file.
KEY_FILE="$HOME/.nvidia_api_key"

NIM_URL="https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL="moonshotai/kimi-k2.6"
NIMCODE_VERSION="0.1.0"
UPSTREAM_RAW="https://raw.githubusercontent.com/natkal-coder/nim-code/main"

# ---------- ui ----------
c_red=$'\033[31m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'
say()  { printf '%s>>%s %s\n'  "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s!!%s %s\n'  "$c_ylw" "$c_rst" "$*" >&2; }
die()  { printf '%sxx%s %s\n'  "$c_red" "$c_rst" "$*" >&2; exit 1; }

mask() {
  local k="$1"
  if [ "${#k}" -lt 20 ]; then echo "(short key)"; return; fi
  echo "${k:0:12}...${k: -4}"
}

# ---------- args ----------
RESET_KEY=0
for arg in "$@"; do
  case "$arg" in
    --reset) RESET_KEY=1 ;;
    -h|--help)
      cat <<EOF
Usage: ./install.sh [--reset]
  --reset   Forget stored key reference and re-detect / re-prompt.
EOF
      exit 0 ;;
    *) die "unknown arg: $arg" ;;
  esac
done

# ---------- 1. node + npm ----------
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  die "Node.js (>=20) and npm are required. Install from https://nodejs.org/ then re-run."
fi
node_major=$(node -p 'process.versions.node.split(".")[0]')
if [ "$node_major" -lt 20 ]; then
  die "Node $node_major is too old. Need >=20."
fi

# ---------- 2. opencode CLI ----------
if ! command -v opencode >/dev/null 2>&1; then
  say "installing opencode CLI globally (opencode-ai)"
  if ! npm i -g opencode-ai 2>/tmp/nim-code-npm.log; then
    warn "global install failed. tail of log:"
    tail -n 20 /tmp/nim-code-npm.log >&2
    die "Try:  sudo npm i -g opencode-ai   (or fix npm prefix to a user-writable dir)"
  fi
else
  say "opencode already installed: $(command -v opencode)"
fi

# ---------- 3. config dir + opencode.json ----------
mkdir -p "$CONFIG_DIR" "$BIN_DIR"
chmod 700 "$CONFIG_DIR"

if [ -n "$SRC_DIR" ]; then
  cp "$SRC_DIR/opencode.json" "$CFG_FILE"
  say "installed config -> $CFG_FILE (from local clone)"
else
  say "fetching opencode.json from $UPSTREAM_RAW"
  if ! curl -fsSL --max-time 15 "$UPSTREAM_RAW/opencode.json" -o "$CFG_FILE"; then
    die "could not download opencode.json from upstream. Check network or use the git-clone install path."
  fi
  say "installed config -> $CFG_FILE (from upstream)"
fi

# ---------- 4. resolve API key ----------
# Priority:
#   --reset:           ignore stored env file, re-detect from sources below
#   1. $NVIDIA_API_KEY already exported in this shell
#   2. $HOME/.nvidia_api_key   (recommended user-managed file, one line)
#   3. previously installed $CONFIG_DIR/env
#   4. interactive prompt -> saves to $HOME/.nvidia_api_key
KEY=""
KEY_SOURCE=""

if [ "$RESET_KEY" -eq 1 ]; then
  rm -f "$ENV_FILE"
  say "cleared previously installed env file"
fi

# 1. exported env
if [ -z "$KEY" ] && [ -n "${NVIDIA_API_KEY:-}" ]; then
  KEY="$NVIDIA_API_KEY"; KEY_SOURCE="\$NVIDIA_API_KEY in your shell"
fi

# 2. $HOME/.nvidia_api_key
if [ -z "$KEY" ] && [ -f "$KEY_FILE" ]; then
  k=$(head -n1 "$KEY_FILE" | tr -d '[:space:]')
  if [ -n "$k" ]; then KEY="$k"; KEY_SOURCE="$KEY_FILE"; fi
fi

# 3. previously installed env (skip if --reset above already removed it)
if [ -z "$KEY" ] && [ -f "$ENV_FILE" ]; then
  k=$( set +eu; . "$ENV_FILE" >/dev/null 2>&1; printf %s "${NVIDIA_API_KEY:-}" )
  if [ -n "$k" ]; then KEY="$k"; KEY_SOURCE="$ENV_FILE (previous install)"; fi
fi

# 4. interactive prompt — only works when we have a tty
if [ -z "$KEY" ]; then
  if [ ! -t 0 ]; then
    die "no key available and no tty for prompt. Set NVIDIA_API_KEY in env, OR put your key in $KEY_FILE before running, OR run install.sh from a normal shell."
  fi
  cat <<EOF

${c_dim}---------------------------------------------------------------${c_rst}
 You need an NVIDIA build.nvidia.com API key.

   1. Open: https://build.nvidia.com
   2. Sign in (free) and pick any model.
   3. Click "Get API Key" -> copy the nvapi-... token.

 Tip: save the token to ${c_grn}$KEY_FILE${c_rst}
      (one line, no quotes). Future runs will pick it up
      automatically.
${c_dim}---------------------------------------------------------------${c_rst}

EOF
  printf 'Paste your NVIDIA API key (input hidden): '
  stty -echo 2>/dev/null || true
  IFS= read -r KEY || true
  stty echo 2>/dev/null || true
  printf '\n'
  [ -n "$KEY" ] || die "no key entered"
  KEY_SOURCE="interactive prompt"
fi

say "using key from: $KEY_SOURCE"
say "key fingerprint: $(mask "$KEY")"

case "$KEY" in
  nvapi-*) : ;;
  *) warn "key does not start with 'nvapi-'. Continuing, but it will likely fail." ;;
esac

# ---------- 5. validate key against NIM ----------
say "validating key against $NIM_URL ..."
http_code=$(curl -sS -o /tmp/nim-code-validate.json -w '%{http_code}' \
  "$NIM_URL/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$DEFAULT_MODEL\",
    \"messages\":[{\"role\":\"user\",\"content\":\"reply with: ok\"}],
    \"max_tokens\": 4
  }") || die "curl to NIM failed (network?)"

case "$http_code" in
  200) say "key OK (model $DEFAULT_MODEL reachable)" ;;
  401|403) rm -f /tmp/nim-code-validate.json
           die "auth rejected ($http_code). Key invalid or revoked. Fix the source and re-run." ;;
  404) warn "model $DEFAULT_MODEL returned 404 — your account may not have access. Auth itself looks OK." ;;
  429) warn "rate-limited (429). Key is valid; you're just throttled." ;;
  *)   warn "unexpected status $http_code. Response head:"
       head -c 400 /tmp/nim-code-validate.json >&2; echo >&2
       die "validation failed" ;;
esac
rm -f /tmp/nim-code-validate.json

# ---------- 6. persist the resolved key + write env file ----------
umask 077
if [ ! -f "$KEY_FILE" ] || [ "$(head -n1 "$KEY_FILE" 2>/dev/null | tr -d '[:space:]')" != "$KEY" ]; then
  printf '%s\n' "$KEY" > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  say "wrote key copy -> $KEY_FILE (chmod 600)"
else
  say "key already present at $KEY_FILE"
fi

cat > "$ENV_FILE" <<EOF
# nim-code env — single source of truth: $KEY_FILE
# Re-run install.sh after rotating the key to refresh this copy.
if [ -r "$KEY_FILE" ]; then
  NVIDIA_API_KEY="\$(head -n1 "$KEY_FILE" | tr -d '[:space:]')"
  export NVIDIA_API_KEY
fi
EOF
chmod 600 "$ENV_FILE"
say "wrote env reference -> $ENV_FILE (chmod 600)"

# ---------- 7. launcher ----------
cat > "$LAUNCHER" <<'LAUNCH'
#!/usr/bin/env bash
# nimcode — launch opencode CLI with the NIM-preconfigured provider.
set -euo pipefail
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nim-code"
ENV_FILE="$CONFIG_DIR/env"
CFG_FILE="$CONFIG_DIR/opencode.json"

[ -f "$ENV_FILE" ] || { echo "nim-code: missing $ENV_FILE — run install.sh" >&2; exit 1; }
[ -f "$CFG_FILE" ] || { echo "nim-code: missing $CFG_FILE — run install.sh" >&2; exit 1; }

set +eu
# shellcheck disable=SC1090
. "$ENV_FILE"
set -eu

command -v opencode >/dev/null 2>&1 || { echo "nim-code: opencode CLI not on PATH — run install.sh" >&2; exit 1; }

if [ -z "${NVIDIA_API_KEY:-}" ]; then
  echo "nim-code: NVIDIA_API_KEY not resolved from $ENV_FILE" >&2
  echo "          fix: put your key in \$HOME/.nvidia_api_key" >&2
  exit 1
fi

export OPENCODE_CONFIG="$CFG_FILE"
exec opencode "$@"
LAUNCH
chmod +x "$LAUNCHER"
say "installed launcher -> $LAUNCHER"

# ---------- 8. PATH check ----------
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) warn "$BIN_DIR is not on your PATH."
     warn "Add this to ~/.bashrc or ~/.zshrc:"
     echo  "    export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---------- done ----------
cat <<EOF

${c_grn}done.${c_rst} launch with:

    ${c_grn}nimcode${c_rst}

(or:  $LAUNCHER)

config:   $CFG_FILE
env:      $ENV_FILE        ${c_dim}(chmod 600)${c_rst}
key src:  $KEY_SOURCE
model:    $DEFAULT_MODEL   ${c_dim}(switch in-session with /models)${c_rst}
version:  $NIMCODE_VERSION
EOF
