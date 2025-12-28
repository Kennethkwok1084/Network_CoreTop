# 安全修复总结 - CSRF 和时间计算问题

**修复日期**: 2024-12-28  
**优先级**: 高（CSRF） + 中（时间计算）  
**状态**: ✅ 已完成并测试

---

## 1. CSRF 保护（高优先级）

### 问题描述
所有 POST 表单（设备管理、任务执行、文件上传、用户管理）都缺少 CSRF 令牌保护。任何恶意站点可诱导已登录用户发起以下敏感操作：
- 删除设备
- 执行采集任务
- 创建新任务
- 上传配置文件
- 创建用户账户

### 解决方案

#### 1.1 后端实现 (topo/web/app_v2.py)

**添加 CSRF 工具函数**：
```python
def generate_csrf_token():
    """生成 CSRF token"""
    return secrets.token_hex(32)
```

**在上下文处理器中注入 CSRF token 到所有模板**：
```python
@app.context_processor
def inject_globals():
    """在模板中可用的全局变量"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = generate_csrf_token()
    
    return {
        'csrf_token': session['_csrf_token'],
        'format_duration': format_duration,
    }
```

**添加 CSRF 验证装饰器**：
```python
def csrf_protect(f):
    """验证 POST 请求的 CSRF token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('_csrf_token', '')
            if not token:
                flash('缺少 CSRF token', 'error')
                return redirect(request.referrer or url_for('index'))
            
            if '_csrf_token' not in session or token != session['_csrf_token']:
                flash('无效的 CSRF token，请重试', 'error')
                return redirect(request.referrer or url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function
```

**在所有 POST 路由上应用装饰器**：
```python
@app.route('/manage/devices/add', methods=['GET', 'POST'])
@login_required
@csrf_protect
def add_device():
    ...

@app.route('/manage/devices/<int:device_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_device(device_id):
    ...

@app.route('/manage/tasks/create', methods=['POST'])
@login_required
@csrf_protect
def create_task():
    ...

@app.route('/manage/tasks/<int:task_id>/execute', methods=['POST'])
@login_required
@csrf_protect
def execute_task(task_id):
    ...

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@csrf_protect
def upload_file():
    ...

@app.route('/manage/users/add', methods=['POST'])
@admin_required
@csrf_protect
def add_user():
    ...
```

#### 1.2 前端实现 - 添加 CSRF token 字段

**manage_devices.html** - 在所有 POST 表单添加隐藏字段：
```html
<!-- 采集任务表单 -->
<form method="POST" action="{{ url_for('create_task') }}" style="display: inline;">
    <input type="hidden" name="device_id" value="{{ device.id }}">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <button type="submit">采集</button>
</form>

<!-- 删除设备表单 -->
<form method="POST" action="{{ url_for('delete_device', device_id=device.id) }}" style="display: inline;">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <button type="submit">删除</button>
</form>
```

**device_form.html** - 在表单开始处添加：
```html
<form method="POST">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <!-- 其他表单字段 -->
</form>
```

**manage_tasks.html** - 在执行任务表单添加：
```html
<form method="POST" action="{{ url_for('execute_task', task_id=task.id) }}" style="display: inline;">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <button type="submit">执行</button>
</form>
```

**upload.html** - 在文件上传表单添加：
```html
<form method="POST" enctype="multipart/form-data">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <!-- 其他表单字段 -->
</form>
```

**manage_users.html** - 在用户添加模态框表单添加：
```html
<form method="POST" action="{{ url_for('add_user') }}">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
    <!-- 其他表单字段 -->
</form>
```

### 测试结果

✅ **CSRF token 生成和验证**：
- Token 在每个会话中自动生成
- Token 注入到所有 POST 表单
- 缺少 token 的请求被拒绝
- 错误的 token 被拒绝
- 有效的 token 请求被接受

### 修改的文件
1. **topo/web/app_v2.py** - 添加 CSRF 生成、验证、装饰器和上下文处理器
2. **topo/web/templates/manage_devices.html** - 添加两个 CSRF 字段（采集、删除）
3. **topo/web/templates/device_form.html** - 添加一个 CSRF 字段
4. **topo/web/templates/manage_tasks.html** - 添加一个 CSRF 字段
5. **topo/web/templates/upload.html** - 添加一个 CSRF 字段
6. **topo/web/templates/manage_users.html** - 添加一个 CSRF 字段

---

## 2. 时间计算问题修复（中优先级）

### 问题描述
manage_tasks.html 第 51-56 行直接使用 `| int` 过滤器计算耗时：
```html
{{ ((task.completed_at | int) - (task.started_at | int)) }}s
```

这会导致：
- ISO 时间字符串（形如 `'2024-12-28 10:30:45'`）无法转换为整数，引发异常
- 空值（None）会抛出类型错误
- 模板渲染失败，页面崩溃

### 解决方案

#### 2.1 在 app_v2.py 中实现安全的时间计算函数

```python
def format_duration(started_at, completed_at):
    """安全计算任务耗时，处理 None 和格式错误"""
    if not started_at or not completed_at:
        return '-'
    
    try:
        # 处理 ISO 格式时间戳
        if isinstance(started_at, str):
            started = datetime.fromisoformat(started_at.replace('Z', '+00:00').split('+')[0])
        else:
            started = started_at
        
        if isinstance(completed_at, str):
            completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00').split('+')[0])
        else:
            completed = completed_at
        
        delta = completed - started
        seconds = int(delta.total_seconds())
        
        if seconds < 0:
            return '-'
        elif seconds < 60:
            return f'{seconds}s'
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f'{minutes}m{secs}s'
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f'{hours}h{minutes}m'
    except (ValueError, TypeError, AttributeError):
        return '-'
```

#### 2.2 通过上下文处理器注入到模板

```python
@app.context_processor
def inject_globals():
    return {
        'csrf_token': session['_csrf_token'],
        'format_duration': format_duration,  # 注入函数
    }
```

#### 2.3 在模板中使用安全函数

**manage_tasks.html** 中的修改：
```html
<!-- 修改前（容易出错） -->
<td>
    {% if task.started_at and task.completed_at %}
    {{ ((task.completed_at | int) - (task.started_at | int)) }}s
    {% else %}
    -
    {% endif %}
</td>

<!-- 修改后（安全） -->
<td>
    {% if task.started_at and task.completed_at %}
    {{ format_duration(task.started_at, task.completed_at) }}
    {% else %}
    -
    {% endif %}
</td>
```

### 测试结果

✅ **时间计算函数的所有场景**：
- 330 秒 → `5m30s`
- 空值 → `-`
- 无效值 → `-`
- 1 小时 15 分钟 → `1h15m`
- 30 秒 → `30s`
- ISO 时间字符串正确解析

### 修改的文件
1. **topo/web/app_v2.py** - 添加 `format_duration` 函数并通过上下文处理器注入
2. **topo/web/templates/manage_tasks.html** - 替换时间差计算语句

---

## 3. 安全建议

### 生产环境部署
1. **启用 HTTPS**: 在生产环境中必须使用 HTTPS，确保 token 在传输中不被窃听
2. **设置安全 Cookie**: 
   ```python
   app.config['SESSION_COOKIE_SECURE'] = True  # 仅 HTTPS 传输
   app.config['SESSION_COOKIE_HTTPONLY'] = True  # 禁止 JavaScript 访问
   app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 防止跨站请求
   ```

3. **使用强密钥**: 将 `SECRET_KEY` 从环境变量读取，不要硬编码

### 进一步增强
- 考虑使用 `cryptography` 库实现更强的 HMAC 验证
- 实现 token 过期机制（可选）
- 添加请求日志记录用于审计

---

## 4. 验证清单

- ✅ CSRF token 自动生成并注入所有模板
- ✅ 所有 POST 表单都包含 `_csrf_token` 隐藏字段
- ✅ 所有 POST 路由都验证 CSRF token
- ✅ 缺少或无效的 token 被拒绝并返回错误消息
- ✅ 时间计算函数处理所有边界情况
- ✅ 模板中使用安全的时间格式函数
- ✅ 所有修改都已测试，没有语法错误

---

## 5. 测试命令

要验证这些修复，可以运行：

```bash
# 检查语法
python3 -m py_compile topo/web/app_v2.py

# 运行完整的 CSRF 测试
python3 << 'EOF'
from topo.web.app_v2 import create_app
import re

app = create_app()

with app.test_client() as client:
    # 登录
    client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=True)
    
    # 获取 CSRF token
    resp = client.get('/manage/devices')
    token_match = re.search(r'name="_csrf_token"\s+value="([^"]+)"', resp.data.decode())
    csrf_token = token_match.group(1) if token_match else None
    
    # 测试有效 token
    resp = client.post('/manage/devices/add', data={
        'device_name': 'Test',
        'device_type': 'huawei',
        'mgmt_ip': '192.168.1.1',
        'username': 'admin',
        'password': 'pass',
        '_csrf_token': csrf_token
    }, follow_redirects=True)
    print(f"有效 token: {resp.status_code}")
    
    # 测试缺失 token
    resp = client.post('/manage/devices/add', data={
        'device_name': 'Test2',
        'device_type': 'huawei',
        'mgmt_ip': '192.168.1.2',
        'username': 'admin',
        'password': 'pass'
    }, follow_redirects=True)
    print(f"缺失 token: {'CSRF' in resp.data.decode()}")
EOF
```

---

## 总结

通过这次修复，系统现在具备：
1. **完整的 CSRF 保护**: 所有敏感 POST 操作都受 token 保护
2. **健壮的时间处理**: 任务耗时计算不会因异常值而崩溃
3. **安全的用户体验**: 用户不知不觉中被保护，同时系统仍然可用

所有修改都经过充分测试，生产环境可安全部署。
