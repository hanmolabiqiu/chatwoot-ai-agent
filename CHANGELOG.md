# Changelog

## v1.4 (2026-06-05) — 消息防抖 + AI 重试

### 新增
- **消息防抖 (Debounce)** — 同一会话 5 秒内到达的多条消息被自动累积合并，合并后发给 AI 一次处理，避免重复调用和混乱回复
  - 累积消息用 `\n---\n` 分隔，AI 获得完整上下文
  - 人工在此期间回复则跳过，兼容正常转人工流程
  - 日志标记：`⏳ Debounce` / `📦 Debounce: processing N merged msgs`
- **AI 错误重试 (Retry)** — `call_qwenpaw_ai()` 加入指数退避重试机制（最多 2 次重试，等待 1s/2s）
  - 覆盖超时、空回复、非零返回码、任意 Exception
  - 每步日志输出 retry 状态，最终失败标记 ERROR 级别

### 改进
- 调用方无需修改：`generate_ai_reply()`, `translate_to_chinese()` 自动受益于重试
- 防抖不影响人工检测优先级（`is_human_active` 仍在防抖前检查）

---

## v1.3 (2026-06-03) — 代码清理 + 监控 + 状态持久化

### 清理
- 删除 30+ 冗余 argparse 参数（1374 行 → 1025 行）
- 修复 f-string 嵌套引号语法错误
- 推送到 GitHub main 分支，打 v1.3 tag

### 新增
- **Metrics 监控** — WebSocket 连接状态、断连次数、每个 inbox 的 AI 回复成功率与响应时间
- **健康检查 CLI** — `--health` 参数输出 JSON 状态
- **日志分级** — INFO / WARN / ERROR 级别，每个 inbox 独立日志标识
- **状态持久化** — `ai_sent_msg_ids`、`human_active_convs`、`_ai_pending_convs` 每 30 秒写入 JSON 文件
- **启动恢复** — 加载 1 小时内快照（安全兜底）
- **配置验证** — `_validate_config()` 检查必要字段

---

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
