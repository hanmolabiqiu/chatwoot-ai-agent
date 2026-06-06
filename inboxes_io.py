#!/usr/bin/env python3
"""
Unified Inboxes Config IO — shared by WS Agent & Provision Server

Provides stateless read/write/validate/construct primitives for
Chatwoot inbox routing configuration (inboxes.json).

Usage:
    import inboxes_io
    cfg = inboxes_io.read_inboxes_raw(Path("inboxes.json"))
    entry = inboxes_io.build_inbox_entry(...)
    inboxes_io.write_inboxes(Path("inboxes.json"), cfg)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("inboxes_io")

# ── Default _meta block ──────────────────────────────────────────
INBOXES_META = {
    "_meta": {
        "version": "1.2",
        "updated_at": None,  # filled at write time
        "description": "Chatwoot WS Agent inbox routing config — hot-reloadable",
    },
}

# ── Required field sets ──────────────────────────────────────────
REQUIRED_ENTRY_KEYS = ["name", "target_agent", "system_prompt", "prompt_template"]
TEMPLATE_PLACEHOLDERS = ["{sender_name}", "{customer_msg}"]


def validate_entry(config: dict) -> bool:
    """Validate a single inbox config entry.

    Checks required keys exist and prompt_template contains
    the mandatory placeholders.
    """
    if not isinstance(config, dict):
        log.warning("Config is not a dict: %s", type(config).__name__)
        return False
    for key in REQUIRED_ENTRY_KEYS:
        if key not in config:
            log.warning("Config missing required key '%s'", key)
            return False
    prompt = config.get("prompt_template", "")
    for ph in TEMPLATE_PLACEHOLDERS:
        if ph not in prompt:
            log.warning("prompt_template missing placeholder %s", ph)
            return False
    return True


def read_inboxes_raw(path: Path) -> dict:
    """Read inboxes.json from *path*.

    Returns the parsed dict, or a dict with just ``_meta`` if the
    file is missing.  Never returns ``None``.
    """
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to read %s: %s", path, e)
    meta = dict(INBOXES_META)
    meta["_meta"] = dict(meta["_meta"])
    meta["_meta"]["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return meta


def write_inboxes(path: Path, config: dict) -> None:
    """Write *config* (dict) to *path* as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Always refresh _meta timestamp
    if "_meta" not in config or not isinstance(config["_meta"], dict):
        config["_meta"] = dict(INBOXES_META["_meta"])
    config["_meta"]["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Inboxes config written to %s", path)


def ensure_agent_workspace(base_dir: Path, agent_id: str, name: str = "") -> Path:
    """Create workspace directory for a QwenPaw agent.

    Returns the created Path.
    """
    agent_dir = base_dir / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir


def build_inbox_entry(name: str, domain: str, channel: str,
                      inbox_id: int, inbox_token: str, agent_id: str) -> dict:
    """Build an inbox config entry dict for *inboxes.json*.

    The entry includes a generic system_prompt and prompt_template
    that callers can override after receiving the dict.
    """
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
