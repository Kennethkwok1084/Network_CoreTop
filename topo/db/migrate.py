"""
数据库迁移工具
用于升级旧版本数据库到最新 schema
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def backup_database(db_path: str) -> str:
    """
    备份数据库
    
    Args:
        db_path: 数据库文件路径
    
    Returns:
        备份文件路径
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ 数据库已备份到: {backup_path}")
    return backup_path


def check_schema_version(conn: sqlite3.Connection) -> dict:
    """
    检查当前 schema 版本和缺失的约束
    
    Args:
        conn: 数据库连接
    
    Returns:
        检查结果字典
    """
    cursor = conn.cursor()
    issues = {}
    
    # 检查 links 表是否有唯一约束
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='links'")
    row = cursor.fetchone()
    if row:
        schema_sql = row[0]
        if 'UNIQUE(src_device, src_if, dst_device, dst_if)' not in schema_sql:
            issues['links_unique_constraint'] = False
            print("⚠ links 表缺少唯一约束")
        else:
            issues['links_unique_constraint'] = True
            print("✓ links 表唯一约束正常")
    
    # 检查是否有重复链路
    cursor.execute("""
        SELECT src_device, src_if, dst_device, dst_if, COUNT(*) as cnt
        FROM links
        GROUP BY src_device, src_if, dst_device, dst_if
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        issues['duplicate_links'] = len(duplicates)
        print(f"⚠ 发现 {len(duplicates)} 组重复链路")
    else:
        issues['duplicate_links'] = 0
        print("✓ 无重复链路")
    
    return issues


def migrate_to_v2(db_path: str, dry_run: bool = False):
    """
    迁移到 v2 schema（添加 links 唯一约束）
    
    Args:
        db_path: 数据库文件路径
        dry_run: 是否仅模拟运行
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}开始迁移数据库: {db_path}")
    
    # 备份
    if not dry_run:
        backup_database(db_path)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 启用外键检查
    conn.execute("PRAGMA foreign_keys = ON")
    
    # 检查当前状态
    issues = check_schema_version(conn)
    
    # 如果已经有唯一约束，跳过
    if issues.get('links_unique_constraint', True):
        print("\n✓ schema 已是最新版本，无需迁移")
        conn.close()
        return
    
    if dry_run:
        print("\n[DRY RUN] 将执行以下操作:")
        print("  1. 创建临时表 links_new（带唯一约束）")
        print("  2. 复制数据并去重")
        print("  3. 删除旧表，重命名新表")
        conn.close()
        return
    
    print("\n开始迁移...")
    cursor = conn.cursor()
    
    try:
        # 1. 创建新表（带唯一约束）
        print("  1/4 创建新表结构...")
        cursor.execute("""
        CREATE TABLE links_new (
            id INTEGER PRIMARY KEY,
            src_device TEXT NOT NULL,
            src_if TEXT NOT NULL,
            dst_device TEXT NOT NULL,
            dst_if TEXT NOT NULL,
            link_type TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'trusted',
            notes TEXT,
            UNIQUE(src_device, src_if, dst_device, dst_if)
        )
        """)
        
        # 2. 复制数据（去重，保留最新的记录）
        print("  2/4 复制数据并去重...")
        cursor.execute("""
        INSERT INTO links_new (src_device, src_if, dst_device, dst_if, link_type, confidence, notes)
        SELECT src_device, src_if, dst_device, dst_if, link_type, confidence, notes
        FROM links
        GROUP BY src_device, src_if, dst_device, dst_if
        HAVING id = MAX(id)
        """)
        
        copied = cursor.rowcount
        print(f"     复制 {copied} 条链路记录")
        
        # 3. 删除旧表
        print("  3/4 删除旧表...")
        cursor.execute("DROP TABLE links")
        
        # 4. 重命名新表
        print("  4/4 重命名新表...")
        cursor.execute("ALTER TABLE links_new RENAME TO links")
        
        # 提交事务
        conn.commit()
        
        # 清理和优化
        print("\n优化数据库...")
        cursor.execute("VACUUM")
        
        print("\n✓ 迁移成功完成！")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        conn.close()


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库迁移工具")
    parser.add_argument("db_path", help="数据库文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅检查，不执行实际迁移")
    parser.add_argument("--check-only", action="store_true", help="仅检查 schema 版本")
    
    args = parser.parse_args()
    
    if args.check_only:
        conn = sqlite3.connect(args.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        check_schema_version(conn)
        conn.close()
    else:
        migrate_to_v2(args.db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
