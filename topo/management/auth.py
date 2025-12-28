#!/usr/bin/env python3
"""
用户认证模块
"""
import bcrypt
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any


class UserAuth:
    """用户认证管理"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def verify_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        验证用户密码
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            用户信息字典，验证失败返回 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, password_hash, email, role, is_active
            FROM users
            WHERE username = ? AND is_active = 1
        """, (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return None
        
        # 验证密码
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # 更新最后登录时间
            self._update_last_login(user['id'])
            
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        
        return None
    
    def _update_last_login(self, user_id: int):
        """更新最后登录时间"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET last_login = ? WHERE id = ?
        """, (datetime.now(), user_id))
        conn.commit()
        conn.close()
    
    def create_user(self, username: str, password: str, email: str = None, 
                    role: str = 'user') -> int:
        """
        创建新用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱
            role: 角色 (admin, user, viewer)
        
        Returns:
            新用户 ID
        """
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, role, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (username, password_hash, email, role))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """修改用户密码"""
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET password_hash = ? WHERE id = ?
        """, (password_hash, user_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取用户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, is_active, created_at, last_login
            FROM users
            WHERE id = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return dict(user)
        return None
    
    def list_users(self, include_inactive: bool = False) -> list:
        """列出所有用户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if include_inactive:
            cursor.execute("""
                SELECT id, username, email, role, is_active, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT id, username, email, role, is_active, created_at, last_login
                FROM users
                WHERE is_active = 1
                ORDER BY created_at DESC
            """)
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return users
    
    def deactivate_user(self, user_id: int) -> bool:
        """停用用户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def log_operation(self, user_id: int, operation: str, target_type: str = None,
                     target_id: int = None, details: str = None, 
                     ip_address: str = None, user_agent: str = None):
        """记录操作日志"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO operation_logs 
            (user_id, operation, target_type, target_id, details, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, operation, target_type, target_id, details, ip_address, user_agent))
        
        conn.commit()
        conn.close()
