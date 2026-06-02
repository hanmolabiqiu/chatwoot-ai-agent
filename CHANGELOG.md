# Changelog

## v1.2 (2026-06-02) — 多租户架构：热加载 + 自动开通

### 新增
- **`inboxes.json`** — 外部配置文件，WS Agent 每 30 秒检测变化自动热加载，新增 inbox 无需重启
- **`provision.py`** — 一键开通脚本：自动建 Chatwoot Inbox + QwenPaw Agent + 写入路由配置，输出嵌入代码

### 改进
- **WS Agent 架构重构** — `INBOX_CONFIG` 从硬编码改为从 `inboxes.json` 动态读取，支持在线新增/修改/删除 inbox
- **超时检查线程** — 同时负责清理过期人工超时 + 热加载配置

### 待做
- FastAdmin 管理后台对接 provision.py
- 租户自助注册 + 支付

---

## v1.1 (2026-06-02) — Amazon 集成 + 人工检测修复

### 新增
- **Amazon API Inbox 集成** — 创建 Inbox 8 (Channel::Api)，支持 Amazon 客户消息路由到 amazon-agent AI 自动回复
- **多 Inbox 路由** — 支持 Inbox 1 (GreatQiu 采购) / Inbox 7 (HALO 博客) / Inbox 8 (Amazon) 三路并行

### 修复
- **API Inbox 人工消息检测** — Channel::Api 发送的消息 sender_type 为 "Contact" 而非 "User"，原检测抓不到，新增 `message_type=1` 兜底检测
- **amazon-agent ID 不匹配** — agent ID 为 `9hxc2Y` 但 INBOX_CONFIG 配置了名称 `amazon-agent`，qwenpaw CLI 查不到导致 AI 空回复

### 配置
- Amazon agent 模型从 xiaomi/mimo-v2.5-pro 改为 opencode/big-pickle

---

## v1.0 (2026-06-01) — 初始版本

### 功能
- **Chatwoot WebSocket AI 客服** — 基于 ActionCable 实时双向通道
- **GreatQiu 采购助手** — Inbox 1 (WebWidget), 英文 sourcing-agent, 自动回复采购询盘
- **HALO 博客技术顾问** — Inbox 7 (WebWidget), 中文 halo-blog-agent, 安防弱电知识库
- **AI ↔ 人工无缝切换**
  - 人工回复后 AI 自动回避
  - 15 分钟超时后 AI 自动接回
  - 会话状态改为 Pending/Resolved 后 AI 恢复
  - AI 识别到需要人工介入 → [HANDOFF] 标记 + 通知坐席
- **私密备注** — 每次 AI 回复后自动写中文备注，方便人工排查
- **HALO 博客兼容** — Pjax 无刷新跳转 + CSP frame-ancestors 适配
- **GitHub 代码管理** — 仓库 `hanmolabiqiu/chatwoot-ai-agent`
