#!/usr/bin/env python3
"""
数据库初始化脚本
手动运行以确保数据库被创建
"""
import sys
import sqlite3
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from topo.db.schema import Database
from topo.db.management_schema import (
    USERS_TABLE, MANAGED_DEVICES_TABLE, COLLECTION_TASKS_TABLE,
    OPERATION_LOGS_TABLE, UPLOAD_FILES_TABLE, SYSTEM_CONFIG_TABLE
)

def init_databases():
    """初始化数据库（所有表在一个数据库中）"""
    # 确保 data 目录存在
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    print(f"✓ 数据目录: {data_dir.absolute()}")
    
    # 初始化数据库（拓扑表+管理表）
    db_path = 'data/topology.db'
    print(f"\n初始化数据库: {db_path}")
    
    try:
        # 1. 创建拓扑表
        print(f"  创建拓扑表...")
        topo_db = Database(db_path)
        topo_db.connect()
        topo_db.init_schema()
        topo_db.close()
        print(f"  ✓ 拓扑表已创建")
        
        # 2. 创建管理表（在同一个数据库中）
        print(f"  创建管理表...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables = [
            ('users', USERS_TABLE),
            ('managed_devices', MANAGED_DEVICES_TABLE),
            ('collection_tasks', COLLECTION_TASKS_TABLE),
            ('operation_logs', OPERATION_LOGS_TABLE),
            ('upload_files', UPLOAD_FILES_TABLE),
            ('system_config', SYSTEM_CONFIG_TABLE)
        ]
        
        for table_name, sql in tables:
            cursor.execute(sql)
            print(f"    ✓ 表 {table_name}")
        
        conn.commit()
        conn.close()
        
        print(f"\n✓ 数据库已创建: {Path(db_path).absolute()}")
        
        # 验证
        db_exists = Path(db_path).exists()
        if db_exists:
            size = Path(db_path).stat().st_size
            print(f"  大小: {size} 字节")
            
            # 列出所有表
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"  表数量: {len(tables)}")
            print(f"\n✓ 所有数据库表初始化成功！")
            return True
        else:
            print(f"\n✗ 数据库未创建")
            return False
            
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import os
    print(f"当前工作目录: {os.getcwd()}\n")
    success = init_databases()
    sys.exit(0 if success else 1)
