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
    """初始化所有数据库"""
    # 确保 data 目录存在
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    print(f"✓ 数据目录: {data_dir.absolute()}")
    
    # 初始化拓扑数据库
    topo_db_path = 'data/topology.db'
    print(f"\n初始化拓扑数据库: {topo_db_path}")
    try:
        topo_db = Database(topo_db_path)
        topo_db.connect()
        topo_db.init_schema()
        topo_db.close()
        print(f"✓ 拓扑数据库已创建: {Path(topo_db_path).absolute()}")
    except Exception as e:
        print(f"✗ 拓扑数据库初始化失败: {e}")
        return False
    
    # 初始化管理数据库
    mgmt_db_path = 'data/management.db'
    print(f"\n初始化管理数据库: {mgmt_db_path}")
    try:
        conn = sqlite3.connect(mgmt_db_path)
        cursor = conn.cursor()
        
        # 执行所有表的创建
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
            print(f"  ✓ 表 {table_name} 已创建")
        
        conn.commit()
        conn.close()
        print(f"✓ 管理数据库已创建: {Path(mgmt_db_path).absolute()}")
    except Exception as e:
        print(f"✗ 管理数据库初始化失败: {e}")
        return False
    
    # 验证
    print(f"\n数据库验证:")
    topo_exists = Path(topo_db_path).exists()
    mgmt_exists = Path(mgmt_db_path).exists()
    
    print(f"  拓扑数据库: {'✓' if topo_exists else '✗'} {Path(topo_db_path).absolute()}")
    print(f"  管理数据库: {'✓' if mgmt_exists else '✗'} {Path(mgmt_db_path).absolute()}")
    
    if topo_exists and mgmt_exists:
        print(f"\n✓ 所有数据库初始化成功！")
        return True
    else:
        print(f"\n✗ 部分数据库未创建")
        return False

if __name__ == '__main__':
    import os
    print(f"当前工作目录: {os.getcwd()}\n")
    success = init_databases()
    sys.exit(0 if success else 1)
