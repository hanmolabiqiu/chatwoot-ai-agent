# Changelog

## v1.4 (2026-06-04) — 多租户开通 + 安全性重构

### 新增
- **provison_server.py** — 555 行 HTTP API 服务，支持 /provision /suspend /activate 端点
  - 自动创建 Chatwoot Inbox + Team + Agent 账号 + QwenPaw Agent + 路由配置
  - Chatwoot Team 管理：每个租户创建独立团队，席位限制（max_agents 默认 3）
  - 失败回滚：创建过程中出错自动删除已建资源
  - X-API-Key 头部认证，Idempotency-Key 幂等性支持（5 分钟 TTL）
  - Session 自动续期：expiry < 1h 时自动重新登录
  - 401 自动重试 3 次，非 JSON 响应错误处理
- **状态持久化** — WS Agent 每 30 秒保存 ai_sent_msg_ids / human_active_convs 到 JSON 文件，重启可恢复
- **会议室模式** — 开发团队 Inbox 消息同时转发多个 AI，`[SKIP]` 机制防重复回复
- **PIBSUB_TOKEN 三级 fallback** — 环境变量 → auth 文件 → login 响应，最后一级仅兜底尝试
- **supervisor 托管** — [program:ws_agent] 自动重启，与旧版 start_agent.sh 解耦

### 修复
- **硬编码凭证全面清除** — CW_EMAIL / CW_PASSWORD 改为环境变量必需，无默认 fallback
- **双重 WebSocket 重连** — 删除 _reconnect()，改为 run_forever(reconnect=5) 自动管理
- **内存泄漏** — ai_sent_msg_ids / processed_ids 无界增长，新增定期清理（上限 10000 条）
- **INBOX_CONFIG KeyError 崩溃** — 缺失配置时改为 skip + log，不再崩溃
- **PID 文件竞争** — /proc/PID/cmdline 验证，防止读取过期 PID
- **Metrics 热路径** — _dirty 标记 + 30 秒 flush，避免每次记录写磁盘
- **SIGTERM 优雅退出** — signal handler + save_state + metrics.flush
- _validate_config 占位符校验（sender_name / customer_msg）
- **幂等性正确实现** — 存储真实响应（含 HTTP 状态码），而非假 success
- **_disable_inbox 注释说明** — Chatwoot API 无真 disable 字段，改用改名+清 channel 方案

### 安全
- 所有敏感信息改为环境变量：CW_BASE / CW_EMAIL / CW_PASSWORD / CW_PLATFORM_TOKEN / CHATHUB_API_KEY
- .env.example 提供模板，.env / chatwoot_auth.json / inboxes.json 加入 .gitignore
- 代码内无硬编码 URL、邮箱、密码、token

---

## v1.3 (2026-06-03) — 监控运维 + 代码清理

### 新增
- **Metrics 监控类** — 跟踪 WebSocket 连接状态、断连次数、每个 inbox 的 AI 回复成功率和响应时间
- **DEFAULT_INBOX_CONFIG** — 硬编码兜底配置，`inboxes.json` 缺失时演示站仍正常工作
- **配置验证** — `_validate_config()` 检查必要字段，不合规配置告警
- **CLI 运维命令** — `--health`、`--metrics`、`--ws-status`、`--list-inboxes`、`--inbox-stats`、`--inbox-stats-csv`、`--inbox-stats-one-line`
- **日志分级** — INFO / WARN / ERROR，写入 `/var/log/chatwoot_ws_agent.log`

### 清理
- 删除 30+ 个冗余 `--inbox-stats-*` argparse 变体，保留 4 个实用格式
- 修复 f-string 嵌套引号语法错误
- 净减 349 行代码（1374 → 1025 行）

### 改进
- README 更新至 v1.3，补全文件列表、CLI 文档、架构图

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
