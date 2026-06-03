# Chatwoot AI Agent — Multi-Inbox Intelligent Customer Service

> A multi-tenant AI customer service platform built on self-hosted Chatwoot.  
> Single WebSocket agent routes conversations to different AI agents per inbox — with seamless AI ↔ Human handoff.

## Architecture

```
Customer (Web Widget / API)
        │
        ▼
Chatwoot Self-Hosted (wss://chatwoot.275763.xyz/cable)
        │
        ▼
  WS Agent (chatwoot_ws_agent.py)
   │  reads inboxes.json → routes by inbox_id
   │
   ├── Inbox 1  →  sourcing-agent     (EN, 采购代理)
   ├── Inbox 7  →  halo-blog-agent    (中文, 安防弱电顾问)
   └── Inbox 8  →  amazon-agent       (EN, Amazon 客服)
```

## Features

| Feature | Description |
|:--------|:-----------|
| **24/7 AI Auto-Reply** | AI responds instantly, acts as human agent (uses User session, not AgentBot) |
| **AI ↔ Human Handoff** | Human replies → AI backs off. Human leaves → AI resumes after 15min timeout |
| **Multi-Inbox Routing** | Single WS agent serves multiple sites/inboxes, each with its own AI agent & knowledge base |
| **Hot-Reload Config** | `inboxes.json` — add/edit inboxes without restarting the agent (30s polling) |
| **Auto-Provision** | `provision.py` — one command to create Chatwoot inbox + AI agent + routing config |
| **Health & Metrics** | CLI: `--health`, `--metrics`, `--ws-status`, `--list-inboxes`, `--inbox-stats` |
| **Default Fallback** | Hardcoded `DEFAULT_INBOX_CONFIG` ensures demo sites work even without `inboxes.json` |
| **Private Notes** | AI auto-generates Chinese notes for human agents on each reply |
| **Zero Monthly Fee** | Self-hosted Chatwoot + QwenPaw, no SaaS subscription |

## Routing Matrix

| Inbox | Site | Agent | Lang | Role |
|:-----:|:-----|:------|:----:|:-----|
| 1 | greatqiu.cn | sourcing-agent | EN | Global Sourcing Advisor |
| 7 | shopqiu.com | halo-blog-agent | 中文 | 安防弱电技术顾问 |
| 8 | Amazon (API) | amazon-agent | EN | Amazon Customer Service |

## Quick Start

```bash
git clone https://github.com/hanmolabiqiu/chatwoot-ai-agent.git
cd chatwoot-ai-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Chatwoot API credentials
python3 chatwoot_ws_agent.py
```

### CLI Commands

```bash
python3 chatwoot_ws_agent.py              # Start the WS agent
python3 chatwoot_ws_agent.py --health     # Health check (JSON)
python3 chatwoot_ws_agent.py --metrics    # Performance metrics (JSON)
python3 chatwoot_ws_agent.py --ws-status  # WebSocket connection status
python3 chatwoot_ws_agent.py --list-inboxes  # List configured inboxes
python3 chatwoot_ws_agent.py --inbox-stats   # Formatted inbox statistics table
python3 chatwoot_ws_agent.py --inbox-stats-csv  # Stats as CSV
python3 chatwoot_ws_agent.py --inbox-stats-one-line  # One-line summary
python3 chatwoot_ws_agent.py --renew      # Force session renew
python3 chatwoot_ws_agent.py --test-ws    # Test WebSocket connection
```

### Add a New Tenant

```bash
python3 provision.py --name "NewSite" --type web_widget --lang en
# Output: inbox ID, agent ID, embed code
```

## File Structure

```
chatwoot-ai-agent/
├── chatwoot_ws_agent.py        # Core engine — WS agent with multi-inbox routing
├── inboxes.json                # Hot-reloadable inbox routing config
├── provision.py                # Auto-provision new tenants
├── CHANGELOG.md                # Version history (v1.0 → v1.3)
├── knowledge-base.md           # Knowledge base for halo-blog-agent
├── SOUL-halo-blog-agent.md     # AI personality — 安防弱电 (Chinese)
├── SOUL-amazon-agent.md        # AI personality — Amazon CS (English)
├── PROFILE-amazon-agent.md     # Amazon agent profile
├── .env.example                # Environment config template
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── .gitignore
```

## Version History

| Ver | Date | Highlights |
|:----|:-----|:-----------|
| v1.3 | 2026-06-03 | Metrics monitoring, health check CLI, default config fallback, inbox-stats cleanup |
| v1.2 | 2026-06-02 | Hot-reload `inboxes.json`, `provision.py` auto-provision |
| v1.1 | 2026-06-02 | Amazon API inbox, API inbox human detection fix |
| v1.0 | 2026-06-01 | Initial: dual inbox routing, AI↔Human handoff, knowledge base |

## Roadmap

- [x] Multi-inbox routing (GreatQiu + HALO + Amazon)
- [x] Hot-reload config (`inboxes.json`)
- [x] Auto-provision script (`provision.py`)
- [x] Health check & metrics monitoring
- [ ] FastAdmin management backend (ChatHub plugin)
- [ ] Tenant self-service registration + payment
- [ ] WhatsApp Business API channel
- [ ] Chatwoot Captain AI integration
- [ ] Automated backup & alerting

## License

MIT
