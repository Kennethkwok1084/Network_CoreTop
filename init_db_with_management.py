#!/usr/bin/env python3
"""
初始化数据库（包含管理表）
"""
from topo.db.schema import Database

if __name__ == "__main__":
    print("正在初始化数据库（包含管理表）...")
    
    db = Database("topo.db")
    db.connect()
    db.init_schema(include_management=True)
    db.close()
    
    print("\n✅ 数据库初始化完成！")
    print("\n默认管理员账号：")
    print("  用户名: admin")
    print("  密码: admin123")
    print("\n⚠️  请首次登录后立即修改密码！")
