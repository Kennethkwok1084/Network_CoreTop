#!/bin/bash
# 快速生成并设置环境变量

echo "🔑 生成安全密钥..."
echo ""

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ADMIN_PASSWORD=$(python3 -c "import secrets; print('Admin_' + secrets.token_urlsafe(12))")

echo "export SECRET_KEY='${SECRET_KEY}'"
echo "export FERNET_KEY='${FERNET_KEY}'"
echo "export ADMIN_PASSWORD='${ADMIN_PASSWORD}'"
echo "export ADMIN_USERNAME='admin'"
echo ""
echo "✅ 复制上面的命令并运行，然后执行:"
export SECRET_KEY="${SECRET_KEY}"
export FERNET_KEY="${FERNET_KEY}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD}"
export ADMIN_USERNAME="admin"
bash "start_web_management.sh"

