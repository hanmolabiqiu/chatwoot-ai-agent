#!/bin/bash
# Force correct env, then exec provision server
unset CW_BASE CW_INTERNAL CW_PLATFORM_TOKEN CW_ADMIN_EMAIL CW_ADMIN_PASSWORD CW_ACCOUNT_ID
export CW_BASE='http://chatwoot-chatwoot-1:3000'
export CW_INTERNAL='http://chatwoot-chatwoot-1:3000'
export CW_PLATFORM_TOKEN='csFwGySM0589tkhZHcLGJjfKLtYSgCGpcup9HSJZ9yE'
export CW_ADMIN_EMAIL='qiuzhida@greatqiu.cn'
export CW_ADMIN_PASSWORD='Qaly8980+'
export CW_ACCOUNT_ID='1'
export CHATHUB_API_KEY='chathub-default-key-change-me'
export GATEWAY_AES_KEY='uUjrtW3+w/rlBmGBOPv6rn7mP264bnOefkiQE9EL+X8='
export CHATHUB_DB_HOST='mysql'
export CHATHUB_DB_PORT='3306'
export CHATHUB_DB_USER='root'
export CHATHUB_DB_PASS='mysql_Py5N2W'
export CHATHUB_DB_NAME='chathub'
cd /app/working/workspaces/wordpress
exec python3 /app/working/workspaces/wordpress/provision_server.py 5566
