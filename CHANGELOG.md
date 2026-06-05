# Changelog

## v1.7 (2026-06-05) — 对话上下文 + 客户画像 + 指数退避重连

### 新增
- **`--session-id` 对话上下文** — WS Agent 维护 `conv_id → session_id` 映射，每次调 `qwenpaw agents chat` 时传入 `--session-id`，AI 获得完整对话历史
  - 同一会话的连续消息不再断开上下文，AI 知道"刚才说过什么"
  - 持久化到状态文件，重启不丢失
  - 自动清理超过 10000 条的大映射表
- **对话摘要** — 每 15 轮 AI 回复后自动调用 AI 压缩历史，生成 1-2 句话摘要
  - 下次请求时将摘要注入 prompt 开头，减少 token 消耗
  - 长对话 AI 仍能记住核心信息（客户需求、讨论过的产品）
- **客户画像** — 维护 `contact_id → 画像` 映射（姓名、最近 3 次交互记录）
  - 每次 AI 回复后自动更新画像
  - 下次对话自动注入客户历史上下文
  - 持久化到状态文件，重启不丢失
- **WebSocket 指数退避重连** — 断线重连从固定 5s 改为指数退避
  - 初始 5s → 10s → 20s → 40s → 最大 60s
  - 重连前自动续期 Chatwoot session（防止长时间断线后 token 过期）
  - 失败时继续尝试，不会停止

### 文件
- `chatwoot_ws_agent.py` 从 1294 行增至 1459 行（+165 行）
- 新增 9 个函数：`_get_or_create_session`、`_prune_sessions`、`_summarize_conversation`、`_get_conversation_context`、`_update_contact_profile`、`_get_contact_context`
- 修改 4 个函数：`call_qwenpaw_ai`（+session_id）、`generate_ai_reply`（+session_id）、`handle_incoming_message`（+3 层 context）、`save_state/load_state`（+3 个持久化字段）
- 重写 1 个函数：`WSAgent.start`（指数退避重连）

---

## v1.6 (2026-06-05) — Platform Gateway + 5 平台 API 集成

### 新增
- **Platform Gateway 库** — 新的 `gateway/` Python 库，in-process 导入 ws_agent，0 网络跳
  - **Amazon PA-API 5** — AWS4-HMAC-SHA256 签名，13 个 marketplace 映射
  - **京东联盟** — MD5 签名，promotiongoodsinfo / goods.query 两个接口
  - **淘宝 TOP API** — MD5 签名，item.get / tbk.item.search 两个接口
  - **拼多多 DDK** — MD5 签名，ddk.goods.search / ddk.goods.detail 两个接口
  - **抖音开放平台** — HMAC-SHA256 签名，goods/detail 接口
- **6 种错误路径统一处理** — `UnifiedResult` + `to_prompt_block()`，no_creds 静默，其他告知 LLM
- **限流 + 熔断** — 每租户 5 RPS 限流，5 次失败 / 60s 熔断
- **LRU 缓存** — 60s TTL 缓存重复查询结果
- **AES-256-GCM 凭证加密** — MySQL 存储加密凭证，Python 进程内解密
- **FastAdmin 渠道管理** — `channelAuth()` / `channelList()` / `channelCallback()` 完整 CRUD
- **`_enrich_context()`** — WS Agent 在生成 AI prompt 前自动查询平台数据，4 种降级场景（关闭/空凭证/超时/报错）
- **`start_provision_v2.sh`** — 环境变量 wrapper（GATEWAY_AES_KEY + CHATHUB_DB_*）

### 架构
- `gateway/ARCHITECTURE.md` — 199 行 9 章节设计文档（库 vs 服务对比、签名算法、错误路径表）
- 13 个 Python 文件，1437 LOC

---

## v1.5 (2026-06-05) — 消息防抖 + AI 重试

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

## v1.4 (2026-06-05) — 多租户开通 + 安全性重构 + 数据脱敏

### 新增
- **provision_server HTTP 服务** — Bottle 框架，端口 5566，session 4-header 认证
- **Chatwoot 团队自动创建** — 每个租户创建 `"{店铺名} 客服团队"`，默认 3 席位
- **API Key 认证** — 所有 POST 端点需 `X-API-Key` 头部（env `CHATHUB_API_KEY`，默认 `chathub-default-key-change-me`）
- **幂等性支持** — `Idempotency-Key` 头，重复请求返回缓存原始响应
- **Chatwoot session 自动续期** — expiry < 1h 时自动重新登录
- **禁用 Inbox 机制** — 改名 + 清 channel + 关欢迎语（Chatwoot API 无真 disable）

### 安全重构
- 删除全部硬编码密钥：`CW_ADMIN_EMAIL`、`CW_ADMIN_PASSWORD`、`CW_PUBSUB_TOKEN` 均从环境变量读取
- `CW_ADMIN_EMAIL`/`CW_ADMIN_PASSWORD` 无 fallback，缺失抛异常
- PUBSUB_TOKEN 三级 fallback：env → auth file → login 响应，仍缺失抛异常
- 401 自动重试（最多 3 次）
- `print()` 全部替换为 `logging`

### 改进
- WS Agent 通过 supervisor `[program:ws_agent]` 管理，自动重启
- metrics 改用 `_dirty` 标记，每 30s flush，避免热路径 IO
- SIGTERM 优雅退出（signal handler → save_state → flush）
- PID 文件竞争通过 `/proc/PID/cmdline` 验证
- `_validate_config` 占位符校验（`{sender_name}` / `{customer_msg}`）

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
