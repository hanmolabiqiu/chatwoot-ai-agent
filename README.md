# Chatwoot AI Agent — 多租户 AI 自动回复系统

基于 Chatwoot ActionCable WebSocket 的实时 AI 客服系统，支持多租户、人工/AI 无缝切换、自动开通。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    QwenPaw Agent                      │
│  ┌─────────────────────┐  ┌──────────────────────┐   │
│  │   WS Agent           │  │  Provision Server     │   │
│  │   (WebSocket 长连接)  │  │  (HTTP API :5566)     │   │
│  │   • 接收实时消息       │  │  • 自动开通租户        │   │
│  │   • AI 自动回复        │  │  • 创建 Inbox/Team   │   │
│  │   • 人工/AI 切换       │  │  • 创建 AI Agent     │   │
│  │   • 多 Inbox 路由      │  │  • 写入路由配置       │   │
│  └─────────┬─────────────┘  └──────────┬───────────┘   │
│            │                           │               │
└────────────┼───────────────────────────┼───────────────┘
             │ WebSocket (wss)           │ HTTP API
             ▼                           ▼
    ┌────────────────┐        ┌──────────────────┐
    │    Chatwoot     │        │   FastAdmin       │
    │  (自托管客服系统)│◄───────│  (PHP 管理后台)    │
    └────────────────┘        └──────────────────┘
```

## 组件说明

### 1. WS Agent (`chatwoot_ws_agent.py`)

WebSocket 长连接实时 AI 客服，**1147 行**。

**核心技术：**
- **ActionCable WebSocket** — 通过 Chatwoot RoomChannel 实时接收消息事件，零轮询
- **多 Inbox 路由** — 根据 `inbox_id` 分发到不同 AI Agent，支持 30+ 租户并发
- **人工 ↔ AI 无缝切换** — 通过消息 ID 追踪 (`ai_sent_msg_ids`) + 对话 Pending 机制 (`_ai_pending_convs`) 精准区分 AI 回复和人工回复，不误判
- **15 分钟人工超时** — 人工回复后 AI 自动回避；超过 15 分钟无人工回复，AI 自动接回
- **会议模式** — 三人实时通信（开发团队 Inbox），消息同时转发多个 AI，`[SKIP]` 机制避免重复回复
- **状态持久化** — 每 30 秒保存到 JSON 文件，重启/崩溃后自动恢复（1 小时内快照安全兜底）
- **热加载配置** — `inboxes.json` 文件变化自动检测，无需重启进程
- **Metrics 监控** — 记录 WebSocket 连接状态、每个 Inbox 的 AI 回复成功率和响应时间
- **Graceful Shutdown** — SIGTERM 信号处理器，退出时保存状态和指标
- **内存保护** — `ai_sent_msg_ids` 和 `processed_ids` 定期清理，上限 10000 条

**AI 回复流程：**
```
客户发消息 → WS 接收 → is_human_active? → 跳过/回复
                                                  ↓
                                    call_qwenpaw_ai() → subprocess.qwenpaw agents chat
                                                  ↓
                                    send_reply() → Chatwoot API (以 User 身份发送)
                                                  ↓
                                    metrics.record_reply() 记录性能指标
```

### 2. Provision Server (`provision_server.py`)

HTTP API 服务，**555 行**，用于自动开通租户。

**端点：**
| 路径 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/provision` | POST | 创建租户（Inbox + 团队 + Agent + 路由配置） |
| `/suspend` | POST | 暂停租户（改名 + 清 Website URL + 关闭欢迎语） |
| `/activate` | POST | 恢复租户（恢复原名 + 重设 Website URL） |

**安全性：**
- 所有 POST 端点需 `X-API-Key` 头部认证
- 幂等性支持：`Idempotency-Key` 头部，5 分钟 TTL，返回真实响应（含正确 HTTP 状态码）
- 输入验证：name/domain/email/channel 格式校验
- Session 管理：自动检测 `expiry` 过期，提前 1 小时自动续期
- Chatwoot API 401 自动重试（3 次）

**幂等性机制：**
```python
# 使用字典存储 {key: response} + 线程锁，避免竞态
# 5 分钟自动过期
_IDEMPOTENT_RESULTS: dict[str, dict] = {}
_IDEMPOTENT_LOCK = threading.Lock()
_IDEMPOTENT_TTL = 300
```

### 3. 控制脚本 (`chatwoot_ws_ctl.sh`)

进程管理脚本，包含 PID 验证（`/proc/PID/cmdline` 防复用）。

## 消息路由配置 (`inboxes.json`)

```json
{
  "1": {
    "name": "GreatQiu",
    "type": "web_widget",
    "target_agent": "sourcing-agent",
    "system_prompt": "你是专业的外贸采购代理...",
    "prompt_template": "客户 '{sender_name}' 发来消息：\n{customer_msg}\n\n请回复..."
  },
  "7": {
    "name": "HALO Blog",
    "type": "web_widget",
    "target_agent": "halo-blog-agent",
    "system_prompt": "你是安防弱电专家...",
    "prompt_template": "..."
  }
}
```

## 人工/AI 切换机制详解

### 核心原理
AI 使用 **User Session** 发消息（不让客户察觉是 AI），通过追踪消息 ID 区分：

1. **AI 回复追踪**：`track_sent_message(msg_id)` 将 ID 存入 `ai_sent_msg_ids`
2. **竞态防护**：`_ai_pending_convs` 在 API 调用前标记对话为 Pending，`try/finally` 保证清理
3. **人工检测**：WS 事件到达时，检查 `is_ai_sent_message(msg_id)` 或 `conv_id in _ai_pending_convs`，任一命中则忽略
4. **超时恢复**：人工最后回复后 15 分钟无响应 → AI 自动接回
5. **状态恢复**：客户将对话改为 Pending → AI 立即恢复

```
时间线：
客户发消息 ──→ AI 回复 ──→ 人工介入 ──→ 人工离开 ──→ 15分钟超时 ──→ AI 接回
                ↑              ↑                              ↑
          ai_sent_msg_ids  mark_human_active()        human_active 过期
          加入 conv_id    conv_id 加入                 conv_id 被清理
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（详见 .env.example）
export CW_BASE=https://your-chatwoot.com
export CW_EMAIL=admin@example.com
export CW_PASSWORD=your-password

# 3. 登录 Chatwoot 获取 session
python3 chatwoot_ws_agent.py --renew

# 4. 启动 WS Agent
python3 chatwoot_ws_agent.py &

# 5. （可选）启动 Provision Server
python3 provision_server.py
```

## 环境变量

### WS Agent 必需
| 变量 | 说明 |
|------|------|
| `CW_BASE` | Chatwoot 服务器地址 |
| `CW_EMAIL` | 管理员账号邮箱 |
| `CW_PASSWORD` | 管理员密码 |
| `CW_PUBSUB_TOKEN` | Chatwoot ActionCable pubsub token（首次运行自动获取） |

### Provision Server 必需
| 变量 | 说明 |
|------|------|
| `CW_BASE` | Chatwoot 服务器地址 |
| `CW_ADMIN_EMAIL` | 管理员邮箱 |
| `CW_ADMIN_PASSWORD` | 管理员密码 |
| `CW_PLATFORM_TOKEN` | Chatwoot Platform API Token |
| `CHATHUB_API_KEY` | API 密钥（默认: chathub-default-key-change-me） |

## 文件结构

```
chatwoot-ai-agent/
├── chatwoot_ws_agent.py      # WebSocket AI Agent（核心，1147 行）
├── provision_server.py       # HTTP 开通服务（555 行）
├── chatwoot_ws_ctl.sh        # 进程管理脚本
├── start_agent.sh            # 启动脚本（旧，推荐用 supervisor）
├── .env.example              # 环境变量模板
├── requirements.txt          # Python 依赖
├── chatwoot_auth.example.json # Session 认证文件模板
├── inboxes.example.json      # 路由配置模板
└── .gitignore
```

## 版本历史

| 版本 | 说明 |
|------|------|
| v1.0 | 初始 WebSocket 版本，支持基本 AI 回复 |
| v1.1 | Amazon API 集成，人工/AI 切换修复 |
| v1.2 | 热加载配置架构 |
| v1.3 | 代码清理优化，Metrics 监控 |
| v1.4 | 多租户架构，Provision Server，状态持久化，安全性修复 |

## 许可证

MIT License
