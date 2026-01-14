#!/usr/bin/env python3
"""
系统管理扩展数据库表
添加用户管理、设备配置、采集任务等表
"""

# 用户表
USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'user',  -- admin, user, viewer
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
"""

# 管理设备表（包含连接信息）
MANAGED_DEVICES_TABLE = """
CREATE TABLE IF NOT EXISTS managed_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT NOT NULL UNIQUE,
    device_type TEXT NOT NULL,  -- huawei, cisco, h3c, etc.
    model TEXT,
    mgmt_ip TEXT NOT NULL,
    mgmt_port INTEGER DEFAULT 22,
    username TEXT NOT NULL,
    password TEXT NOT NULL,  -- 加密存储
    enable_password TEXT,
    description TEXT,
    group_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    auto_collect INTEGER NOT NULL DEFAULT 0,  -- 是否自动采集
    collect_interval INTEGER DEFAULT 86400,  -- 采集间隔（秒），默认24小时
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);
"""

# 采集任务表
COLLECTION_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS collection_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'manual',  -- manual, scheduled, auto
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, success, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    log_file_path TEXT,
    error_message TEXT,
    commands_executed TEXT,  -- JSON array of commands
    created_by INTEGER,
    FOREIGN KEY (device_id) REFERENCES managed_devices(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);
"""

# 操作日志表
OPERATION_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    operation TEXT NOT NULL,  -- login, logout, add_device, delete_device, etc.
    target_type TEXT,  -- device, user, task, etc.
    target_id INTEGER,
    details TEXT,  -- JSON details
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

# 文件上传记录表
UPLOAD_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS upload_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    file_hash TEXT,
    device_name TEXT,
    uploaded_by INTEGER NOT NULL,
    import_status TEXT DEFAULT 'pending',  -- pending, processing, success, failed
    import_result TEXT,  -- JSON result
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);
"""

# 系统配置表
SYSTEM_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users(id)
);
"""

# 索引
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
    "CREATE INDEX IF NOT EXISTS idx_managed_devices_name ON managed_devices(device_name);",
    "CREATE INDEX IF NOT EXISTS idx_managed_devices_ip ON managed_devices(mgmt_ip);",
    "CREATE INDEX IF NOT EXISTS idx_collection_tasks_device ON collection_tasks(device_id);",
    "CREATE INDEX IF NOT EXISTS idx_collection_tasks_status ON collection_tasks(status);",
    "CREATE INDEX IF NOT EXISTS idx_operation_logs_user ON operation_logs(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_operation_logs_created ON operation_logs(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_upload_files_uploaded_by ON upload_files(uploaded_by);",
]


def init_management_tables(conn):
    """初始化管理表"""
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute(USERS_TABLE)
    cursor.execute(MANAGED_DEVICES_TABLE)
    cursor.execute(COLLECTION_TASKS_TABLE)
    cursor.execute(OPERATION_LOGS_TABLE)
    cursor.execute(UPLOAD_FILES_TABLE)
    cursor.execute(SYSTEM_CONFIG_TABLE)
    
    # 创建索引
    for index_sql in INDEXES:
        cursor.execute(index_sql)
    
    conn.commit()
    

def create_default_admin(conn, username=None, password=None):
    """
    创建默认管理员账号
    
    由于安全原因，admin 用户名和密码必须从环境变量提供，不允许硬编码默认值。
    
    环境变量:
    - ADMIN_USERNAME: 管理员用户名（默认: admin）
    - ADMIN_PASSWORD: 管理员密码（必须提供，最少 12 字符强密码）
    """
    import bcrypt
    import os
    
    # 从环境变量读取，如果有参数则使用参数（用于自动化）
    username = username or os.environ.get('ADMIN_USERNAME', 'admin')
    password = password or os.environ.get('ADMIN_PASSWORD')
    
    # 验证密码强度
    if not password:
        raise ValueError(
            "FATAL: 管理员密码未设置\n"
            "  环境变量 ADMIN_PASSWORD 必须提供\n"
            "  生成强密码: python3 -c \"import secrets; print(secrets.token_urlsafe(16))\"\n"
            "  然后设置: export ADMIN_PASSWORD='<生成的密码>'"
        )
    
    # 开发模式：跳过密码强度验证
    
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return False
    
    # 创建管理员
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("""
        INSERT INTO users (username, password_hash, email, role, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, (username, password_hash, 'admin@localhost', 'admin', 1))
    
    conn.commit()
    return True
