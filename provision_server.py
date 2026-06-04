#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ChatHub Provision HTTP Service.

Called by FastAdmin PHP to provision a tenant:
  → creates Chatwoot team + inbox + agent account
  → writes inboxes.json (WS Agent hot-reloads within 30s)
  → creates QwenPaw agent workspace
Returns JSON for PHP to save to chathub_tenant table.
"""

import json
import logging
import os
import secrets
import threading
import string
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bottle

# ── logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("provision")

# ── paths (all inside QwenPaw container) ──────────────────────────
WORKSPACE_DIR = Path("/app/working/workspaces")
SCRIPT_DIR = WORKSPACE_DIR / "wordpress" / "skills" / "wordpress-cli"
INBOXES_PATH = SCRIPT_DIR / "inboxes.json"
AUTH_FILE = SCRIPT_DIR / "chatwoot_auth.json"

# Chatwoot base config
CW_BASE = os.environ.get("CW_BASE", "http://localhost:3000")
CW_INTERNAL = os.environ.get("CW_INTERNAL", "http://chatwoot-chatwoot-1:3000")
CW_ACCOUNT_ID = int(os.environ.get("CW_ACCOUNT_ID", "1"))
CW_PLATFORM_TOKEN = os.environ.get("CW_PLATFORM_TOKEN", "")
# API key for provision/suspend/activate endpoints
CHATHUB_API_KEY = os.environ.get("CHATHUB_API_KEY", "chathub-default-key-change-me")


def _gen_password(length: int = 14) -> str:
    chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-='
    return ''.join(secrets.choice(chars) for _ in range(length))


def _relogin_chatwoot() -> dict:
    email = os.environ.get("CW_ADMIN_EMAIL")
    password = os.environ.get("CW_ADMIN_PASSWORD")
    if not email:
        raise RuntimeError("CW_ADMIN_EMAIL not set — cannot login")
    if not password:
        raise RuntimeError("CW_ADMIN_PASSWORD not set — cannot login")
    url = f"{CW_BASE}/auth/sign_in"
    payload = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=15)
    headers = {k.lower(): v for k, v in resp.headers.items()}
    data = {
        "access-token": headers.get("access-token", ""),
        "client": headers.get("client", ""),
        "expiry": headers.get("expiry", ""),
        "uid": headers.get("uid", ""),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Chatwoot session refreshed for %s", data["uid"])
    return {
        "access-token": data["access-token"],
        "client": data["client"],
        "expiry": data["expiry"],
        "uid": data["uid"],
        "Content-Type": "application/json",
    }


def _get_session_headers() -> dict:
    """Load session from file, auto-renew if expired or missing."""
    import time as _t
    if AUTH_FILE.exists():
        data = json.loads(AUTH_FILE.read_text())
        expiry = int(data.get("expiry", 0))
        if expiry - _t.time() < 3600:
            log.info("Session < 1h (%ds left), renewing", expiry - int(_t.time()))
            return _relogin_chatwoot()
        if all([data.get("access-token"), data.get("client"), data.get("uid")]):
            return {
                "access-token": data["access-token"],
                "client": data["client"],
                "expiry": data["expiry"],
                "uid": data["uid"],
                "Content-Type": "application/json",
            }
    return _relogin_chatwoot()


def _call_cw(method: str, path: str, body: Optional[dict], retries: int = 3) -> dict:
    """Call Chatwoot API with retry on 401 (auto-renew session)."""
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
                log.warning(f"401 on {method} {path} (attempt {attempt+1}), re-login & retry")
                AUTH_FILE.unlink(missing_ok=True)
                continue
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"CW API error {e.code} on {method} {path}: {body_text}")
    raise RuntimeError(f"Exhausted {retries} retries on {method} {path}: {last_err}")


def _call_internal(method: str, path: str,
                    body: Optional[dict],
                    extra_headers: Optional[dict] = None,
                    retries: int = 3) -> dict:
    """Call Chatwoot internal (platform) API with retry."""
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
                log.warning(f"Internal API error {e.code} on {method} {path}, retry {attempt+1}")
                continue
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"Internal API error {e.code} on {method} {path}: {body_text}")
    raise RuntimeError(f"Exhausted {retries} retries on internal {method} {path}")


def _check_api_key():
    """Verify X-API-Key header matches CHATHUB_API_KEY."""
    key = bottle.request.get_header("X-API-Key", "")
    if key != CHATHUB_API_KEY:
        bottle.response.status = 401
        return json.dumps({"error": "Invalid or missing X-API-Key"})


def _create_agent(email: str, name: str = "") -> dict:
    """Create a Chatwoot user + agent. Returns {agent_cw_id, password}.
    Rolls back (deletes user) if agent creation fails."""
    password = _gen_password()
    display_name = name or email.split("@")[0]

    user = _call_internal(
        "POST",
        "/platform/api/v1/users",
        {"name": display_name, "email": email, "password": password},
        extra_headers={"api_access_token": CW_PLATFORM_TOKEN},
    )
    if not user.get("id"):
        raise RuntimeError(f"Platform API user creation failed: {user}")
    uid = user["id"]

    try:
        agent = _call_cw(
            "POST",
            f"/api/v1/accounts/{CW_ACCOUNT_ID}/agents",
            {"email": email, "name": display_name, "role": "agent"},
        )
    except Exception as e:
        # Rollback: delete the orphaned platform user
        try:
            _call_internal(
                "DELETE",
                f"/platform/api/v1/users/{uid}",
                None,
                extra_headers={"api_access_token": CW_PLATFORM_TOKEN},
            )
        except Exception:
            pass
        raise RuntimeError(f"Agent creation failed, rolled back user {uid}: {e}")

    if not agent.get("id"):
        raise RuntimeError(f"Agent creation failed: {agent}")

    return {"agent_cw_id": agent["id"], "password": password}


def _add_agent_to_team(agent_cw_id: int, team_id: int) -> None:
    """Assign agent to team."""
    try:
        _call_cw(
            "POST",
            f"/api/v1/accounts/{CW_ACCOUNT_ID}/teams/{team_id}/team_members",
            {"user_ids": [agent_cw_id]},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log.warning("add_agent_to_team failed: agent=%s team=%s err=%s %s", agent_cw_id, team_id, e.code, body)
    except Exception as e:
        log.warning("add_agent_to_team failed: agent=%s team=%s err=%s", agent_cw_id, team_id, e)


def _read_inboxes() -> dict:
    if INBOXES_PATH.exists():
        return json.loads(INBOXES_PATH.read_text(encoding="utf-8"))
    return {
        "_meta": {
            "version": "1.1",
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": "Chatwoot WS Agent inbox routing config \u2014 hot-reloadable",
        },
    }


def _write_inboxes(config: dict) -> None:
    INBOXES_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOXES_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ensure_agent_workspace(agent_id: str, name: str) -> Path:
    agent_dir = WORKSPACE_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir


def _build_inbox_entry(name: str, domain: str, channel: str,
                       inbox_id: int, inbox_token: str, agent_id: str) -> dict:
    return {
        "name": name,
        "type": channel,
        "target_agent": agent_id,
        "system_prompt": (
            f"You are a customer service agent for {name} ({domain}). "
            f"Answer questions professionally in the customer's language. "
            f"If you cannot fully resolve the issue, end with [HANDOFF]."
        ),
        "prompt_template": (
            "Customer '{sender_name}' sent this message:\n\n"
            "{customer_msg}\n\n"
            "Write a direct reply (no preamble, no markdown). "
            "Keep it concise (2-4 sentences). "
            "Use the same language as the customer."
        ),
        "note_prefix": f"\U0001f916 AI \u81ea\u52a8\u56de\u590d ({name})",
        "signature": "",
        "status": "active",
    }


# ── Idempotency store ────────────────────────────────────────────
# Stores {key: response_dict} with 5-minute TTL.
_IDEMPOTENT_RESULTS: dict[str, dict] = {}
_IDEMPOTENT_LOCK = threading.Lock()
_IDEMPOTENT_TTL = 300


def _check_idempotency(key: str) -> Optional[dict]:
    """Return cached result if key was already processed, else None."""
    if not key:
        return None
    with _IDEMPOTENT_LOCK:
        if key in _IDEMPOTENT_RESULTS:
            log.info("Idempotent request %s, returning cached result", key)
            cached = _IDEMPOTENT_RESULTS[key]
            # Restore HTTP status from cached entry
            status = cached.pop("_http_status", 200)
            bottle.response.status = status
            return cached
        return None


def _store_idempotency(key: str, response: dict, status: int = 200) -> None:
    """Store the response for an idempotency key (thread-safe, auto-expire).

    Args:
        key: Idempotency-Key header value.
        response: The JSON response dict to cache.
        status: HTTP status code to restore on cache hit.
    """
    if not key:
        return
    with _IDEMPOTENT_LOCK:
        if key not in _IDEMPOTENT_RESULTS:
            entry = dict(response)
            entry["_http_status"] = status
            _IDEMPOTENT_RESULTS[key] = entry
            # Schedule cleanup after TTL
            threading.Timer(_IDEMPOTENT_TTL, lambda: _IDEMPOTENT_RESULTS.pop(key, None)).start()


# ── Provision endpoint ────────────────────────────────────────────

@bottle.post("/provision")
def provision():
    result = None
    idempotency_key = bottle.request.get_header("Idempotency-Key", "")

    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    try:
        data = bottle.request.json
    except Exception:
        bottle.response.status = 400
        return {"error": "invalid JSON body"}

    name = (data or {}).get("name", "").strip()
    domain = (data or {}).get("domain", "").strip()
    email = (data or {}).get("email", "").strip()
    channel = (data or {}).get("type", "web_widget")
    agent_id = (data or {}).get("agent_id", "")
    max_agents = int((data or {}).get("max_agents", 3))

    # Input validation (stateless — always deterministic, no need to cache)
    if not name:
        bottle.response.status = 400
        return {"error": "name is required"}
    if len(name) > 100:
        bottle.response.status = 400
        return {"error": "name too long (max 100 chars)"}
    if not domain:
        bottle.response.status = 400
        return {"error": "domain is required"}
    if len(domain) > 255:
        bottle.response.status = 400
        return {"error": "domain too long (max 255 chars)"}
    if not email or "@" not in email or len(email) > 255:
        bottle.response.status = 400
        return {"error": "valid email is required"}
    if channel not in ("web_widget", "api"):
        bottle.response.status = 400
        return {"error": "type must be 'web_widget' or 'api'"}

    # Idempotency check (after validation, so only provisioning results get cached)
    cached = _check_idempotency(idempotency_key)
    if cached:
        return cached

    # ── Provisioning (non-idempotent, stateful operations) ──────
    try:
        # 1. Create Chatwoot agent (Platform API + Agents API)
        agent_info = _create_agent(email, name)

        # 2. Create team
        team = _call_cw(
            "POST",
            f"/api/v1/accounts/{CW_ACCOUNT_ID}/teams",
            {
                "name": f"{name} 客服团队",
                "description": f"{name} 的专属客服团队（限制 {max_agents} 席）",
            },
        )
        team_id = team.get("id")

        # 3. Assign agent to team
        _add_agent_to_team(agent_info["agent_cw_id"], team_id)

        # 4. Create inbox
        inbox_payload = {
            "name": name,
            "channel": {
                "type": channel,
                "website_url": domain if channel == "web_widget" else "",
                "widget_color": "#6366f1",
                "welcome_title": f"欢迎来到 {name}",
                "welcome_tagline": f"您好！欢迎访问 {name}，请问有什么可以帮您？",
            },
        }
        inbox = _call_cw(
            "POST",
            f"/api/v1/accounts/{CW_ACCOUNT_ID}/inboxes",
            inbox_payload,
        )

        inbox_id = inbox.get("id")
        inbox_token = inbox.get("access_token", "")
        inbox_name = inbox.get("name", name)
        website_token = inbox.get("website_token", "") or inbox.get("access_token", "")
        embed_code = (
            f"<script>\n"
            f"  (function(d,t) {{\n"
            f"    var g=d.createElement(t),s=d.getElementsByTagName(t)[0];\n"
            f'    g.src="{CW_BASE}/packs/js/sdk.js";\n'
            f"    g.defer=1;g.async=1;\n"
            f"    s.parentNode.insertBefore(g,s);\n"
            f"    g.onload=function(){{\n"
            f"      window.chatwootSettings={{\n"
            f'        position:"right",\n'
            f'        type:"standard",\n'
            f'        launcherTitle:"Chat"\n'
            f"      }};\n"
            f"      window.chatwootSDK.run({{\n"
            f'        websiteToken:"{website_token}",\n'
            f'        baseUrl:"{CW_BASE}"\n'
            f"      }});\n"
            f"    }};\n"
            f"  }})(document,\"script\");\n"
            f"</script>"
        )

        # 5. Create agent workspace
        if not agent_id:
            agent_id = f"chathub-{inbox_id}"
        agent_dir = _ensure_agent_workspace(agent_id, name)

        # 6. Update inboxes.json
        config = _read_inboxes()
        entry = _build_inbox_entry(name, domain, channel, inbox_id, inbox_token, agent_id)
        config[str(inbox_id)] = entry
        config.setdefault("_meta", {})["updated_at"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        _write_inboxes(config)

        result = {
            "inbox_id": inbox_id,
            "inbox_token": inbox_token,
            "inbox_name": inbox_name,
            "team_id": team_id,
            "team_name": f"{name} 客服团队",
            "agent_id": agent_id,
            "agent_cw_id": agent_info["agent_cw_id"],
            "agent_cw_password": agent_info["password"],
            "agent_dir": str(agent_dir),
            "embed_code": embed_code,
            "ws_agent_updated": True,
        }

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        bottle.response.status = 502
        result = {"error": f"Chatwoot API error: {e.code}", "detail": body}
    except urllib.error.URLError as e:
        bottle.response.status = 502
        result = {"error": f"Chatwoot network error: {e.reason}"}
    except Exception as e:
        bottle.response.status = 500
        result = {"error": str(e)}

    # Store idempotency result (both success and failure)
    _store_idempotency(idempotency_key, result if result else {"error": "unknown"}, bottle.response.status_code)
    return result


@bottle.get("/health")
def health():
    return {"status": "ok"}


# ── Suspend endpoint ─────────────────────────────────────────────

def _disable_inbox(inbox_id: int) -> None:
    """Disable Chatwoot inbox: rename, clear website_url, disable auto-assignment."""
    _call_cw(
        "PUT",
        f"/api/v1/accounts/{CW_ACCOUNT_ID}/inboxes/{inbox_id}",
        {
            "enable_auto_assignment": False,
            "name": f"[Suspended] Inbox #{inbox_id}",
        },
    )
    # Also clear channel website_url if web_widget
    try:
        inbox = _call_cw("GET", f"/api/v1/accounts/{CW_ACCOUNT_ID}/inboxes/{inbox_id}")
        ch = inbox.get("channel", {})
        if ch.get("type") == "Channel::WebWidget":
            _call_cw(
                "PUT",
                f"/api/v1/accounts/{CW_ACCOUNT_ID}/inboxes/{inbox_id}",
                {
                    "channel": {
                        "website_url": "",
                        "welcome_title": "Service Suspended",
                        "welcome_tagline": "This chat service has been suspended.",
                    }
                },
            )
    except Exception as e:
        log.warning("Failed to clear inbox %d channel settings: %s", inbox_id, e)


def _update_inbox_status(inbox_id: int, status: str) -> None:
    """Update inboxes.json entry status."""
    config = _read_inboxes()
    key = str(inbox_id)
    if key in config:
        config[key]["status"] = status
        config.setdefault("_meta", {})["updated_at"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        _write_inboxes(config)


@bottle.post("/suspend")
def suspend():
    """Suspend a tenant: disable Chatwoot inbox + mark inboxes.json as suspended."""
    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    try:
        data = bottle.request.json
    except Exception:
        bottle.response.status = 400
        return {"error": "invalid JSON body"}

    inbox_id = (data or {}).get("inbox_id")
    if not inbox_id:
        bottle.response.status = 400
        return {"error": "inbox_id is required"}

    try:
        # 1. Disable Chatwoot inbox
        _disable_inbox(int(inbox_id))

        # 2. Mark inboxes.json as suspended
        _update_inbox_status(int(inbox_id), "suspended")

        return {"success": True, "message": f"Inbox {inbox_id} suspended"}

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        bottle.response.status = 502
        return {"error": f"Chatwoot API error: {e.code}", "detail": body}
    except Exception as e:
        bottle.response.status = 500
        return {"error": str(e)}


@bottle.post("/activate")
def activate():
    """Re-activate a suspended tenant: re-enable inbox + mark active."""
    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    try:
        data = bottle.request.json
    except Exception:
        bottle.response.status = 400
        return {"error": "invalid JSON body"}

    inbox_id = (data or {}).get("inbox_id")
    if not inbox_id:
        bottle.response.status = 400
        return {"error": "inbox_id is required"}

    try:
        _call_cw(
            "PUT",
            f"/api/v1/accounts/{CW_ACCOUNT_ID}/inboxes/{inbox_id}",
            {"enable_auto_assignment": True},
        )
        _update_inbox_status(int(inbox_id), "active")

        return {"success": True, "message": f"Inbox {inbox_id} activated"}

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        bottle.response.status = 502
        return {"error": f"Chatwoot API error: {e.code}", "detail": body}
    except Exception as e:
        bottle.response.status = 500
        return {"error": str(e)}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5566
    log.info("Starting ChatHub Provision Server on port %d (threaded)", port)
    bottle.run(host="0.0.0.0", port=port, debug=False, server="wsgiref", num_threads=4)
