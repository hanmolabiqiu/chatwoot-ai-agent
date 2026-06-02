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

# ===== CONFIG =====
CW_BASE = "https://chatwoot.275763.xyz"
CW_WS_URL = CW_BASE.replace("https://", "wss://").replace("http://", "ws://") + "/cable"
CW_ACCOUNT_ID = 1
CW_AUTH_URL = f"{CW_BASE}/auth/sign_in"
CW_API_BASE = f"{CW_BASE}/api/v1/accounts/{CW_ACCOUNT_ID}"

SCRIPT_DIR = Path(__file__).parent
AUTH_FILE = SCRIPT_DIR / "chatwoot_auth.json"
PROCESSED_FILE = SCRIPT_DIR / ".chatwoot_ws_processed.json"

# ===== INBOX ROUTING CONFIG =====
# Map inbox_id → AI agent config
INBOX_CONFIG = {
    1: {
        "name": "GreatQiu",
        "target_agent": "sourcing-agent",
        "system_prompt": (
            "You are a professional China sourcing agent from GreatQiu (based in Shaoxing, Zhejiang, China). "
            "You help international clients with product sourcing, supplier verification, "
            "quality control, logistics, and supply chain management.\n\n"
            "IMPORTANT - Decide if you can fully handle this or need a human:\n"
            "- If the customer asks about specific PRICING, MOQ, PLACING ORDERS, "
            "CUSTOMIZATION, SHIPPING QUOTES, or COMPLEX TECHNICAL SPECS that require "
            "real-time data from suppliers → end your reply with [HANDOFF] on a new line.\n"
            "- If you can answer the question fully using your general knowledge "
            "(company info, services, processes, general timelines) → do NOT add [HANDOFF]."
        ),
        "prompt_template": (
            "A customer named '{sender_name}' sent this message:\n\n"
            "{customer_msg}\n\n"
            "Write a direct reply (no preamble, no markdown). Keep it concise (2-4 sentences). "
            "Use the same language as the customer. "
            "Always sign with '- GreatQiu Team'."
        ),
        "note_prefix": "🤖 AI 自动回复 (GreatQiu)",
        "signature": "- GreatQiu Team",
    },
    7: {
        "name": "HALO Blog",
        "target_agent": "halo-blog-agent",
        "system_prompt": (
            "你是一名专业的安防弱电与IT基础设施技术顾问，来自Q师傅知识库。"
            "你帮助客户解答关于交换机配置、监控系统、网络布线、弱电工程、服务器运维等技术问题。\n\n"
            "重要 - 判断是否需要人工介入：\n"
            "- 如果客户询问具体的项目报价、施工方案定制、现场勘查需求、"
            "或需要实际采购产品 → 在回复末尾加一行 [HANDOFF]。\n"
            "- 如果是回答一般性的技术问题（设备参数、配置方法、故障排查思路等）→ 不加 [HANDOFF]。"
        ),
        "prompt_template": (
            "客户 '{sender_name}' 发送了以下消息：\n\n"
            "{customer_msg}\n\n"
            "请用中文直接回复（不要前缀，不要Markdown）。保持简洁（2-4句话）。"
            "回复语气专业友善，体现技术专家的可靠性。"
            "以'- Q师傅知识库'署名。"
        ),
        "note_prefix": "🤖 AI 自动回复 (Q师傅知识库)",
        "signature": "- Q师傅知识库",
    }
}

# Agent identity (from /api/v1/profile response)
PUBSUB_TOKEN = "JQ3wQYDy6LUMwvHouKKV2scr"
USER_ID = 1

# Login credentials for auto-renewal
CW_EMAIL = os.environ.get("CW_EMAIL", "qiuzhida@greatqiu.cn")
CW_PASSWORD = os.environ.get("CW_PASSWORD", "Qaly8980+")

RENEW_THRESHOLD = timedelta(hours=6)
TZ = timezone(timedelta(hours=8))

# ===== HUMAN HANDOFF CONFIG =====
# If a human agent has replied in this conversation but hasn't replied
# for HUMAN_TIMEOUT_MINUTES, the AI resumes auto-replying.
HUMAN_TIMEOUT_MINUTES = 15

# ===== LOGGING =====

def log(msg):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

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
    return {
        "access-token": "uueUhS5OBWOeabNdleUa8w",
        "client": "4xu1KgEP3RzNoM86hAkeCg",
        "expiry": "1785135457",
        "uid": "qiuzhida@greatqiu.cn",
    }

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
        data = {"access-token": access_token, "client": client, "expiry": expiry, "uid": uid,
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
    log("WARNING: Using fallback headers")
    return get_headers()

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
ai_sent_msg_ids = set()
ai_sent_lock = Lock()

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

# ===== AI HELPERS =====

import re as _re  # used for session-id stripping

def call_qwenpaw_ai(prompt, system_prompt=None, target_agent="sourcing-agent"):
    """Call QwenPaw AI via agents chat.

    Args:
        prompt: The user message
        system_prompt: Optional system instructions (appended before prompt)
        target_agent: Which agent to call (default:sourcing-agent, translation:default)
    """
    full_prompt = (system_prompt + "\n\n" + prompt) if system_prompt else prompt
    try:
        result = subprocess.run(
            ["qwenpaw", "agents", "chat",
             "--from-agent", "wordpress",
             "--to-agent", target_agent,
             "--text", full_prompt],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode != 0:
            log(f"AI error (rc={result.returncode}): {result.stderr[:200]}")
            return None
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
        if not reply:
            log(f"⚠️ AI reply empty after cleaning. Raw: {raw[:200]}")
            return None
        return reply
    except subprocess.TimeoutExpired:
        log("AI call timed out")
        return None
    except Exception as e:
        log(f"AI error: {e}")
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

def generate_ai_reply(customer_msg, sender_name, inbox_id):
    """Generate an AI reply for a customer message, routed by inbox_id.

    Uses INBOX_CONFIG[inbox_id] to pick the right AI agent, system prompt,
    and prompt template. Instructs AI to self-assess handoff need via [HANDOFF].
    """
    config = INBOX_CONFIG.get(inbox_id)
    if not config:
        log(f"No config for inbox #{inbox_id}, falling back to sourcing-agent")
        config = INBOX_CONFIG[1]

    prompt = config["prompt_template"].format(
        sender_name=sender_name,
        customer_msg=customer_msg
    )
    reply = call_qwenpaw_ai(prompt, config["system_prompt"],
                            target_agent=config["target_agent"])

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

# ===== MESSAGE HANDLER =====

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

    log(f"📩 [{config['name']}] New msg #{msg_id} from '{sender_name}' in conv #{conv_id}: {content[:100]}")

    # Generate AI reply with inbox-specific config
    log(f"🤖 [{config['name']}] Generating AI reply...")
    reply = generate_ai_reply(content, sender_name, inbox_id)
    if not reply:
        log(f"⚠️ [{config['name']}] Empty AI reply, skipping")
        return

    log(f"💬 [{config['name']}] AI reply: {reply[:150]}")

    # Check if AI thinks this needs human handoff
    needs_handoff = False
    if "[HANDOFF]" in reply:
        needs_handoff = True
        reply = reply.replace("[HANDOFF]", "").replace("\n[HANDOFF]", "").replace("[HANDOFF]\n", "").strip()
        log(f"🚩 [{config['name']}] AI detected handoff needed for conv #{conv_id}")

    # Send the reply (will be tracked in ai_sent_msg_ids)
    ok, resp_data = send_reply(conv_id, reply, headers)
    if ok:
        log(f"✅ Reply sent to conv #{conv_id}")
    else:
        log(f"❌ Failed to send reply: {resp_data}")

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
        self.reconnect_delay = 1
        self.last_pong = time.time()

    def on_open(self, ws):
        log("🟢 WebSocket connected")
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
            self.reconnect_delay = 1
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

    def _on_message_created(self, msg_data):
        """Handle a message_created event.

        Detects human agent messages (for handoff tracking)
        and processes incoming customer messages (for AI reply).
        """
        msg_id = msg_data.get("id")
        sender_type = msg_data.get("sender_type")
        conv_id = msg_data.get("conversation_id")

        # 🔑 Detect human agent messages (sender_type="User" that are NOT from AI)
        if sender_type == "User" and conv_id and msg_id:
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

        # Process incoming customer messages as before
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
        log(f"🔴 WS Error: {error}")

    def on_close(self, ws, status, msg):
        log(f"🔴 WebSocket closed (status={status}, msg={msg})")
        if self.running.is_set():
            self._reconnect()

    def _reconnect(self):
        delay = min(self.reconnect_delay, 60)
        log(f"Reconnecting in {delay}s...")
        time.sleep(delay)
        self.reconnect_delay = min(delay * 2, 60)
        self.start()

    def start(self):
        """Start WebSocket connection (blocking)."""
        self.headers = ensure_session()
        log(f"Connecting to {CW_WS_URL}")

        self.ws = websocket.WebSocketApp(
            CW_WS_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        # Run forever (blocks)
        self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_interval=15,
            ping_timeout=5,
            reconnect=5  # built-in reconnect
        )

    def stop(self):
        """Stop the WebSocket connection."""
        self.running.clear()
        if self.ws:
            self.ws.close()
        log("Agent stopped")

# ===== TIMEOUT CHECKER THREAD =====

def timeout_checker_loop():
    """Background thread that cleans up expired human_active entries."""
    while True:
        time.sleep(60)  # Check every minute
        try:
            clean_expired_human_active()
        except Exception as e:
            log(f"Timeout checker error: {e}")

# ===== MAIN =====

def main():
    parser = argparse.ArgumentParser(description="Chatwoot WebSocket AI Agent")
    parser.add_argument("--renew", action="store_true", help="Force renew session & exit")
    parser.add_argument("--test-ws", action="store_true", help="Test WebSocket connection & exit")
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

    log(f"🚀 Chatwoot WS Agent starting...")
    log(f"⚙️  Human timeout: {HUMAN_TIMEOUT_MINUTES}min")
    log(f"⚙️  Account ID: {CW_ACCOUNT_ID}")

    # Start the timeout checker daemon
    checker = Thread(target=timeout_checker_loop, daemon=True)
    checker.start()
    log("⏱️  Timeout checker started")

    # Start the main agent
    agent = WSAgent()
    try:
        agent.start()
    except KeyboardInterrupt:
        log("Shutting down...")
        agent.stop()

if __name__ == "__main__":
    main()

