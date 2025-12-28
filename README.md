# GCC 核心交换机拓扑自动化管理系统

🚀 **全栈网络拓扑管理平台** - 支持 SSH 自动采集、Web 可视化、异常检测、多格式导出

## ✨ 核心特性

### 📡 自动化采集
- **SSH 自动采集**：通过 Paramiko 自动连接交换机，执行命令并保存日志
- **多厂商支持**：华为、思科、H3C、锐捷等主流厂商
- **定时任务**：可配置自动定期采集，无需人工干预
- **批量管理**：支持管理多台设备，批量执行采集任务

### 🌐 Web 管理系统
- **用户认证**：基于角色的权限控制（Admin/User/Viewer）
- **设备管理**：设备配置 CRUD、连接信息加密存储
- **任务调度**：采集任务创建、执行、历史记录
- **文件上传**：支持手动上传日志文件并自动导入
- **拓扑可视化**：Mermaid.js 实时渲染网络拓扑图

### 🔍 智能分析
- **日志解析**：自动解析 LLDP、Trunk、接口描述、STP 等信息
- **异常检测**：识别环路风险、Trunk 不一致、LLDP 邻居抖动等 4 类异常
- **接口标准化**：自动规范化 `GE/XGE/Eth-Trunk` 格式
- **哈希去重**：避免重复导入，支持增量更新

### 📊 数据导出
- **多格式支持**：Mermaid (.mmd)、PDF (Graphviz)、Markdown
- **API 接口**：RESTful API 支持程序化访问
- **批量导出**：支持批量导出所有设备拓扑

## 📦 快速开始

### 方式 1：使用 Web 管理系统（推荐）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库
python init_db_with_management.py

# 3. 启动 Web 服务器
./start_web_management.sh
# 或
python -m topo.web.app_v2 --port 5000

# 4. 访问浏览器
http://127.0.0.1:5000

# 5. 登录（首次）
用户名: admin
密码: admin123
```

**功能说明：**
- ✅ 设备管理：添加交换机 IP、用户名、密码
- ✅ 自动采集：SSH 连接设备，执行命令，保存日志
- ✅ 任务调度：创建采集任务，查看执行历史
- ✅ 文件上传：手动上传日志文件并导入
- ✅ 拓扑可视化：查看网络拓扑图和异常
- ✅ 用户管理：多用户、角色权限控制

---

### 方式 2：使用 CLI 命令行（传统）

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install click

# （可选）安装 PDF 导出支持
sudo apt install graphviz  # Linux (Debian/Ubuntu)
brew install graphviz      # macOS
# 或安装 Mermaid CLI: npm install -g @mermaid-js/mermaid-cli
```

### 2. 准备日志文件

在华为交换机上执行以下命令并保存输出到 `data/raw/` 目录：

```bash
# 必需命令
display lldp neighbor brief
display lldp neighbor system-name
display eth-trunk
display interface description
display stp brief

# 示例：保存到文件
# SSH 到交换机后：screen-length 0 temporary
# 然后执行上述命令，复制输出到 data/raw/Core_CSS_20231228.log
```

### 3. 导入日志

```bash
# 使用便捷脚本
./topo_cli import-log data/raw/Core_CSS_20231228.log

# 或直接调用 Python 模块
python -m topo import-log data/raw/Core_CSS_20231228.log

# 批量导入
./topo_cli import-log data/raw/*.log
```

输出示例：
```
正在导入日志文件: data/raw/Core_CSS_20231228.log
✓ 导入成功！
  设备名: Core
  LLDP 邻居: 3 条
  Trunk 配置: 2 个
  接口配置: 4 个
  STP Blocked: 1 个
  链路: 3 条
```

### 4. 查看设备与异常

```bash
# 列出所有设备
./topo_cli list-devices

# 查看检测到的异常
./topo_cli anomalies

# 查看导入历史
./topo_cli history
```

### 5. 导出拓扑图

```bash
# 导出为 Mermaid 格式
./topo_cli export Core --format mermaid -o outputs/core.mmd

# 导出为 Markdown（包含 Mermaid 代码块）
./topo_cli export Core --format markdown -o outputs/core.md

# 导出为 PDF（需要安装 Graphviz 或 Mermaid CLI）
./topo_cli export Core --format pdf -o outputs/core.pdf
```

### 6. 启动 Web 界面（可选）

```bash
# 使用便捷脚本
python test_web.py

# 或使用 Flask CLI
.venv/bin/python -m flask --app topo.web.app:create_app run --host 0.0.0.0 --port 5000

# 或使用模块启动
.venv/bin/python -m topo.web.app --port 5000 --debug

# 访问浏览器
# 打开 http://127.0.0.1:5000
```

Web 界面功能：
- **设备列表**：查看所有设备统计（设备数、异常数、链路数）
- **设备详情**：可视化拓扑图（Mermaid 渲染）、链路列表、异常列表
- **异常检测**：过滤查看不同类型的网络异常
- **导出功能**：下载 Mermaid/DOT 格式拓扑文件
- **API 接口**：RESTful API 支持程序化访问

## 📚 使用示例

# 导出为 PDF（需要 Graphviz）
./topo_cli export Core --format pdf-graphviz -o outputs/core.pdf

# 限制链路数量（防止图过大）
./topo_cli export Core --max-links 30
```

## 📋 CLI 命令参考

```bash
# 导入日志
./topo_cli import-log <log_file> [--device <name>] [--force]

# 列出设备
./topo_cli list-devices [--anomalies]  # 仅显示有异常的设备

# 查看异常
./topo_cli anomalies [--severity error|warning]

# 导出拓扑
./topo_cli export <device> \
  --format mermaid|markdown|pdf-graphviz|pdf-mermaid|dot \
  --output <file> \
  --max-links <num>

# 标记链路可信度
./topo_cli mark <device> <src_if> <dst_device> <dst_if> trusted|suspect|ignore

# 查看导入历史
./topo_cli history

# 帮助信息
./topo_cli --help
./topo_cli <command> --help
```

## 🔧 高级用法

### 使用不同的数据库

```bash
# 所有命令都支持 --database 参数
./topo_cli -d /path/to/project.db import-log device.log
./topo_cli -d /path/to/project.db list-devices
```

### 编程接口

```python
from topo.db.dao import TopoDAO
from topo.parser import LogParser
from topo.rules.detector import detect_all_anomalies
from topo.exporter.mermaid import MermaidExporter

# 使用 Context Manager 自动管理事务
with TopoDAO("topo.db") as dao:
    # 导入日志
    parser = LogParser(dao)
    result = parser.import_log_file("data/raw/Core.log")
    
    # 运行异常检测
    detect_all_anomalies(dao)
    
    # 导出拓扑图
    exporter = MermaidExporter(dao)
    exporter.export_device_topology(
        "Core",
        output_file="outputs/core.mmd",
        max_phy_links=50
    )
    # 自动提交和关闭
```

## 📂 项目结构

```
network_CoreTopo/
├── topo/                    # 核心代码
│   ├── __init__.py
│   ├── __main__.py         # CLI 入口
│   ├── cli.py              # Click 命令实现
│   ├── db/                 # 数据库层
│   │   ├── schema.py       # SQLite 表结构定义
│   │   ├── dao.py          # 数据访问对象
│   │   ├── migrate.py      # 数据库迁移工具
│   │   └── verify.py       # 完整性验证
│   ├── parser/             # 日志解析器
│   │   ├── __main__.py     # 主解析器入口
│   │   ├── file_reader.py  # 文件读取（编码检测）
│   │   ├── normalize.py    # 接口名标准化
│   │   ├── lldp.py         # LLDP 邻居解析
│   │   ├── trunk.py        # Eth-Trunk 解析
│   │   ├── interface_desc.py # 接口描述解析
│   │   └── stp.py          # STP 状态解析
│   ├── exporter/           # 拓扑导出
│   │   ├── mermaid.py      # Mermaid 格式
│   │   └── pdf.py          # PDF 导出
│   ├── rules/              # 异常检测规则
│   │   └── detector.py     # 4 种检测规则
│   └── utils/              # 工具函数
│       └── logging_config.py
├── data/                   # 数据目录
│   └── raw/               # 原始日志文件
├── outputs/               # 导出结果
├── docs/                  # 文档
│   ├── develop.md        # 开发文档（v0.3）
│   └── usage_examples.md # 使用示例
├── tests/                # 测试（进行中）
├── topo_cli              # 便捷启动脚本
├── test_pdf_export.sh    # PDF 导出测试脚本
├── topo.db              # SQLite 数据库（运行时生成）
└── README.md            # 本文件
```

## 🔍 异常检测说明

工具会自动检测以下 4 类网络异常：

1. **suspect_loop** - 疑似环路
   - 单个物理接口出现多个不同 LLDP 邻居
   - 可能原因：环路、链路抖动、中间设备故障

2. **suspect_mixed_link** - 疑似混合链路
   - 同一接口既有 LLDP 邻居又有接口描述指向不同设备
   - 需要人工确认哪个信息更准确

3. **trunk_inconsistent** - Trunk 不一致
   - Trunk 成员接口指向不同的邻居设备
   - 可能配置错误或物理连接问题

4. **unstable_neighbor** - LLDP 邻居不稳定
   - 邻居 Exptime < 60 秒（默认 120 秒）
   - 可能链路质量差或 LLDP 配置问题

对于误报，可使用 `./topo_cli mark` 命令标记链路为 `ignore`。

## 🛠️ 故障排查

### 编码问题

```bash
# 工具自动检测 UTF-8/UTF-16/GBK，如仍有问题可手动转换
iconv -f GBK -t UTF-8 device.log > device_utf8.log
```

### 数据库损坏

```bash
# 备份
cp topo.db topo.db.backup

# 验证完整性
python -m topo.db.verify topo.db

# 迁移修复
python -m topo.db.migrate topo.db
```

### PDF 导出失败

```bash
# 检查转换工具
which dot    # Graphviz
which mmdc   # Mermaid CLI

# 先导出中间格式
./topo_cli export Core -f dot -o core.dot
./topo_cli export Core -f mermaid -o core.mmd

# 手动转换
dot -Tpdf core.dot -o core.pdf
mmdc -i core.mmd -o core.pdf
```

## 📊 开发状态

- ✅ 数据库设计（8 张表，外键约束）
- ✅ 日志解析器（LLDP、Trunk、接口描述、STP）
- ✅ 异常检测（4 种规则）
- ✅ 导出功能（Mermaid、PDF）
- ✅ CLI 接口（6 个命令）
- ✅ Web UI（Flask 应用，8 个路由）
- ✅ 单元测试（19 个测试全部通过）
- ⏳ 集成测试（可选，未开始）

## 🌐 Web 界面

### 启动服务器

```bash
# 方式 1：使用测试脚本
python test_web.py

# 方式 2：使用 Flask CLI
.venv/bin/python -m flask --app topo.web.app:create_app run --host 0.0.0.0

# 方式 3：使用模块启动（支持自定义参数）
.venv/bin/python -m topo.web.app --port 5000 --host 127.0.0.1 --debug
```

### 功能特性

- **设备列表页** (`/`)
  - 统计卡片：总设备数、异常数量、链路数量
  - 设备表格：名称、型号、导入时间、链路数、异常数
  
- **设备详情页** (`/device/<name>`)
  - 设备基本信息（名称、型号、管理 IP、SysName）
  - Mermaid.js 实时渲染拓扑图（支持缩放、导出）
  - 链路列表（源/目标接口、可信度标记）
  - 关联异常列表（类型、严重性、详细信息）

- **异常检测页** (`/anomalies`)
  - 全局异常列表（可按严重性过滤）
  - 异常类型说明（4 种检测规则解释）
  - 设备名、接口、检测时间

- **API 接口**
  - `GET /api/device/<name>/topology` - 获取 Mermaid 代码（JSON）
  - `GET /api/device/<name>/export/<format>` - 导出拓扑（mermaid/dot/pdf）
  - `POST /api/link/mark` - 标记链路可信度
  - `GET /api/detect` - 触发异常检测

### 技术栈

- **后端**：Flask 3.1.0 (Python 3.13)
- **前端**：原生 HTML5/CSS3 + Mermaid.js 10.x
- **数据库**：SQLite 3 (WAL 模式)
- **可视化**：Mermaid.js (客户端渲染)

## 📊 项目状态

## 📖 更多文档

- [开发文档](docs/develop.md) - 详细的技术设计与架构说明
- [使用示例](docs/usage_examples.md) - 完整的使用场景和工作流
- [数据库 Schema](topo/db/schema.py) - 数据模型详细定义

## 📝 许可证

（待添加）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
