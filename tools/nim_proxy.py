#!/usr/bin/env python3
"""nim_proxy.py — local rate-limit proxy in front of NIM.

Why: NIM free tier caps at 40 RPM per key. Agent loops (opencode, nimcode,
custom scripts) burst above that and get 429'd mid-run, killing tasks
unrecoverably. This proxy queues requests under a token-bucket limit so the
agent never sees a 429 — it just runs slightly slower when the cap is hit.

Run:
  # one key, default 38 RPM
  python3 tools/nim_proxy.py

  # two keys, round-robin (75 RPM combined under 40-per-key)
  NIM_KEYS="nvapi-A...,nvapi-B..." python3 tools/nim_proxy.py

  # custom limit (e.g., 60 RPM if you have a paid endpoint)
  NIM_RPM=60 python3 tools/nim_proxy.py

Then point opencode at it. Edit ~/.config/nim-code/opencode.json:
    "baseURL": "http://localhost:8123/v1"

The proxy itself talks to https://integrate.api.nvidia.com/v1 upstream.

Stdlib only — no pip install needed.
"""
import http.server
import json
import logging
import os
import socketserver
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

# --- config ---
LISTEN_HOST   = os.environ.get("NIM_PROXY_HOST", "127.0.0.1")
LISTEN_PORT   = int(os.environ.get("NIM_PROXY_PORT", "8123"))
UPSTREAM      = os.environ.get("NIM_UPSTREAM", "https://integrate.api.nvidia.com")
RPM           = int(os.environ.get("NIM_RPM", "38"))    # per-key. NVIDIA cap is 40.
MIN_INTERVAL  = float(os.environ.get("NIM_MIN_INTERVAL", "5"))  # seconds between calls per key
LOG_LEVEL     = os.environ.get("NIM_PROXY_LOG", "INFO")

# Keys: prefer NIM_KEYS (comma-separated) for round-robin; fall back to
# NVIDIA_API_KEY (single). Strip whitespace, drop empties, dedupe (preserve order).
def _load_keys() -> list[str]:
    raw = os.environ.get("NIM_KEYS", "").strip()
    if raw:
        keys = [k.strip() for k in raw.split(",") if k.strip()]
    else:
        single = os.environ.get("NVIDIA_API_KEY", "").strip()
        keys = [single] if single else []
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k); out.append(k)
    return out

KEYS = _load_keys()
if not KEYS:
    sys.exit("nim_proxy: no keys configured. Set NVIDIA_API_KEY or NIM_KEYS.")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s nim_proxy %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nim_proxy")


# --- token bucket (one per key) ---
class TokenBucket:
    """Refills at `rate` tokens per second, capped at `capacity`.
    `acquire()` blocks until a token is available."""
    def __init__(self, capacity: float, rate_per_sec: float):
        self.capacity = capacity
        self.rate = rate_per_sec
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)

    def _refill_locked(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self, n: int = 1, key_id: str = "?") -> float:
        """Block until n tokens are available. Returns wait time in seconds."""
        t0 = time.monotonic()
        with self.cond:
            while True:
                self._refill_locked()
                if self.tokens >= n:
                    self.tokens -= n
                    waited = time.monotonic() - t0
                    if waited > 0.05:
                        log.info(f"[{key_id}] waited {waited*1000:.0f}ms for token (bucket={self.tokens:.1f})")
                    return waited
                # how long until we'd have n tokens?
                deficit = n - self.tokens
                sleep_for = max(0.05, deficit / self.rate)
                self.cond.wait(timeout=sleep_for)


# Per-key bucket. Each key gets its own bucket so they don't share quota.
BUCKETS = {k: TokenBucket(capacity=RPM, rate_per_sec=RPM / 60.0) for k in KEYS}


class MinIntervalGate:
    """Per-key serializing gate: at most one request through every `interval`
    seconds. Set NIM_MIN_INTERVAL=0 to disable. Defense in depth on top of the
    token bucket — useful when users want strict pacing regardless of bucket
    state (e.g. agent recursion loops that should pause between turns)."""
    def __init__(self, interval: float):
        self.interval = max(0.0, interval)
        self.lock = threading.Lock()
        self.last_release = 0.0   # monotonic time of last grant

    def acquire(self, key_id: str = "?") -> float:
        """Block until this gate is ready. Returns wait time in seconds."""
        if self.interval <= 0:
            return 0.0
        t0 = time.monotonic()
        with self.lock:
            now = time.monotonic()
            since = now - self.last_release
            if since < self.interval:
                wait = self.interval - since
                # Hold the lock while sleeping so other requests for THIS key
                # are also gated.
                time.sleep(wait)
            self.last_release = time.monotonic()
            waited = time.monotonic() - t0
            if waited > 0.05:
                log.info(f"[{key_id}] gate held {waited*1000:.0f}ms (interval={self.interval}s)")
            return waited


GATES = {k: MinIntervalGate(MIN_INTERVAL) for k in KEYS}


# --- round-robin key selector ---
class KeyRouter:
    """Atomic round-robin across configured keys."""
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.idx = 0
        self.lock = threading.Lock()

    def next(self) -> str:
        with self.lock:
            k = self.keys[self.idx]
            self.idx = (self.idx + 1) % len(self.keys)
            return k

router = KeyRouter(KEYS)


def _key_id(k: str) -> str:
    """8-char fingerprint of a key for logging — never log the raw key."""
    return f"{k[:8]}…{k[-4:]}" if len(k) > 14 else "key?"


# --- proxy handler ---
class Proxy(http.server.BaseHTTPRequestHandler):

    # Silence the default access-log; we log our own.
    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def _proxy(self):
        # Pick a key, acquire a token, AND wait the min-interval gate.
        # Two layers: bucket (RPM cap) + gate (strict pacing between calls).
        key = router.next()
        kid = _key_id(key)
        BUCKETS[key].acquire(1, kid)
        GATES[key].acquire(kid)

        # Build upstream request
        upstream_url = f"{UPSTREAM}{self.path}"
        body = b""
        clen = int(self.headers.get("Content-Length", "0") or 0)
        if clen > 0:
            body = self.rfile.read(clen)

        req = urllib.request.Request(upstream_url, data=body if body else None, method=self.command)
        # Pass through headers EXCEPT Host (urllib sets it) and the inbound Authorization
        # (we replace with the rotated key).
        for h, v in self.headers.items():
            if h.lower() in ("host", "authorization", "content-length"):
                continue
            req.add_header(h, v)
        req.add_header("Authorization", f"Bearer {key}")
        if body:
            req.add_header("Content-Length", str(len(body)))

        # Try to extract model from JSON body for logging
        model = "?"
        try:
            if body:
                model = json.loads(body).get("model", "?")
        except Exception:
            pass

        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                # Mirror status + headers (drop hop-by-hop)
                self.send_response(resp.status)
                hop = {"connection", "keep-alive", "transfer-encoding", "te",
                       "trailers", "upgrade", "proxy-authenticate", "proxy-authorization"}
                for h, v in resp.headers.items():
                    if h.lower() in hop:
                        continue
                    self.send_header(h, v)
                self.end_headers()
                # Stream body in chunks so SSE works
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                dt = (time.monotonic() - t0) * 1000
                log.info(f"[{kid}] {self.command} {self.path} model={model} -> {resp.status} ({dt:.0f}ms)")
        except urllib.error.HTTPError as e:
            body_preview = (e.read() or b"")[:200].decode("utf-8", "replace")
            log.warning(f"[{kid}] upstream {e.code} model={model}: {body_preview}")
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(body_preview.encode())
        except Exception as e:
            log.error(f"[{kid}] proxy error model={model}: {e}")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"proxy: {e}"}).encode())

    def _health(self):
        """Local health endpoint — DO NOT forward upstream. Used by the
        nimcode launcher to verify the proxy is reachable before pointing
        opencode at it."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"nim-code proxy ok\n")

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._health()
        else:
            self._proxy()
    def do_POST(self): self._proxy()
    def do_PUT(self):  self._proxy()


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    log.info(f"NIM rate-limit proxy listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    log.info(f"upstream: {UPSTREAM}")
    log.info(f"keys: {len(KEYS)} configured  ->  effective RPM: {RPM * len(KEYS)} (token bucket)")
    log.info(f"min interval per key: {MIN_INTERVAL}s (NIM_MIN_INTERVAL=0 disables)")
    for k in KEYS:
        log.info(f"  - {_key_id(k)}  bucket={RPM} RPM")
    log.info("point opencode at:  baseURL = http://%s:%d/v1", LISTEN_HOST, LISTEN_PORT)
    log.info("press Ctrl-C to stop")
    srv = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Proxy)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        srv.server_close()


if __name__ == "__main__":
    main()
