"""
数据访问对象（DAO）层
提供设备、接口、链路、异常等的增删改查操作，支持 upsert 和去重逻辑
"""

import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from .schema import Database
except ImportError:
    from schema import Database


class DeviceDAO:
    """设备数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert(self, name: str, mgmt_ip: str = None, vendor: str = "Huawei", 
               model: str = None, site: str = None) -> int:
        """插入或更新设备，返回设备 ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO devices (name, mgmt_ip, vendor, model, site)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                mgmt_ip = COALESCE(excluded.mgmt_ip, mgmt_ip),
                vendor = COALESCE(excluded.vendor, vendor),
                model = COALESCE(excluded.model, model),
                site = COALESCE(excluded.site, site)
        """, (name, mgmt_ip, vendor, model, site))
        
        # 获取插入或更新的设备 ID
        cursor.execute("SELECT id FROM devices WHERE name = ?", (name,))
        return cursor.fetchone()[0]
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """根据名称查询设备"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def list_all(self) -> List[Dict]:
        """列出所有设备"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM devices ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


class InterfaceDAO:
    """接口数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert(self, device_id: int, name: str, description: str = None,
               admin_status: str = None, oper_status: str = None) -> int:
        """插入或更新接口"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO interfaces (device_id, name, description, admin_status, oper_status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id, name) DO UPDATE SET
                description = COALESCE(excluded.description, description),
                admin_status = COALESCE(excluded.admin_status, admin_status),
                oper_status = COALESCE(excluded.oper_status, oper_status)
        """, (device_id, name, description, admin_status, oper_status))
        
        cursor.execute("SELECT id FROM interfaces WHERE device_id = ? AND name = ?", 
                      (device_id, name))
        return cursor.fetchone()[0]
    
    def update_description(self, device_id: int, name: str, description: str):
        """更新接口描述"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE interfaces SET description = ? 
            WHERE device_id = ? AND name = ?
        """, (description, device_id, name))
    
    def get_by_device(self, device_id: int) -> List[Dict]:
        """查询设备的所有接口"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM interfaces WHERE device_id = ?", (device_id,))
        return [dict(row) for row in cursor.fetchall()]


class TrunkDAO:
    """Eth-Trunk 数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert(self, device_id: int, name: str, mode: str = None, 
               oper_status: str = None) -> int:
        """插入或更新 Trunk"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trunks (device_id, name, mode, oper_status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id, name) DO UPDATE SET
                mode = COALESCE(excluded.mode, mode),
                oper_status = COALESCE(excluded.oper_status, oper_status)
        """, (device_id, name, mode, oper_status))
        
        cursor.execute("SELECT id FROM trunks WHERE device_id = ? AND name = ?", 
                      (device_id, name))
        return cursor.fetchone()[0]
    
    def add_member(self, trunk_id: int, interface_id: int):
        """添加 Trunk 成员"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO trunk_members (trunk_id, interface_id)
            VALUES (?, ?)
        """, (trunk_id, interface_id))
    
    def get_members(self, trunk_id: int) -> List[Dict]:
        """查询 Trunk 的成员接口"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT i.* FROM interfaces i
            JOIN trunk_members tm ON i.id = tm.interface_id
            WHERE tm.trunk_id = ?
        """, (trunk_id,))
        return [dict(row) for row in cursor.fetchall()]


class LLDPNeighborDAO:
    """LLDP 邻居数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def insert(self, device_id: int, local_if: str, neighbor_dev: str,
               neighbor_if: str = None, exptime: int = None,
               source_file: str = None, collected_at: str = None):
        """插入 LLDP 邻居记录"""
        if collected_at is None:
            collected_at = datetime.now().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO lldp_neighbors 
            (device_id, local_if, neighbor_dev, neighbor_if, exptime, source_file, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (device_id, local_if, neighbor_dev, neighbor_if, exptime, source_file, collected_at))
    
    def get_by_device(self, device_id: int) -> List[Dict]:
        """查询设备的所有 LLDP 邻居"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM lldp_neighbors WHERE device_id = ?", (device_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def count_neighbors_per_interface(self, device_id: int) -> Dict[str, int]:
        """统计每个接口的邻居数量（用于异常检测）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT local_if, COUNT(DISTINCT neighbor_dev) as count
            FROM lldp_neighbors
            WHERE device_id = ?
            GROUP BY local_if
        """, (device_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}


class LinkDAO:
    """链路数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert(self, src_device: str, src_if: str, dst_device: str, dst_if: str,
               link_type: str = "phy", confidence: str = "trusted", notes: str = None):
        """插入或更新链路"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO links (src_device, src_if, dst_device, dst_if, link_type, confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(src_device, src_if, dst_device, dst_if) DO UPDATE SET
                link_type = excluded.link_type,
                confidence = excluded.confidence,
                notes = COALESCE(excluded.notes, notes)
        """, (src_device, src_if, dst_device, dst_if, link_type, confidence, notes))
    
    def update_confidence(self, src_device: str, src_if: str, 
                         dst_device: str, dst_if: str, confidence: str):
        """更新链路可信度"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE links SET confidence = ?
            WHERE src_device = ? AND src_if = ? AND dst_device = ? AND dst_if = ?
        """, (confidence, src_device, src_if, dst_device, dst_if))
    
    def get_by_device(self, device: str, confidence_filter: List[str] = None) -> List[Dict]:
        """查询设备相关的链路"""
        cursor = self.conn.cursor()
        if confidence_filter:
            placeholders = ','.join('?' * len(confidence_filter))
            cursor.execute(f"""
                SELECT * FROM links 
                WHERE (src_device = ? OR dst_device = ?)
                AND confidence IN ({placeholders})
            """, (device, device, *confidence_filter))
        else:
            cursor.execute("""
                SELECT * FROM links WHERE src_device = ? OR dst_device = ?
            """, (device, device))
        return [dict(row) for row in cursor.fetchall()]


class AnomalyDAO:
    """异常数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def insert(self, device_id: int, anomaly_type: str, severity: str = "warning",
               detail_json: str = None):
        """插入异常记录"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO anomalies (device_id, type, severity, detail_json)
            VALUES (?, ?, ?, ?)
        """, (device_id, anomaly_type, severity, detail_json))
    
    def get_by_device(self, device_id: int) -> List[Dict]:
        """查询设备的所有异常"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM anomalies WHERE device_id = ? ORDER BY created_at DESC", 
                      (device_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def list_all(self, severity: str = None) -> List[Dict]:
        """列出所有异常，可按严重级别过滤"""
        cursor = self.conn.cursor()
        if severity:
            cursor.execute("SELECT * FROM anomalies WHERE severity = ? ORDER BY created_at DESC", 
                          (severity,))
        else:
            cursor.execute("SELECT * FROM anomalies ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


class ImportDAO:
    """导入审计数据访问"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def check_hash_exists(self, file_hash: str) -> bool:
        """检查文件 hash 是否已导入"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM imports WHERE hash = ?", (file_hash,))
        return cursor.fetchone()[0] > 0
    
    def record_import(self, device_name: str, source_file: str, file_hash: str):
        """记录导入任务"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO imports (device_name, source_file, hash)
            VALUES (?, ?, ?)
        """, (device_name, source_file, file_hash))
    
    def list_recent(self, limit: int = 10) -> List[Dict]:
        """列出最近的导入记录"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM imports ORDER BY imported_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


class TopoDAO:
    """统一的 DAO 入口，整合所有数据访问对象"""
    
    def __init__(self, db_path: str = "topo.db"):
        self.db = Database(db_path)
        self.db.connect()
        self.db.init_schema()  # 确保表结构存在
        
        # 初始化各子 DAO
        self.devices = DeviceDAO(self.db.conn)
        self.interfaces = InterfaceDAO(self.db.conn)
        self.trunks = TrunkDAO(self.db.conn)
        self.lldp_neighbors = LLDPNeighborDAO(self.db.conn)
        self.links = LinkDAO(self.db.conn)
        self.anomalies = AnomalyDAO(self.db.conn)
        self.imports = ImportDAO(self.db.conn)
    
    def commit(self):
        """提交事务"""
        self.db.conn.commit()
    
    def rollback(self):
        """回滚事务"""
        self.db.conn.rollback()
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


if __name__ == "__main__":
    # 测试 DAO
    with TopoDAO("test_topo.db") as dao:
        # 插入测试设备
        dev_id = dao.devices.upsert("Core_CSS", mgmt_ip="192.168.1.1", model="S12700")
        print(f"✓ 设备插入成功，ID: {dev_id}")
        
        # 插入接口
        if_id = dao.interfaces.upsert(dev_id, "GigabitEthernet1/6/0/21", 
                                      description="To Building A")
        print(f"✓ 接口插入成功，ID: {if_id}")
        
        # 插入 LLDP 邻居
        dao.lldp_neighbors.insert(dev_id, "GigabitEthernet1/6/0/21", 
                                  "Ruijie", "Te0/52", exptime=101)
        print("✓ LLDP 邻居插入成功")
        
        # 查询设备
        devices = dao.devices.list_all()
        print(f"✓ 查询到 {len(devices)} 个设备")
    
    print("\n数据库 DAO 测试成功！")
