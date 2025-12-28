# 使用示例

本文档展示 GCC 核心交换机拓扑自动化工具的常见使用场景。

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install click

# （可选）安装 PDF 导出支持
sudo apt install graphviz  # Linux
brew install graphviz      # macOS
```

### 2. 导入日志文件

```bash
# 方式 1：使用便捷脚本
./topo_cli import-log data/raw/Core_CSS_20231228.log

# 方式 2：直接调用 Python 模块
python -m topo import-log data/raw/Core_CSS_20231228.log

# 导入多个文件
./topo_cli import-log data/raw/*.log
```

### 3. 查看设备列表

```bash
./topo_cli list-devices
```

输出示例：
```
共 2 个设备:

• Core
  链路: 3 条
  异常: 1 个
    - [info] stp_blocked

• Problem
  链路: 3 条
  异常: 1 个
    - [warning] suspect_loop
```

### 4. 查看异常检测结果

```bash
./topo_cli anomalies
```

输出示例：
```
共检测到 2 个异常:

[WARNING] suspect_loop
  设备: ID:2
  时间: 2025-12-28 06:18:29
  详情: {
    "interface": "GigabitEthernet1/0/1",
    "neighbors": ["Switch-A", "Switch-B"],
    "count": 2,
    "reason": "单个物理口出现多个不同邻居设备，可能存在环路或链路抖动"
}
```

### 5. 导出拓扑图

#### 5.1 导出 Mermaid 格式

```bash
# 导出为 .mmd 文件
./topo_cli export Core --format mermaid -o outputs/core.mmd

# 导出为 Markdown 格式（包含 Mermaid 代码块）
./topo_cli export Core --format markdown -o outputs/core.md
```

#### 5.2 导出 PDF 格式

```bash
# 使用 Graphviz 导出（需要安装 dot 命令）
./topo_cli export Core --format pdf-graphviz -o outputs/core.pdf

# 使用 Mermaid CLI 导出（需要安装 mmdc 命令）
./topo_cli export Core --format pdf-mermaid -o outputs/core.pdf

# 仅生成 DOT 文件（不转换为 PDF）
./topo_cli export Core --format dot -o outputs/core.dot
```

#### 5.3 限制链路数量

```bash
# 限制最多显示 20 条物理链路（防止图过大）
./topo_cli export Core --max-links 20
```

### 6. 标记链路可信度

当检测到误报时，可以手动标记链路的可信度：

```bash
# 标记为可信
./topo_cli mark Core XGE1/0/1 Core-Backup XGE1/0/2 trusted

# 标记为可疑
./topo_cli mark Core GE1/6/0/21 Unknown-Device GE0/1 suspect

# 标记为忽略
./topo_cli mark Core GE1/6/0/22 Test-Device GE0/1 ignore
```

### 7. 查看导入历史

```bash
./topo_cli history
```

输出示例：
```
最近 2 次导入:

• Core
  文件: data/raw/Core_CSS_20231228.log
  时间: 2025-12-28 06:15:46
  哈希: 26e107853f0464e4...

• Problem
  文件: data/raw/Problematic_Device.log
  时间: 2025-12-28 06:18:25
  哈希: 8d6ed84c0d5a61db...
```

## 高级用法

### 使用不同的数据库

```bash
# 指定数据库文件路径
./topo_cli -d /path/to/custom.db import-log device.log
./topo_cli -d /path/to/custom.db list-devices
```

### 编程接口示例

```python
from topo.db.dao import TopoDAO
from topo.parser import LogParser
from topo.rules.detector import detect_all_anomalies
from topo.exporter.mermaid import MermaidExporter

# 初始化 DAO
dao = TopoDAO("topo.db")

# 导入日志
parser = LogParser(dao)
parser.import_log_file("data/raw/Core.log")
dao.commit()

# 运行异常检测
detect_all_anomalies(dao)
dao.commit()

# 导出拓扑图
exporter = MermaidExporter(dao)
exporter.export_device_topology(
    "Core",
    output_file="outputs/core.mmd",
    max_phy_links=50
)

# 关闭连接
dao.close()
```

### Context Manager 模式

```python
from topo.db.dao import TopoDAO

with TopoDAO("topo.db") as dao:
    # 所有操作
    devices = dao.devices.list_all()
    for device in devices:
        print(device['name'])
    
    # 自动提交和关闭
```

## 工作流示例

### 完整的网络拓扑发现流程

```bash
# 1. 收集所有核心交换机的日志文件
#    假设已通过 SSH 收集到 data/raw/ 目录

# 2. 批量导入日志
for log in data/raw/*.log; do
    ./topo_cli import-log "$log"
done

# 3. 查看所有设备
./topo_cli list-devices

# 4. 检查异常
./topo_cli anomalies

# 5. 导出每个设备的拓扑图
./topo_cli export Core -f pdf-graphviz -o outputs/Core.pdf
./topo_cli export Aggregation -f pdf-graphviz -o outputs/Aggregation.pdf

# 6. 对于误报的链路，手动标记
./topo_cli mark Core GE1/0/1 Unknown GE0/1 ignore

# 7. 重新导出（会应用新的可信度标记）
./topo_cli export Core -f mermaid -o outputs/Core_updated.mmd
```

### 增量更新流程

```bash
# 第一次导入
./topo_cli import-log data/raw/Core_20231228.log

# 一周后，再次导入（自动去重）
./topo_cli import-log data/raw/Core_20240105.log

# 查看导入历史
./topo_cli history

# 导出最新拓扑
./topo_cli export Core -f pdf-graphviz
```

## 故障排查

### 日志文件编码问题

工具会自动尝试 UTF-8、UTF-16、GBK 编码。如果仍有问题：

```bash
# 检查文件编码
file -i data/raw/device.log

# 转换编码
iconv -f GBK -t UTF-8 device.log > device_utf8.log
```

### 数据库损坏

```bash
# 备份数据库
cp topo.db topo.db.backup

# 使用迁移工具修复
python -m topo.db.migrate topo.db

# 验证完整性
python -m topo.db.verify topo.db
```

### PDF 导出失败

```bash
# 检查是否安装了转换工具
which dot       # Graphviz
which mmdc      # Mermaid CLI

# 如果未安装，可以先导出 .mmd 或 .dot 文件
./topo_cli export Core -f mermaid -o core.mmd
./topo_cli export Core -f dot -o core.dot

# 然后手动转换
dot -Tpdf core.dot -o core.pdf
mmdc -i core.mmd -o core.pdf
```

## 性能优化

### 大规模网络（>100 个设备）

```bash
# 限制每个设备的链路数量
./topo_cli export Core --max-links 30

# 使用 DOT 格式（比 Mermaid 快）
./topo_cli export Core -f dot
```

### 数据库性能

```python
from topo.db.dao import TopoDAO

# 批量操作时关闭自动提交
dao = TopoDAO("topo.db")

# 批量插入
for log_file in log_files:
    parser.import_log_file(log_file)
    # 不要每次都 commit

# 最后统一提交
dao.commit()
dao.close()
```

## 参考

- [开发文档](develop.md) - 详细的技术设计
- [README](../README.md) - 项目概览
- [数据库 Schema](../topo/db/schema.py) - 数据模型定义
