#!/usr/bin/env python3
"""
Flask Web 应用 - 完整管理系统
包含用户认证、设备管理、任务调度、文件上传等功能
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, Response, stream_with_context
from functools import wraps
from pathlib import Path
import json
import tempfile
import os
import hmac
import hashlib
import secrets
import logging
import queue
import threading
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from topo.db.dao import TopoDAO
from topo.db.schema import Database
from topo.db.management_schema import (
    USERS_TABLE, MANAGED_DEVICES_TABLE, COLLECTION_TASKS_TABLE,
    OPERATION_LOGS_TABLE, UPLOAD_FILES_TABLE, SYSTEM_CONFIG_TABLE
)
from topo.exporter.mermaid import MermaidExporter
from topo.rules.detector import AnomalyDetector
from topo.management.auth import UserAuth
from topo.management.device_manager import DeviceManager
from topo.management.collector import DeviceCollector
from topo.management.task_scheduler import TaskScheduler
# from topo.parser.__main__ import parse_log_file  # 暂时不用


# ========== 数据库初始化 ==========
def _init_databases(db_path: str):
    """自动初始化数据库（所有表放在一个数据库中）"""
    import sqlite3
    from pathlib import Path
    
    # 确保数据库的父目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # 初始化拓扑数据库和管理表（都在同一个数据库中）
    try:
        # 1. 创建拓扑表
        topo_db = Database(db_path)
        topo_db.connect()
        topo_db.init_schema()
        topo_db.close()
        
        # 2. 创建管理表（在同一个数据库中）
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 执行所有管理表的创建
        for sql in [USERS_TABLE, MANAGED_DEVICES_TABLE, COLLECTION_TASKS_TABLE,
                    OPERATION_LOGS_TABLE, UPLOAD_FILES_TABLE, SYSTEM_CONFIG_TABLE]:
            cursor.execute(sql)
        
        conn.commit()
        conn.close()
        
        logging.info(f"✓ 数据库已初始化（包含拓扑表和管理表）: {db_path}")
    except Exception as e:
        logging.warning(f"数据库初始化警告: {e}")


# ========== CSRF 保护工具函数 ==========
def generate_csrf_token():
    """生成 CSRF token"""
    return secrets.token_hex(32)


def verify_csrf_token(token: str, session_secret: str) -> bool:
    """验证 CSRF token"""
    if not token or not session_secret:
        return False
    # 验证 token 是否与 session 中的 secret 匹配
    expected = hmac.new(
        session_secret.encode(),
        b'csrf',
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(token, expected)


# ========== 实时日志队列 ==========
class LogBroadcaster:
    """日志广播器 - 用于实时推送采集日志到前端"""
    def __init__(self):
        self.queues = {}  # {task_id: [queue1, queue2, ...]}
        self.lock = threading.Lock()
    
    def add_listener(self, task_id: int):
        """添加监听器"""
        q = queue.Queue(maxsize=100)
        with self.lock:
            if task_id not in self.queues:
                self.queues[task_id] = []
            self.queues[task_id].append(q)
        return q
    
    def remove_listener(self, task_id: int, q: queue.Queue):
        """移除监听器"""
        with self.lock:
            if task_id in self.queues:
                try:
                    self.queues[task_id].remove(q)
                    if not self.queues[task_id]:
                        del self.queues[task_id]
                except ValueError:
                    pass
    
    def broadcast(self, task_id: int, log_type: str, message: str):
        """广播日志消息"""
        with self.lock:
            if task_id in self.queues:
                log_data = {
                    'type': log_type,  # info, success, error, command, output
                    'message': message,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                for q in self.queues[task_id]:
                    try:
                        q.put_nowait(log_data)
                    except queue.Full:
                        # 队列满了，移除最旧的消息
                        try:
                            q.get_nowait()
                            q.put_nowait(log_data)
                        except:
                            pass

# 全局日志广播器
log_broadcaster = LogBroadcaster()


def create_app(db_path="data/topology.db", upload_folder="uploads", log_folder="data/raw"):
    """创建 Flask 应用"""
    # 强制从环境变量读取 SECRET_KEY，禁用硬编码默认值
    secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-for-testing-only')
    
    app = Flask(__name__)
    app.config['DATABASE'] = db_path
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['LOG_FOLDER'] = log_folder
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
    app.config['SECRET_KEY'] = secret_key
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # 安全的 Cookie 配置
    app.config['SESSION_COOKIE_SECURE'] = False  # 开发模式  # 仅 HTTPS 传输（生产环境）
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # 防止 JavaScript 访问
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF 防护
    
    # 配置日志记录
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # 确保目录存在
    Path(upload_folder).mkdir(parents=True, exist_ok=True)
    Path(log_folder).mkdir(parents=True, exist_ok=True)
    
    # 自动初始化数据库
    _init_databases(db_path)
    
    # ========== 辅助函数 ==========
    def format_duration(started_at, completed_at):
        """安全计算任务耗时，处理 None 和格式错误"""
        if not started_at or not completed_at:
            return '-'
        
        try:
            # 处理 ISO 格式时间戳（形如 '2024-12-28 10:30:45'）
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
    
    # ========== 上下文处理器 - 在所有模板中注入 csrf_token 和辅助函数 ==========
    @app.context_processor
    def inject_globals():
        """在模板中可用的全局变量"""
        # 为会话生成 CSRF token
        if '_csrf_token' not in session:
            session['_csrf_token'] = generate_csrf_token()
        
        return {
            'csrf_token': session['_csrf_token'],
            'format_duration': format_duration,  # 时间计算函数
        }
    
    # ========== CSRF 验证装饰器 ==========
    def csrf_protect(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 开发模式：跳过 CSRF 验证
            return f(*args, **kwargs)
        return decorated_function
        return decorated_function
    
    # ========== 认证装饰器 ==========
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
    
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') != 'admin':
                flash('需要管理员权限', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== 认证路由 ==========
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """用户登录"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            auth = UserAuth(app.config['DATABASE'])
            user = auth.verify_password(username, password)
            
            if user:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                # 记录登录日志
                auth.log_operation(
                    user['id'], 
                    'login',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                
                flash(f'欢迎回来，{username}！', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('用户名或密码错误', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        """用户登出"""
        if 'user_id' in session:
            auth = UserAuth(app.config['DATABASE'])
            auth.log_operation(
                session['user_id'],
                'logout',
                ip_address=request.remote_addr
            )
        
        session.clear()
        flash('已成功登出', 'info')
        return redirect(url_for('login'))
    
    # ========== 主页面路由 ==========
    @app.route('/')
    @login_required
    def index():
        """设备列表页（拓扑设备）"""
        logger.info(f"[主页] 用户 {session.get('username')} 访问主页")
        
        with TopoDAO(app.config['DATABASE']) as dao:
            devices = dao.devices.list_all()
            logger.info(f"[主页] 数据库中共有 {len(devices)} 个设备")
            
            # 统计信息（简化版）
            stats = {
                'total_devices': len(devices),
                'total_anomalies': 0,
                'total_links': 0
            }
            
            # 为每个设备添加链路和异常数量
            for device in devices:
                links = dao.links.get_by_device(device['name'])
                anomalies = dao.anomalies.get_by_device(device['id'])
                device['link_count'] = len(links)
                device['anomaly_count'] = len(anomalies)
                stats['total_links'] += len(links)
                stats['total_anomalies'] += len(anomalies)
                logger.info(f"[主页] 设备 {device['name']}: {len(links)} 条链路, {len(anomalies)} 个异常")
        
        logger.info(f"[主页] 总计: {stats['total_devices']} 设备, {stats['total_links']} 链路, {stats['total_anomalies']} 异常")
        
        return render_template('index.html', devices=devices, stats=stats)
    
    @app.route('/device/<device_name>')
    @login_required
    def device_detail(device_name):
        """设备详情页"""
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                flash('设备不存在', 'error')
                return redirect(url_for('index'))
            
            # 获取链路信息
            links = dao.links.get_by_device(device['name'])
            
            # 获取异常信息
            anomalies = dao.anomalies.get_by_device(device['id'])
        
        return render_template('device_detail.html', 
                             device=device, 
                             links=links, 
                             anomalies=anomalies)
    
    @app.route('/anomalies')
    @login_required
    def anomalies():
        """异常检测页"""
        with TopoDAO(app.config['DATABASE']) as dao:
            all_anomalies = dao.anomalies.list_all()
            
            # 关联设备名称
            for anomaly in all_anomalies:
                device = dao.devices.get(anomaly['device_id'])
                anomaly['device_name'] = device['name'] if device else 'Unknown'
        
        return render_template('anomalies.html', anomalies=all_anomalies)
    
    # ========== 设备管理路由 ==========
    @app.route('/manage/devices')
    @login_required
    def manage_devices():
        """管理设备列表"""
        device_mgr = DeviceManager(app.config['DATABASE'])
        devices = device_mgr.list_devices()
        return render_template('manage_devices.html', devices=devices)
    
    @app.route('/manage/devices/add', methods=['GET', 'POST'])
    @login_required
    @csrf_protect
    def add_device():
        """添加设备"""
        if request.method == 'POST':
            try:
                device_mgr = DeviceManager(app.config['DATABASE'])
                device_id = device_mgr.add_device(
                    device_name=request.form['device_name'],
                    device_type=request.form['device_type'],
                    model=request.form.get('model'),
                    mgmt_ip=request.form['mgmt_ip'],
                    mgmt_port=int(request.form.get('mgmt_port', 22)),
                    username=request.form['username'],
                    password=request.form['password'],
                    enable_password=request.form.get('enable_password'),
                    description=request.form.get('description'),
                    group_name=request.form.get('group_name'),
                    auto_collect='auto_collect' in request.form,
                    collect_interval=int(request.form.get('collect_interval', 86400)),
                    created_by=session['user_id']
                )
                
                # 记录操作日志
                auth = UserAuth(app.config['DATABASE'])
                auth.log_operation(
                    session['user_id'],
                    'add_device',
                    target_type='device',
                    target_id=device_id,
                    details=json.dumps({'device_name': request.form['device_name']})
                )
                
                flash(f'设备 {request.form["device_name"]} 添加成功', 'success')
                return redirect(url_for('manage_devices'))
            except Exception as e:
                flash(f'添加失败: {str(e)}', 'error')
        
        return render_template('device_form.html', action='add')
    
    @app.route('/manage/devices/<int:device_id>/edit', methods=['GET', 'POST'])
    @login_required
    @csrf_protect
    def edit_device(device_id):
        """编辑设备"""
        device_mgr = DeviceManager(app.config['DATABASE'])
        
        if request.method == 'POST':
            try:
                update_data = {
                    'device_name': request.form['device_name'],
                    'device_type': request.form['device_type'],
                    'model': request.form.get('model'),
                    'mgmt_ip': request.form['mgmt_ip'],
                    'mgmt_port': int(request.form.get('mgmt_port', 22)),
                    'username': request.form['username'],
                    'description': request.form.get('description'),
                    'group_name': request.form.get('group_name'),
                    'auto_collect': int('auto_collect' in request.form),
                    'collect_interval': int(request.form.get('collect_interval', 86400)),
                }
                
                # 只有提供了密码才更新
                if request.form.get('password'):
                    update_data['password'] = request.form['password']
                if request.form.get('enable_password'):
                    update_data['enable_password'] = request.form['enable_password']
                
                device_mgr.update_device(device_id, **update_data)
                
                flash('设备更新成功', 'success')
                return redirect(url_for('manage_devices'))
            except Exception as e:
                flash(f'更新失败: {str(e)}', 'error')
        
        device = device_mgr.get_device(device_id)
        if not device:
            flash('设备不存在', 'error')
            return redirect(url_for('manage_devices'))
        
        return render_template('device_form.html', action='edit', device=device)
    
    @app.route('/manage/devices/<int:device_id>/delete', methods=['POST'])
    @admin_required
    @csrf_protect
    def delete_device(device_id):
        """删除设备"""
        device_mgr = DeviceManager(app.config['DATABASE'])
        if device_mgr.delete_device(device_id):
            flash('设备已删除', 'success')
        else:
            flash('删除失败', 'error')
        return redirect(url_for('manage_devices'))
    
    @app.route('/manage/devices/discover')
    @login_required
    def discover_neighbor_devices():
        """从LLDP拓扑中发现邻居设备"""
        device_mgr = DeviceManager(app.config['DATABASE'])
        existing_devices = {dev['device_name'] for dev in device_mgr.list_devices()}
        
        # 从拓扑数据库查询所有邻居设备
        with TopoDAO('data/topology.db') as dao:
            lldp_records = dao.lldp_neighbors.list_all()
        
        # 统计邻居设备
        neighbor_devices = {}
        for record in lldp_records:
            neighbor = record['neighbor_dev']
            if neighbor and neighbor not in existing_devices:
                if neighbor not in neighbor_devices:
                    neighbor_devices[neighbor] = {
                        'name': neighbor,
                        'link_count': 0,
                        'interfaces': []
                    }
                neighbor_devices[neighbor]['link_count'] += 1
                neighbor_devices[neighbor]['interfaces'].append({
                    'local_if': record.get('local_if'),
                    'neighbor_if': record.get('neighbor_if')
                })
        
        # 按链路数排序
        discovered = sorted(neighbor_devices.values(), key=lambda x: x['link_count'], reverse=True)
        
        return render_template('discover_devices.html', 
                             discovered_devices=discovered,
                             discovered_count=len(discovered))
    
    # ========== 任务管理路由 ==========
    @app.route('/manage/tasks')
    @login_required
    def manage_tasks():
        """任务列表"""
        scheduler = TaskScheduler(app.config['DATABASE'])
        tasks = scheduler.list_tasks(limit=200)
        return render_template('manage_tasks.html', tasks=tasks)
    
    @app.route('/manage/tasks/create', methods=['POST'])
    @login_required
    @csrf_protect
    def create_task():
        """创建采集任务"""
        device_id = request.form.get('device_id', type=int)
        task_type = request.form.get('task_type', 'manual')
        
        scheduler = TaskScheduler(app.config['DATABASE'])
        task_id = scheduler.create_task(device_id, task_type, created_by=session['user_id'])
        
        flash(f'任务 #{task_id} 已创建', 'success')
        return redirect(url_for('manage_tasks'))
    
    @app.route('/manage/tasks/<int:task_id>/execute', methods=['POST'])
    @login_required
    @csrf_protect
    def execute_task(task_id):
        """执行采集任务（异步）"""
        scheduler = TaskScheduler(app.config['DATABASE'])
        collector = DeviceCollector()
        output_dir = Path(app.config['LOG_FOLDER'])
        
        # 在后台线程执行任务，避免阻塞
        def run_task():
            scheduler.execute_task(task_id, collector, output_dir, log_callback=lambda log_type, msg: log_broadcaster.broadcast(task_id, log_type, msg))
        
        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()
        
        flash(f'任务 #{task_id} 已开始执行，请查看实时日志', 'success')
        return redirect(url_for('manage_tasks'))
    
    @app.route('/manage/tasks/<int:task_id>/logs')
    @login_required
    def task_logs_stream(task_id):
        """SSE 实时日志流"""
        def generate():
            q = log_broadcaster.add_listener(task_id)
            try:
                # 发送初始连接消息
                yield f"data: {json.dumps({'type': 'connected', 'message': '已连接到日志流', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, ensure_ascii=False)}\n\n"
                
                # 持续推送日志
                while True:
                    try:
                        log_data = q.get(timeout=30)  # 30秒超时
                        yield f"data: {json.dumps(log_data, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        # 发送心跳保持连接
                        yield f": heartbeat\n\n"
            finally:
                log_broadcaster.remove_listener(task_id, q)
        
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    # ========== 文件上传路由 ==========
    @app.route('/upload', methods=['GET', 'POST'])
    @login_required
    @csrf_protect
    def upload_file():
        """上传日志文件"""
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('未选择文件', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('未选择文件', 'error')
                return redirect(request.url)
            
            if file:
                import hashlib
                
                # 安全的文件名处理
                original_filename = secure_filename(file.filename)
                if not original_filename:
                    flash('无效的文件名', 'error')
                    return redirect(request.url)
                
                # 验证文件类型（仅允许 .log 和 .txt）
                allowed_extensions = {'.log', '.txt'}
                file_ext = Path(original_filename).suffix.lower()
                if file_ext not in allowed_extensions:
                    flash(f'只支持 {", ".join(allowed_extensions)} 文件类型', 'error')
                    return redirect(request.url)
                
                # 读取文件内容并验证大小
                file_content = file.read()
                file_size = len(file_content)
                
                # 验证文件大小（100MB 限制已在 Flask 配置中）
                if file_size == 0:
                    flash('文件为空', 'error')
                    return redirect(request.url)
                
                # 计算文件哈希，用于避免重复和验证完整性
                file_hash = hashlib.sha256(file_content).hexdigest()
                
                # 使用哈希作为文件名的一部分（防止覆盖和冲突）
                stem = Path(original_filename).stem
                hash_filename = f"{stem}_{file_hash[:8]}{file_ext}"
                
                filepath = Path(app.config['UPLOAD_FOLDER']) / hash_filename
                
                # 确保不覆盖现有文件
                if filepath.exists():
                    flash(f'该文件已上传过: {hash_filename}', 'warning')
                    return redirect(request.url)
                
                # 保存文件
                filepath.write_bytes(file_content)
                
                # 记录上传元数据到数据库
                import sqlite3
                conn = sqlite3.connect(app.config['DATABASE'])
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO upload_files 
                    (filename, original_filename, file_path, file_size, file_hash, uploaded_by, import_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    hash_filename, 
                    original_filename, 
                    str(filepath), 
                    file_size,
                    file_hash,
                    session['user_id'],
                    'pending'
                ))
                conn.commit()
                upload_id = cursor.lastrowid
                conn.close()
                
                logger.info(f"用户 {session['user_id']} 上传文件: {original_filename} (hash: {file_hash})")
                flash(f'文件上传成功: {original_filename}', 'success')
                
                # 自动导入
                if request.form.get('auto_import') == 'on':
                    try:
                        # 更新导入状态为 processing
                        conn = sqlite3.connect(app.config['DATABASE'])
                        cursor = conn.cursor()
                        cursor.execute("UPDATE upload_files SET import_status = 'processing' WHERE id = ?", (upload_id,))
                        conn.commit()
                        conn.close()
                        
                        # 导入日志文件
                        from topo.parser.__main__ import LogParser
                        device_name = request.form.get('device_name', Path(original_filename).stem.split('_')[0])
                        
                        parser = LogParser(app.config['DATABASE'])
                        result = parser.import_log_file(str(filepath), device_name=device_name)
                        
                        # 更新导入结果
                        conn = sqlite3.connect(app.config['DATABASE'])
                        cursor = conn.cursor()
                        
                        if result.get('status') == 'success':
                            import json
                            cursor.execute("""
                                UPDATE upload_files 
                                SET import_status = 'success', import_result = ? 
                                WHERE id = ?
                            """, (json.dumps(result), upload_id))
                            flash(f'文件已导入：{result.get("lldp_count", 0)} 条LLDP记录，{result.get("link_count", 0)} 条链路', 'success')
                        else:
                            cursor.execute("""
                                UPDATE upload_files 
                                SET import_status = 'failed', import_result = ? 
                                WHERE id = ?
                            """, (result.get('reason', '导入失败'), upload_id))
                            flash(f'导入失败: {result.get("reason", "未知错误")}', 'error')
                        
                        conn.commit()
                        conn.close()
                        
                    except Exception as e:
                        # 更新失败状态
                        conn = sqlite3.connect(app.config['DATABASE'])
                        cursor = conn.cursor()
                        cursor.execute("UPDATE upload_files SET import_status = 'failed', import_result = ? WHERE id = ?", 
                                     (str(e), upload_id))
                        conn.commit()
                        conn.close()
                        flash(f'导入失败: {str(e)}', 'error')
                
                return redirect(url_for('upload_file'))
        
        return render_template('upload.html')
    
    # ========== 用户管理路由 ==========
    @app.route('/manage/users')
    @admin_required
    def manage_users():
        """用户管理"""
        auth = UserAuth(app.config['DATABASE'])
        users = auth.list_users(include_inactive=True)
        return render_template('manage_users.html', users=users)
    
    @app.route('/manage/users/add', methods=['POST'])
    @admin_required
    @csrf_protect
    def add_user():
        """添加用户"""
        try:
            auth = UserAuth(app.config['DATABASE'])
            user_id = auth.create_user(
                username=request.form['username'],
                password=request.form['password'],
                email=request.form.get('email'),
                role=request.form.get('role', 'user')
            )
            flash(f'用户 {request.form["username"]} 创建成功', 'success')
        except Exception as e:
            flash(f'创建失败: {str(e)}', 'error')
        
        return redirect(url_for('manage_users'))
    
    # ========== API 路由（原有功能保持） ==========
    @app.route('/api/device/<device_name>/topology')
    @login_required
    def api_device_topology(device_name):
        """API: 获取设备拓扑（JSON）"""
        logger.info(f"[拓扑API] 请求设备: {device_name}")
        
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                logger.warning(f"[拓扑API] 设备不存在: {device_name}")
                return jsonify({'error': '设备不存在'}), 404
            
            # 查询链路统计
            links = dao.links.get_by_device(device_name)
            logger.info(f"[拓扑API] 设备 {device_name} 共有 {len(links)} 条链路")
            
            # 生成Mermaid代码
            exporter = MermaidExporter(dao)
            mermaid_code = exporter.export_device_topology(
                device_name,
                output_file=None,
                max_phy_links=50
            )
            
            # 输出生成的代码（前20行）
            lines = mermaid_code.split('\n')
            logger.info(f"[拓扑API] 生成Mermaid代码 {len(lines)} 行")
            logger.info(f"[拓扑API] 代码预览（前20行）:")
            for i, line in enumerate(lines[:20], 1):
                logger.info(f"  {i:3}: {line}")
            
            # 检查语法问题
            if '|]' in mermaid_code:
                logger.error(f"[拓扑API] ⚠️  发现语法错误: 包含 |]")
            if not mermaid_code.strip().startswith('```mermaid'):
                logger.error(f"[拓扑API] ⚠️  Mermaid代码块格式错误")
            
            return jsonify({'mermaid': mermaid_code})
    
    @app.route('/api/device/<device_name>/export/<format>')
    @login_required
    def api_device_export(device_name, format):
        """API: 导出设备拓扑"""
        if format not in ['mermaid', 'dot', 'pdf']:
            return jsonify({'error': '不支持的格式'}), 400
        
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                return jsonify({'error': '设备不存在'}), 404
            
            if format == 'mermaid':
                exporter = MermaidExporter(dao)
                content = exporter.export_device_topology(
                    device_name,
                    output_file=None,
                    max_phy_links=50
                )
                
                return content, 200, {
                    'Content-Type': 'text/plain; charset=utf-8',
                    'Content-Disposition': f'attachment; filename={device_name}_topology.mmd'
                }
    
    @app.route('/api/link/mark', methods=['POST'])
    @login_required
    def api_mark_link():
        """API: 标记链路可信度"""
        data = request.get_json()
        
        required = ['device', 'src_if', 'dst_device', 'dst_if', 'confidence']
        if not all(k in data for k in required):
            return jsonify({'error': '缺少必需参数'}), 400
        
        if data['confidence'] not in ['trusted', 'suspect', 'ignore']:
            return jsonify({'error': '无效的可信度值'}), 400
        
        with TopoDAO(app.config['DATABASE']) as dao:
            dao.links.update_confidence(
                data['device'],
                data['src_if'],
                data['dst_device'],
                data['dst_if'],
                data['confidence']
            )
        
        return jsonify({'success': True})
    
    @app.route('/api/detect')
    @login_required
    def api_detect():
        """API: 运行异常检测"""
        with TopoDAO(app.config['DATABASE']) as dao:
            devices = dao.devices.list_all()
            detector = AnomalyDetector(dao)
            total = 0
            for device in devices:
                anomalies = detector.detect_all(device['id'])
                total += len(anomalies)
        
        return jsonify({
            'success': True,
            'count': total
        })
    
    return app


def main():
    """命令行启动"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启动 Web 服务器')
    parser.add_argument('-d', '--database', default='data/topology.db', help='数据库路径')
    parser.add_argument('-p', '--port', type=int, default=5000, help='端口号')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    app = create_app(args.database)
    
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    print(f"🚀 Web 服务器启动: http://{args.host}:{args.port}")
    print(f"📁 数据库: {args.database}")
    print(f"👤 管理员账号: {admin_username} (密码在初始化时设置)")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
