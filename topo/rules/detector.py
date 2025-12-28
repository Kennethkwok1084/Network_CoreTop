"""
异常检测规则模块
根据 develop.md 第 5.6 节实现
检测多邻居口、Trunk成员不一致、邻居名异常等问题
"""

import json
import logging
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, dao):
        """
        Args:
            dao: TopoDAO 实例
        """
        self.dao = dao
        self.anomalies = []
    
    def detect_all(self, device_id: int) -> List[Dict[str, Any]]:
        """
        执行所有异常检测
        
        Args:
            device_id: 设备 ID
        
        Returns:
            异常列表
        """
        self.anomalies = []
        
        self.detect_suspect_loop(device_id)
        self.detect_suspect_mixed_link(device_id)
        self.detect_trunk_inconsistent(device_id)
        
        # 保存异常到数据库
        for anomaly in self.anomalies:
            self.dao.anomalies.insert(
                device_id=device_id,
                anomaly_type=anomaly['type'],
                severity=anomaly['severity'],
                detail_json=json.dumps(anomaly['detail'], ensure_ascii=False)
            )
        
        return self.anomalies
    
    def detect_suspect_loop(self, device_id: int):
        """
        检测单物理口出现多个不同邻居设备（疑似环路）
        
        Args:
            device_id: 设备 ID
        """
        lldp_records = self.dao.lldp_neighbors.get_by_device(device_id)
        
        # 按接口聚合邻居
        interface_neighbors = defaultdict(set)
        for record in lldp_records:
            local_if = record['local_if']
            neighbor_dev = record['neighbor_dev']
            interface_neighbors[local_if].add(neighbor_dev)
        
        # 检测多邻居
        for local_if, neighbors in interface_neighbors.items():
            if len(neighbors) > 1:
                self.anomalies.append({
                    'type': 'suspect_loop',
                    'severity': 'warning',
                    'detail': {
                        'interface': local_if,
                        'neighbors': list(neighbors),
                        'count': len(neighbors),
                        'reason': '单个物理口出现多个不同邻居设备，可能存在环路或链路抖动'
                    }
                })
                logger.warning(
                    f"检测到疑似环路: {local_if} → {neighbors}"
                )
    
    def detect_suspect_mixed_link(self, device_id: int):
        """
        检测邻居设备名为空或大量 "-" 的异常情况
        
        Args:
            device_id: 设备 ID
        """
        lldp_records = self.dao.lldp_neighbors.get_by_device(device_id)
        
        if not lldp_records:
            return
        
        # 统计异常邻居名
        total_count = len(lldp_records)
        invalid_count = 0
        invalid_records = []
        
        for record in lldp_records:
            neighbor_dev = record['neighbor_dev'].strip()
            # 空名称或只有连字符
            if not neighbor_dev or neighbor_dev == '-' or set(neighbor_dev) == {'-', '_'}:
                invalid_count += 1
                invalid_records.append({
                    'interface': record['local_if'],
                    'neighbor_dev': neighbor_dev or '(空)'
                })
        
        # 如果超过 50% 的邻居名异常，报警
        if total_count > 0 and invalid_count / total_count > 0.5:
            self.anomalies.append({
                'type': 'suspect_mixed_link',
                'severity': 'warning',
                'detail': {
                    'total_neighbors': total_count,
                    'invalid_count': invalid_count,
                    'invalid_ratio': round(invalid_count / total_count, 2),
                    'examples': invalid_records[:5],  # 只显示前5个
                    'reason': '大量邻居设备名为空或异常，可能是 LLDP 配置问题'
                }
            })
            logger.warning(
                f"检测到异常邻居名比例过高: {invalid_count}/{total_count} "
                f"({invalid_count / total_count * 100:.1f}%)"
            )
    
    def detect_trunk_inconsistent(self, device_id: int):
        """
        检测 Trunk 成员指向多个不同设备（不一致）
        
        Args:
            device_id: 设备 ID
        """
        cursor = self.dao.db.conn.cursor()
        
        # 查询所有 Trunk
        cursor.execute('SELECT id, name FROM trunks WHERE device_id = ?', (device_id,))
        trunks = cursor.fetchall()
        
        for trunk in trunks:
            trunk_id = trunk['id']
            trunk_name = trunk['name']
            
            # 获取 Trunk 成员接口
            members = self.dao.trunks.get_members(trunk_id)
            if not members:
                continue
            
            # 查询每个成员接口的 LLDP 邻居
            member_neighbors = defaultdict(set)
            for member in members:
                member_if = member['name']
                
                cursor.execute(
                    'SELECT neighbor_dev FROM lldp_neighbors WHERE device_id = ? AND local_if = ?',
                    (device_id, member_if)
                )
                neighbors = cursor.fetchall()
                
                for neighbor in neighbors:
                    neighbor_dev = neighbor['neighbor_dev']
                    member_neighbors[member_if].add(neighbor_dev)
            
            # 收集所有邻居设备
            all_neighbors = set()
            for neighbors in member_neighbors.values():
                all_neighbors.update(neighbors)
            
            # 如果 Trunk 成员指向多个不同设备，报警
            if len(all_neighbors) > 1:
                self.anomalies.append({
                    'type': 'trunk_inconsistent',
                    'severity': 'error',
                    'detail': {
                        'trunk_name': trunk_name,
                        'members': [m['name'] for m in members],
                        'neighbors': list(all_neighbors),
                        'member_details': {
                            member_if: list(neighbors) 
                            for member_if, neighbors in member_neighbors.items()
                        },
                        'reason': 'Trunk 成员接口指向不同的邻居设备，配置可能有误'
                    }
                })
                logger.error(
                    f"检测到 Trunk 不一致: {trunk_name} → {all_neighbors}"
                )
    
    def detect_unstable_neighbor(self, device_id: int, threshold: float = 0.3):
        """
        检测 Exptime 波动异常（需要多次采集数据）
        
        Args:
            device_id: 设备 ID
            threshold: 波动系数阈值（默认 30%）
        """
        cursor = self.dao.db.conn.cursor()
        
        # 查询同一邻居的多次采集记录
        cursor.execute("""
            SELECT local_if, neighbor_dev, 
                   COUNT(DISTINCT exptime) as exptime_count,
                   AVG(exptime) as avg_exptime,
                   MIN(exptime) as min_exptime,
                   MAX(exptime) as max_exptime
            FROM lldp_neighbors
            WHERE device_id = ? AND exptime IS NOT NULL
            GROUP BY local_if, neighbor_dev
            HAVING exptime_count > 1
        """, (device_id,))
        
        unstable_neighbors = cursor.fetchall()
        
        for record in unstable_neighbors:
            avg_exp = record['avg_exptime']
            min_exp = record['min_exptime']
            max_exp = record['max_exptime']
            
            # 计算波动系数
            if avg_exp > 0:
                variation = (max_exp - min_exp) / avg_exp
                
                if variation > threshold:
                    self.anomalies.append({
                        'type': 'unstable_neighbor',
                        'severity': 'info',
                        'detail': {
                            'interface': record['local_if'],
                            'neighbor': record['neighbor_dev'],
                            'avg_exptime': avg_exp,
                            'min_exptime': min_exp,
                            'max_exptime': max_exp,
                            'variation': round(variation, 2),
                            'reason': f'Exptime 波动系数 {variation:.1%} 超过阈值 {threshold:.1%}'
                        }
                    })
                    logger.info(
                        f"检测到 Exptime 不稳定: {record['local_if']} → "
                        f"{record['neighbor_dev']} (波动: {variation:.1%})"
                    )


def run_anomaly_detection(db_path: str = "topo.db", device_id: int = None):
    """
    运行异常检测（独立脚本入口）
    
    Args:
        db_path: 数据库路径
        device_id: 设备 ID（None 则检测所有设备）
    """
    from ..db.dao import TopoDAO
    
    with TopoDAO(db_path) as dao:
        if device_id is None:
            # 检测所有设备
            devices = dao.devices.list_all()
            device_ids = [dev['id'] for dev in devices]
        else:
            device_ids = [device_id]
        
        total_anomalies = 0
        
        for dev_id in device_ids:
            logger.info(f"检测设备 ID={dev_id}")
            detector = AnomalyDetector(dao)
            anomalies = detector.detect_all(dev_id)
            
            if anomalies:
                logger.warning(f"设备 {dev_id} 发现 {len(anomalies)} 个异常")
                for anomaly in anomalies:
                    print(f"  [{anomaly['severity'].upper()}] {anomaly['type']}: {anomaly['detail']}")
            
            total_anomalies += len(anomalies)
        
        dao.commit()
        
        print(f"\n总计发现 {total_anomalies} 个异常")
        return total_anomalies


if __name__ == "__main__":
    import sys
    import argparse
    
    # 允许独立运行
    try:
        from ..utils.logging_config import setup_logging
    except ImportError:
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
        from topo.utils.logging_config import setup_logging
    
    setup_logging(level="INFO")
    
    parser = argparse.ArgumentParser(description="运行异常检测")
    parser.add_argument('--db', default='topo.db', help='数据库路径')
    parser.add_argument('--device-id', type=int, help='设备 ID（可选）')
    
    args = parser.parse_args()
    
    run_anomaly_detection(args.db, args.device_id)
