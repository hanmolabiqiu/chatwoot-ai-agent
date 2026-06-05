# FastAdmin ChatHub Addon

PHP frontend for the Chatwoot AI multi-tenant SaaS system, packaged as a FastAdmin addon (ThinkPHP 5).

## What this is

A self-contained FastAdmin plugin that provides the **user-facing** side of the platform: registration, plan selection, payment (Alipay/WeChat), member center, and channel credential management. All HTML is inlined in the controller (no `view/` templates, no FastAdmin render engine) — see "Architecture" below for why.

The **service-side** lives in this same monorepo, one level up: `gateway/` (in-process Python library), `chatwoot_ws_agent.py` (WebSocket agent), and `provision_server.py` (HTTP provisioning API). The addon talks to those via HTTP only.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                 FastAdmin ChatHub Addon (this dir)                │
│                                                                  │
│   public/  →  register / landing / my / channelAuth / payNotify   │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │  controller/Index.php (2108 lines)                       │    │
│   │   • All HTML inlined as PHP heredoc                      │    │
│   │   • POST to chathub-provision over HTTP/JSON             │    │
│   │   • _initialize() whitelists public + user actions       │    │
│   │   • Idempotency-Key for safe webhook retries             │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│   model/ChathubTenant.php  →  TP5 model with JSON getters         │
│   config.php               →  17 admin-fillable config fields    │
│   install.sql              →  5 tables (tenant/log/order/...)     │
└──────────────────────────────────┬───────────────────────────────┘
                                   │  HTTP/JSON
                                   ▼
              ┌──────────────────────────────────────┐
              │   chathub-provision (Python service) │
              │   :5566 /provision /suspend ...      │
              └──────────────────────────────────────┘
```

### Why no `view/` directory?

FastAdmin's template engine uses ThinkPHP's `view()` / `fetch()` with ThinkTemplate syntax. For this addon, we deliberately use pure `echo` + PHP heredoc strings inside the controller because:

1. **Single-file deploys** — the entire UI for `my()` and `register()` is in `controller/Index.php`, no template files to keep in sync.
2. **Dynamic flash messages** — the `FLASH_MESSAGE` placeholder is replaced via `str_replace` at the end of `my()` based on query string params (`?just_paid=1` / `?provisioning=1` / `?pending=1` / `?error=...`).
3. **No template-engine dependency** — works on any ThinkPHP 5 install without `think-template` package.

If you need to customize the UI, edit the heredoc strings inside `controller/Index.php` directly. Search for `register()` and `my()` for the two main render blocks.

## Routes (URL → controller action)

| URL | Action | Auth | Purpose |
|---|---|---|---|
| `/addons/chathub/index/landing` | `landing` | public | Landing page |
| `/addons/chathub/index/register` | `register` | public | Registration + plan selection |
| `/addons/chathub/index/login` | `login` | public | Login form |
| `/addons/chathub/index/doLogin` | `doLogin` | public | Login submit |
| `/addons/chathub/index/logout` | `logout` | public | Logout |
| `/addons/chathub/index/my` | `my` | user (session) | Member center (tenant list) |
| `/addons/chathub/index/channelList` | `channelList` | user | Choose a channel to bind |
| `/addons/chathub/index/channelAuth` | `channelAuth` | user | OAuth redirect (5 platforms) |
| `/addons/chathub/index/channelCallback` | `channelCallback` | user | OAuth callback |
| `/addons/chathub/index/reprovision` | `reprovision` | user | Manually retry provisioning |
| `/addons/chathub/index/payAlipay` | `payAlipay` | user | Start Alipay payment |
| `/addons/chathub/index/payWechat` | `payWechat` | user | Start WeChat payment |
| `/addons/chathub/index/payNotify` | `payNotify` | public (webhook) | Alipay/WeChat async callback |
| `/addons/chathub/index/payReturn` | `payReturn` | public (webhook) | Alipay/WeChat sync return |

## Install

### 1. Copy addon directory

```bash
cp -r fastadmin/chathub /www/sites/<your-site>/index/addons/
```

### 2. Run SQL

The 5 tables are defined in `install.sql` (uses `__PREFIX__` placeholder for FastAdmin table prefix). Run via phpMyAdmin or `mysql`:

```bash
mysql -u <user> -p <dbname> < install.sql
```

The script will substitute `__PREFIX__` with `fa_` (or whatever your `prefix` config is) — FastAdmin's `db()->execute()` does this automatically, or you can `sed` first.

If you already have a v1.0–v1.5 install, run `MIGRATIONS.md` instead.

### 3. Enable the addon

FastAdmin Admin → 插件管理 → local install → upload this dir → enable.

### 4. Configure

FastAdmin Admin → 插件管理 → ChatHub → 配置:

| Field | Example | Required |
|---|---|---|
| `provision_server_url` | `http://CoPaw:5566` | yes |
| `site_name` | `ChatHub` | yes |
| `chatwoot_url` | `https://chatwoot.example.com` | yes |
| `chatwoot_api_token` | (your personal access token) | yes |
| `alipay_app_id` / `alipay_merchant_private_key` / `alipay_public_key` | (from 支付宝开放平台) | if 支付宝 enabled |
| `wechat_app_id` / `wechat_mch_id` / `wechat_api_v3_key` / `wechat_cert_path` / `wechat_key_path` | (from 微信支付商户平台) | if 微信支付 enabled |

**Important:** All payment fields use sandbox values by default. Switch off `alipay_sandbox` / `wechat_sandbox` for production.

### 5. Verify

```bash
curl -I https://<your-site>/addons/chathub/index/landing
# should be HTTP 200
```

## Tenant lifecycle

```
register()         →  status='provisioning' (called from chathub-provision sync)
                     │
                     ├─ success  →  status='active' (embed_code populated)
                     │
                     └─ failure  →  status='pending' (user can retry from my.html)

payNotify()        →  _markOrderPaid() + _provisionAsync() if embed_code empty
                     │
                     └─ _provisionAsync() success → status='active' + embed_code written

reprovision()      →  user-initiated retry; same path as payNotify fallback
```

The `provisioning` state is **new in v1.6** (see MIGRATIONS.md). Before that, the state machine went straight `pending → active`, which meant a payment that succeeded but the chathub-provision call timed out left the user in a "paid but no embed code" limbo.

## Changelog (this component)

- **v1.8** — Payment flow completion: `_markOrderPaid` calls `_provisionAsync` on empty `embed_code`; new `reprovision` action; `payReturn` smart redirect (3 branches); `provisioning` state badge; schema migration
- **v1.6** — Channel bindings (`channelAuth` / `channelCallback`) for Amazon/JD/Taobao/PDD/TikTok
- **v1.0** — Initial release: register/login/my/landing

## License

AGPL v3 — see `LICENSE` and root `LICENSE`.

## Related

- `../gateway/` — Platform Gateway Python library (5 platform adapters)
- `../chatwoot_ws_agent.py` — WebSocket agent that calls Gateway
- `../provision_server.py` — HTTP provisioning API that the addon calls
- `../CHANGELOG.md` — Top-level changelog
