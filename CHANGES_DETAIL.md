# 修改文件清单

## 已修改的文件及其具体改动

### 1. topo/web/app_v2.py
**行数**: 591 行（原 495 行）  
**修改类型**: 代码添加和装饰器应用

#### 修改内容：

**A. 导入语句添加** (第 1-15 行)
- 添加: `import hmac`, `import hashlib`, `import secrets`
- 用途: CSRF token 生成和验证

**B. CSRF 工具函数** (第 30-35 行, 新增)
```python
def generate_csrf_token():
    """生成 CSRF token"""
    return secrets.token_hex(32)

def verify_csrf_token(token: str, session_secret: str) -> bool:
    """验证 CSRF token"""
    # ... (未使用，备用)
```

**C. 时间计算函数** (第 61-95 行, 新增)
```python
def format_duration(started_at, completed_at):
    """安全计算任务耗时，处理 None 和格式错误"""
    # 完整的时间解析和格式化逻辑
    # 处理边界情况: None, 无效格式, 负时间差
```

**D. 上下文处理器** (第 97-108 行, 新增)
```python
@app.context_processor
def inject_globals():
    """在模板中注入 csrf_token 和 format_duration"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = generate_csrf_token()
    return {
        'csrf_token': session['_csrf_token'],
        'format_duration': format_duration,
    }
```

**E. CSRF 验证装饰器** (第 110-127 行, 新增)
```python
def csrf_protect(f):
    """验证 POST 请求的 CSRF token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('_csrf_token', '')
            if not token or token != session.get('_csrf_token'):
                flash('无效的 CSRF token', 'error')
                return redirect(request.referrer or url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
```

**F. 路由装饰器添加** (第 272-365 行)

添加 `@csrf_protect` 装饰器到 7 个 POST 路由：

1. **add_device** (第 272 行)
   ```python
   @app.route('/manage/devices/add', methods=['GET', 'POST'])
   @login_required
   @csrf_protect  # ← 新增
   def add_device():
   ```

2. **edit_device** (第 300 行)
   ```python
   @app.route('/manage/devices/<int:device_id>/edit', methods=['GET', 'POST'])
   @login_required
   @csrf_protect  # ← 新增
   def edit_device(device_id):
   ```

3. **delete_device** (第 327 行)
   ```python
   @app.route('/manage/devices/<int:device_id>/delete', methods=['POST'])
   @admin_required
   @csrf_protect  # ← 新增
   def delete_device(device_id):
   ```

4. **create_task** (第 342 行)
   ```python
   @app.route('/manage/tasks/create', methods=['POST'])
   @login_required
   @csrf_protect  # ← 新增
   def create_task():
   ```

5. **execute_task** (第 356 行)
   ```python
   @app.route('/manage/tasks/<int:task_id>/execute', methods=['POST'])
   @login_required
   @csrf_protect  # ← 新增
   def execute_task(task_id):
   ```

6. **upload_file** (第 372 行)
   ```python
   @app.route('/upload', methods=['GET', 'POST'])
   @login_required
   @csrf_protect  # ← 新增
   def upload_file():
   ```

7. **add_user** (第 414 行)
   ```python
   @app.route('/manage/users/add', methods=['POST'])
   @admin_required
   @csrf_protect  # ← 新增
   def add_user():
   ```

---

### 2. topo/web/templates/manage_devices.html
**修改行数**: 2 处

#### 修改 1: 采集任务表单 (第 57-61 行)
```html
<!-- 修改前 -->
<form method="POST" action="{{ url_for('create_task') }}" style="display: inline;">
    <input type="hidden" name="device_id" value="{{ device.id }}">
    <button type="submit" class="btn btn-sm">采集</button>
</form>

<!-- 修改后 -->
<form method="POST" action="{{ url_for('create_task') }}" style="display: inline;">
    <input type="hidden" name="device_id" value="{{ device.id }}">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
    <button type="submit" class="btn btn-sm">采集</button>
</form>
```

#### 修改 2: 删除设备表单 (第 63-68 行)
```html
<!-- 修改前 -->
<form method="POST" action="{{ url_for('delete_device', device_id=device.id) }}" style="display: inline;" onsubmit="return confirm('确定删除此设备吗？');">
    <button type="submit" class="btn btn-sm btn-danger">删除</button>
</form>

<!-- 修改后 -->
<form method="POST" action="{{ url_for('delete_device', device_id=device.id) }}" style="display: inline;" onsubmit="return confirm('确定删除此设备吗？');">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
    <button type="submit" class="btn btn-sm btn-danger">删除</button>
</form>
```

---

### 3. topo/web/templates/device_form.html
**修改行数**: 1 处 (第 11 行之后)

```html
<!-- 修改前 -->
<div class="card" style="max-width: 800px;">
    <form method="POST">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">

<!-- 修改后 -->
<div class="card" style="max-width: 800px;">
    <form method="POST">
        <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
```

---

### 4. topo/web/templates/manage_tasks.html
**修改行数**: 2 处

#### 修改 1: 时间计算函数 (第 51-56 行)
```html
<!-- 修改前 - 容易崩溃 -->
<td>
    {% if task.started_at and task.completed_at %}
    {{ ((task.completed_at | int) - (task.started_at | int)) }}s
    {% else %}
    -
    {% endif %}
</td>

<!-- 修改后 - 安全 -->
<td>
    {% if task.started_at and task.completed_at %}
    {{ format_duration(task.started_at, task.completed_at) }}  <!-- ← 改用安全函数 -->
    {% else %}
    -
    {% endif %}
</td>
```

#### 修改 2: 执行任务表单 (第 68-72 行)
```html
<!-- 修改前 -->
<form method="POST" action="{{ url_for('execute_task', task_id=task.id) }}" style="display: inline;">
    <button type="submit" class="btn btn-sm" style="background: #52c41a; color: white;">执行</button>
</form>

<!-- 修改后 -->
<form method="POST" action="{{ url_for('execute_task', task_id=task.id) }}" style="display: inline;">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
    <button type="submit" class="btn btn-sm" style="background: #52c41a; color: white;">执行</button>
</form>
```

---

### 5. topo/web/templates/upload.html
**修改行数**: 1 处 (第 8 行之后)

```html
<!-- 修改前 -->
<div class="card" style="max-width: 600px;">
    <form method="POST" enctype="multipart/form-data">
        <div class="form-group">

<!-- 修改后 -->
<div class="card" style="max-width: 600px;">
    <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
        <div class="form-group">
```

---

### 6. topo/web/templates/manage_users.html
**修改行数**: 1 处 (第 71 行之后)

```html
<!-- 修改前 -->
<form method="POST" action="{{ url_for('add_user') }}">
    <div class="form-group">

<!-- 修改后 -->
<form method="POST" action="{{ url_for('add_user') }}">
    <input type="hidden" name="_csrf_token" value="{{ csrf_token }}">  <!-- ← 新增 -->
    <div class="form-group">
```

---

## 修改统计

| 文件 | 修改数 | 类型 | 说明 |
|------|--------|------|------|
| app_v2.py | 96 行 | 添加 | CSRF token 生成、验证、装饰器；时间计算函数；7 个路由装饰器 |
| manage_devices.html | 2 个 | 添加 CSRF 字段 | 采集和删除表单各添加一个字段 |
| device_form.html | 1 个 | 添加 CSRF 字段 | 设备添加/编辑表单 |
| manage_tasks.html | 2 个 | 修改+添加 CSRF | 时间计算改用安全函数；执行表单添加字段 |
| upload.html | 1 个 | 添加 CSRF 字段 | 文件上传表单 |
| manage_users.html | 1 个 | 添加 CSRF 字段 | 用户添加表单 |
| **总计** | **8 处** | - | - |

---

## 代码复杂度和影响范围

### 代码量变化
- **app_v2.py**: +96 行 (原 495 → 591 行，+19%)
- **模板文件**: +7 个隐藏字段
- **总代码变化**: ~100 行左右

### 性能影响
- ✅ **最小**: Token 生成使用 `secrets.token_hex` (极快)
- ✅ **最小**: 模板注入使用上下文处理器 (无额外查询)
- ✅ **无数据库影响**: 不需要修改数据库表

### 兼容性
- ✅ **完全兼容**: 不破坏现有功能
- ✅ **无依赖添加**: 仅使用 Python 标准库 (`secrets`, `hmac`, `hashlib`)
- ✅ **模板语法**: 使用标准 Jinja2 语法

---

## 验证步骤

```bash
# 1. 检查语法
python3 -m py_compile topo/web/app_v2.py

# 2. 启动应用
python3 -c "from topo.web.app_v2 import create_app; app = create_app(); print('✓ 应用初始化成功')"

# 3. 运行测试（见 SECURITY_FIXES.md）
```

---

## 回滚指南

若需要回滚这些修改，关键步骤：

1. **恢复 app_v2.py**:
   - 删除 `generate_csrf_token()`, `verify_csrf_token()`, `format_duration()` 函数
   - 删除 `@app.context_processor` 和 `csrf_protect` 装饰器定义
   - 删除所有路由上的 `@csrf_protect` 装饰器

2. **恢复模板**:
   - 删除所有 `<input type="hidden" name="_csrf_token">` 行
   - 恢复 manage_tasks.html 中的时间计算为 `| int` 过滤器

3. **删除导入**:
   - 删除 app_v2.py 中新增的 `import hmac, hashlib, secrets`
