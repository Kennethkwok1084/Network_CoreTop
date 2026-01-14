#!/usr/bin/env python3
"""
任务调度模块
管理采集任务的创建、执行和调度
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度管理"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_task(self, device_id: int, task_type: str = 'manual',
                   created_by: int = None) -> int:
        """
        创建采集任务
        
        Args:
            device_id: 设备 ID
            task_type: 任务类型 (manual, scheduled, auto)
            created_by: 创建者用户 ID
        
        Returns:
            任务 ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO collection_tasks (device_id, task_type, status, created_by)
            VALUES (?, ?, 'pending', ?)
        """, (device_id, task_type, created_by))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"创建采集任务 #{task_id} (设备ID: {device_id}, 类型: {task_type})")
        return task_id
    
    def update_task_status(self, task_id: int, status: str, 
                          log_file_path: str = None, error_message: str = None,
                          commands_executed: List[str] = None):
        """
        更新任务状态
        
        Args:
            task_id: 任务 ID
            status: 状态 (running, success, failed)
            log_file_path: 日志文件路径
            error_message: 错误信息
            commands_executed: 执行的命令列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        fields = ["status = ?"]
        values = [status]
        
        if status == 'running':
            fields.append("started_at = ?")
            values.append(datetime.now())
        elif status in ['success', 'failed']:
            fields.append("completed_at = ?")
            values.append(datetime.now())
        
        if log_file_path:
            fields.append("log_file_path = ?")
            values.append(log_file_path)
        
        if error_message:
            fields.append("error_message = ?")
            values.append(error_message)
        
        if commands_executed:
            fields.append("commands_executed = ?")
            values.append(json.dumps(commands_executed, ensure_ascii=False))
        
        values.append(task_id)
        
        cursor.execute(f"""
            UPDATE collection_tasks
            SET {', '.join(fields)}
            WHERE id = ?
        """, values)
        
        conn.commit()
        conn.close()
        
        logger.info(f"任务 #{task_id} 状态更新为: {status}")
    
    def get_task(self, task_id: int) -> Optional[Dict]:
        """获取任务信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, d.device_name, d.device_type, d.mgmt_ip
            FROM collection_tasks t
            LEFT JOIN managed_devices d ON t.device_id = d.id
            WHERE t.id = ?
        """, (task_id,))
        
        task = cursor.fetchone()
        conn.close()
        
        if task:
            return dict(task)
        return None
    
    def list_tasks(self, device_id: int = None, status: str = None,
                  limit: int = 100) -> List[Dict]:
        """
        列出任务
        
        Args:
            device_id: 设备 ID 过滤
            status: 状态过滤
            limit: 返回数量限制
        
        Returns:
            任务列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT t.*, d.device_name, d.device_type, d.mgmt_ip
            FROM collection_tasks t
            LEFT JOIN managed_devices d ON t.device_id = d.id
            WHERE 1=1
        """
        params = []
        
        if device_id:
            query += " AND t.device_id = ?"
            params.append(device_id)
        
        if status:
            query += " AND t.status = ?"
            params.append(status)
        
        query += " ORDER BY t.id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return tasks
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取所有待执行的任务"""
        return self.list_tasks(status='pending', limit=1000)
    
    def delete_task(self, task_id: int) -> bool:
        """删除任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM collection_tasks WHERE id = ?", (task_id,))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0

    def _parse_timestamp(self, value) -> Optional[datetime]:
        """解析数据库时间戳"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='ignore')
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            return None

    def _device_has_pending_task(self, device_id: int) -> bool:
        """检查设备是否已有待执行或运行中的任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM collection_tasks
            WHERE device_id = ? AND status IN ('pending', 'running')
            """,
            (device_id,)
        )
        has_pending = cursor.fetchone()[0] > 0
        conn.close()
        return has_pending

    def _get_last_success_time(self, device_id: int) -> Optional[datetime]:
        """获取最近一次成功采集时间"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MAX(completed_at) FROM collection_tasks
            WHERE device_id = ? AND status = 'success'
            """,
            (device_id,)
        )
        last_completed = cursor.fetchone()[0]
        conn.close()
        return self._parse_timestamp(last_completed)

    def enqueue_due_tasks(self) -> List[int]:
        """
        为启用自动采集的设备创建到期任务

        Returns:
            新创建的任务 ID 列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, device_name, collect_interval
            FROM managed_devices
            WHERE is_active = 1 AND auto_collect = 1
            """
        )
        devices = cursor.fetchall()
        conn.close()

        created_tasks = []
        now = datetime.now()

        for device in devices:
            device_id = device['id']
            try:
                collect_interval = int(device['collect_interval'] or 86400)
            except (TypeError, ValueError):
                collect_interval = 86400

            if self._device_has_pending_task(device_id):
                continue

            last_success = self._get_last_success_time(device_id)
            if not last_success:
                due = True
            else:
                elapsed = (now - last_success).total_seconds()
                due = elapsed >= collect_interval

            if due:
                task_id = self.create_task(device_id, task_type='scheduled')
                created_tasks.append(task_id)
                logger.info(
                    f"设备 {device['device_name']} 到期，创建任务 #{task_id} "
                    f"(间隔: {collect_interval}s)"
                )

        return created_tasks

    def execute_pending_tasks(self, collector, output_dir: Path, limit: int = None) -> List[int]:
        """
        执行所有待执行的任务

        Args:
            collector: DeviceCollector 实例
            output_dir: 日志输出目录
            limit: 最大执行数量

        Returns:
            执行过的任务 ID 列表
        """
        tasks = self.get_pending_tasks()
        if limit is not None:
            tasks = tasks[:limit]

        executed = []
        for task in tasks:
            if self.execute_task(task['id'], collector, output_dir):
                executed.append(task['id'])
        return executed
    
    def execute_task(self, task_id: int, collector, output_dir: Path, log_callback=None) -> bool:
        """
        执行采集任务
        
        Args:
            task_id: 任务 ID
            collector: DeviceCollector 实例
            output_dir: 输出目录
            log_callback: 日志回调函数 log_callback(log_type, message)
        
        Returns:
            是否成功
        """
        from .device_manager import DeviceManager
        
        task = self.get_task(task_id)
        if not task:
            logger.error(f"任务 #{task_id} 不存在")
            if log_callback:
                log_callback('error', f'[错误] 任务 #{task_id} 不存在')
            return False
        
        # 更新为运行中
        self.update_task_status(task_id, 'running')
        if log_callback:
            log_callback('info', f'[开始] 任务 #{task_id} 开始执行')
            log_callback('info', f'[设备] {task["device_name"]} ({task["mgmt_ip"]})')
        
        try:
            # 获取设备信息（包含解密后的密码）
            device_manager = DeviceManager(self.db_path)
            device = device_manager.get_device(task['device_id'], decrypt_password=True)
            
            if not device:
                raise Exception(f"设备 ID {task['device_id']} 不存在")
            
            # 执行采集（传递日志回调）
            logger.info(f"开始执行任务 #{task_id}: {device['device_name']}")
            result = collector.collect_device_info(device, log_callback=log_callback)
            
            if result['status'] == 'success':
                # 保存日志文件
                log_path = collector.save_to_file(result, output_dir)
                
                if log_callback:
                    log_callback('success', f'[完成] 日志已保存到: {log_path.name if log_path else "未知"}')
                    log_callback('success', f'[成功] 任务执行成功，共执行 {len(result["commands"])} 条命令')
                
                # 更新任务状态
                self.update_task_status(
                    task_id,
                    'success',
                    log_file_path=str(log_path) if log_path else None,
                    commands_executed=result['commands']
                )
                
                logger.info(f"任务 #{task_id} 执行成功")
                return True
            else:
                # 更新为失败
                error_msg = result.get('error', 'Unknown error')
                if log_callback:
                    log_callback('error', f'[失败] {error_msg}')
                
                self.update_task_status(
                    task_id,
                    'failed',
                    error_message=error_msg,
                    commands_executed=result['commands']
                )
                
                logger.error(f"任务 #{task_id} 执行失败: {error_msg}")
                return False
                
        except Exception as e:
            error_msg = str(e) if str(e) else repr(e)
            logger.error(f"任务 #{task_id} 执行异常: {error_msg}", exc_info=True)
            if log_callback:
                log_callback('error', f'[异常] {error_msg}')
            self.update_task_status(task_id, 'failed', error_message=error_msg)
            return False
