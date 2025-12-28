#!/usr/bin/env python3
"""
设备配置管理模块
"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
import os
import base64


class DeviceManager:
    """设备配置管理"""
    
    def __init__(self, db_path: str, encryption_key: str = None):
        self.db_path = db_path
        
        # 从环境变量或参数读取加密密钥
        if encryption_key:
            key = encryption_key
        else:
            key = os.environ.get('FERNET_KEY')
            if not key:
                # 如果没有密钥，尝试从配置文件读取
                config_file = os.path.expanduser('~/.topo_fernet_key')
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        key = f.read().strip()
                else:
                    raise ValueError(
                        "FATAL: Fernet 加密密钥未找到\n"
                        "  必须通过以下方式之一提供:\n"
                        "  1. 环境变量: export FERNET_KEY='<base64密钥>'\n"
                        "  2. 配置文件: ~/.topo_fernet_key\n"
                        "\n"
                        "  生成新密钥: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
                        "  保存到: ~/.topo_fernet_key\n"
                        "  或导出为: export FERNET_KEY='<生成的密钥>'"
                    )
        
        try:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f"ERROR: 无效的 Fernet 密钥格式: {e}")
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _encrypt_password(self, password: str) -> str:
        """加密密码"""
        return self.cipher.encrypt(password.encode()).decode()
    
    def _decrypt_password(self, encrypted: str) -> str:
        """解密密码"""
        return self.cipher.decrypt(encrypted.encode()).decode()
    
    def add_device(self, device_name: str, device_type: str, mgmt_ip: str,
                   username: str, password: str, model: str = None,
                   mgmt_port: int = 22, enable_password: str = None,
                   description: str = None, group_name: str = None,
                   auto_collect: bool = False, collect_interval: int = 86400,
                   created_by: int = None) -> int:
        """
        添加管理设备
        
        Args:
            device_name: 设备名称
            device_type: 设备类型 (huawei, cisco, h3c, etc.)
            mgmt_ip: 管理 IP
            username: SSH 用户名
            password: SSH 密码
            model: 设备型号
            mgmt_port: SSH 端口
            enable_password: Enable 密码
            description: 描述
            group_name: 设备分组
            auto_collect: 是否自动采集
            collect_interval: 采集间隔（秒）
            created_by: 创建者用户 ID
        
        Returns:
            新设备 ID
        """
        encrypted_password = self._encrypt_password(password)
        encrypted_enable = self._encrypt_password(enable_password) if enable_password else None
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO managed_devices (
                device_name, device_type, model, mgmt_ip, mgmt_port,
                username, password, enable_password, description, group_name,
                auto_collect, collect_interval, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (device_name, device_type, model, mgmt_ip, mgmt_port,
              username, encrypted_password, encrypted_enable, description, group_name,
              int(auto_collect), collect_interval, created_by))
        
        device_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return device_id
    
    def update_device(self, device_id: int, **kwargs) -> bool:
        """更新设备信息"""
        # 处理密码加密
        if 'password' in kwargs:
            kwargs['password'] = self._encrypt_password(kwargs['password'])
        if 'enable_password' in kwargs and kwargs['enable_password']:
            kwargs['enable_password'] = self._encrypt_password(kwargs['enable_password'])
        
        # 构建更新语句
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['device_name', 'device_type', 'model', 'mgmt_ip', 'mgmt_port',
                      'username', 'password', 'enable_password', 'description', 'group_name',
                      'is_active', 'auto_collect', 'collect_interval']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        fields.append("updated_at = ?")
        values.append(datetime.now())
        values.append(device_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            UPDATE managed_devices
            SET {', '.join(fields)}
            WHERE id = ?
        """, values)
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def delete_device(self, device_id: int) -> bool:
        """删除设备"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM managed_devices WHERE id = ?", (device_id,))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def get_device(self, device_id: int, decrypt_password: bool = False) -> Optional[Dict[str, Any]]:
        """获取设备信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM managed_devices WHERE id = ?
        """, (device_id,))
        
        device = cursor.fetchone()
        conn.close()
        
        if device:
            device_dict = dict(device)
            if decrypt_password:
                device_dict['password'] = self._decrypt_password(device_dict['password'])
                if device_dict.get('enable_password'):
                    device_dict['enable_password'] = self._decrypt_password(device_dict['enable_password'])
            else:
                # 不返回密码
                device_dict.pop('password', None)
                device_dict.pop('enable_password', None)
            return device_dict
        
        return None
    
    def get_device_by_name(self, device_name: str, decrypt_password: bool = False) -> Optional[Dict[str, Any]]:
        """根据名称获取设备"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM managed_devices WHERE device_name = ?
        """, (device_name,))
        
        device = cursor.fetchone()
        conn.close()
        
        if device:
            device_dict = dict(device)
            if decrypt_password:
                device_dict['password'] = self._decrypt_password(device_dict['password'])
                if device_dict.get('enable_password'):
                    device_dict['enable_password'] = self._decrypt_password(device_dict['enable_password'])
            else:
                device_dict.pop('password', None)
                device_dict.pop('enable_password', None)
            return device_dict
        
        return None
    
    def list_devices(self, group_name: str = None, device_type: str = None,
                    is_active: bool = None) -> List[Dict[str, Any]]:
        """列出设备"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM managed_devices WHERE 1=1"
        params = []
        
        if group_name:
            query += " AND group_name = ?"
            params.append(group_name)
        
        if device_type:
            query += " AND device_type = ?"
            params.append(device_type)
        
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(int(is_active))
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        devices = cursor.fetchall()
        conn.close()
        
        # 不返回密码
        result = []
        for device in devices:
            device_dict = dict(device)
            device_dict.pop('password', None)
            device_dict.pop('enable_password', None)
            result.append(device_dict)
        
        return result
    
    def get_auto_collect_devices(self) -> List[Dict[str, Any]]:
        """获取需要自动采集的设备"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM managed_devices
            WHERE is_active = 1 AND auto_collect = 1
            ORDER BY device_name
        """)
        
        devices = cursor.fetchall()
        conn.close()
        
        # 解密密码用于采集
        result = []
        for device in devices:
            device_dict = dict(device)
            device_dict['password'] = self._decrypt_password(device_dict['password'])
            if device_dict.get('enable_password'):
                device_dict['enable_password'] = self._decrypt_password(device_dict['enable_password'])
            result.append(device_dict)
        
        return result
