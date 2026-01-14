"""
解析器主入口
整合所有解析器，实现增量导入、去重、hash 计算
根据 develop.md 第 5.7 节实现
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .file_reader import (
    read_file, 
    calculate_file_hash, 
    split_command_blocks,
    extract_device_name_from_file
)
from .lldp import parse_lldp_brief
from .trunk import parse_eth_trunk
from .interface_desc import parse_interface_description
from .stp import parse_stp_brief, get_blocked_ports

try:
    from ..db.dao import TopoDAO
    from ..utils.logging_config import setup_logging
except ImportError:
    # 开发时直接运行的兼容处理
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    from topo.db.dao import TopoDAO
    from topo.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


class LogParser:
    """日志解析器主类"""
    
    def __init__(self, db_path: str = "topo.db"):
        self.db_path = db_path
        self.stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'devices_created': 0,
            'lldp_records': 0,
            'trunks_created': 0,
            'interfaces_updated': 0,
            'stp_blocked': 0
        }
    
    def import_log_file(self, file_path: str, device_name: str = None, force: bool = False) -> Dict[str, Any]:
        """
        导入单个日志文件
        
        Args:
            file_path: 日志文件路径
            device_name: 设备名称（可选，如不提供则从文件名提取）
            force: 是否强制重新导入（忽略哈希检查）
        
        Returns:
            导入结果统计
        """
        logger.info(f"开始导入: {file_path}")
        
        # 计算文件 hash
        file_hash = calculate_file_hash(file_path)
        
        # 使用 DAO
        with TopoDAO(self.db_path) as dao:
            # 检查是否已导入
            if dao.imports.check_hash_exists(file_hash):
                if not force:
                    logger.warning(f"文件已导入过（hash: {file_hash[:16]}...），跳过")
                    self.stats['files_skipped'] += 1
                    return {'status': 'skipped', 'reason': 'duplicate', 'hash': file_hash}
                logger.warning(f"文件已导入过（hash: {file_hash[:16]}...），强制重新导入")
            
            # 提取设备名
            if not device_name:
                device_name = extract_device_name_from_file(file_path)
                logger.info(f"提取设备名: {device_name}")
            
            # 读取文件内容
            try:
                content = read_file(file_path)
            except ValueError as e:
                logger.error(f"文件读取失败: {e}")
                return {'status': 'error', 'reason': str(e)}
            
            # 分割命令块
            blocks = split_command_blocks(content)
            logger.info(f"分割为 {len(blocks)} 个命令块")
            
            # 创建或更新设备
            device_id = dao.devices.upsert(device_name)
            self.stats['devices_created'] += 1
            logger.info(f"设备 ID: {device_id}")
            
            # 解析各个命令块
            collected_at = datetime.now().isoformat()
            
            import_stats = {
                'lldp_count': 0,
                'trunk_count': 0,
                'interface_count': 0,
                'stp_blocked_count': 0,
                'link_count': 0,
            }

            for command, output in blocks:
                self._parse_command_block(
                    dao, device_id, device_name, 
                    command, output, file_path, collected_at,
                    import_stats=import_stats
                )
            
            # 记录导入任务
            dao.imports.record_import(device_name, file_path, file_hash)
            dao.commit()
            
            self.stats['files_processed'] += 1
            logger.info(f"✓ 导入完成: {file_path}")
            
            return {
                'status': 'success',
                'device_name': device_name,
                'hash': file_hash,
                'file_hash': file_hash,
                'blocks': len(blocks),
                **import_stats
            }
    
    def _parse_command_block(
        self, dao: TopoDAO, device_id: int, device_name: str,
        command: str, output: str, source_file: str, collected_at: str,
        import_stats: Optional[Dict[str, int]] = None
    ):
        """解析单个命令块"""
        cmd_lower = command.lower()
        
        # 1. LLDP neighbor brief
        if 'lldp neighbor brief' in cmd_lower:
            neighbors = parse_lldp_brief(output)
            logger.debug(f"解析 LLDP brief: {len(neighbors)} 条记录")
            
            for neighbor in neighbors:
                dao.lldp_neighbors.insert(
                    device_id=device_id,
                    local_if=neighbor.local_if,
                    neighbor_dev=neighbor.neighbor_dev,
                    neighbor_if=neighbor.neighbor_if,
                    exptime=neighbor.exptime,
                    source_file=source_file,
                    collected_at=collected_at
                )
                self.stats['lldp_records'] += 1
                if import_stats is not None:
                    import_stats['lldp_count'] += 1
                
                # 生成链路记录
                if neighbor.neighbor_if:
                    dao.links.upsert(
                        src_device=device_name,
                        src_if=neighbor.local_if,
                        dst_device=neighbor.neighbor_dev,
                        dst_if=neighbor.neighbor_if,
                        link_type='phy'
                    )
                    if import_stats is not None:
                        import_stats['link_count'] += 1
        
        # 2. Eth-Trunk
        elif 'eth-trunk' in cmd_lower:
            trunks = parse_eth_trunk(output)
            logger.debug(f"解析 Eth-Trunk: {len(trunks)} 个")
            
            for trunk in trunks:
                trunk_id = dao.trunks.upsert(
                    device_id=device_id,
                    name=trunk.name,
                    mode=trunk.mode,
                    oper_status=trunk.oper_status
                )
                self.stats['trunks_created'] += 1
                if import_stats is not None:
                    import_stats['trunk_count'] += 1
                
                # 添加成员接口
                for member_if in trunk.members:
                    # 先创建接口记录
                    if_id = dao.interfaces.upsert(
                        device_id=device_id,
                        name=member_if,
                        oper_status=trunk.oper_status
                    )
                    # 添加到 trunk_members
                    dao.trunks.add_member(trunk_id, if_id)
        
        # 3. Interface description
        elif 'interface description' in cmd_lower:
            interfaces = parse_interface_description(output)
            logger.debug(f"解析接口描述: {len(interfaces)} 个")
            
            for if_name, if_desc in interfaces.items():
                dao.interfaces.upsert(
                    device_id=device_id,
                    name=if_desc.name,
                    description=if_desc.description,
                    admin_status=if_desc.admin_status,
                    oper_status=if_desc.protocol_status
                )
                self.stats['interfaces_updated'] += 1
                if import_stats is not None:
                    import_stats['interface_count'] += 1
        
        # 4. STP brief
        elif 'stp brief' in cmd_lower:
            stp_ports = parse_stp_brief(output)
            logger.debug(f"解析 STP: {len(stp_ports)} 个端口")
            
            blocked_ports = get_blocked_ports(stp_ports)
            if blocked_ports:
                logger.info(f"发现 {len(blocked_ports)} 个 STP 阻塞端口")
                self.stats['stp_blocked'] += len(blocked_ports)
                if import_stats is not None:
                    import_stats['stp_blocked_count'] += len(blocked_ports)
                
                # 记录异常
                import json
                dao.anomalies.insert(
                    device_id=device_id,
                    anomaly_type='stp_blocked',
                    severity='info',
                    detail_json=json.dumps({
                        'blocked_ports': blocked_ports,
                        'count': len(blocked_ports)
                    })
                )
    
    def print_stats(self):
        """打印统计信息"""
        print("\n" + "="*60)
        print("导入统计")
        print("="*60)
        print(f"处理文件数: {self.stats['files_processed']}")
        print(f"跳过文件数: {self.stats['files_skipped']}")
        print(f"设备数: {self.stats['devices_created']}")
        print(f"LLDP 记录: {self.stats['lldp_records']}")
        print(f"Trunk 数: {self.stats['trunks_created']}")
        print(f"接口更新: {self.stats['interfaces_updated']}")
        print(f"STP 阻塞端口: {self.stats['stp_blocked']}")
        print("="*60)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="华为交换机日志解析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入单个文件
  python -m topo.parser data/raw/core_css.log
  
  # 指定设备名
  python -m topo.parser data/raw/core.log --device Core_CSS
  
  # 批量导入
  python -m topo.parser data/raw/*.log
  
  # 指定数据库
  python -m topo.parser data/raw/core.log --db mydb.db
        """
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='日志文件路径（支持通配符）'
    )
    parser.add_argument(
        '--device',
        help='设备名称（可选，默认从文件名提取）'
    )
    parser.add_argument(
        '--db',
        default='topo.db',
        help='数据库文件路径（默认: topo.db）'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别（默认: INFO）'
    )
    parser.add_argument(
        '--log-file',
        help='日志文件路径（可选）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(
        level=args.log_level,
        log_file=args.log_file,
        console=True
    )
    
    # 创建解析器
    parser_instance = LogParser(db_path=args.db)
    
    # 处理文件列表（支持通配符）
    import glob
    all_files = []
    for pattern in args.files:
        matched = glob.glob(pattern)
        if matched:
            all_files.extend(matched)
        else:
            all_files.append(pattern)  # 可能是精确路径
    
    # 去重
    all_files = list(set(all_files))
    
    if not all_files:
        logger.error("未找到匹配的文件")
        return 1
    
    logger.info(f"找到 {len(all_files)} 个文件待处理")
    
    # 逐个导入
    for file_path in all_files:
        if not Path(file_path).exists():
            logger.warning(f"文件不存在: {file_path}")
            continue
        
        try:
            result = parser_instance.import_log_file(file_path, device_name=args.device)
            if result['status'] == 'success':
                logger.info(f"✓ {file_path} 导入成功")
            elif result['status'] == 'skipped':
                logger.warning(f"⊘ {file_path} 已跳过")
        except Exception as e:
            logger.error(f"✗ {file_path} 导入失败: {e}", exc_info=True)
    
    # 打印统计
    parser_instance.print_stats()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
