"""
数据库完整性验证工具
检查外键约束、重复数据等问题
"""

import sqlite3
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def verify_database_integrity(db_path: str) -> Dict[str, Any]:
    """
    验证数据库完整性
    
    Args:
        db_path: 数据库文件路径
    
    Returns:
        验证结果字典
    """
    results = {
        'foreign_keys_enabled': False,
        'journal_mode': None,
        'orphan_records': {},
        'duplicate_links': 0,
        'issues': []
    }
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    # 1. 检查外键是否启用
    cursor.execute("PRAGMA foreign_keys")
    fk_enabled = cursor.fetchone()[0]
    results['foreign_keys_enabled'] = bool(fk_enabled)
    if not fk_enabled:
        results['issues'].append("外键检查未启用")
        logger.warning("⚠ 外键检查未启用")
    else:
        logger.info("✓ 外键检查已启用")
    
    # 2. 检查 journal 模式
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    results['journal_mode'] = journal_mode
    logger.info(f"✓ Journal 模式: {journal_mode}")
    
    # 3. 检查外键完整性
    logger.info("\n检查外键完整性...")
    cursor.execute("PRAGMA foreign_key_check")
    fk_violations = cursor.fetchall()
    if fk_violations:
        results['issues'].append(f"发现 {len(fk_violations)} 条外键违规")
        logger.error(f"✗ 发现 {len(fk_violations)} 条外键违规:")
        for violation in fk_violations[:5]:  # 只显示前5条
            logger.error(f"  {violation}")
    else:
        logger.info("✓ 无外键违规")
    
    # 4. 检查孤立的接口记录（device 不存在）
    try:
        cursor.execute("""
            SELECT i.id, i.device_id, i.name
            FROM interfaces i
            LEFT JOIN devices d ON i.device_id = d.id
            WHERE d.id IS NULL
            LIMIT 10
        """)
        orphan_interfaces = cursor.fetchall()
        if orphan_interfaces:
            results['orphan_records']['interfaces'] = len(orphan_interfaces)
            results['issues'].append(f"{len(orphan_interfaces)} 条孤立接口记录")
            logger.warning(f"⚠ 发现 {len(orphan_interfaces)} 条孤立接口记录")
    except sqlite3.OperationalError:
        logger.info("⊘ 跳过接口检查（表不存在）")
    
    # 5. 检查孤立的 LLDP 记录
    try:
        cursor.execute("""
            SELECT l.id, l.device_id
            FROM lldp_neighbors l
            LEFT JOIN devices d ON l.device_id = d.id
            WHERE d.id IS NULL
            LIMIT 10
        """)
        orphan_lldp = cursor.fetchall()
        if orphan_lldp:
            results['orphan_records']['lldp_neighbors'] = len(orphan_lldp)
            results['issues'].append(f"{len(orphan_lldp)} 条孤立 LLDP 记录")
            logger.warning(f"⚠ 发现 {len(orphan_lldp)} 条孤立 LLDP 记录")
    except sqlite3.OperationalError:
        logger.info("⊘ 跳过 LLDP 检查（表不存在）")
    
    # 6. 检查重复链路（如果没有唯一约束）
    cursor.execute("""
        SELECT src_device, src_if, dst_device, dst_if, COUNT(*) as cnt
        FROM links
        GROUP BY src_device, src_if, dst_device, dst_if
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        results['duplicate_links'] = len(duplicates)
        results['issues'].append(f"{len(duplicates)} 组重复链路")
        logger.warning(f"⚠ 发现 {len(duplicates)} 组重复链路")
    else:
        logger.info("✓ 无重复链路")
    
    # 7. 检查 links 表是否有唯一约束
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='links'")
    row = cursor.fetchone()
    if row:
        schema_sql = row[0]
        if 'UNIQUE(src_device, src_if, dst_device, dst_if)' not in schema_sql:
            results['issues'].append("links 表缺少唯一约束")
            logger.warning("⚠ links 表缺少唯一约束，建议运行迁移")
        else:
            logger.info("✓ links 表唯一约束正常")
    
    conn.close()
    
    # 总结
    print("\n" + "="*60)
    if not results['issues']:
        print("✓ 数据库完整性检查通过！")
    else:
        print(f"⚠ 发现 {len(results['issues'])} 个问题:")
        for issue in results['issues']:
            print(f"  - {issue}")
        print("\n建议:")
        if '外键检查未启用' in results['issues']:
            print("  1. 确保所有连接都执行 PRAGMA foreign_keys=ON")
        if 'links 表缺少唯一约束' in results['issues']:
            print("  2. 运行 python -m topo.db.migrate topo.db 进行迁移")
        if any('孤立' in i for i in results['issues']):
            print("  3. 清理孤立记录或重建相关设备")
    print("="*60)
    
    return results


def cleanup_orphan_records(db_path: str, dry_run: bool = True):
    """
    清理孤立记录
    
    Args:
        db_path: 数据库文件路径
        dry_run: 是否仅模拟（不实际删除）
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}清理孤立记录...")
    
    # 删除孤立的接口
    cursor.execute("""
        DELETE FROM interfaces
        WHERE device_id NOT IN (SELECT id FROM devices)
    """)
    interfaces_deleted = cursor.rowcount if not dry_run else 0
    print(f"  {'将' if dry_run else '已'}删除 {interfaces_deleted} 条孤立接口记录")
    
    # 删除孤立的 LLDP 记录
    cursor.execute("""
        DELETE FROM lldp_neighbors
        WHERE device_id NOT IN (SELECT id FROM devices)
    """)
    lldp_deleted = cursor.rowcount if not dry_run else 0
    print(f"  {'将' if dry_run else '已'}删除 {lldp_deleted} 条孤立 LLDP 记录")
    
    # 删除孤立的异常记录
    cursor.execute("""
        DELETE FROM anomalies
        WHERE device_id NOT IN (SELECT id FROM devices)
    """)
    anomalies_deleted = cursor.rowcount if not dry_run else 0
    print(f"  {'将' if dry_run else '已'}删除 {anomalies_deleted} 条孤立异常记录")
    
    if not dry_run:
        conn.commit()
        print("\n✓ 清理完成")
    else:
        print("\n[DRY RUN] 使用 --execute 参数执行实际清理")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库完整性验证工具")
    parser.add_argument("db_path", help="数据库文件路径")
    parser.add_argument("--cleanup", action="store_true", help="清理孤立记录")
    parser.add_argument("--execute", action="store_true", help="实际执行清理（默认为 dry-run）")
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_orphan_records(args.db_path, dry_run=not args.execute)
    else:
        verify_database_integrity(args.db_path)
