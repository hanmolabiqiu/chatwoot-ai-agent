# Chathub FastAdmin Addon — Migrations

This file documents schema migrations applied to the chathub tables between releases. Always back up your database before applying migrations.

## v1.6 — channel_type + status enum extension

**Date:** 2026-06-05
**Reason:** Support 5 platform integrations (Amazon/京东/淘宝/拼多多/抖音) and add explicit "provisioning" state in tenant lifecycle.

### `fa_chathub_tenant`

```sql
ALTER TABLE `fa_chathub_tenant`
  ADD COLUMN `user_id` INT(11) UNSIGNED DEFAULT NULL COMMENT 'fa_user.id (创建者)' AFTER `id`,
  ADD COLUMN `team_id` INT(11) DEFAULT NULL COMMENT 'Chatwoot Team ID' AFTER `inbox_token`,
  ADD COLUMN `max_agents` INT(11) NOT NULL DEFAULT 3 COMMENT '最大坐席数' AFTER `agent_name`,
  ADD COLUMN `expire_at` DATETIME DEFAULT NULL COMMENT '到期时间' AFTER `provisioned_at`,
  ADD KEY `idx_user_id` (`user_id`),
  MODIFY COLUMN `channel_type` ENUM('web_widget','api','amazon','jd','taobao','pdd','tiktok') NOT NULL DEFAULT 'web_widget' COMMENT '通道类型',
  MODIFY COLUMN `status` ENUM('pending','provisioning','active','suspended','disabled') NOT NULL DEFAULT 'pending' COMMENT '状态';
```

### `fa_chathub_log`

```sql
ALTER TABLE `fa_chathub_log`
  MODIFY COLUMN `tenant_id` INT(11) UNSIGNED NOT NULL DEFAULT 0 COMMENT '租户ID (0=系统级)';
```

### New tables

```sql
-- v1.8 支付订单
CREATE TABLE IF NOT EXISTS `fa_chathub_order` (
  ... (see install.sql for full schema)
);

-- v1.6 渠道账号 (5 平台)
CREATE TABLE IF NOT EXISTS `fa_chathub_channel_account` (
  ... (see install.sql for full schema)
);

-- v1.6 Gateway 调用日志
CREATE TABLE IF NOT EXISTS `fa_chathub_gateway_log` (
  ... (see install.sql for full schema)
);
```

## Rollback

```sql
-- v1.6 rollback
ALTER TABLE `fa_chathub_tenant`
  DROP COLUMN `user_id`,
  DROP COLUMN `team_id`,
  DROP COLUMN `max_agents`,
  DROP COLUMN `expire_at`,
  DROP KEY `idx_user_id`,
  MODIFY COLUMN `channel_type` ENUM('web_widget','api') NOT NULL DEFAULT 'web_widget' COMMENT '通道类型',
  MODIFY COLUMN `status` ENUM('pending','active','suspended','disabled') NOT NULL DEFAULT 'pending' COMMENT '状态';
DROP TABLE IF EXISTS `fa_chathub_order`;
DROP TABLE IF EXISTS `fa_chathub_channel_account`;
DROP TABLE IF EXISTS `fa_chathub_gateway_log`;
```

## Notes

- The `provisioning` status was added because the previous 4-state machine (pending→active→suspended→disabled) had no slot for "paid but Chatwoot resources not yet provisioned". After payNotify, the tenant enters `provisioning` briefly while the chathub-provision service creates Inbox/Team/Agent, then transitions to `active`. If provisioning fails, status reverts to `pending` and the user can click "重新开通" to retry.
- The `channel_type` enum now has 7 values. The original 2 (web_widget/api) are still functional; the 5 new ones (amazon/jd/taobao/pdd/tiktok) are routed through `gateway/` Python library on the WS agent side.
