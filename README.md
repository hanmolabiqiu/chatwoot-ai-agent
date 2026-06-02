# Chatwoot AI Agent — Multi-Inbox Intelligent Customer Service

> **v1.0 — The Ancestor Version**  
> The foundation of a multi-tenant AI customer service platform built on self-hosted Chatwoot.

## Architecture Overview

```
Customer (via Web Widget)
        │
        ▼
Chatwoot Self-Hosted (wss://)
        │
        ▼
Chatwoot WS Agent ←── INBOX_CONFIG routing
   │          │
   ▼          ▼
sourcing-agent  halo-blog-agent
 (Inbox 1)      (Inbox 7)
 English        简体中文
```

### Core Features

| Feature | Description |
|:---------|:------------|
| **7×24 AI Auto-Reply** | AI responds instantly to customer inquiries |
| **AI ↔ Human Handoff** | Seamless switching: human replies → AI backs off; human leaves → AI resumes (15min timeout) |
| **Customer-Unaware** | AI uses User session, not AgentBot — customer sees "agent reply" |
| **Multi-Inbox Routing** | Single WS agent routes by `inbox_id` to different AI agents & knowledge bases |
| **Private Notes** | AI auto-generates Chinese translation notes for human agents |
| **Offline Resilience** | Bubble stays visible even when no agent is online |
| **Zero Monthly Fee** | Self-hosted Chatwoot + QwenPaw, no SaaS subscription |

### Routing Matrix

| Inbox ID | Site | AI Agent | Language | Role |
|:--------:|:-----|:---------|:--------:|:-----|
| 1 | greatqiu.cn | sourcing-agent | EN | Global Sourcing Advisor |
| 7 | shopqiu.com | halo-blog-agent | 简体中文 | 安防弱电技术顾问 |

## Quick Start

### Prerequisites
- Python 3.8+
- Self-hosted [Chatwoot](https://www.chatwoot.com/) instance
- [QwenPaw](https://qwenpaw.dev/) (or any OpenAI-compatible API)

### Installation

```bash
git clone https://github.com/hanmolabiqiu/chatwoot-ai-agent.git
cd chatwoot-ai-agent
pip install -r requirements.txt
```

### Configuration

Copy and edit the environment file:

```bash
cp .env.example .env
```

Configure your Chatwoot API credentials and AI model settings in `.env`.

### Run

```bash
python3 chatwoot_ws_agent.py
```

The agent will connect to Chatwoot via WebSocket and start listening for messages.

## Project Structure

```
chatwoot-ai-agent/
├── chatwoot_ws_agent.py     # Main WS agent — the core engine
├── knowledge-base.md         # Knowledge base for halo-blog-agent
├── SOUL-halo-blog-agent.md   # AI personality for 安防弱电 (Chinese)
├── .env.example              # Environment configuration template
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── .gitignore                # Git ignore rules
```

## Version History

| Version | Date | Highlights |
|:--------|:-----|:-----------|
| v1.0 | 2026-05-31 | Initial release — dual inbox routing, AI↔Human handoff, knowledge base |

## Roadmap

- [ ] **Config Center** — Dynamic INBOX_CONFIG from database instead of hardcoded
- [ ] **Multi-Tenant Platform** — Auto-provision inboxes on payment, user self-service dashboard
- [ ] **Amazon API Integration** — Product research, order management, customer message sync
- [ ] **TikTok Channel** — Social commerce integration
- [ ] **Tenant Knowledge Base UI** — Self-managed KB per tenant
- [ ] **Seat-Based Billing** — Pay-per-agent pricing model

## License

MIT
