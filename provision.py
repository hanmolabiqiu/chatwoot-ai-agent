#!/usr/bin/env python3
"""
Tenant Provisioning Script — Chatwoot AI Agent Platform
========================================================
Automatically creates a new tenant (inbox + AI agent) and registers it
in inboxes.json for the WS agent to pick up via hot-reload.

Usage:
  # Website Widget (独立站嵌入)
  python3 provision.py --name "MyShop" --type web_widget --domain myshop.com

  # API Inbox (亚马逊/TikTok等)
  python3 provision.py --name "AmazonStore" --type api --lang zh

  # With custom prompt
  python3 provision.py --name "TechSupport" --type web_widget --domain tech.com \
      --lang en --system-prompt "You are a tech support agent..."

Output:
  - Inbox ID, identifier, embed code (for widget) or API credentials
  - Writes to inboxes.json automatically
"""

import os, sys, json, argparse, time, requests
from pathlib import Path
from datetime import datetime, timezone

# ===== CONFIG =====
CW_BASE = os.environ.get("CW_BASE", "https://chatwoot.275763.xyz")
CW_ACCOUNT_ID = int(os.environ.get("CW_ACCOUNT_ID", "1"))
CW_API_BASE = f"{CW_BASE}/api/v1/accounts/{CW_ACCOUNT_ID}"

SCRIPT_DIR = Path(__file__).parent
AUTH_FILE = SCRIPT_DIR / "chatwoot_auth.json"
INBOX_CONFIG_FILE = SCRIPT_DIR / "inboxes.json"

# ===== AUTH =====
def get_headers():
    """Load session headers from auth file."""
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text())
            return {
                "access-token": data.get("access-token"),
                "client": data.get("client"),
                "expiry": data.get("expiry"),
                "uid": data.get("uid"),
                "Content-Type": "application/json",
            }
        except Exception as e:
            print(f"WARNING: Failed to load auth: {e}")
    print("ERROR: No valid auth. Run chatwoot_ws_agent.py --renew first.")
    sys.exit(1)

# ===== CHATWOOT API =====
def create_inbox(name, inbox_type, domain=None, headers=None):
    """Create a Chatwoot inbox via API.

    Args:
        name: Display name for the inbox
        inbox_type: 'web_widget' or 'api'
        domain: Website URL (required for web_widget)
        headers: Auth headers

    Returns:
        dict with inbox_id, identifier, etc.
    """
    if inbox_type == "web_widget" and not domain:
        print("ERROR: --domain required for web_widget type")
        sys.exit(1)

    payload = {"name": name}

    if inbox_type == "web_widget":
        # Ensure domain has protocol
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        payload["channel"] = {
            "type": "web_widget",
            "website_url": domain
        }
    elif inbox_type == "api":
        payload["channel"] = {"type": "api"}
    else:
        print(f"ERROR: Unknown inbox type: {inbox_type}")
        sys.exit(1)

    r = requests.post(f"{CW_API_BASE}/inboxes", json=payload, headers=headers, timeout=15)
    if r.status_code not in (200, 201):
        print(f"ERROR: Create inbox failed: {r.status_code} {r.text[:300]}")
        sys.exit(1)

    data = r.json()
    return {
        "inbox_id": data.get("id"),
        "name": data.get("name"),
        "identifier": data.get("webhook_url", ""),  # widget uses this
        "website_token": data.get("website_token", ""),
        "api_channel": data.get("channel", {}).get("type"),
    }

# ===== QWENPAW AGENT =====
def create_qwenpaw_agent(agent_id, display_name, lang="zh"):
    """Create a QwenPaw agent workspace + config.

    This creates the agent directory structure. The agent will be auto-detected
    by QwenPaw on next restart or config reload.

    Returns:
        Path to the agent workspace
    """
    # Determine workspace path
    qwenpaw_base = Path(os.environ.get("QWENPAW_WORKING_DIR", "/app/working/workspaces"))
    agent_dir = qwenpaw_base / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Create agent.json
    agent_config = {
        "id": agent_id,
        "name": display_name,
        "description": f"Auto-provisioned agent for {display_name}",
        "workspace_dir": str(agent_dir),
        "enabled": True,
    }
    (agent_dir / "agent.json").write_text(json.dumps(agent_config, indent=2))

    # Create basic SOUL.md
    if lang == "zh":
        soul = f"""# {display_name} AI 客服

你是 {display_name} 的 AI 客服助手。

## 职责
- 专业、友善地回答客户问题
- 无法处理时标记 [HANDOFF] 请求人工介入
- 保持简洁，2-4句话回复

## 风格
- 用中文回复
- 语气专业但不死板
- 直接回答，不绕弯子
"""
    else:
        soul = f"""# {display_name} AI Customer Service

You are the AI customer service agent for {display_name}.

## Responsibilities
- Answer customer questions professionally and friendly
- Mark [HANDOFF] when human intervention is needed
- Keep replies concise (2-4 sentences)

## Style
- Professional but approachable
- Direct answers, no fluff
"""
    (agent_dir / "SOUL.md").write_text(soul)

    # Create empty PROFILE.md
    (agent_dir / "PROFILE.md").write_text(f"# {display_name} Agent Profile\n\nAuto-provisioned.\n")

    print(f"  Agent workspace: {agent_dir}")
    return agent_dir

# ===== INBOXES.JSON =====
def update_inboxes_config(inbox_id, name, inbox_type, agent_id, lang="zh"):
    """Add new inbox to inboxes.json."""
    # Load existing
    config = {}
    if INBOX_CONFIG_FILE.exists():
        try:
            config = json.loads(INBOX_CONFIG_FILE.read_text())
        except Exception:
            pass

    # Default prompts by language
    if lang == "zh":
        system_prompt = f"你是 {name} 的 AI 客服助手。专业回复客户问题，需要人工时加 [HANDOFF]。"
        prompt_template = "客户 '{sender_name}' 发来消息：\n\n{customer_msg}\n\n直接回复，简洁专业（2-4句话）。用中文。"
        note_prefix = f"🤖 AI 自动回复 ({name})"
        signature = f"- {name} 客服"
    else:
        system_prompt = f"You are the AI customer service agent for {name}. Answer professionally. Add [HANDOFF] when human intervention is needed."
        prompt_template = "Customer '{sender_name}' sent this message:\n\n{customer_msg}\n\nWrite a direct reply (no preamble, no markdown). Keep it concise (2-4 sentences). Use the same language as the customer."
        note_prefix = f"🤖 AI Auto-Reply ({name})"
        signature = f"- {name} Team"

    # Add/update entry
    config[str(inbox_id)] = {
        "name": name,
        "type": inbox_type,
        "target_agent": agent_id,
        "system_prompt": system_prompt,
        "prompt_template": prompt_template,
        "note_prefix": note_prefix,
        "signature": signature,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Update meta
    config["_meta"] = {
        "version": "1.1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Chatwoot WS Agent inbox routing config — hot-reloadable",
    }

    INBOX_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"  Config written: {INBOX_CONFIG_FILE}")

# ===== MAIN =====
def main():
    parser = argparse.ArgumentParser(description="Provision a new tenant inbox + AI agent")
    parser.add_argument("--name", required=True, help="Tenant display name")
    parser.add_argument("--type", required=True, choices=["web_widget", "api"],
                        help="Inbox type: web_widget (website) or api (platform)")
    parser.add_argument("--domain", default=None, help="Website domain (required for web_widget)")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="Language (default: zh)")
    parser.add_argument("--agent-id", default=None, help="Custom agent ID (default: auto-generated)")
    parser.add_argument("--system-prompt", default=None, help="Custom system prompt (overrides default)")
    args = parser.parse_args()

    # Generate agent ID
    agent_id = args.agent_id or f"agent-{args.name.lower().replace(' ', '-')}"

    print(f"\n{'='*50}")
    print(f"  Provisioning: {args.name}")
    print(f"  Type: {args.type}")
    print(f"  Agent: {agent_id}")
    print(f"{'='*50}\n")

    # Step 1: Create Chatwoot inbox
    print("[1/3] Creating Chatwoot inbox...")
    headers = get_headers()
    inbox_info = create_inbox(args.name, args.type, args.domain, headers)
    inbox_id = inbox_info["inbox_id"]
    print(f"  Inbox #{inbox_id}: {inbox_info['name']}")

    # Step 2: Create QwenPaw agent
    print("[2/3] Creating AI agent...")
    agent_dir = create_qwenpaw_agent(agent_id, args.name, args.lang)

    # Step 3: Update inboxes.json
    print("[3/3] Updating routing config...")
    update_inboxes_config(inbox_id, args.name, args.type, agent_id, args.lang)

    # Override system prompt if provided
    if args.system_prompt:
        import inboxes_config_helper  # noqa - if exists
        # Manual override
        config = json.loads(INBOX_CONFIG_FILE.read_text())
        config[str(inbox_id)]["system_prompt"] = args.system_prompt
        INBOX_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        print(f"  Custom system prompt applied")

    # Print summary
    print(f"\n{'='*50}")
    print(f"  ✅ PROVISIONING COMPLETE")
    print(f"{'='*50}")
    print(f"  Inbox ID:    {inbox_id}")
    print(f"  Agent ID:    {agent_id}")
    print(f"  Agent Dir:   {agent_dir}")

    if args.type == "web_widget":
        token = inbox_info.get("website_token", "")
        print(f"\n  📋 Widget Embed Code:")
        print(f"  <script>")
        print(f"    window.chatwootSettings = {{}};")
        print(f"    (function(d,t) {{")
        print(f"      var BASE_URL=\"{CW_BASE}\";")
        print(f"      var g=d.createElement(t),s=d.getElementsByTagName(t)[0];")
        print(f"      g.src=BASE_URL+'/packs/js/sdk.js';")
        print(f"      g.async=!0;")
        print(f"      s.parentNode.insertBefore(g,s);")
        print(f"      g.onload=function(){{")
        print(f"        window.chatwootSDK.run({{")
        print(f"          websiteToken: '{token}',")
        print(f"          baseUrl: BASE_URL")
        print(f"        }})")
        print(f"      }}")
        print(f"    }})(document,'script');")
        print(f"  </script>")
    elif args.type == "api":
        print(f"\n  📋 API Credentials:")
        print(f"  Inbox ID:     {inbox_id}")
        print(f"  (Use Chatwoot API to create conversations and send messages)")

    print(f"\n  ⚡ WS Agent will auto-detect this inbox within 30s (hot-reload)")
    print(f"  ⚡ Restart QwenPaw to register the new agent: qwenpaw daemon restart")
    print()

if __name__ == "__main__":
    main()
