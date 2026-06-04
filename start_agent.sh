#!/bin/sh
# ⚠️ WARNING: This script is deprecated. WS Agent is now managed by supervisor.
# Use: supervisorctl start ws_agent
#
# If you need to manually start (e.g. for debugging):
cd /app/working/workspaces/wordpress/skills/wordpress-cli
exec nohup python3 -u chatwoot_ws_agent.py > /var/log/chatwoot_ws_agent.log 2>&1 &
