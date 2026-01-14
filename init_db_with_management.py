#!/usr/bin/env python3
"""
初始化数据库（包含管理表）
"""
import os
import sys

from topo.db.schema import Database


def main() -> int:
    print("正在初始化数据库（包含管理表）...")

    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print(
            "\nFATAL: 未设置 ADMIN_PASSWORD 环境变量，无法创建管理员账号。\n"
            "请先设置管理员密码，例如：\n"
            "  export ADMIN_PASSWORD='Your-Strong-Password'\n"
            "然后重新运行初始化脚本。",
            file=sys.stderr
        )
        return 1

    db = Database("topo.db")
    db.connect()

    try:
        db.init_schema(include_management=True)
    except ValueError as exc:
        print(f"\n初始化失败: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    print("\n✅ 数据库初始化完成！")
    print("\n管理员账号：")
    print(f"  用户名: {admin_username}")
    print("  密码: 使用 ADMIN_PASSWORD 环境变量提供")
    print("\n⚠️  如已有管理员账号，本次初始化不会重置密码。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
