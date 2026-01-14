# GCC 核心交换机拓扑自动化（S12700/S6730）开发文档（v0.3）

> 实现手册为主，设计蓝图为辅：从日志解析到导出、Web/CLI 最小实现、数据模型与字段规范均在此。无框架/依赖限制，可自由选型。

---

## 0. 快速浏览（对齐）
- **定位**：校园/园区网；核心 S12700 + 汇聚 S6730；离线日志解析优先，同时支持 Web 管理与采集。
- **核心闭环**：日志导入/采集 → 解析/异常标记 → SQLite → Web/CLI 补全 → Mermaid/PDF 导出。
- **优先级**：先做可跑通的一跳拓扑 + Web 管理最小可用；定时采集依赖调度器常驻执行。

---

## 1. 目标与边界

### 1.1 MVP 范围
1. **输入**：核心/汇聚交换机通过 SSH 采集的命令输出（`.log/.txt`，UTF-8/UTF-16/GBK 均可）。
2. **解析**：结构化设备信息、LLDP 邻居、Eth-Trunk 成员、接口描述、STP 摘要。
3. **存储**：SQLite，支持多台设备增量导入；记录来源文件与时间。
4. **异常标记**：多邻居口、Trunk 成员指向多个设备等，自动打 `suspect`。
5. **输出**：Mermaid `.mmd/.md`；PDF（Graphviz/ReportLab/Mermaid 转 SVG 再转 PDF）。
6. **交互**：Web + CLI；支持用户认证、设备管理、采集任务、导出拓扑。

### 1.2 非目标（当前阶段不做）
- 不做 Visio/其他专有格式导出。
- 不做实时全网发现，仅离线日志驱动。
- 不强行自动消除所有环路，优先提示 + 人工确认。
- 不做复杂多租户；仅提供基础角色权限（admin/user/viewer）。

---

## 2. 总体架构

```mermaid
flowchart LR
  raw[原始日志 *.log] --> ingest[导入/编码探测]
  ingest --> parse[解析器：LLDP / Eth-Trunk / STP / Desc]
  parse --> normalize[接口名标准化 + 去重]
  normalize --> rules[异常规则\n(多邻居/Trunk 异常/Exptime 波动)]
  rules --> sqlite[(SQLite)]
  sqlite --> ui[Web/CLI：人工确认/补全描述]
  sqlite --> exportMermaid[导出 Mermaid]
  sqlite --> exportPDF[导出 PDF]
  exportMermaid --> outputs[outputs/]
  exportPDF --> outputs
```

核心模块：
- `collector`（后续）：SSH 采集器，可选。
- `parser`：日志解析 + 接口归一化 + 异常规则。
- `db`：SQLite schema + migration + DAO。
- `exporter`：Mermaid / PDF。
- `ui`：Flask/Jinja 或 CLI。

**最小可用要求（MVP）**
- CLI：`topo import-log <file>`，`topo export <device> --format mermaid|markdown|pdf-graphviz|pdf-mermaid|dot`，`topo mark <device> <src_if> <dst_device> <dst_if> trusted|suspect|ignore`。
- Web：上传日志、列表设备、编辑接口描述、标记链路可信度、导出按钮。

---

## 3. 输入采集与约定
- **必跑命令**（核心/汇聚通用）：  
  `display lldp neighbor brief`；`display lldp neighbor system-name`；`display eth-trunk`；`display interface description`；`display stp brief`。  
  可选：`display version`、`display device`、`display interface brief`。
- **采集器支持**：内置 Huawei/Cisco/H3C 命令集；解析器当前以 Huawei `display` 输出为主。
- **限制兼容**：`display stp brief` 不带参数；过滤用 `| inc` 时兼容空结果。
- **文件命名建议**：`{device}_{yyyymmdd_hhmm}.log`，导入时保存 `device_name` 与 `hash` 便于去重。
- **编码处理**：探测 UTF-8/UTF-16，小文件一次读入；大文件按块流式。
- **单元划分**：同一文件可能包含多段命令输出，用命令提示符或命令回显作为分隔。

示例日志片段（LLDP brief）：
```
Local Intf    Exptime  Neighbor Dev            Neighbor Intf
GE1/6/0/21    101      Ruijie                  Te0/52
GE1/6/0/21    102      Huawei                  GE0/0/0
```

示例日志片段（Eth-Trunk）：
```
Eth-Trunk6   NORMAL   1   1000M(a)  1000M(a)  up
  Port Status
  GE1/6/0/19    Product: GigabitEthernet     Status: up
  GE1/6/0/20    Product: GigabitEthernet     Status: up
```

---

## 4. 数据模型（SQLite）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `devices` | `id`, `name`, `mgmt_ip`, `vendor`, `model`, `site`, `created_at` | 设备主表 |
| `interfaces` | `id`, `device_id`, `name`, `description`, `admin_status`, `oper_status` | 接口基础信息 |
| `trunks` | `id`, `device_id`, `name`, `mode`, `oper_status` | Eth-Trunk 元数据 |
| `trunk_members` | `trunk_id`, `interface_id` | Trunk 成员映射 |
| `lldp_neighbors` | `id`, `device_id`, `local_if`, `neighbor_dev`, `neighbor_if`, `exptime`, `source_file`, `collected_at` | 原始 LLDP 记录 |
| `links` | `id`, `src_device`, `src_if`, `dst_device`, `dst_if`, `link_type`(phy/trunk), `confidence`(trusted/suspect/ignore), `notes` | 用于绘图的边 |
| `anomalies` | `id`, `device_id`, `type`, `severity`, `detail_json`, `created_at` | 异常记录 |
| `imports` | `id`, `device_name`, `source_file`, `hash`, `imported_at` | 导入任务审计 |

索引建议：
- `lldp_neighbors(device_id, local_if)`；`links(src_device, src_if)`；`imports(hash)`。

管理扩展表（Web 管理系统）：
- `users`、`managed_devices`、`collection_tasks`、`operation_logs`、`upload_files`、`system_config`。
- `device_credentials` 用于采集连接信息（单设备一条记录）。

DDL（示例，可直接执行）：
```sql
create table devices (
  id integer primary key,
  name text not null unique,
  mgmt_ip text,
  vendor text,
  model text,
  site text,
  created_at text default current_timestamp
);
create table interfaces (
  id integer primary key,
  device_id integer not null,
  name text not null,
  description text,
  admin_status text,
  oper_status text,
  unique(device_id, name)
);
create table trunks (
  id integer primary key,
  device_id integer not null,
  name text not null,
  mode text,
  oper_status text,
  unique(device_id, name)
);
create table trunk_members (
  trunk_id integer not null,
  interface_id integer not null,
  primary key (trunk_id, interface_id)
);
create table lldp_neighbors (
  id integer primary key,
  device_id integer not null,
  local_if text not null,
  neighbor_dev text not null,
  neighbor_if text,
  exptime integer,
  source_file text,
  collected_at text
);
create table links (
  id integer primary key,
  src_device text not null,
  src_if text not null,
  dst_device text not null,
  dst_if text not null,
  link_type text not null, -- phy/trunk
  confidence text not null default 'trusted', -- trusted/suspect/ignore
  notes text
);
create table anomalies (
  id integer primary key,
  device_id integer,
  type text,
  severity text,
  detail_json text,
  created_at text default current_timestamp
);
create table imports (
  id integer primary key,
  device_name text,
  source_file text,
  hash text unique,
  imported_at text default current_timestamp
);
```

---

## 5. 解析器设计（实现手册）

### 5.1 接口名标准化（必须）
- `GE` → `GigabitEthernet`；`XGE` → `XGigabitEthernet`；`Eth-TrunkX` 保持。
- 去掉多余空格与大小写差异，统一斜杠 `/`。

伪代码：
```python
def normalize_ifname(name: str) -> str:
    n = name.strip().replace(" ", "")
    n = re.sub(r"^GE", "GigabitEthernet", n, flags=re.I)
    n = re.sub(r"^XGE", "XGigabitEthernet", n, flags=re.I)
    return n
```

### 5.2 LLDP
- 解析 `neighbor brief`（含 Exptime）为主；`neighbor system-name` 可选接入用于补全设备名。
- 落库键：`(local_device, local_interface, neighbor_device, neighbor_interface)`，附 `exptime`、`source_file`。
- 对同一接口出现多个邻居，标记 `suspect_loop`。

解析要点：
- 表头行含 `Local Intf`；后续列用空格分隔，邻居设备名可包含 `-`、`_`。
- `Exptime` 取整；若为空则设为 NULL。
- 将接口名先 normalize 再入库。

### 5.3 Eth-Trunk
- 解析模式 `NORMAL/LACP`、成员口列表、oper status。
- 折叠规则：成员口若指向同一邻居 → 生成一条 trunk 边；指向多个邻居 → `trunk_inconsistent` 异常。

解析要点：
- `Eth-TrunkX` 行含模式、优先级、速率、状态；成员行以两个空格缩进或带 `Port Status`。
- 记录 `trunks`，成员落 `trunk_members`。

### 5.4 接口描述
- 解析 `display interface description`；空描述留空，支持后续 Web 补全。
- 补全后更新 `interfaces.description`，供导出时显示地点/楼栋。

解析要点：
- 行格式类似：`GigabitEthernet1/6/0/21  up   up   description text...`
- 描述可能包含空格，取接口名后的剩余文本。

### 5.5 STP 摘要
- 只解析整表输出，标注处于 `Discarding/Blocked` 的口，辅助定位环路。

解析要点：
- 行含接口、角色、状态；状态 `Discarding/Blocked/Forwarding`。
- 为处于阻塞的接口添加 `anomalies` 记录，类型 `stp_blocked`。

### 5.6 异常规则
- `suspect_loop`：单物理口出现多个不同邻居设备。
- `suspect_mixed_link`：邻居设备名为空或大量 “-”。
- `unstable_neighbor`：Exptime 波动（需多次采集比对）。
- `trunk_inconsistent`：Trunk 成员指向多个设备。

实现建议：
- 当前默认检测包含 `suspect_loop`、`suspect_mixed_link`、`trunk_inconsistent`；`unstable_neighbor` 需额外触发。
- 解析完成后按接口聚合邻居，计数>1 → `suspect_loop`。
- 统计邻居名为空或 `-` 占比>50% → `suspect_mixed_link`。
- 对同一 `(device, local_if, neighbor_dev)` 不同采集的 `exptime` 波动系数>阈值 → `unstable_neighbor`。

### 5.7 去重与增量
- 以 `imports.hash` 防重复导入同一文件。
- 同一设备、同一接口、相同邻居的记录若来源更近，覆盖旧记录；保留 `collected_at`。

伪代码（导入）：
```python
if hash(file) in imports: skip
for block in parse_blocks(file):
    parse_lldp(block) / parse_trunk(block) / ...
    upsert records by (device, ifname, neighbor)
record import row
```

---

## 6. 导出设计

### 6.1 Mermaid（首选）
- 默认折叠 Trunk，物理口仅展示前 N 条（配置项，如 30）。
- 可信度：`trusted` 正常绘制，`suspect` 用特殊样式/颜色，`ignore` 不导出。
- 多跳：导入多台汇聚日志后，按 BFS 分层展开（当前实现为中心设备一跳）。

Mermaid 生成示例（函数签名）：
```python
def render_mermaid(db, device, max_phys_links=30):
    # 查询 links，按 link_type、confidence 过滤
    # 生成 mermaid graph LR 文本
```

样式建议（若需自定义）：`classDef suspect fill:#ffe6e6,stroke:#ff4d4f;`，`classDef trusted fill:#e6f7ff,stroke:#1890ff;`。若需官方设备图标/扁平化网元，可后续接入（需确认素材来源）。

### 6.2 PDF（离线友好）
- 路线 1：Mermaid → `mmdc` → SVG/PNG → PDF。
- 路线 2：Graphviz dot 直接产 PDF（全离线）。

输出目录：`outputs/topology.mmd`，`outputs/topology.pdf`。

---

## 7. UI / CLI 需求（最小实现）

### 7.1 Web（推荐）
- 功能要点：用户认证、设备管理、采集任务管理、日志上传、拓扑可视化、导出下载。
- API：提供设备拓扑与导出接口（`/api/device/<name>/topology`、`/api/device/<name>/export/<format>`）。
- UI 要素：设备列表、任务列表、异常列表、导出按钮、上传入口。

### 7.2 CLI（同步 Web 的核心操作）
- `topo import-log <file>`：导入日志（可用 `--force` 忽略哈希检查）。
- `topo list-devices [--anomalies]`
- `topo export <device> --format mermaid|markdown|pdf-graphviz|pdf-mermaid|dot -o outputs/core.mmd`
- `topo mark <device> <src_if> <dst_device> <dst_if> trusted|suspect|ignore`
- `topo schedule --interval 300`（自动采集调度器）。
  需在设备管理中启用 `auto_collect` 并设置 `collect_interval`。

---

## 8. 开发环境与目录结构

### 8.1 环境
- Python 3.11+，依赖：`click`、`flask`、`jinja2`、`werkzeug`、`bcrypt`、`paramiko`、`cryptography`、`pytest`。
- PDF 导出：系统安装 `graphviz` 或 `mermaid-cli`。
- 离线场景：提前准备 `mermaid-cli`/`graphviz` 的本地安装包。
- Web 管理环境变量：`SECRET_KEY`（必需）、`ADMIN_PASSWORD`（初始化管理员）、`FERNET_KEY`（加密设备密码，可存 `~/.topo_fernet_key`）。

### 8.2 目录建议
```
gcc-topology/
  app.py                 # Flask 入口（可选）
  topo/
    collector/           # SSH 采集
    parser/              # Huawei 日志解析
    db/                  # sqlite + migration
    exporter/            # mermaid/pdf 导出
    rules/               # 异常检测规则
    management/          # 设备/任务/认证管理
    web/                 # Web 界面
  data/
    raw/                 # 原始日志
    parsed/              # 解析中间产物（json）
  docs/
    develop.md
  uploads/               # Web 上传日志
  logs/                  # 运行日志
  outputs/
    topology.mmd
    topology.pdf
```

---

## 9. 开发与验证流程
1. 准备日志：放入 `data/raw/*.log`。
2. 运行解析：`./topo_cli import-log data/raw/core.log` 或 `python -m topo import-log data/raw/core.log`。
3. 查看 SQLite：`sqlite3 topo.db "select * from lldp_neighbors limit 5;"`。
4. 标记链路/补全描述：通过 Web/CLI。
5. 导出：`./topo_cli export Core_CSS --format mermaid -o outputs/core.mmd`。
6. 校验：手动检查多邻居口、Trunk 折叠是否正确。

---

## 10. 测试计划
- 单元测试：接口归一化、LLDP/Eth-Trunk/STP 解析、异常规则。
- 集成测试：导入一份真实核心日志，生成 SQLite + Mermaid，核对邻居数量（例如核心日志中 LLDP 95 条、Trunk 19 个）。
- 回归：多设备增量导入，确认去重逻辑与导出一致性。

---

## 11. 路线图（迭代建议）
1. **核心一跳**：日志导入 → 解析 → SQLite → Mermaid。
2. **异常提示 + 人工确认**：UI/CLI 编辑 description、可信度；渲染 suspect 样式。
3. **汇聚批量导入**：多台汇聚日志，BFS 生成多跳拓扑。
4. **自动采集（可选）**：SSH/批量执行，含账号/密码/密钥管理。

---

## 12. 附录：常见问题
- `display stp brief` 无输出：保持兼容，解析为空表即可。
- 多邻居口：优先提示并标记 `suspect`，不自动决策。
- 编码异常：启用编码探测，统一内部使用 UTF-8。
