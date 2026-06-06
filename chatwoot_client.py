#!/usr/bin/env python3
"""
Unified Chatwoot API Client — shared by WS Agent & Provision Server

Provides:
  - Session management (login, renew, load/save auth file)
  - User session API calls (_call_cw, auto-renew on 401)
  - Platform API calls (_call_internal)
  - Password generation

Usage:
    import chatwoot_client
    chatwoot_client.CW_AUTH_FILE = Path("...")
    data = chatwoot_client._call_cw("GET", "/api/v1/accounts/1/conversations")
"""

import json
import logging
import os
import secrets
import string
import time as _time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("chatwoot_client")

# ── Module-level config (env var defaults, overridable by callers) ──
CW_BASE = os.environ.get("CW_BASE", "http://localhost:3000")
CW_INTERNAL = os.environ.get("CW_INTERNAL", "http://chatwoot-chatwoot-1:3000")
CW_ACCOUNT_ID = int(os.environ.get("CW_ACCOUNT_ID", "1"))
CW_PLATFORM_TOKEN = os.environ.get("CW_PLATFORM_TOKEN", "")
CW_EMAIL = os.environ.get("CW_EMAIL") or os.environ.get("CW_ADMIN_EMAIL", "")
CW_PASSWORD = os.environ.get("CW_PASSWORD") or os.environ.get("CW_ADMIN_PASSWORD", "")

AUTH_FILE_ENV = os.environ.get("CW_AUTH_FILE", "")
if AUTH_FILE_ENV:
    CW_AUTH_FILE = Path(AUTH_FILE_ENV)
else:
    # Fallback: try __file__ parent (works for both skills/ and repo), else cwd
    _parent = Path(__file__).parent
    if _parent.joinpath("chatwoot_auth.json").exists():
        CW_AUTH_FILE = _parent / "chatwoot_auth.json"
    else:
        CW_AUTH_FILE = Path("chatwoot_auth.json")

CW_AUTH_FILE = CW_AUTH_FILE.resolve()


# ====================================================================
#  PASSWORD GENERATION
# ====================================================================

def _gen_password(length: int = 14) -> str:
    """Generate a random secure password."""
    chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-='
    return ''.join(secrets.choice(chars) for _ in range(length))


# ====================================================================
#  SESSION MANAGEMENT (shared)
# ====================================================================

def load_auth() -> Optional[dict]:
    """Load saved auth data from JSON file. Returns None if missing/invalid."""
    if CW_AUTH_FILE.exists():
        try:
            data = json.loads(CW_AUTH_FILE.read_text(encoding="utf-8"))
            if all(k in data for k in ("access-token", "client", "expiry", "uid")):
                return data
        except Exception as e:
            log.warning("Failed to load auth file: %s", e)
    return None


def save_auth(data: dict) -> None:
    """Save auth data to JSON file."""
    CW_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    CW_AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Session saved to %s", CW_AUTH_FILE)


def get_headers() -> Optional[dict]:
    """Return auth headers dict from saved session, or None."""
    auth = load_auth()
    if auth:
        return {
            "access-token": auth.get("access-token"),
            "client": auth.get("client"),
            "expiry": auth.get("expiry"),
            "uid": auth.get("uid"),
        }
    return None


def renew_session() -> Optional[dict]:
    """Login to Chatwoot and save session. Returns auth data dict, or None on failure."""
    email = CW_EMAIL
    password = CW_PASSWORD
    if not email or not password:
        log.error("CW_EMAIL/CW_PASSWORD (or CW_ADMIN_EMAIL/CW_ADMIN_PASSWORD) not set")
        return None

    url = f"{CW_BASE}/auth/sign_in"
    payload = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            access_token = headers.get("access-token", "")
            client = headers.get("client", "")
            expiry = headers.get("expiry", "")
            uid = headers.get("uid", "")

            if not all([access_token, client, expiry, uid]):
                log.error("Login response missing required headers: %s", headers)
                return None

            # Extract pubsub_token from body (ActionCable auth)
            pubsub_token = ""
            try:
                body = json.loads(resp.read())
                pubsub_token = body.get("data", {}).get("pubsub_token", "")
            except Exception:
                pass

            data = {
                "access-token": access_token,
                "client": client,
                "expiry": expiry,
                "uid": uid,
                "pubsub_token": pubsub_token,
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            save_auth(data)
            log.info("Chatwoot session refreshed for %s (expiry=%s)", uid, expiry)
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log.error("Login HTTP %d: %s", e.code, body[:200])
        return None
    except Exception as e:
        log.error("Login error: %s", e)
        return None


def ensure_session() -> Optional[dict]:
    """Get valid session headers, auto-renew if missing/expired.
    Returns headers dict, or None if no session available."""
    auth = load_auth()
    now = _time.time()
    if auth:
        try:
            expiry_ts = int(auth.get("expiry", "0"))
            remaining = expiry_ts - now
            if remaining > 3600:  # >1h remaining, valid
                return get_headers()
            if remaining > 0:
                log.info("Session expires in %ds, renewing", int(remaining))
            else:
                log.info("Session expired %ds ago, renewing", -int(remaining))
        except (ValueError, TypeError):
            pass

    new_auth = renew_session()
    if new_auth:
        return get_headers()
    return None


# ====================================================================
#  PROVISION-SERVER COMPAT FUNCTIONS (returns headers WITH Content-Type)
# ====================================================================

def _relogin_chatwoot() -> dict:
    """Login and return headers dict (includes Content-Type).
    Raises RuntimeError on failure."""
    email = CW_EMAIL
    password = CW_PASSWORD
    if not email or not password:
        raise RuntimeError("CW_EMAIL / CW_ADMIN_EMAIL and CW_PASSWORD / CW_ADMIN_PASSWORD must be set")

    url = f"{CW_BASE}/auth/sign_in"
    payload = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            h = {k.lower(): v for k, v in resp.headers.items()}
            data = {
                "access-token": h.get("access-token", ""),
                "client": h.get("client", ""),
                "expiry": h.get("expiry", ""),
                "uid": h.get("uid", ""),
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if not all([data["access-token"], data["client"], data["uid"]]):
                raise RuntimeError(f"Login missing headers: {h}")
            CW_AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.info("Chatwoot session refreshed for %s", data["uid"])
            return {
                "access-token": data["access-token"],
                "client": data["client"],
                "expiry": data["expiry"],
                "uid": data["uid"],
                "Content-Type": "application/json",
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"Login HTTP {e.code}: {body[:200]}")


def _get_session_headers() -> dict:
    """Load session from file, auto-renew if <1h remaining.
    Returns header dict (includes Content-Type).
    Raises RuntimeError if login fails."""
    if CW_AUTH_FILE.exists():
        try:
            data = json.loads(CW_AUTH_FILE.read_text(encoding="utf-8"))
            expiry = int(data.get("expiry", 0))
            if expiry - _time.time() < 3600:
                log.info("Session < 1h (%ds left), renewing", expiry - int(_time.time()))
                return _relogin_chatwoot()
            if all([data.get("access-token"), data.get("client"), data.get("uid")]):
                return {
                    "access-token": data["access-token"],
                    "client": data["client"],
                    "expiry": data["expiry"],
                    "uid": data["uid"],
                    "Content-Type": "application/json",
                }
        except Exception as e:
            log.warning("Auth file read error: %s", e)
    return _relogin_chatwoot()


# ====================================================================
#  API CALLS (sync, urllib)
# ====================================================================

def _call_cw(method: str, path: str, body: Optional[dict] = None,
             retries: int = 3) -> dict:
    """Call Chatwoot User API with session auth.
    Auto-renew on 401. Returns parsed JSON dict.
    Raises RuntimeError on failure."""
    url = f"{CW_BASE}{path}"
    last_err = None
    for attempt in range(retries):
        headers = _get_session_headers()
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt < retries - 1:
                log.warning("401 on %s %s (attempt %d), re-login & retry",
                            method, path, attempt + 1)
                CW_AUTH_FILE.unlink(missing_ok=True) if CW_AUTH_FILE.exists() else None
                continue
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"CW API error {e.code} on {method} {path}: {body_text}")
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                log.warning("Retry %d on %s %s: %s", attempt + 1, method, path, e)
                continue
            raise RuntimeError(f"CW API error on {method} {path}: {last_err}")
    raise RuntimeError(f"Exhausted {retries} retries on {method} {path}: {last_err}")


def _call_internal(method: str, path: str, body: Optional[dict] = None,
                   extra_headers: Optional[dict] = None,
                   retries: int = 3) -> dict:
    """Call Chatwoot Platform API (internal, with api_access_token).
    Returns parsed JSON dict. Raises RuntimeError on failure."""
    url = f"{CW_INTERNAL}{path}"
    for attempt in range(retries):
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if attempt < retries - 1:
                log.warning("Internal API error %s on %s %s, retry %d",
                            e.code, method, path, attempt + 1)
                continue
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"Internal API error {e.code} on {method} {path}: {body_text}")
        except Exception as e:
            if attempt < retries - 1:
                log.warning("Internal retry %d on %s %s: %s", attempt + 1, method, path, e)
                continue
            raise RuntimeError(f"Internal API error on {method} {path}: {e}")
    raise RuntimeError(f"Exhausted {retries} retries on internal {method} {path}")


# ====================================================================
#  SHORTCUTS
# ====================================================================

def get_profile() -> Optional[dict]:
    """Fetch /api/v1/profile to get current user info."""
    try:
        return _call_cw("GET", "/api/v1/profile")
    except RuntimeError as e:
        log.error("Profile fetch failed: %s", e)
        return None


# ====================================================================
#  CLI  (for quick testing)
# ====================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chatwoot API Client CLI")
    parser.add_argument("--renew", action="store_true", help="Force renew session")
    parser.add_argument("--profile", action="store_true", help="Get current user profile")
    parser.add_argument("--call", nargs=3, metavar=("METHOD", "PATH", "BODY"),
                        help="Make an API call (body is JSON string or '-')")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    if args.renew:
        data = renew_session()
        if data:
            print(f"Session renewed: {data['uid']} (expiry={data['expiry']})")
        else:
            print("Session renewal failed", file=sys.stderr)
            sys.exit(1)

    if args.profile:
        profile = get_profile()
        if profile:
            print(json.dumps(profile, ensure_ascii=False, indent=2))
        else:
            print("Profile fetch failed", file=sys.stderr)
            sys.exit(1)

    if args.call:
        method, path, body_str = args.call
        body = json.loads(str(body_str)) if body_str and body_str != "-" else None
        try:
            result = _call_cw(method, path, body=body)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except RuntimeError as e:
            print(f"API call failed: {e}", file=sys.stderr)
            sys.exit(1)
