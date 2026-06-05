#!/usr/bin/env python3
"""
Chatwoot WebSocket Agent — Real-time AI Auto-Reply with Human Handoff
=======================================================================
Connects to Chatwoot ActionCable WebSocket for instant message delivery,
generates AI replies, and sends Chinese private notes.

Features:
  - Real-time AI auto-reply to customer messages
  - Human handoff: detects human agent replies and backs off
  - AI-initiated handoff: AI suggests human intervention when needed
  - Timeout recovery: AI resumes after human inactivity (configurable)
  - Status-based recovery: AI resumes when conversation is resolved/pending

Usage:
  python3 chatwoot_ws_agent.py                    # Run (daemon mode)
  python3 chatwoot_ws_agent.py --renew            # Force renew session & exit
  python3 chatwoot_ws_agent.py --test-ws          # Test WebSocket connection & exit

Requirements:
  pip install websocket-client
"""

import os, sys, json, time, subprocess, argparse, ssl, signal
import requests
import websocket
from pathlib import Path
from datetime import datetime, timezone, timedelta
from threading import Thread, Event, Lock
from collections import defaultdict

# ===== CONFIG =====
CW_BASE = os.environ.get("CW_BASE", "http://localhost:3000")
CW_WS_URL = CW_BASE.replace("https://", "wss://").replace("http://", "ws://") + "/cable"
CW_ACCOUNT_ID = 1
CW_AUTH_URL = f"{CW_BASE}/auth/sign_in"
CW_API_BASE = f"{CW_BASE}/api/v1/accounts/{CW_ACCOUNT_ID}"

SCRIPT_DIR = Path(__file__).parent
AUTH_FILE = SCRIPT_DIR / "chatwoot_auth.json"
PROCESSED_FILE = SCRIPT_DIR / ".chatwoot_ws_processed.json"
METRICS_FILE = SCRIPT_DIR / ".chatwoot_ws_metrics.json"
STATE_FILE = SCRIPT_DIR / ".chatwoot_ws_state.json"

# ===== INBOX ROUTING CONFIG (hot-reloadable from inboxes.json) =====
INBOX_CONFIG_FILE = Path(os.environ.get(
    "INBOX_CONFIG_FILE",
    str(Path(__file__).parent / "inboxes.json")
))
INBOX_CONFIG = {}
_INBOX_CONFIG_MTIME = 0

# Default fallback config (hardcoded for demo sites)
DEFAULT_INBOX_CONFIG = {
    1: {
        "name": "GreatQiu",
        "type": "web_widget",
        "target_agent": "sourcing-agent",
        "system_prompt": "You are a professional China sourcing agent from GreatQiu (based in Shaoxing, Zhejiang, China). You help international clients with product sourcing, supplier verification, quality control, logistics, and supply chain management.\n\nIMPORTANT - Decide if you can fully handle this or need a human:\n- If the customer asks about specific PRICING, MOQ, PLACING ORDERS, CUSTOMIZATION, SHIPPING QUOTES, or COMPLEX TECHNICAL SPECS that require real-time data from suppliers → end your reply with [HANDOFF] on a new line.\n- If you can answer the question fully using your general knowledge (company info, services, processes, general timelines) → do NOT add [HANDOFF].",
        "prompt_template": "A customer named '{sender_name}' sent this message:\n\n{customer_msg}\n\nWrite a direct reply (no preamble, no markdown). Keep it concise (2-4 sentences). Use the same language as the customer. Always sign with '- GreatQiu Team'.",
        "note_prefix": "🤖 AI 自动回复 (GreatQiu)",
        "signature": "- GreatQiu Team",
        "status": "active"
    },
    7: {
        "name": "HALO Blog",
        "type": "web_widget",
        "target_agent": "halo-blog-agent",
        "system_prompt": "你是一名专业的安防弱电与IT基础设施技术顾问，来自Q师傅知识库。你帮助客户解答关于交换机配置、监控系统、网络布线、弱电工程、服务器运维等技术问题。\n\n重要 - 判断是否需要人工介入：\n- 如果客户询问具体的项目报价、施工方案定制、现场勘查需求、或需要实际采购产品 → 在回复末尾加一行 [HANDOFF]。\n- 如果是回答一般性的技术问题（设备参数、配置方法、故障排查思路等）→ 不加 [HANDOFF]。",
        "prompt_template": "客户 '{sender_name}' 发送了以下消息：\n\n{customer_msg}\n\n请用中文直接回复（不要前缀，不要Markdown）。保持简洁（2-4句话）。回复语气专业友善，体现技术专家的可靠性。以'- Q师傅知识库'署名。",
        "note_prefix": "🤖 AI 自动回复 (Q师傅知识库)",
        "signature": "- Q师傅知识库",
        "status": "active"
    }
}

def _validate_config(config):
    """Validate inbox config structure and required placeholders."""
    required_keys = ["name", "target_agent", "system_prompt", "prompt_template"]
    template_placeholders = ["{sender_name}", "{customer_msg}"]
    if not isinstance(config, dict):
        return False
    for key in required_keys:
        if key not in config:
            log(f"Config missing required key '{key}'", "WARN")
            return False
    for ph in template_placeholders:
        if ph not in config.get("prompt_template", ""):
            log(f"prompt_template missing placeholder {ph}", "WARN")
            return False
    return True

def _load_inboxes_config():
    """Load inbox config from JSON file. Falls back to DEFAULT_INBOX_CONFIG if file missing."""
    global INBOX_CONFIG, _INBOX_CONFIG_MTIME
    try:
        if not INBOX_CONFIG_FILE.exists():
            if not INBOX_CONFIG:  # Only log on first load
                log(f"inboxes.json not found: {INBOX_CONFIG_FILE}, using default config", "WARN")
                INBOX_CONFIG = DEFAULT_INBOX_CONFIG.copy()
                log(f"Default config loaded: {list(INBOX_CONFIG.keys())}")
            return
        mtime = INBOX_CONFIG_FILE.stat().st_mtime
        if mtime <= _INBOX_CONFIG_MTIME:
            return  # no change
        raw = json.loads(INBOX_CONFIG_FILE.read_text())
        new_cfg = {}
        for k, v in raw.items():
            if k.startswith("_"):
                continue  # skip _meta etc.
            try:
                inbox_id = int(k)
                if _validate_config(v):
                    new_cfg[inbox_id] = v
                else:
                    log(f"Invalid config for inbox #{k}, skipping", "WARN")
            except (ValueError, TypeError):
                continue
        
        # Detect changes
        old_keys = set(INBOX_CONFIG.keys()) if INBOX_CONFIG else set()
        new_keys = set(new_cfg.keys())
        added = new_keys - old_keys
        removed = old_keys - new_keys
        changed = {k for k in old_keys & new_keys if INBOX_CONFIG.get(k) != new_cfg.get(k)}
        
        if added or removed or changed:
            log(f"📋 Config changes detected:", "INFO")
            if added:
                log(f"   ➕ Added: {[new_cfg[k]['name'] for k in added]}", "INFO")
            if removed:
                log(f"   ➖ Removed: {[INBOX_CONFIG[k]['name'] for k in removed]}", "INFO")
            if changed:
                log(f"   🔄 Changed: {[new_cfg[k]['name'] for k in changed]}", "INFO")
        
        INBOX_CONFIG = new_cfg
        _INBOX_CONFIG_MTIME = mtime
        log(f"Inboxes config loaded: {list(INBOX_CONFIG.keys())} (mtime={mtime})")
    except Exception as e:
        log(f"Failed to load inboxes.json: {e}, using default config", "ERROR")
        if not INBOX_CONFIG:
            INBOX_CONFIG = DEFAULT_INBOX_CONFIG.copy()

# Login credentials for auto-renewal
CW_EMAIL = os.environ.get("CW_EMAIL")
CW_PASSWORD = os.environ.get("CW_PASSWORD")
# Agent identity (from /api/v1/profile response)


RENEW_THRESHOLD = timedelta(hours=6)
TZ = timezone(timedelta(hours=8))

# ===== HUMAN HANDOFF CONFIG =====
# If a human agent has replied in this conversation but hasn't replied
# for HUMAN_TIMEOUT_MINUTES, the AI resumes auto-replying.
HUMAN_TIMEOUT_MINUTES = 15

# ===== LOGGING =====

def log(msg, level="INFO", inbox_name=None):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{inbox_name}] " if inbox_name else ""
    print(f"[{ts}] [{level}] {prefix}{msg}", flush=True)

# ===== MONITORING & METRICS =====

class Metrics:
    """Track performance metrics per inbox. Saves to disk every 30s to avoid hot-path I/O."""
    
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.lock = Lock()
        self.data = self._load()
        self._dirty = False
    
    def _load(self):
        if self.filepath.exists():
            try:
                return json.loads(self.filepath.read_text())
            except:
                pass
        return {
            "started_at": datetime.now(TZ).isoformat(),
            "ws_connected": False,
            "ws_disconnects": 0,
            "ws_last_disconnect": None,
            "inboxes": {}
        }
    
    def _save(self):
        """Write to disk only if dirty."""
        if not self._dirty:
            return
        try:
            self.filepath.write_text(json.dumps(self.data, indent=2))
            self._dirty = False
        except Exception as e:
            log(f"Failed to save metrics: {e}", "WARN")
    
    def flush(self):
        """Force write to disk (called on SIGTERM / periodic flush)."""
        with self.lock:
            self._save()
    
    def ws_connected(self):
        with self.lock:
            self.data["ws_connected"] = True
            self._dirty = True
    
    def ws_disconnected(self, reason="unknown"):
        with self.lock:
            self.data["ws_connected"] = False
            self.data["ws_disconnects"] += 1
            self.data["ws_last_disconnect"] = {
                "time": datetime.now(TZ).isoformat(),
                "reason": reason
            }
            self._dirty = True
        log(f"⚠️ WebSocket disconnected: {reason}", "WARN")
    
    def record_reply(self, inbox_id, inbox_name, success, duration_ms):
        with self.lock:
            inbox_key = str(inbox_id)
            if inbox_key not in self.data["inboxes"]:
                self.data["inboxes"][inbox_key] = {
                    "name": inbox_name,
                    "total_requests": 0,
                    "success": 0,
                    "failed": 0,
                    "total_duration_ms": 0,
                    "avg_duration_ms": 0,
                    "last_reply": None
                }
            
            inbox = self.data["inboxes"][inbox_key]
            inbox["total_requests"] += 1
            if success:
                inbox["success"] += 1
            else:
                inbox["failed"] += 1
            inbox["total_duration_ms"] += duration_ms
            inbox["avg_duration_ms"] = inbox["total_duration_ms"] / inbox["total_requests"]
            inbox["last_reply"] = datetime.now(TZ).isoformat()
            self._dirty = True
    
    def get_summary(self):
        with self.lock:
            summary = {
                "uptime_since": self.data["started_at"],
                "ws_connected": self.data["ws_connected"],
                "ws_disconnects": self.data["ws_disconnects"],
                "ws_last_disconnect": self.data["ws_last_disconnect"],
                "inboxes": {}
            }
            for inbox_id, stats in self.data["inboxes"].items():
                success_rate = (stats["success"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0
                summary["inboxes"][inbox_id] = {
                    "name": stats["name"],
                    "total": stats["total_requests"],
                    "success": stats["success"],
                    "failed": stats["failed"],
                    "success_rate": f"{success_rate:.1f}%",
                    "avg_ms": f"{stats['avg_duration_ms']:.0f}",
                    "last_reply": stats["last_reply"]
                }
            return summary

# Global metrics instance
metrics = Metrics(METRICS_FILE)

# Initial load (after log is defined)
_load_inboxes_config()

# ===== SESSION MANAGEMENT (same as polling agent) =====

def load_auth():
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text())
            if all(k in data for k in ("access-token", "client", "expiry", "uid")):
                return data
        except Exception as e:
            log(f"WARNING: Failed to load auth file: {e}")
    return None

def save_auth(data):
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    log(f"Session saved to {AUTH_FILE}")

def get_headers():
    auth = load_auth()
    if auth:
        return {
            "access-token": auth.get("access-token"),
            "client": auth.get("client"),
            "expiry": auth.get("expiry"),
            "uid": auth.get("uid"),
        }
    return None

def renew_session():
    log("Renewing Chatwoot session...")
    try:
        r = requests.post(CW_AUTH_URL, json={"email": CW_EMAIL, "password": CW_PASSWORD}, timeout=15)
        if r.status_code != 200:
            log(f"Login failed: {r.status_code} {r.text[:200]}")
            return None
        access_token = r.headers.get("access-token")
        client = r.headers.get("client")
        expiry = r.headers.get("expiry")
        uid = r.headers.get("uid")
        if not all([access_token, client, expiry, uid]):
            log(f"Missing headers: {dict(r.headers)}")
            return None
        # Extract pubsub_token from response body (ActionCable auth)
        pubsub_token = ""
        try:
            pubsub_token = r.json().get("data", {}).get("pubsub_token", "")
        except Exception:
            pass
        data = {"access-token": access_token, "client": client, "expiry": expiry, "uid": uid,
                "pubsub_token": pubsub_token,
                "updated_at": datetime.now(TZ).isoformat()}
        save_auth(data)
        exp_time = datetime.fromtimestamp(int(expiry))
        log(f"Session renewed, expires: {exp_time}")
        return data
    except Exception as e:
        log(f"Renewal error: {e}")
        return None

def ensure_session():
    auth = load_auth()
    now = time.time()
    if auth:
        try:
            expiry_ts = int(auth.get("expiry", "0"))
            remaining = timedelta(seconds=expiry_ts - now)
            log(f"Session expires in {remaining}")
            if remaining > RENEW_THRESHOLD:
                return get_headers()
        except (ValueError, TypeError):
            pass
    log("Session needs renewal")
    new_auth = renew_session()
    if new_auth:
        return {
            "access-token": new_auth["access-token"],
            "client": new_auth["client"],
            "expiry": new_auth["expiry"],
            "uid": new_auth["uid"],
        }
    raise RuntimeError(
        "No Chatwoot session available. "
        "Ensure 'chatwoot_auth.json' exists or CW_EMAIL/CW_PASSWORD env vars are set."
    )

# ===== PROCESSED MESSAGE TRACKING =====

def load_processed():
    if PROCESSED_FILE.exists():
        try:
            return set(json.loads(PROCESSED_FILE.read_text()))
        except: pass
    return set()

def save_processed(ids):
    keep = list(ids)[-1000:]  # keep last 1000
    PROCESSED_FILE.write_text(json.dumps(keep))

processed_ids = load_processed()
processed_lock = Lock()
MAX_PROCESSED_IDS = 10000

def prune_processed_ids():
    """Keep processed_ids from growing unbounded."""
    global processed_ids
    with processed_lock:
        if len(processed_ids) > MAX_PROCESSED_IDS:
            sorted_ids = sorted(processed_ids, reverse=True)
            processed_ids = set(sorted_ids[:MAX_PROCESSED_IDS // 2])
            save_processed(processed_ids)

def is_processed(msg_id):
    with processed_lock:
        return msg_id in processed_ids

def mark_processed(msg_id):
    with processed_lock:
        processed_ids.add(msg_id)
        if len(processed_ids) % 20 == 0:
            save_processed(processed_ids)

# ===== AI-SENT MESSAGE TRACKING =====
# Track message IDs that OUR AI sent via the API.
# This lets us distinguish our own AI replies from human agent messages
# when receiving events via WebSocket (since both use sender_type="User").
MAX_AI_SENT_IDS = 10000
ai_sent_msg_ids = set()
ai_sent_lock = Lock()

def prune_ai_sent_ids():
    """Keep ai_sent_msg_ids from growing unbounded."""
    global ai_sent_msg_ids
    with ai_sent_lock:
        if len(ai_sent_msg_ids) > MAX_AI_SENT_IDS:
            sorted_ids = sorted(ai_sent_msg_ids, reverse=True)
            ai_sent_msg_ids = set(sorted_ids[:MAX_AI_SENT_IDS // 2])

# Track conversation IDs where we just sent a message (race condition safety net)
# Entries are added BEFORE API call, removed AFTER tracking the real message ID.
_ai_pending_convs = set()
_ai_pending_lock = Lock()

def track_sent_message(msg_id):
    if msg_id:
        with ai_sent_lock:
            ai_sent_msg_ids.add(msg_id)

def is_ai_sent_message(msg_id):
    with ai_sent_lock:
        return msg_id in ai_sent_msg_ids

# ===== HUMAN ACTIVE TRACKING =====
# Track conversations where a human agent has sent a message.
# {conversation_id: timestamp_of_last_human_message}
human_active_convs = {}
human_active_lock = Lock()

def mark_human_active(conv_id):
    """Record that a human agent has engaged in this conversation."""
    with human_active_lock:
        human_active_convs[conv_id] = time.time()
    log(f"👤 Human marked active for conv #{conv_id}")

def is_human_active(conv_id):
    """Check if a human is still active in this conversation.
    
    Returns True if a human has replied within HUMAN_TIMEOUT_MINUTES.
    Auto-removes expired entries.
    """
    with human_active_lock:
        ts = human_active_convs.get(conv_id)
        if ts is None:
            return False
        elapsed = time.time() - ts
        if elapsed > HUMAN_TIMEOUT_MINUTES * 60:
            del human_active_convs[conv_id]
            log(f"⏱️ Conv #{conv_id} human timeout ({HUMAN_TIMEOUT_MINUTES}min), AI resuming")
            return False
        return True

def remove_human_active(conv_id):
    """Remove a conversation from human active tracking.
    
    Called when conversation is resolved, changed to pending,
    or explicitly handed back to AI.
    """
    with human_active_lock:
        if conv_id in human_active_convs:
            del human_active_convs[conv_id]
            log(f"🔄 Conv #{conv_id} removed from human active, AI may resume")

def clean_expired_human_active():
    """Periodic cleanup of expired human active entries."""
    with human_active_lock:
        now = time.time()
        expired = [cid for cid, ts in human_active_convs.items()
                   if now - ts > HUMAN_TIMEOUT_MINUTES * 60]
        for cid in expired:
            del human_active_convs[cid]
            log(f"⏱️ Conv #{cid} human timeout (cleanup), AI resuming")


# ===== STATE PERSISTENCE (survive restart) =====

def save_state():
    """Persist ai_sent_msg_ids, human_active_convs, _ai_pending_convs to JSON."""
    try:
        with ai_sent_lock, human_active_lock, _ai_pending_lock:
            state = {
                "ai_sent_msg_ids": list(ai_sent_msg_ids),
                "human_active_convs": human_active_convs.copy(),
                "ai_pending_convs": list(_ai_pending_convs),
                "saved_at": time.time()
            }
        # Add session map
        with _conv_session_lock:
            state["conv_session_map"] = _conv_session_map.copy()
        # Add summaries & rounds
        with _conv_conv_lock:
            state["conv_summaries"] = _conv_summaries.copy()
            state["conv_rounds"] = _conv_rounds.copy()
        # Add contact profiles
        with _contact_profile_lock:
            state["contact_profiles"] = _contact_profiles.copy()
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(f"save_state error: {e}", "WARN")


def load_state():
    """Restore state from JSON. Safety-first: only restore if file is recent (< 1h old)."""
    global ai_sent_msg_ids, human_active_convs, _ai_pending_convs
    try:
        if not STATE_FILE.exists():
            log("No state file found, starting fresh")
            return
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        saved_at = state.get("saved_at", 0)
        age = time.time() - saved_at

        if age > 3600:
            log(f"State file too old ({age/60:.0f}min), ignoring — safety first", "WARN")
            STATE_FILE.unlink(missing_ok=True)
            return

        with ai_sent_lock:
            ai_sent_msg_ids = set(state.get("ai_sent_msg_ids", []))
        with human_active_lock:
            human_active_convs = state.get("human_active_convs", {})
        with _ai_pending_lock:
            _ai_pending_convs = set(state.get("ai_pending_convs", []))
        # Restore session map
        with _conv_session_lock:
            _conv_session_map.update(state.get("conv_session_map", {}))
        # Restore summaries & rounds
        with _conv_conv_lock:
            _conv_summaries.update(state.get("conv_summaries", {}))
            _conv_rounds.update(state.get("conv_rounds", {}))
        # Restore contact profiles
        with _contact_profile_lock:
            _contact_profiles.update(state.get("contact_profiles", {}))

        log(f"State restored: {len(ai_sent_msg_ids)} msg_ids, {len(human_active_convs)} active convs, "
            f"{len(_conv_session_map)} sessions, {len(_conv_summaries)} summaries, "
            f"{len(_contact_profiles)} profiles")
    except Exception as e:
        log(f"load_state error: {e} (starting fresh)", "WARN")
        STATE_FILE.unlink(missing_ok=True)


# ===== DEBOUNCE (message coalescing) =====
# Accumulate messages from same conv within 5s window.
# Only process the last one with all accumulated context.
DEBOUNCE_WINDOW = 5  # seconds
_debounce_timers: dict[int, float] = {}  # conv_id → last message time
_debounce_msgs: dict[int, list[str]] = {}  # conv_id → accumulated messages
_debounce_lock = Lock()


# ===== SESSION-ID MAPPING (per-conversation QwenPaw context) =====
_conv_session_map: dict[int, str] = {}  # conv_id → qwenpaw session_id
_conv_session_lock = Lock()


def _get_or_create_session(conv_id):
    """Return existing session_id for a conversation, or create a new one."""
    with _conv_session_lock:
        sid = _conv_session_map.get(conv_id)
        if not sid:
            sid = f"conv_{conv_id}_{int(time.time())}"
            _conv_session_map[conv_id] = sid
        return sid


def _prune_sessions():
    """Trim session map when it grows too large."""
    with _conv_session_lock:
        if len(_conv_session_map) > 10000:
            _conv_session_map.clear()
            log("🧹 Session map too large, cleared", "WARN")


# ===== CONVERSATION SUMMARIZATION =====
_conv_rounds: dict[int, int] = {}  # conv_id → AI reply count
_conv_summaries: dict[int, str] = {}  # conv_id → latest AI-generated summary
_conv_conv_lock = Lock()
SUMMARY_THRESHOLD = 15  # generate summary after every N AI replies


def _summarize_conversation(conv_id, prompt, reply, target_agent):
    """Ask AI to produce a short summary of this conversation so far."""
    with _conv_conv_lock:
        old_summary = _conv_summaries.get(conv_id, "")
    summary_prompt = (
        f"Existing summary: {old_summary}\n\n"
        f"Latest customer message: {prompt[:200]}\n"
        f"Your reply: {reply[:500]}\n\n"
        "Produce a concise 1-2 sentence summary (in English) of the "
        "entire conversation so far. Focus on customer needs, products "
        "discussed, and any decisions made. Keep it under 100 words."
    )
    summary = call_qwenpaw_ai(summary_prompt, target_agent=target_agent)
    if summary:
        with _conv_conv_lock:
            _conv_summaries[conv_id] = summary


def _get_conversation_context(conv_id):
    """Return summary string for this conv, or empty string."""
    with _conv_conv_lock:
        return _conv_summaries.get(conv_id, "")


# ===== CONTACT PROFILING =====
_contact_profiles: dict[int, dict] = {}  # contact_id → profile dict
_contact_profile_lock = Lock()


def _update_contact_profile(contact_id, sender_name, msg, reply):
    """Extract relevant info from conversation and update contact profile."""
    if not contact_id:
        return
    with _contact_profile_lock:
        profile = _contact_profiles.get(contact_id, {})
        profile["name"] = sender_name
        profile["last_seen"] = time.time()
        # Keep a rolling log of last 3 interactions
        interactions = profile.get("interactions", [])
        interactions.append({"msg": msg[:100], "reply": reply[:100], "ts": time.time()})
        profile["interactions"] = interactions[-3:]
        _contact_profiles[contact_id] = profile


def _get_contact_context(contact_id):
    """Return a prompt-friendly profile string for this contact."""
    if not contact_id:
        return ""
    with _contact_profile_lock:
        profile = _contact_profiles.get(contact_id)
    if not profile:
        return ""
    parts = [f"Contact name: {profile.get('name', 'Unknown')}"]
    interactions = profile.get("interactions", [])
    if interactions:
        parts.append(f"Last {len(interactions)} interaction(s):")
        for i, ix in enumerate(interactions):
            parts.append(f"  [{i+1}] \"{ix['msg']}\" → \"{ix['reply'][:80]}\"")
    return "\n".join(parts)


# ===== AI HELPERS =====

import re as _re  # used for session-id stripping

GATEWAY_ENABLED = os.environ.get("GATEWAY_ENABLED", "1") == "1"

def call_qwenpaw_ai(prompt, system_prompt=None, target_agent="sourcing-agent",
                    retries=2, session_id=None):
    """Call QwenPaw AI via agents chat, with retries on failure.

    Args:
        prompt: The user message
        system_prompt: Optional system instructions (appended before prompt)
        target_agent: Which agent to call (default:sourcing-agent, translation:default)
        retries: Number of retries on failure (exponential backoff)
        session_id: Optional QwenPaw session ID for conversation continuity
    """
    full_prompt = (system_prompt + "\n\n" + prompt) if system_prompt else prompt
    cmd = ["qwenpaw", "agents", "chat",
           "--from-agent", "wordpress",
           "--to-agent", target_agent,
           "--text", full_prompt]
    if session_id:
        cmd.extend(["--session-id", session_id])
    last_error = None
    for attempt in range(1 + retries):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode == 0 and result.stdout.strip():
                # Clean output: remove INFO/SESSION/Agent lines
                raw = result.stdout.strip()
                lines = raw.split("\n")
                clean_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith(("INFO:", "[Agent")):
                        continue
                    # Remove [SESSION: ...] prefix from any line
                    stripped = _re.sub(r'\[SESSION:\s*[^\]]*\]\s*', '', stripped)
                    if stripped:
                        clean_lines.append(stripped)
                reply = "\n".join(clean_lines).strip()
                if reply:
                    return reply
            last_error = f"rc={result.returncode}" if result.returncode != 0 else "empty reply"
            if result.stderr:
                last_error += f" stderr={result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            last_error = "timeout (90s)"
        except Exception as e:
            last_error = str(e)[:200]
        if attempt < retries:
            wait = 2 ** attempt  # 1s, 2s
            log(f"⚠️ AI call failed ({last_error}), retry {attempt+1}/{retries} in {wait}s", "WARN")
            time.sleep(wait)
    log(f"❌ AI call failed after {retries+1} attempts: {last_error}", "ERROR")
    return None


def translate_to_chinese(text):
    """Translate text to Simplified Chinese."""
    prompt = (
        f"Translate the following text to Simplified Chinese. "
        f"Keep all factual details (names, numbers, URLs) intact. "
        f"Only output the translation, no explanations.\n\n{text}"
    )
    result = call_qwenpaw_ai(prompt, target_agent="default")
    return result if result else text

def generate_ai_reply(customer_msg, sender_name, inbox_id, context="", session_id=None):
    config = INBOX_CONFIG.get(inbox_id)
    if not config:
        log(f"No config for inbox #{inbox_id}, skipping", "WARN")
        return None

    body = f"{context}\n\n{customer_msg}" if context else customer_msg
    prompt = config["prompt_template"].format(
        sender_name=sender_name,
        customer_msg=body
    )
    reply = call_qwenpaw_ai(prompt, config["system_prompt"],
                            target_agent=config["target_agent"],
                            session_id=session_id)

    if not reply:
        return reply

    # Strip common meta-prefixes the AI sometimes adds (for English prompts)
    for prefix in [
        "Here's the professional reply:\n\n---\n\n",
        "Here's the professional reply:\n\n",
        "Here's my professional reply:\n\n",
        "Here's the reply:\n\n",
        "Professional reply:\n\n",
    ]:
        if reply.startswith(prefix):
            reply = reply[len(prefix):]
            break

    return reply

# ===== CHATWOOT API =====

def send_reply(conv_id, content, headers):
    """Send a message as the current user. Tracks the returned message ID."""
    with _ai_pending_lock:
        _ai_pending_convs.add(conv_id)
    try:
        r = requests.post(f"{CW_API_BASE}/conversations/{conv_id}/messages",
            json={"content": content}, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            track_sent_message(data.get("id"))
            return True, data
        return False, r.text
    finally:
        with _ai_pending_lock:
            _ai_pending_convs.discard(conv_id)

def send_private_note(conv_id, content, headers):
    """Send a private note (agents-only). Tracks message ID to avoid false human detection."""
    with _ai_pending_lock:
        _ai_pending_convs.add(conv_id)
    try:
        r = requests.post(f"{CW_API_BASE}/conversations/{conv_id}/messages",
            json={"content": content, "private": True}, headers=headers, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            track_sent_message(data.get("id"))
            return True
        return False
    finally:
        with _ai_pending_lock:
            _ai_pending_convs.discard(conv_id)

def update_conversation_status(conv_id, status, headers):
    """Update conversation status (pending/open/resolved)."""
    try:
        r = requests.post(f"{CW_API_BASE}/conversations/{conv_id}/toggle_status",
            json={"status": status}, headers=headers, timeout=5)
        return r.status_code in (200, 201)
    except Exception as e:
        log(f"Status update error: {e}")
        return False

# ===== MEETING ROOM =====
MEETING_ROOM_INBOX_ID = 22  # "开发团队" inbox
MEETING_AGENTS = [
    {"id": "QWEN", "label": "[QWEN]", "agent": "wordpress"},
    {"id": "OpenCode", "label": "[OpenCode]", "agent": "opencode"},
]
_meeting_ai_sent_ids = set()  # track AI-sent message IDs to avoid loop

def handle_meeting_message(msg_data, headers):
    """Handle messages in the 开发团队 meeting room inbox.

    - Messages from AI agents (tracked IDs) → skip (avoid loop)
    - Messages from human (qiu) → forward to both QWEN and OpenCode
    - AI replies with [SKIP] → don't send to Chatwoot
    - Other AI replies → send with [QWEN] or [OpenCode] prefix
    """
    msg_id = msg_data.get("id")
    if not msg_id or is_processed(msg_id):
        return

    content = str(msg_data.get("content", "")).strip()
    conv_id = msg_data.get("conversation_id")
    if not content or not conv_id:
        return

    # Skip AI's own messages (avoid infinite loop)
    if msg_id in _meeting_ai_sent_ids:
        mark_processed(msg_id)
        return

    # Skip private notes
    if msg_data.get("private", False):
        return

    mark_processed(msg_id)
    sender_name = msg_data.get("sender", {}).get("name", "Unknown")
    log(f"📩 [会议] msg #{msg_id} from '{sender_name}': {content[:100]}")

    # Forward to each AI agent
    for agent_cfg in MEETING_AGENTS:
        prompt = (
            f"You are {agent_cfg['id']}, a team member in a dev team meeting room.\n"
            f"Message from '{sender_name}':\n\n{content}\n\n"
            f"If this message is relevant to you or you have something useful to add, reply normally.\n"
            f"If this message is NOT relevant to you, reply with ONLY: [SKIP]\n"
            f"Do NOT add any explanation if you reply [SKIP]."
        )
        reply = call_qwenpaw_ai(prompt, target_agent=agent_cfg["agent"])
        if not reply:
            log(f"⚠️ [会议] {agent_cfg['id']} returned empty", "WARN")
            continue

        # Check for [SKIP]
        if reply.strip() == "[SKIP]" or "[SKIP]" in reply:
            log(f"⏭️ [会议] {agent_cfg['id']} skipped (not relevant)")
            continue

        # Send reply with agent label prefix
        tagged_reply = f"{agent_cfg['label']} {reply}"
        ok, resp = send_reply(conv_id, tagged_reply, headers)
        if ok:
            _meeting_ai_sent_ids.add(resp.get("id"))
            log(f"✅ [会议] {agent_cfg['id']} replied to conv #{conv_id}")
        else:
            log(f"❌ [会议] {agent_cfg['id']} failed: {resp}", "ERROR")

# ===== MESSAGE HANDLER =====

def _enrich_context(inbox_id, customer_msg, config):
    if not GATEWAY_ENABLED:
        return ""
    channel = config.get("type", "web_widget")
    if channel not in ("amazon", "jd", "taobao", "pdd", "tiktok"):
        return ""
    tenant_id = config.get("tenant_id")
    if not tenant_id:
        return ""
    asin_match = _re.search(r'\b(B0[A-Z0-9]{8})\b', customer_msg, _re.IGNORECASE)
    query = {"asin": asin_match.group(1).upper()} if asin_match else {"keyword": customer_msg[:50]}
    try:
        from gateway import fetch
        result = fetch(channel, tenant_id, query, timeout=3.0)
        return result.to_prompt_block()
    except Exception as e:
        log(f"Gateway enrich error: {e}")
        return ""

def handle_incoming_message(msg_data, headers):
    """Process an incoming customer message (with human handoff awareness)."""
    msg_id = msg_data.get("id")
    if not msg_id:
        return
    if is_processed(msg_id):
        return

    # Validate it's a customer incoming message
    sender_type = msg_data.get("sender_type")
    # Chatwoot enum: 0=incoming, 1=outgoing, 2=activity, 3=template
    message_type = msg_data.get("message_type")
    is_private = msg_data.get("private", False)

    if sender_type != "Contact":
        return
    if message_type != 0:  # 0 = incoming (customer message)
        return
    if is_private:
        return

    # Route by inbox_id
    inbox_id = msg_data.get("inbox_id")
    config = INBOX_CONFIG.get(inbox_id)
    if not config:
        log(f"⏭️ Unknown inbox #{inbox_id}, skipping")
        return

    content = str(msg_data.get("content", "")).strip()
    conv_id = msg_data.get("conversation_id")
    sender_name = "Customer"
    if msg_data.get("sender"):
        sender_name = msg_data["sender"].get("name", "Customer")

    if not content or not conv_id:
        return

    # 🔑 Check if a human agent is active in this conversation
    if is_human_active(conv_id):
        log(f"⏭️ [{config['name']}] Conv #{conv_id} has active human agent, skipping AI reply")
        return

    # Mark immediately to avoid duplicate processing
    mark_processed(msg_id)

    # ===== DEBOUNCE: coalesce rapid messages from same conv =====
    with _debounce_lock:
        now = time.time()
        last_time = _debounce_timers.get(conv_id, 0)
        if now - last_time < DEBOUNCE_WINDOW:
            # Within debounce window → accumulate, don't reply yet
            if conv_id not in _debounce_msgs:
                _debounce_msgs[conv_id] = []
            _debounce_msgs[conv_id].append(content)
            _debounce_timers[conv_id] = now
            log(f"⏳ [{config['name']}] Debounce #{conv_id}: accumulated msg #{msg_id} (window {DEBOUNCE_WINDOW}s)")
            return
        # First message or window expired → process now
        _debounce_timers[conv_id] = now
        # Collect any previously accumulated messages
        accumulated = _debounce_msgs.pop(conv_id, [])
        if accumulated:
            accumulated.append(content)
            content = "\n---\n".join(accumulated)
            log(f"📦 [{config['name']}] Debounce #{conv_id}: processing {len(accumulated)} merged msgs")

    # ===== END DEBOUNCE =====

    log(f"📩 [{config['name']}] New msg #{msg_id} from '{sender_name}' in conv #{conv_id}: {content[:100]}", inbox_name=config['name'])

    # ===== SESSION-ID: maintain conversation continuity =====
    session_id = _get_or_create_session(conv_id)
    # ===== CONVERSATION SUMMARY: inject past context =====
    conv_context = _get_conversation_context(conv_id)
    # ===== CONTACT PROFILE: inject customer history =====
    contact_id = msg_data.get("sender", {}).get("id")
    contact_context = _get_contact_context(contact_id)

    # Build enriched context
    context_parts = []
    gateway_ctx = _enrich_context(inbox_id, content, config)
    if gateway_ctx:
        context_parts.append(gateway_ctx)
    if conv_context:
        context_parts.append(f"[Conversation so far: {conv_context}]")
    if contact_context:
        context_parts.append(f"[Customer history: {contact_context}]")
    all_context = "\n".join(context_parts)

    # Generate AI reply with inbox-specific config
    log(f"🤖 [{config['name']}] Generating AI reply...", inbox_name=config['name'])
    start_time = time.time()
    reply = generate_ai_reply(content, sender_name, inbox_id,
                              context=all_context, session_id=session_id)
    duration_ms = (time.time() - start_time) * 1000

    if not reply:
        log(f"⚠️ [{config['name']}] Empty AI reply, skipping", "WARN", config['name'])
        metrics.record_reply(inbox_id, config['name'], False, duration_ms)
        return

    log(f"💬 [{config['name']}] AI reply ({duration_ms:.0f}ms): {reply[:150]}", inbox_name=config['name'])

    # ===== POST-REPLY: update conversation summary & contact profile =====
    with _conv_conv_lock:
        rounds = _conv_rounds.get(conv_id, 0) + 1
        _conv_rounds[conv_id] = rounds
    if rounds > 0 and rounds % SUMMARY_THRESHOLD == 0:
        # Generate summary every SUMMARY_THRESHOLD AI replies
        _summarize_conversation(conv_id, content, reply, config["target_agent"])
    _update_contact_profile(contact_id, sender_name, content, reply)
    
    if not reply:
        log(f"⚠️ [{config['name']}] Empty AI reply, skipping", "WARN", config['name'])
        metrics.record_reply(inbox_id, config['name'], False, duration_ms)
        return

    log(f"💬 [{config['name']}] AI reply ({duration_ms:.0f}ms): {reply[:150]}", inbox_name=config['name'])

    # Check if AI thinks this needs human handoff
    needs_handoff = False
    if "[HANDOFF]" in reply:
        needs_handoff = True
        reply = reply.replace("[HANDOFF]", "").replace("\n[HANDOFF]", "").replace("[HANDOFF]\n", "").strip()
        log(f"🚩 [{config['name']}] AI detected handoff needed for conv #{conv_id}")

    # Send the reply (will be tracked in ai_sent_msg_ids)
    ok, resp_data = send_reply(conv_id, reply, headers)
    if ok:
        log(f"✅ Reply sent to conv #{conv_id}", inbox_name=config['name'])
        metrics.record_reply(inbox_id, config['name'], True, duration_ms)
    else:
        log(f"❌ Failed to send reply: {resp_data}", "ERROR", config['name'])
        metrics.record_reply(inbox_id, config['name'], False, duration_ms)

    # Send private note with translation
    chinese_summary = translate_to_chinese(
        f"Customer {sender_name}: {content}\n\nAI Agent replied: {reply}"
    )
    note = (
        f"🤖 AI 自动回复\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📩 客户消息:\n{content}\n\n"
        f"💬 AI 回复:\n{reply}\n\n"
        f"🌐 中文摘要:\n{chinese_summary}"
    )
    if send_private_note(conv_id, note, headers):
        log(f"✅ Private note sent to conv #{conv_id}")
    else:
        log(f"❌ Failed to send private note")

    # If handoff needed: send alert + change conversation status to 'open'
    if needs_handoff:
        handoff_note = (
            f"⚠️ ⚠️ ⚠️ 建议人工介入 ⚠️ ⚠️ ⚠️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"客户 '{sender_name}' 的询问 AI 判断需要人工处理。\n"
            f"请尽快回复此会话。\n\n"
            f"📩 客户消息原文:\n{content}"
        )
        send_private_note(conv_id, handoff_note, headers)
        # Change conversation to 'open' so Chatwoot alerts human agents
        update_conversation_status(conv_id, "open", headers)
        log(f"🔔 Handoff alert sent for conv #{conv_id}")

# ===== WEBSOCKET CLIENT =====

class WSAgent:
    def __init__(self):
        self.ws = None
        self.headers = None
        self.running = Event()
        self.running.set()
        self.last_pong = time.time()

    def on_open(self, ws):
        log("🟢 WebSocket connected")
        metrics.ws_connected()
        # Subscribe to RoomChannel
        sub = json.dumps({
            "channel": "RoomChannel",
            "pubsub_token": PUBSUB_TOKEN,
            "user_id": USER_ID,
            "account_id": CW_ACCOUNT_ID
        })
        ws.send(json.dumps({"command": "subscribe", "identifier": sub}))
        log("📡 Subscribing to RoomChannel...")

    def on_message(self, ws, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        t = data.get("type")

        if t == "ping":
            self.last_pong = time.time()
            return

        if t == "welcome":
            log("📡 Connected to Chatwoot ActionCable")
            return

        if t == "confirm_subscription":
            log("✅ RoomChannel subscription confirmed")
            return

        if t == "reject_subscription":
            log("❌ Subscription REJECTED! Check credentials")
            return

        # Process events
        msg = data.get("message", {})
        if isinstance(msg, dict):
            event = msg.get("event", "")
            if event == "presence.update":
                pass  # ignore silently
            elif event in ("message.created", "MESSAGE_CREATED"):
                self._on_message_created(msg.get("data", {}))
            elif event in ("conversation.updated", "CONVERSATION_UPDATED"):
                self._on_conversation_updated(msg.get("data", {}))
            elif event in ("conversation.created", "CONVERSATION_CREATED"):
                log(f"📋 New conversation created")
            elif event:
                log(f"📡 Event: {event}")
        else:
            # Debug: log any non-dict messages
            log(f"📡 Raw message: {str(data)[:200]}", "DEBUG")

    def _on_message_created(self, msg_data):
        """Handle a message_created event.

        Detects human agent messages (for handoff tracking)
        and processes incoming customer messages (for AI reply).
        """
        msg_id = msg_data.get("id")
        sender_type = msg_data.get("sender_type")
        conv_id = msg_data.get("conversation_id")
        message_type = msg_data.get("message_type")

        # 🔑 Detect human agent messages (sender_type="User" that are NOT from AI)
        is_human = False
        if sender_type == "User" and conv_id and msg_id:
            is_human = True
        # API Inbox: outgoing msgs (type=1) from admin have sender_type="Contact"
        # Detect via: NOT from AI + message_type=1 (outgoing) + not private note
        if not is_human and message_type == 1 and conv_id and msg_id and not msg_data.get("private", False):
            if not is_ai_sent_message(msg_id):
                with _ai_pending_lock:
                    if conv_id not in _ai_pending_convs:
                        is_human = True
        
        if is_human:
            with _ai_pending_lock:
                is_pending = conv_id in _ai_pending_convs
            if is_pending or is_ai_sent_message(msg_id):
                pass  # This is our own AI message, ignore
            else:
                # This message was sent by a human agent (not our AI)
                mark_human_active(conv_id)
                sender_info = msg_data.get("sender", {})
                agent_name = sender_info.get("name", "Unknown") if isinstance(sender_info, dict) else "Unknown"
                content = str(msg_data.get("content", ""))[:100]
                log(f"👤 Human agent '{agent_name}' replied in conv #{conv_id}: {content}")

        # Route to meeting room or normal inbox handler
        inbox_id = msg_data.get("inbox_id")
        if inbox_id == MEETING_ROOM_INBOX_ID:
            Thread(target=handle_meeting_message, args=(msg_data, self.headers), daemon=True).start()
        else:
            Thread(target=handle_incoming_message, args=(msg_data, self.headers), daemon=True).start()

    def _on_conversation_updated(self, data):
        """Handle conversation status changes.

        If conversation is resolved or changed to pending,
        allow AI to resume.
        """
        if not data:
            return
        conv_id = data.get("id")
        status = data.get("status")
        if not conv_id:
            return
        if status in ("resolved", "pending"):
            remove_human_active(conv_id)
            log(f"🔄 Conv #{conv_id} status -> '{status}', AI may resume")
        elif status == "open":
            log(f"🔄 Conv #{conv_id} status -> 'open'")

    def on_error(self, ws, error):
        log(f"🔴 WS Error: {error}", "ERROR")
        metrics.ws_disconnected(str(error))

    def on_close(self, ws, status, msg):
        log(f"🔴 WebSocket closed (status={status}, msg={msg})", "WARN")
        metrics.ws_disconnected(f"status={status}, msg={msg}")

    def start(self):
        """Start WebSocket connection with exponential backoff reconnect."""
        self.headers = ensure_session()
        delay = 5  # start at 5s
        max_delay = 60
        attempt = 0

        while self.running.is_set():
            if attempt > 0:
                log(f"🔄 Reconnecting in {delay}s (attempt #{attempt})...")
                time.sleep(delay)
                delay = min(delay * 2, max_delay)  # 5 → 10 → 20 → 40 → 60
                # Re-fetch session headers in case they expired during downtime
                try:
                    self.headers = ensure_session()
                except Exception as e:
                    log(f"Session renewal failed before reconnect: {e}", "WARN")
                    continue

            log(f"Connecting to {CW_WS_URL}")
            self.ws = websocket.WebSocketApp(
                CW_WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            self.ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_interval=15,
                ping_timeout=5,
                reconnect=0  # disable internal reconnect; we handle it
            )
            attempt += 1

    def stop(self):
        """Stop the WebSocket connection."""
        self.running.clear()
        if self.ws:
            self.ws.close()
        log("Agent stopped")

# ===== TIMEOUT CHECKER THREAD =====

def timeout_checker_loop():
    """Background thread: clean expired handoffs + hot-reload config + persist state."""
    while True:
        time.sleep(30)  # Check every 30s
        try:
            clean_expired_human_active()
            prune_ai_sent_ids()
            prune_processed_ids()
            _load_inboxes_config()  # hot-reload if file changed
            save_state()  # persist state every 30s
            metrics.flush()  # persist metrics every 30s
        except Exception as e:
            log(f"Timeout checker error: {e}")

PUBSUB_TOKEN = os.environ.get("CW_PUBSUB_TOKEN", "")
USER_ID = int(os.environ.get("CW_USER_ID", "1"))
if not PUBSUB_TOKEN:
    # Fallback: read directly from auth file
    _auth_path = Path(__file__).parent / "chatwoot_auth.json"
    if _auth_path.exists():
        try:
            _auth_data = json.loads(_auth_path.read_text())
            PUBSUB_TOKEN = _auth_data.get("pubsub_token", "")
        except Exception:
            pass
if not PUBSUB_TOKEN:
    # Last resort: try renewing session to get pubsub_token from login response
    log("PUBSUB_TOKEN not set, attempting session renewal to obtain it...", "WARN")
    _new_auth = None
    try:
        _r = requests.post(
            CW_AUTH_URL,
            json={"email": CW_EMAIL, "password": CW_PASSWORD},
            timeout=15
        )
        if _r.status_code == 200:
            _body = _r.json()
            PUBSUB_TOKEN = _body.get("data", {}).get("pubsub_token", "")
    except Exception:
        pass
if not PUBSUB_TOKEN:
    raise RuntimeError(
        "Missing Chatwoot pubsub token. "
        "Set CW_PUBSUB_TOKEN env var or include 'pubsub_token' in chatwoot_auth.json"
    )

# ===== MAIN =====

def main():

    # Restore persisted state BEFORE handling any args (--health etc. need it)
    load_state()

    parser = argparse.ArgumentParser(description="Chatwoot WebSocket AI Agent")
    parser.add_argument("--renew", action="store_true", help="Force renew session & exit")
    parser.add_argument("--test-ws", action="store_true", help="Test WebSocket connection & exit")
    parser.add_argument("--health", action="store_true", help="Print health status (JSON) & exit")
    parser.add_argument("--metrics", action="store_true", help="Print detailed metrics (JSON) & exit")
    parser.add_argument("--reset-metrics", action="store_true", help="Reset all metrics & exit")
    parser.add_argument("--inbox-metrics", type=int, help="Print metrics for specific inbox ID")
    parser.add_argument("--ws-status", action="store_true", help="Print WebSocket connection status & exit")
    parser.add_argument("--list-inboxes", action="store_true", help="List configured inboxes & exit")
    parser.add_argument("--inbox-stats", action="store_true", help="Print formatted inbox statistics table & exit")
    parser.add_argument("--inbox-stats-json", action="store_true", help="Print inbox statistics as JSON & exit")
    parser.add_argument("--inbox-stats-csv", action="store_true", help="Print inbox statistics as CSV & exit")
    parser.add_argument("--inbox-stats-one-line", action="store_true", help="Print inbox stats as single line & exit")
    args = parser.parse_args()

    if args.renew:
        renew_session()
        return

    if args.test_ws:
        log("Testing WebSocket connection...")
        headers = ensure_session()
        log("Session OK, testing WS...")
        agent = WSAgent()
        # Just connect and subscribe, then exit after 5 seconds
        def _timeout():
            time.sleep(5)
            log("Test OK, disconnecting...")
            agent.stop()
        Thread(target=_timeout, daemon=True).start()
        agent.start()
        return

    if args.health:
        # Print health status with metrics
        summary = metrics.get_summary()
        status = {
            "status": "running",
            "inboxes": list(INBOX_CONFIG.keys()),
            "human_timeout_minutes": HUMAN_TIMEOUT_MINUTES,
            "active_human_convs": len(human_active_convs),
            "processed_msgs": len(processed_ids),
            "ai_sent_msgs": len(ai_sent_msg_ids),
            "config_source": "inboxes.json" if INBOX_CONFIG_FILE.exists() else "default",
            "metrics": summary
        }
        print(json.dumps(status, indent=2))
        return

    if args.metrics:
        # Print detailed metrics
        print(json.dumps(metrics.get_summary(), indent=2))
        return

    if args.reset_metrics:
        # Reset metrics
        metrics.data = {
            "started_at": datetime.now(TZ).isoformat(),
            "ws_connected": False,
            "ws_disconnects": 0,
            "ws_last_disconnect": None,
            "inboxes": {}
        }
        metrics.flush()
        print("Metrics reset successfully")
        return

    if args.inbox_metrics:
        # Print metrics for specific inbox
        inbox_id = args.inbox_metrics
        summary = metrics.get_summary()
        inbox_data = summary.get("inboxes", {}).get(str(inbox_id))
        if inbox_data:
            print(json.dumps({inbox_id: inbox_data}, indent=2))
        else:
            print(f"No metrics found for inbox {inbox_id}")
        return

    if args.ws_status:
        # Print WebSocket status
        summary = metrics.get_summary()
        ws_status = {
            "connected": summary["ws_connected"],
            "disconnects": summary["ws_disconnects"],
            "last_disconnect": summary["ws_last_disconnect"],
            "uptime_since": summary["uptime_since"]
        }
        print(json.dumps(ws_status, indent=2))
        return

    if args.list_inboxes:
        # List configured inboxes
        inboxes = []
        for inbox_id, config in INBOX_CONFIG.items():
            inboxes.append({
                "id": inbox_id,
                "name": config["name"],
                "type": config.get("type", "unknown"),
                "target_agent": config["target_agent"],
                "status": config.get("status", "active")
            })
        print(json.dumps(inboxes, indent=2))
        return

    if args.inbox_stats:
        # Print formatted inbox statistics
        summary = metrics.get_summary()
        print("\n📊 Inbox Statistics")
        print("=" * 60)
        print(f"{'Inbox':<15} {'Name':<15} {'Total':<8} {'Success':<8} {'Failed':<8} {'Rate':<8} {'Avg (ms)':<10}")
        print("-" * 60)
        for inbox_id, stats in summary.get("inboxes", {}).items():
            print(f"{inbox_id:<15} {stats['name']:<15} {stats['total']:<8} {stats['success']:<8} {stats['failed']:<8} {stats['success_rate']:<8} {stats['avg_ms']:<10}")
        print("=" * 60)
        return

    if args.inbox_stats_json:
        # Print inbox statistics as JSON
        summary = metrics.get_summary()
        print(json.dumps(summary.get("inboxes", {}), indent=2))
        return


    if args.inbox_stats_csv:
        # Print inbox statistics as CSV
        summary = metrics.get_summary()
        print("inbox_id,name,total,success,failed,success_rate,avg_ms")
        for inbox_id, stats in summary.get("inboxes", {}).items():
            print(f"{inbox_id},{stats['name']},{stats['total']},{stats['success']},{stats['failed']},{stats['success_rate']},{stats['avg_ms']}")
        return

    if args.inbox_stats_one_line:
        # Print one-line inbox statistics
        summary = metrics.get_summary()
        total_requests = sum(stats["total"] for stats in summary.get("inboxes", {}).values())
        total_success = sum(stats["success"] for stats in summary.get("inboxes", {}).values())
        success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0
        inboxes = [f"{inbox_id}:{stats['name']}" for inbox_id, stats in summary.get("inboxes", {}).items()]
        print(f"📊 {len(summary.get('inboxes', {}))} inboxes | {total_requests} req | {success_rate:.1f}% success | {', '.join(inboxes)}")
        return

    log(f"🚀 Chatwoot WS Agent starting...")
    log(f"⚙️  Human timeout: {HUMAN_TIMEOUT_MINUTES}min")
    log(f"⚙️  Account ID: {CW_ACCOUNT_ID}")

    if GATEWAY_ENABLED:
        try:
            from gateway import gateway_loop as _gw_loop
            _gw_loop.start()
            log("🌐 Platform Gateway event loop started")
        except Exception as e:
            log(f"⚠️ Gateway init failed (continuing without): {e}", "WARN")

    # Start the timeout checker daemon
    checker = Thread(target=timeout_checker_loop, daemon=True)
    checker.start()
    log("⏱️  Timeout checker started")

    # Start the main agent
    agent = WSAgent()
    
    def _shutdown(signum, frame):
        log(f"Received signal {signum}, shutting down gracefully...")
        agent.stop()
        if GATEWAY_ENABLED:
            try:
                from gateway import gateway_loop as _gw_loop
                _gw_loop.stop()
            except Exception:
                pass
        save_state()
        metrics.flush()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    
    try:
        agent.start()
    except KeyboardInterrupt:
        log("Shutting down...")
        agent.stop()
        save_state()
        metrics.flush()

if __name__ == "__main__":
    main()


