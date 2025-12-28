"""
SQLite 数据库 Schema 定义
实现 develop.md 第 4 节的 8 张表结构
"""

import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    """数据库连接和表结构管理"""
    
    def __init__(self, db_path: str = "topo.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_wal_compatible = True  # 确保 WAL 模式下的一致性
    
    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 支持字典式访问
        
        # 启用外键约束检查（必须在任何操作前执行）
        self.conn.execute("PRAGMA foreign_keys = ON")
        # 启用 WAL 模式提升并发性能
        self.conn.execute("PRAGMA journal_mode = WAL")
        # 设置同步模式为 NORMAL 平衡性能与安全
        self.conn.execute("PRAGMA synchronous = NORMAL")
        
        # 验证外键是否真正启用（防止 WAL 模式下被覆盖）
        if self._ensure_wal_compatible:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            fk_enabled = cursor.fetchone()[0]
            if not fk_enabled:
                import logging
                logging.warning("外键检查未启用，可能是 WAL 模式兼容性问题")
        
        return self.conn
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def init_schema(self, include_management=False):
        """
        初始化数据库表结构
        
        Args:
            include_management: 是否包含管理表（用户、设备配置等）
        """
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        # 1. devices 表：设备主表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            mgmt_ip TEXT,
            vendor TEXT,
            model TEXT,
            site TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 2. interfaces 表：接口基础信息
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS interfaces (
            id INTEGER PRIMARY KEY,
            device_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            admin_status TEXT,
            oper_status TEXT,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """)
        
        # 3. trunks 表：Eth-Trunk 元数据
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trunks (
            id INTEGER PRIMARY KEY,
            device_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            mode TEXT,
            oper_status TEXT,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """)
        
        # 4. trunk_members 表：Trunk 成员映射
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trunk_members (
            trunk_id INTEGER NOT NULL,
            interface_id INTEGER NOT NULL,
            PRIMARY KEY (trunk_id, interface_id),
            FOREIGN KEY (trunk_id) REFERENCES trunks(id),
            FOREIGN KEY (interface_id) REFERENCES interfaces(id)
        )
        """)
        
        # 5. lldp_neighbors 表：原始 LLDP 记录
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lldp_neighbors (
            id INTEGER PRIMARY KEY,
            device_id INTEGER NOT NULL,
            local_if TEXT NOT NULL,
            neighbor_dev TEXT NOT NULL,
            neighbor_if TEXT,
            exptime INTEGER,
            source_file TEXT,
            collected_at TEXT,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """)
        
        # 6. links 表：用于绘图的边
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY,
            src_device TEXT NOT NULL,
            src_if TEXT NOT NULL,
            dst_device TEXT NOT NULL,
            dst_if TEXT NOT NULL,
            link_type TEXT NOT NULL,  -- phy/trunk
            confidence TEXT NOT NULL DEFAULT 'trusted',  -- trusted/suspect/ignore
            notes TEXT,
            UNIQUE(src_device, src_if, dst_device, dst_if)
        )
        """)
        
        # 7. anomalies 表：异常记录
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY,
            device_id INTEGER,
            type TEXT,
            severity TEXT,
            detail_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """)
        
        # 8. imports 表：导入任务审计
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY,
            device_name TEXT,
            source_file TEXT,
            hash TEXT UNIQUE,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 创建索引（优化查询性能）
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_lldp_device_if 
        ON lldp_neighbors(device_id, local_if)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_src 
        ON links(src_device, src_if)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_imports_hash 
        ON imports(hash)
        """)
        
        # 9. 设备凭证表（用于 SSH 自动采集）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            management_ip TEXT NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            ssh_username TEXT NOT NULL,
            ssh_password TEXT,           -- 加密存储
            ssh_private_key TEXT,        -- SSH 密钥路径
            protocol TEXT DEFAULT 'ssh', -- ssh/telnet
            enable_password TEXT,        -- 特权模式密码
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
            UNIQUE(device_id)
        )
        """)
        
        # 初始化管理表（如果需要）
        if include_management:
            from .management_schema import init_management_tables, create_default_admin
            init_management_tables(self.conn)
            create_default_admin(self.conn)
        
        self.conn.commit()
        print(f"✓ 数据库表结构初始化完成: {self.db_path}")

    
    def __enter__(self):
        """上下文管理器：进入"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出"""
        self.close()


if __name__ == "__main__":
    # 测试：初始化数据库
    db = Database("topo.db")
    db.connect()
    db.init_schema()
    db.close()
    print("数据库初始化成功！")
