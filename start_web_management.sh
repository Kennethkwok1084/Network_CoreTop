#!/bin/bash
# GCC 拓扑管理系统 - 快速启动脚本

set -e

echo "🌐 GCC 网络拓扑自动化管理系统"
echo "================================"
echo ""

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
    echo "📦 初始化数据库..."
    .venv/bin/python init_db_with_management.py
    echo ""
fi

# 启动服务器
echo "🚀 启动 Web 管理系统..."
echo ""
echo "访问地址: http://127.0.0.1:5000"
echo "默认账号: admin / admin123"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "================================"
echo ""

.venv/bin/python -m topo.web.app_v2 --port 5000 --host 0.0.0.0
