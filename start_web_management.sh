#!/bin/bash
# GCC 拓扑管理系统 - 快速启动脚本

set -e

echo "🌐 GCC 网络拓扑自动化管理系统"
echo "================================"
echo ""

# 必需的安全配置
if [ -z "$SECRET_KEY" ]; then
    echo "❌ 未设置 SECRET_KEY 环境变量"
    echo "   生成一个强密钥: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    echo "   然后设置: export SECRET_KEY='<生成的密钥>'"
    exit 1
fi

# FERNET_KEY 用于加密设备密码（缺失时仅提示）
if [ -z "$FERNET_KEY" ] && [ ! -f "$HOME/.topo_fernet_key" ]; then
    echo "⚠️  未检测到 FERNET_KEY，将无法保存设备密码"
    echo "   生成密钥: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo "   设置环境变量: export FERNET_KEY='<生成的密钥>'"
    echo "   或保存到: ~/.topo_fernet_key"
    echo ""
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 未找到虚拟环境，请先运行:"
    echo "   python3 -m venv .venv"
    echo "   source .venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# 检查数据库
if [ ! -f "topo.db" ]; then
    if [ -z "$ADMIN_PASSWORD" ]; then
        echo "❌ 未设置 ADMIN_PASSWORD，无法初始化管理员账号"
        echo "   设置环境变量: export ADMIN_PASSWORD='<强密码>'"
        exit 1
    fi
    echo "📦 初始化数据库..."
    .venv/bin/python init_db_with_management.py
    echo ""
fi

# 启动服务器
echo "🚀 启动 Web 管理系统..."
echo ""
echo "访问地址: http://127.0.0.1:5000"
echo "管理员账号: ${ADMIN_USERNAME:-admin} (密码来自 ADMIN_PASSWORD)"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "================================"
echo ""

.venv/bin/python -m topo.web.app_v2 --port 5000 --host 0.0.0.0
