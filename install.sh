#!/usr/bin/env bash
# nim-code installer
# Installs the opencode CLI, drops a NIM-preconfigured opencode.json into
# ~/.config/nim-code/, picks up your NVIDIA build.nvidia.com API key
# (from $HOME/.nvidia_api_key, an existing env var, or an interactive
# prompt), validates it live, and installs a `nimcode` launcher into
# ~/.local/bin.
#
# Re-running is safe (idempotent). Pass --reset to wipe stored key.
set -euo pipefail
trap '
  rc=$?
  printf "\033[31mxx\033[0m install.sh failed at line %d (exit %d)\n" "${LINENO}" "$rc" >&2
  if [ -n "${POSTHOG_API_KEY:-}" ] && [ -d "${CONFIG_DIR:-}" ]; then
    iid=$(cat "$CONFIG_DIR/install_id" 2>/dev/null) || iid=""
    [ -n "$iid" ] && telemetry_send install_fail "$iid" || true
  fi
' ERR

# ---------- paths ----------
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nim-code"
ENV_FILE="$CONFIG_DIR/env"
CFG_FILE="$CONFIG_DIR/opencode.json"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/nimcode"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Canonical user-visible key file. We tell users to put their nvapi-... here.
KEY_FILE="$HOME/.nvidia_api_key"

NIM_URL="https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL="moonshotai/kimi-k2.6"
NIMCODE_VERSION="0.1.0"

# --- telemetry (PostHog Cloud) ---
# Maintainers: paste the Project API Key here to enable telemetry. Empty
# string disables outbound ping entirely.
# Get one free at https://posthog.com -> Project -> API Keys.
# See telemetry/README.md for the full setup procedure.
POSTHOG_API_KEY="phc_vBuMdENF5HnK6LdjimWvxdoMPPzHAGKBCYWSPKhMRWfG"
POSTHOG_HOST="https://us.i.posthog.com"   # or https://eu.i.posthog.com

# Users opt out via either:
#   export NIMCODE_NO_TELEMETRY=1
#   touch ~/.config/nim-code/no-telemetry
telemetry_send() {
  local event="$1"; local id="$2"
  [ -n "${POSTHOG_API_KEY:-}" ] || return 0
  [ -z "${NIMCODE_NO_TELEMETRY:-}" ] || return 0
  [ ! -f "$CONFIG_DIR/no-telemetry" ] || return 0
  local os arch
  os=$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -cd 'A-Za-z0-9._-' | cut -c1-32)
  arch=$(uname -m 2>/dev/null | tr -cd 'A-Za-z0-9._-' | cut -c1-32)
  curl -fsS --max-time 3 -o /dev/null \
    -H 'Content-Type: application/json' \
    -d "{
      \"api_key\":\"$POSTHOG_API_KEY\",
      \"event\":\"nimcode_$event\",
      \"distinct_id\":\"$id\",
      \"properties\":{\"version\":\"$NIMCODE_VERSION\",\"os\":\"$os\",\"arch\":\"$arch\"}
    }" \
    "$POSTHOG_HOST/i/v0/e/" 2>/dev/null || true
}

# Generate-or-load a random install id. Stored at $CONFIG_DIR/install_id.
ensure_install_id() {
  local f="$CONFIG_DIR/install_id"
  if [ -f "$f" ]; then cat "$f"; return; fi
  local id
  if command -v uuidgen >/dev/null 2>&1; then
    id=$(uuidgen | tr -d '-' | cut -c1-32)
  else
    id=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-32)
  fi
  mkdir -p "$CONFIG_DIR"
  umask 077
  printf '%s\n' "$id" > "$f"
  printf %s "$id"
}

# ---------- ui ----------
c_red=$'\033[31m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'
say()  { printf '%s>>%s %s\n'  "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s!!%s %s\n'  "$c_ylw" "$c_rst" "$*" >&2; }
die()  { printf '%sxx%s %s\n'  "$c_red" "$c_rst" "$*" >&2; exit 1; }

mask() {
  # show nvapi-XXXXXX...YYYY without revealing the middle
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

[ -f "$SRC_DIR/opencode.json" ] || die "opencode.json missing next to installer ($SRC_DIR). Re-clone the repo."
cp "$SRC_DIR/opencode.json" "$CFG_FILE"
say "installed config -> $CFG_FILE"

INSTALL_ID="$(ensure_install_id)"

# ---------- 4. resolve API key ----------
# Priority:
#   --reset:           ignore stored env file, re-detect from sources below
#   1. $NVIDIA_API_KEY already exported in this shell
#   2. $HOME/.nvidia_api_key   (recommended user-managed file, one line)
#   3. previously installed $CONFIG_DIR/env
#   4. interactive prompt -> offers to save to $HOME/.nvidia_api_key
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

# 4. interactive prompt
if [ -z "$KEY" ]; then
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
  # Will be saved to $KEY_FILE in step 6 unconditionally.
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

# ---------- 6. persist the resolved key, then write a trivial env file ----------
# Design choice: COPY the resolved key into ~/.nvidia_api_key and have the env
# file read only that. We do NOT source other env files at launch time —
# external files can reference unset vars and break under the launcher's
# strict mode. The cost: if you rotate the key elsewhere you must re-run
# install.sh to refresh this copy.
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

# Write meta (version + telemetry config) for the launcher to read.
cat > "$CONFIG_DIR/meta" <<EOF
NIMCODE_VERSION="$NIMCODE_VERSION"
POSTHOG_API_KEY="$POSTHOG_API_KEY"
POSTHOG_HOST="$POSTHOG_HOST"
EOF
chmod 600 "$CONFIG_DIR/meta"

# ---------- 7. launcher ----------
# Heredoc is QUOTED so the launcher body is taken verbatim — no install-time
# variable expansion inside. The launcher reads $CONFIG_DIR/meta at runtime
# to learn its version and telemetry URL.
cat > "$LAUNCHER" <<'LAUNCH'
#!/usr/bin/env bash
# nimcode — launch opencode CLI with the NIM-preconfigured provider.
set -euo pipefail
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nim-code"
ENV_FILE="$CONFIG_DIR/env"
CFG_FILE="$CONFIG_DIR/opencode.json"
META_FILE="$CONFIG_DIR/meta"

[ -f "$ENV_FILE" ] || { echo "nim-code: missing $ENV_FILE — run install.sh" >&2; exit 1; }
[ -f "$CFG_FILE" ] || { echo "nim-code: missing $CFG_FILE — run install.sh" >&2; exit 1; }

set +eu
# shellcheck disable=SC1090
. "$ENV_FILE"
[ -f "$META_FILE" ] && . "$META_FILE"
set -eu

command -v opencode >/dev/null 2>&1 || { echo "nim-code: opencode CLI not on PATH — run install.sh" >&2; exit 1; }

if [ -z "${NVIDIA_API_KEY:-}" ]; then
  echo "nim-code: NVIDIA_API_KEY not resolved from $ENV_FILE" >&2
  echo "          fix: put your key in \$HOME/.nvidia_api_key" >&2
  exit 1
fi

# First-run telemetry. Strict opt-outs: env var, marker file, or empty key.
if [ -n "${POSTHOG_API_KEY:-}" ] \
   && [ -z "${NIMCODE_NO_TELEMETRY:-}" ] \
   && [ ! -f "$CONFIG_DIR/no-telemetry" ] \
   && [ ! -f "$CONFIG_DIR/first_run_done" ] \
   && [ -f "$CONFIG_DIR/install_id" ]; then
  iid=$(cat "$CONFIG_DIR/install_id")
  os=$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -cd 'A-Za-z0-9._-' | cut -c1-32)
  arch=$(uname -m 2>/dev/null | tr -cd 'A-Za-z0-9._-' | cut -c1-32)
  curl -fsS --max-time 3 -o /dev/null \
    -H 'Content-Type: application/json' \
    -d "{
      \"api_key\":\"$POSTHOG_API_KEY\",
      \"event\":\"nimcode_first_run\",
      \"distinct_id\":\"$iid\",
      \"properties\":{\"version\":\"${NIMCODE_VERSION:-unknown}\",\"os\":\"$os\",\"arch\":\"$arch\"}
    }" \
    "${POSTHOG_HOST:-https://us.i.posthog.com}/i/v0/e/" 2>/dev/null || true
  touch "$CONFIG_DIR/first_run_done"
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

# ---------- 9. telemetry ping (opt-out via NIMCODE_NO_TELEMETRY or $CONFIG_DIR/no-telemetry) ----------
telemetry_send install_ok "$INSTALL_ID"

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
