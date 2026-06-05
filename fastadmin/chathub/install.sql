CREATE TABLE IF NOT EXISTS `__PREFIX__chathub_tenant` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_id` int(11) unsigned DEFAULT NULL COMMENT 'fa_user.id (创建者)',
  `tenant_name` varchar(100) NOT NULL DEFAULT '' COMMENT '租户名称',
  `domain` varchar(255) NOT NULL DEFAULT '' COMMENT '域名',
  `email` varchar(255) NOT NULL DEFAULT '' COMMENT 'Chatwoot登录邮箱',
  `inbox_id` int(11) DEFAULT NULL COMMENT 'Chatwoot Inbox ID',
  `inbox_token` varchar(100) DEFAULT NULL COMMENT 'Chatwoot Inbox Token',
  `team_id` int(11) DEFAULT NULL COMMENT 'Chatwoot Team ID',
  `agent_id` varchar(100) DEFAULT NULL COMMENT 'QwenPaw Agent ID',
  `agent_cw_id` int(11) DEFAULT NULL COMMENT 'Chatwoot Agent用户ID',
  `agent_cw_password` varchar(100) DEFAULT NULL COMMENT 'Chatwoot初始密码',
  `agent_name` varchar(100) DEFAULT NULL COMMENT 'QwenPaw Agent 名称',
  `max_agents` int(11) NOT NULL DEFAULT 3 COMMENT '最大坐席数',
  `channel_type` enum('web_widget','api','amazon','jd','taobao','pdd','tiktok') NOT NULL DEFAULT 'web_widget' COMMENT '通道类型',
  `status` enum('pending','provisioning','active','suspended','disabled') NOT NULL DEFAULT 'pending' COMMENT '状态',
  `config` text COMMENT '配置JSON',
  `embed_code` text COMMENT '嵌入代码',
  `api_credentials` text COMMENT 'API凭据JSON',
  `provisioned_at` datetime DEFAULT NULL COMMENT '开通时间',
  `expire_at` datetime DEFAULT NULL COMMENT '到期时间',
  `last_active_at` datetime DEFAULT NULL COMMENT '最后活跃时间',
  `createtime` int(10) DEFAULT NULL COMMENT '创建时间',
  `updatetime` int(10) DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_domain` (`domain`),
  KEY `idx_status` (`status`),
  KEY `idx_inbox_id` (`inbox_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ChatHub租户表';

CREATE TABLE IF NOT EXISTS `__PREFIX__chathub_log` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `tenant_id` int(11) unsigned NOT NULL DEFAULT 0 COMMENT '租户ID (0=系统级)',
  `action` varchar(50) NOT NULL DEFAULT '' COMMENT '操作类型 (register/renew/pay_notify_*/reprovision/...)',
  `detail` text COMMENT '操作详情',
  `status` enum('success','failed') NOT NULL DEFAULT 'success' COMMENT '状态',
  `operator` varchar(100) DEFAULT NULL COMMENT '操作人 (用户邮箱或system)',
  `createtime` int(10) DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_tenant_id` (`tenant_id`),
  KEY `idx_action` (`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ChatHub操作日志表';

CREATE TABLE IF NOT EXISTS `__PREFIX__chathub_order` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `order_no` varchar(50) NOT NULL COMMENT '订单号',
  `tenant_id` int(11) unsigned NOT NULL COMMENT '租户ID',
  `user_id` int(11) unsigned NOT NULL COMMENT '下单用户ID',
  `plan` varchar(20) NOT NULL COMMENT '方案 (basic/pro/enterprise)',
  `amount` decimal(10,2) NOT NULL COMMENT '金额',
  `pay_method` varchar(20) DEFAULT NULL COMMENT '支付方式 (alipay/wechat)',
  `pay_trade_no` varchar(100) DEFAULT NULL COMMENT '支付平台交易号',
  `status` enum('pending','paid','failed','refunded') NOT NULL DEFAULT 'pending' COMMENT '状态',
  `paid_at` datetime DEFAULT NULL COMMENT '支付完成时间',
  `expire_at` datetime DEFAULT NULL COMMENT '续期到期时间',
  `createtime` int(10) unsigned NOT NULL COMMENT '创建时间',
  `updatetime` int(10) unsigned DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_tenant_id` (`tenant_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ChatHub订单表';

CREATE TABLE IF NOT EXISTS `__PREFIX__chathub_channel_account` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `tenant_id` int(11) unsigned NOT NULL COMMENT '租户ID',
  `channel` enum('amazon','jd','taobao','pdd','tiktok') NOT NULL COMMENT '平台',
  `shop_id` varchar(100) DEFAULT NULL COMMENT '店铺ID',
  `shop_name` varchar(200) DEFAULT NULL COMMENT '店铺名称',
  `credentials_encrypted` varbinary(2048) NOT NULL COMMENT 'AES-256-GCM 加密凭据',
  `expires_at` datetime DEFAULT NULL COMMENT 'Access Token 过期时间',
  `status` enum('active','expired','error','paused') DEFAULT 'active' COMMENT '状态',
  `last_error` text COMMENT '最后一次错误',
  `last_refresh_at` datetime DEFAULT NULL COMMENT '上次刷新时间',
  `rate_limit_per_sec` int(10) unsigned DEFAULT 5 COMMENT '每秒请求上限',
  `createtime` int(10) DEFAULT NULL COMMENT '创建时间',
  `updatetime` int(10) DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_tenant_id` (`tenant_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ChatHub渠道账号表';

CREATE TABLE IF NOT EXISTS `__PREFIX__chathub_gateway_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `tenant_id` int(11) unsigned NOT NULL COMMENT '租户ID',
  `channel` enum('amazon','jd','taobao','pdd','tiktok') NOT NULL COMMENT '平台',
  `query_hash` char(64) NOT NULL COMMENT '查询内容 SHA256',
  `status` enum('success','cache_hit','rate_limited','breaker_open','error','timeout','no_creds') NOT NULL COMMENT '调用结果',
  `latency_ms` int(10) unsigned DEFAULT NULL COMMENT '延迟(毫秒)',
  `error_msg` varchar(500) DEFAULT NULL COMMENT '错误信息',
  `createtime` int(10) DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_tenant_id` (`tenant_id`),
  KEY `idx_channel_status` (`channel`,`status`),
  KEY `idx_createtime` (`createtime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ChatHub Gateway调用日志';
