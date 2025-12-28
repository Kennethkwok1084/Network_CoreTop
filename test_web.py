#!/usr/bin/env python3
"""测试 Web 服务器"""
from topo.web.app import create_app

if __name__ == '__main__':
    app = create_app('topo.db')
    print("🚀 启动 Web 服务器: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=False)
