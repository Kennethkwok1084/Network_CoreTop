"""
数据库迁移脚本：添加设备上联配置字段
执行时间：2024-01
目的：支持手动配置设备连接到核心交换机的特定接口
"""

import sqlite3
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate(db_path='data/topology.db'):
    """添加上联配置字段到managed_devices表"""
    
    if not os.path.exists(db_path):
        print(f"错误：数据库文件 {db_path} 不存在")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(managed_devices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_applied = []
        
        # 添加 uplink_device_id 字段
        if 'uplink_device_id' not in columns:
            print("添加 uplink_device_id 字段...")
            cursor.execute("""
                ALTER TABLE managed_devices 
                ADD COLUMN uplink_device_id INTEGER 
                REFERENCES managed_devices(id)
            """)
            migrations_applied.append('uplink_device_id')
        else:
            print("字段 uplink_device_id 已存在，跳过")
        
        # 添加 uplink_interface 字段
        if 'uplink_interface' not in columns:
            print("添加 uplink_interface 字段...")
            cursor.execute("""
                ALTER TABLE managed_devices 
                ADD COLUMN uplink_interface TEXT
            """)
            migrations_applied.append('uplink_interface')
        else:
            print("字段 uplink_interface 已存在，跳过")
        
        # 添加 uplink_type 字段
        if 'uplink_type' not in columns:
            print("添加 uplink_type 字段...")
            cursor.execute("""
                ALTER TABLE managed_devices 
                ADD COLUMN uplink_type TEXT DEFAULT 'auto'
            """)
            migrations_applied.append('uplink_type')
        else:
            print("字段 uplink_type 已存在，跳过")
        
        # 创建索引提高查询性能
        if migrations_applied:
            print("创建索引...")
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_uplink_device 
                    ON managed_devices(uplink_device_id)
                """)
                print("索引创建成功")
            except Exception as e:
                print(f"索引创建失败（可能已存在）: {e}")
        
        conn.commit()
        
        if migrations_applied:
            print(f"\n✅ 迁移成功！已添加字段: {', '.join(migrations_applied)}")
        else:
            print("\n✅ 所有字段已存在，无需迁移")
        
        # 显示表结构
        print("\n当前 managed_devices 表结构：")
        cursor.execute("PRAGMA table_info(managed_devices)")
        for col in cursor.fetchall():
            print(f"  {col[1]}: {col[2]}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    # 获取数据库路径
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'data/topology.db'
    
    print(f"开始迁移数据库: {db_path}\n")
    success = migrate(db_path)
    sys.exit(0 if success else 1)
