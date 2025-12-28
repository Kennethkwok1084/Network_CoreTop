# Web UI 使用指南

## 快速启动

### 1. 启动服务器

```bash
# 方式 1：使用测试脚本（推荐）
cd /srv/code/network_CoreTopo
python test_web.py

# 方式 2：使用 Flask CLI
.venv/bin/python -m flask --app topo.web.app:create_app run --host 0.0.0.0 --port 5000

# 方式 3：使用模块启动（支持自定义参数）
.venv/bin/python -m topo.web.app --port 5000 --host 127.0.0.1 --debug

# 方式 4：指定数据库路径
.venv/bin/python -m topo.web.app --database /path/to/custom.db --port 8080
```

### 2. 访问界面

打开浏览器访问：
- 本地访问：http://127.0.0.1:5000
- 网络访问：http://<服务器IP>:5000

**注意**：默认使用 Flask 开发服务器，生产环境请使用 Gunicorn/uWSGI 等 WSGI 服务器。

## 功能页面

### 首页 - 设备列表 (`/`)

**功能特性：**
- 统计卡片显示：
  - 总设备数
  - 检测到的异常数量
  - 拓扑链路总数
- 设备表格列：
  - 设备名称（点击查看详情）
  - 设备型号
  - 导入时间
  - 链路数量
  - 异常数量

**操作：**
- 点击设备名称 → 跳转到设备详情页
- 点击导航栏"异常检测" → 查看全局异常列表

---

### 设备详情页 (`/device/<设备名>`)

**功能模块：**

#### 1. 设备基本信息
显示卡片：
- 设备名称（Device Name）
- 设备型号（Model）
- 管理 IP（Management IP）
- 系统名称（System Name，来自 LLDP）

#### 2. 拓扑图可视化
- **渲染引擎**：Mermaid.js（客户端实时渲染）
- **图形类型**：Graph LR（从左到右流程图）
- **节点样式**：
  - 中心设备：蓝色填充 + 加粗边框
  - 可疑设备：红色填充
  - Trunk 链路：绿色边框
- **操作功能**：
  - 浏览器内缩放、拖动
  - 点击"下载 Mermaid"按钮 → 下载 `.mmd` 文件
  - 点击"下载 DOT"按钮 → 下载 Graphviz `.dot` 文件

#### 3. 链路列表表格
显示设备的所有物理/逻辑链路：
- 源接口（Source Interface）
- 目标设备（Destination Device）
- 目标接口（Destination Interface）
- 可信度（Confidence）：
  - `trusted` - 已确认（绿色）
  - `suspect` - 可疑（橙色）
  - `ignore` - 忽略（灰色）

**操作：**
- 使用 CLI 命令标记链路可信度：
  ```bash
  ./topo_cli mark Core GE1/6/0/21 --confidence suspect
  ```

#### 4. 异常列表
显示与该设备相关的所有检测到的异常：
- 异常类型（Type）
- 严重性（Severity）：error / warning
- 检测时间（Detected At）
- 详细信息（Detail）：JSON 格式

---

### 异常检测页 (`/anomalies`)

**功能特性：**

#### 1. 异常列表表格
显示全局所有异常记录：
- 设备名称
- 异常类型（`suspect_loop` / `suspect_mixed_link` / `trunk_inconsistent` / `unstable_neighbor`）
- 严重性级别
- 检测时间
- 详细信息（可展开查看 JSON）

**过滤功能：**
- 点击"筛选"按钮 → 按严重性过滤（error / warning）

#### 2. 异常类型说明表格
详细解释 4 种检测规则：

| 类型 | 说明 | 可能原因 |
|------|------|----------|
| `suspect_loop` | 单个物理接口出现多个不同 LLDP 邻居 | 环路、链路抖动、中间设备故障 |
| `suspect_mixed_link` | 同一接口的 LLDP 和描述指向不同设备 | 配置不同步、误接线 |
| `trunk_inconsistent` | Trunk 成员接口指向不同邻居设备 | 配置错误、物理连接问题 |
| `unstable_neighbor` | LLDP Exptime < 60 秒 | 链路质量差、LLDP 配置异常 |

---

## API 接口

### 1. 获取设备拓扑（JSON）

```http
GET /api/device/<设备名>/topology
```

**响应示例：**
```json
{
  "mermaid": "```mermaid\ngraph LR\n  Core[Core]:::center\n  ..."
}
```

**使用场景：**
- 程序化获取拓扑数据
- 集成到其他系统
- 批量导出脚本

---

### 2. 导出设备拓扑（文件）

```http
GET /api/device/<设备名>/export/<格式>
```

**支持格式：**
- `mermaid` - Mermaid 图表代码（`.mmd`）
- `dot` - Graphviz DOT 格式（`.dot`）
- `pdf` - PDF 文档（需安装 Graphviz 或 Mermaid CLI）

**示例：**
```bash
# 下载 Core 设备的 Mermaid 拓扑
curl -O http://127.0.0.1:5000/api/device/Core/export/mermaid

# 批量导出所有设备
for device in Core Problem; do
  curl -o "${device}.mmd" "http://127.0.0.1:5000/api/device/${device}/export/mermaid"
done
```

---

### 3. 标记链路可信度（POST）

```http
POST /api/link/mark
Content-Type: application/json

{
  "device": "Core",
  "src_if": "GigabitEthernet1/6/0/21",
  "dst_device": "Ruijie Building A",
  "dst_if": "TenGigabitEthernet0/52",
  "confidence": "trusted"
}
```

**可信度值：**
- `trusted` - 已人工确认
- `suspect` - 需要核查
- `ignore` - 忽略误报

**使用场景：**
- 批量标记自动化脚本
- 第三方工具集成

---

### 4. 触发异常检测

```http
GET /api/detect
```

**响应示例：**
```json
{
  "success": true,
  "count": 2
}
```

**说明：**
- 重新运行所有设备的异常检测
- 返回检测到的异常总数

---

## 技术架构

### 前端技术栈
- **HTML5**：语义化标签
- **CSS3**：响应式网格布局（Grid + Flexbox）
- **JavaScript**：Mermaid.js 10.x（通过 CDN 加载）

### 后端技术栈
- **Flask 3.1.0**：轻量级 Web 框架
- **Python 3.13**：类型提示、dataclasses
- **SQLite 3**：WAL 模式、外键约束

### 数据流
```
浏览器
  ↓ HTTP Request
Flask 路由
  ↓ 调用
TopoDAO (数据访问层)
  ↓ 查询
SQLite 数据库 (topo.db)
  ↓ 返回数据
Jinja2 模板渲染
  ↓ HTML + Mermaid 代码
浏览器
  ↓ Mermaid.js 解析
拓扑图渲染显示
```

---

## 生产部署

### 使用 Gunicorn（推荐）

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动 4 个 worker
gunicorn -w 4 -b 0.0.0.0:5000 "topo.web.app:create_app()"

# 使用配置文件
gunicorn -c gunicorn_config.py "topo.web.app:create_app()"
```

**gunicorn_config.py 示例：**
```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
timeout = 30
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"
```

---

### 使用 Nginx 反向代理

**Nginx 配置示例：**
```nginx
server {
    listen 80;
    server_name topo.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /srv/code/network_CoreTopo/topo/web/static;
    }
}
```

---

### 使用 Systemd 服务

**创建 `/etc/systemd/system/topo-web.service`：**
```ini
[Unit]
Description=GCC Topology Web UI
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/srv/code/network_CoreTopo
Environment="PATH=/srv/code/network_CoreTopo/.venv/bin"
ExecStart=/srv/code/network_CoreTopo/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "topo.web.app:create_app()"
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**启动服务：**
```bash
sudo systemctl daemon-reload
sudo systemctl enable topo-web
sudo systemctl start topo-web
sudo systemctl status topo-web
```

---

## 故障排查

### 问题 1：端口被占用

**错误信息：**
```
OSError: [Errno 98] Address already in use
```

**解决方法：**
```bash
# 查找占用 5000 端口的进程
lsof -i :5000
# 或
netstat -tlnp | grep :5000

# 杀掉进程
kill -9 <PID>

# 或更换端口
.venv/bin/python -m topo.web.app --port 8080
```

---

### 问题 2：数据库锁定

**错误信息：**
```
sqlite3.OperationalError: database is locked
```

**解决方法：**
```bash
# 检查数据库是否已启用 WAL 模式
sqlite3 topo.db "PRAGMA journal_mode;"
# 应返回 wal

# 如果不是 WAL，手动设置
sqlite3 topo.db "PRAGMA journal_mode=WAL;"

# 杀掉占用数据库的进程
fuser topo.db
```

---

### 问题 3：Mermaid 图表不显示

**可能原因：**
1. CDN 无法访问
2. JavaScript 被浏览器阻止
3. Mermaid 代码语法错误

**解决方法：**
```bash
# 检查浏览器控制台（F12 → Console）
# 查看是否有 JavaScript 错误

# 手动测试 Mermaid 代码
curl -s "http://127.0.0.1:5000/api/device/Core/topology" | jq -r '.mermaid'

# 复制到 Mermaid Live Editor 测试
# https://mermaid.live
```

---

### 问题 4：服务器性能慢

**优化方法：**

1. **增加 Gunicorn Worker 数量**
   ```bash
   # CPU 核心数 * 2 + 1
   gunicorn -w 9 -b 0.0.0.0:5000 "topo.web.app:create_app()"
   ```

2. **启用 SQLite 查询缓存**
   ```python
   # 在 dao.py 中添加
   cursor.execute("PRAGMA cache_size = -10000")  # 10MB 缓存
   ```

3. **使用 Redis 缓存拓扑数据**
   ```bash
   pip install flask-caching redis
   ```

---

## 安全建议

### 1. 不要在公网暴露 Flask 开发服务器

❌ **不安全：**
```bash
.venv/bin/python -m topo.web.app --host 0.0.0.0 --port 5000 --debug
```

✅ **推荐：**
```bash
# 本地开发
.venv/bin/python -m topo.web.app --host 127.0.0.1 --port 5000

# 生产环境
gunicorn -b 127.0.0.1:5000 "topo.web.app:create_app()" & nginx 反向代理
```

### 2. 添加身份验证（可选）

```python
# topo/web/app.py
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # 实现你的认证逻辑
    return username == "admin" and password == "secret"

@app.route('/')
@auth.login_required
def index():
    # ...
```

### 3. 限制请求速率

```bash
pip install Flask-Limiter

# app.py
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/detect')
@limiter.limit("10 per minute")
def api_detect():
    # ...
```

---

## 更多资源

- [Flask 文档](https://flask.palletsprojects.com/)
- [Mermaid.js 文档](https://mermaid.js.org/)
- [Gunicorn 部署指南](https://gunicorn.org/)
- [Nginx 反向代理](https://nginx.org/en/docs/)
