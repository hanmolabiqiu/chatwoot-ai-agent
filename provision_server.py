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
import threading
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bottle

# ── Shared modules (same repo) ───────────────────────────────────
# provision_server.py is in chatwoot-ai-agent/, so sibling import works
import chatwoot_client
import inboxes_io

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

# Point chatwoot_client at the same auth file
chatwoot_client.CW_AUTH_FILE = SCRIPT_DIR / "chatwoot_auth.json"
# Enable CW_ADMIN_EMAIL/PASSWORD env var reading (chatwoot_client reads both CW_EMAIL and CW_ADMIN_EMAIL)
chatwoot_client.CW_BASE = os.environ.get("CW_BASE", "http://localhost:3000")
chatwoot_client.CW_INTERNAL = os.environ.get("CW_INTERNAL", "http://chatwoot-chatwoot-1:3000")
chatwoot_client.CW_ACCOUNT_ID = int(os.environ.get("CW_ACCOUNT_ID", "1"))
chatwoot_client.CW_PLATFORM_TOKEN = os.environ.get("CW_PLATFORM_TOKEN", "")

# API key for provision/suspend/activate endpoints
CHATHUB_API_KEY = os.environ.get("CHATHUB_API_KEY", "chathub-default-key-change-me")


def _check_api_key():
    """Verify X-API-Key header matches CHATHUB_API_KEY."""
    key = bottle.request.get_header("X-API-Key", "")
    if key != CHATHUB_API_KEY:
        bottle.response.status = 401
        return json.dumps({"error": "Invalid or missing X-API-Key"})


def _create_agent(email: str, name: str = "") -> dict:
    """Create a Chatwoot user + agent. Returns {agent_cw_id, password}.
    Rolls back (deletes user) if agent creation fails."""
    password = chatwoot_client._gen_password()
    display_name = name or email.split("@")[0]

    user = chatwoot_client._call_internal(
        "POST",
        "/platform/api/v1/users",
        {"name": display_name, "email": email, "password": password},
        extra_headers={"api_access_token": chatwoot_client.CW_PLATFORM_TOKEN},
    )
    if not user.get("id"):
        raise RuntimeError(f"Platform API user creation failed: {user}")
    uid = user["id"]

    try:
        agent = chatwoot_client._call_cw(
            "POST",
            f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/agents",
            {"email": email, "name": display_name, "role": "agent"},
        )
    except Exception as e:
        # Rollback: delete the orphaned platform user
        try:
            chatwoot_client._call_internal(
                "DELETE",
                f"/platform/api/v1/users/{uid}",
                None,
                extra_headers={"api_access_token": chatwoot_client.CW_PLATFORM_TOKEN},
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
        chatwoot_client._call_cw(
            "POST",
            f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/teams/{team_id}/team_members",
            {"user_ids": [agent_cw_id]},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log.warning("add_agent_to_team failed: agent=%s team=%s err=%s %s", agent_cw_id, team_id, e.code, body)
    except Exception as e:
        log.warning("add_agent_to_team failed: agent=%s team=%s err=%s", agent_cw_id, team_id, e)


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
        team = chatwoot_client._call_cw(
            "POST",
            f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/teams",
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
        inbox = chatwoot_client._call_cw(
            "POST",
            f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/inboxes",
            inbox_payload,
        )

        inbox_id = inbox.get("id")
        inbox_token = inbox.get("access_token", "")
        inbox_name = inbox.get("name", name)
        website_token = inbox.get("website_token", "") or inbox.get("access_token", "")
        _emb_cw_base = chatwoot_client.CW_BASE
        embed_code = (
            f"<script>\n"
            f"  (function(d,t) {{\n"
            f"    var g=d.createElement(t),s=d.getElementsByTagName(t)[0];\n"
            f'    g.src="{_emb_cw_base}/packs/js/sdk.js";\n'
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
            f'        baseUrl:"{_emb_cw_base}"\n'
            f"      }});\n"
            f"    }};\n"
            f"  }})(document,\"script\");\n"
            f"</script>"
        )

        # 5. Create agent workspace
        if not agent_id:
            agent_id = f"chathub-{inbox_id}"
        agent_dir = inboxes_io.ensure_agent_workspace(WORKSPACE_DIR, agent_id, name)

        # 6. Update inboxes.json
        config = inboxes_io.read_inboxes_raw(INBOXES_PATH)
        entry = inboxes_io.build_inbox_entry(name, domain, channel, inbox_id, inbox_token, agent_id)
        config[str(inbox_id)] = entry
        config.setdefault("_meta", {})["updated_at"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        inboxes_io.write_inboxes(INBOXES_PATH, config)

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
    chatwoot_client._call_cw(
        "PUT",
        f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/inboxes/{inbox_id}",
        {
            "enable_auto_assignment": False,
            "name": f"[Suspended] Inbox #{inbox_id}",
        },
    )
    # Also clear channel website_url if web_widget
    try:
        inbox = chatwoot_client._call_cw("GET", f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/inboxes/{inbox_id}")
        ch = inbox.get("channel", {})
        if ch.get("type") == "Channel::WebWidget":
            chatwoot_client._call_cw(
                "PUT",
                f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/inboxes/{inbox_id}",
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
    config = inboxes_io.read_inboxes_raw(INBOXES_PATH)
    key = str(inbox_id)
    if key in config:
        config[key]["status"] = status
        config.setdefault("_meta", {})["updated_at"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        inboxes_io.write_inboxes(INBOXES_PATH, config)


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
        chatwoot_client._call_cw(
            "PUT",
            f"/api/v1/accounts/{chatwoot_client.CW_ACCOUNT_ID}/inboxes/{inbox_id}",
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
