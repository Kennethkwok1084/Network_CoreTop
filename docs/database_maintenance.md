# 数据库维护指南

## 1. 日志配置（必须）

在主程序入口添加日志配置，否则 `file_reader.py` 的警告不会显示：

```python
from topo.utils.logging_config import setup_logging

# 方式 1：仅控制台输出
setup_logging(level="INFO")

# 方式 2：同时写入文件
setup_logging(level="INFO", log_file="logs/topo_20231228.log")

# 方式 3：使用默认日志文件（自动按日期命名）
from topo.utils.logging_config import get_default_log_file
setup_logging(level="INFO", log_file=get_default_log_file())
```

## 2. 数据库迁移（旧数据库必须）

如果已有旧版本 `topo.db`（缺少 links 表唯一约束），**必须运行迁移**：

### 检查是否需要迁移
```bash
python -m topo.db.migrate topo.db --check-only
```

### 模拟迁移（不执行，仅预览）
```bash
python -m topo.db.migrate topo.db --dry-run
```

### 执行迁移（会自动备份）
```bash
python -m topo.db.migrate topo.db
```

迁移会：
- 自动备份数据库为 `topo.db.backup_YYYYMMDD_HHMMSS`
- 创建新表结构（带唯一约束）
- 复制并去重数据
- VACUUM 优化空间

## 3. 完整性验证

定期检查数据库健康状态：

```bash
# 验证外键、重复链路、孤立记录
python -m topo.db.verify topo.db

# 清理孤立记录（模拟）
python -m topo.db.verify topo.db --cleanup

# 实际清理
python -m topo.db.verify topo.db --cleanup --execute
```

## 4. WAL 模式注意事项

### 多进程/多连接场景
所有访问同一数据库的进程/连接都必须启用外键检查：

```python
import sqlite3

conn = sqlite3.connect("topo.db")
conn.execute("PRAGMA foreign_keys = ON")  # 必须每次连接都执行
```

### 推荐做法
始终使用项目提供的 `Database` 或 `TopoDAO` 类，它们已自动配置：

```python
from topo.db.dao import TopoDAO

# 自动启用外键检查、WAL 模式
with TopoDAO("topo.db") as dao:
    dao.devices.upsert("Core_A", mgmt_ip="192.168.1.1")
```

### 直接使用 sqlite3 的风险
```python
# ❌ 错误示例：缺少外键检查
conn = sqlite3.connect("topo.db")
cursor = conn.cursor()
cursor.execute("INSERT INTO interfaces (device_id, name) VALUES (999, 'GE1/0/1')")
# 可能插入脏数据（device_id=999 不存在）

# ✅ 正确示例
conn = sqlite3.connect("topo.db")
conn.execute("PRAGMA foreign_keys = ON")  # 启用外键
cursor = conn.cursor()
cursor.execute("INSERT INTO interfaces (device_id, name) VALUES (999, 'GE1/0/1')")
# 会抛出 IntegrityError
```

## 5. 文件大小限制

`file_reader.read_file()` 默认限制 100MB，超大文件需调整：

```python
from topo.parser.file_reader import read_file

# 允许读取 200MB 文件
content = read_file("large_log.txt", max_size=200*1024*1024)
```

或分割大文件：
```bash
# Linux/macOS
split -b 50M large_log.txt chunk_

# Windows PowerShell
Get-Content large_log.txt -ReadCount 50000 | Set-Content -Path "chunk_{0}.txt"
```

## 6. 故障排查

### 外键检查未生效
```python
import sqlite3
conn = sqlite3.connect("topo.db")
cursor = conn.cursor()

# 检查外键状态
cursor.execute("PRAGMA foreign_keys")
print(cursor.fetchone()[0])  # 应该是 1

# 检查 journal 模式
cursor.execute("PRAGMA journal_mode")
print(cursor.fetchone()[0])  # 应该是 wal
```

### 重复链路问题
```sql
-- 查找重复链路
SELECT src_device, src_if, dst_device, dst_if, COUNT(*) as cnt
FROM links
GROUP BY src_device, src_if, dst_device, dst_if
HAVING cnt > 1;

-- 手动去重（保留最新）
DELETE FROM links
WHERE id NOT IN (
    SELECT MAX(id)
    FROM links
    GROUP BY src_device, src_if, dst_device, dst_if
);
```

### 日志警告不显示
确保主程序调用了 `setup_logging()`：
```python
# 在 main 函数开头
from topo.utils.logging_config import setup_logging
setup_logging(level="WARNING")  # 至少 WARNING 级别
```

## 7. 最佳实践总结

1. ✅ 所有新项目使用最新 schema（自动包含唯一约束）
2. ✅ 旧数据库运行一次 `migrate.py`
3. ✅ 主程序入口配置日志（`setup_logging()`）
4. ✅ 定期运行 `verify.py` 检查完整性
5. ✅ 使用 `TopoDAO` 而非直接 `sqlite3.connect()`
6. ✅ WAL 模式下每个连接都启用外键检查
7. ✅ 超大日志文件分割后再导入
