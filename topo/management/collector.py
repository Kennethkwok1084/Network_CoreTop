#!/usr/bin/env python3
"""
SSH 自动采集模块
支持华为、思科等设备的自动采集
"""
import paramiko
import time
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DeviceCollector:
    """设备信息采集器"""
    
    # 华为设备采集命令
    HUAWEI_COMMANDS = [
        'screen-length 0 temporary',
        'display version',
        'display device',
        'display lldp neighbor brief',
        'display lldp neighbor',
        'display eth-trunk',
        'display interface description',
        'display stp brief',
        'display ip interface brief',
    ]
    
    # 思科设备采集命令
    CISCO_COMMANDS = [
        'terminal length 0',
        'show version',
        'show inventory',
        'show cdp neighbors',
        'show cdp neighbors detail',
        'show etherchannel summary',
        'show interfaces description',
        'show spanning-tree summary',
        'show ip interface brief',
    ]
    
    # H3C 设备采集命令
    H3C_COMMANDS = [
        'screen-length disable',
        'display version',
        'display device',
        'display lldp neighbor-information',
        'display link-aggregation summary',
        'display interface description',
        'display stp brief',
        'display ip interface brief',
    ]
    
    def __init__(self, timeout: int = 30, read_timeout: int = 10):
        """
        初始化采集器
        
        Args:
            timeout: SSH 连接超时（秒）
            read_timeout: 命令执行超时（秒）
        """
        self.timeout = timeout
        self.read_timeout = read_timeout
    
    def collect_device_info(self, device_config: Dict, log_callback=None) -> Dict:
        """
        采集单个设备信息
        
        Args:
            device_config: 设备配置字典，包含 mgmt_ip, username, password 等
            log_callback: 日志回调函数 log_callback(log_type, message)
        
        Returns:
            采集结果字典
        """
        result = {
            'device_name': device_config.get('device_name'),
            'device_type': device_config.get('device_type'),
            'status': 'pending',
            'started_at': datetime.now(),
            'completed_at': None,
            'commands': [],
            'output': '',
            'error': None,
        }
        
        ssh = None
        try:
            if log_callback:
                log_callback('info', f'[连接] 正在连接到 {device_config["mgmt_ip"]}:{device_config.get("mgmt_port", 22)}...')
            
            # 创建 SSH 客户端
            ssh = paramiko.SSHClient()
            
            # 加载已知主机文件（通常是 ~/.ssh/known_hosts）
            known_hosts_file = os.path.expanduser('~/.ssh/known_hosts')
            if os.path.exists(known_hosts_file):
                ssh.load_system_host_keys(known_hosts_file)
            
            # 开发模式：自动接受所有主机密钥
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接设备
            logger.info(f"正在连接设备 {device_config['device_name']} ({device_config['mgmt_ip']})...")
            try:
                ssh.connect(
                    hostname=device_config['mgmt_ip'],
                    port=device_config.get('mgmt_port', 22),
                    username=device_config['username'],
                    password=device_config['password'],
                    timeout=self.timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
                
                if log_callback:
                    log_callback('success', f'[连接] SSH 连接成功 (用户: {device_config["username"]})')
                    
            except paramiko.ssh_exception.SSHException as e:
                if 'not found in known_hosts' in str(e):
                    result['error'] = (
                        f"主机密钥验证失败: {device_config['mgmt_ip']} 未在已知主机列表中\n"
                        "解决方法:\n"
                        "1. 手动连接一次以添加主机密钥: ssh -o StrictHostKeyChecking=accept-new admin@{}\n"
                        "2. 或设置 SSH_TRUST_NEW_HOSTS=true (仅限测试环境)"
                    ).format(device_config['mgmt_ip'])
                    logger.error(result['error'])
                    if log_callback:
                        log_callback('error', f'[错误] {result["error"]}')
                    return result
                raise
            
            # 获取交互式 shell
            channel = ssh.invoke_shell()
            time.sleep(1)
            
            # 清空欢迎信息
            if channel.recv_ready():
                channel.recv(65535)
            
            # 根据设备类型选择命令
            device_type = device_config.get('device_type', 'huawei').lower()
            if device_type == 'cisco':
                commands = self.CISCO_COMMANDS
            elif device_type == 'h3c':
                commands = self.H3C_COMMANDS
            else:
                commands = self.HUAWEI_COMMANDS
            
            # 执行命令
            output_lines = []
            for idx, cmd in enumerate(commands, 1):
                logger.info(f"执行命令: {cmd}")
                result['commands'].append(cmd)
                
                if log_callback:
                    log_callback('command', f'[{idx}/{len(commands)}] 执行命令: {cmd}')
                
                # 发送命令
                channel.send(cmd + '\n')
                time.sleep(1)
                
                # 读取输出
                cmd_output = self._read_channel_output(channel)
                output_lines.append(f"{'='*60}")
                output_lines.append(f"命令: {cmd}")
                output_lines.append(f"{'='*60}")
                output_lines.append(cmd_output)
                output_lines.append('')
                
                if log_callback:
                    output_preview = cmd_output[:200].replace('\n', ' ') if cmd_output else '(无输出)'
                    log_callback('output', f'[输出] {output_preview}...')
            
            result['output'] = '\n'.join(output_lines)
            result['status'] = 'success'
            result['completed_at'] = datetime.now()
            
            logger.info(f"设备 {device_config['device_name']} 采集成功")
            
            if log_callback:
                log_callback('success', f'[采集] 采集完成，共收集 {len(result["output"])} 字节数据')
            
        except paramiko.AuthenticationException as e:
            error_msg = f"认证失败: {str(e)}"
            logger.error(error_msg)
            if log_callback:
                log_callback('error', f'[错误] {error_msg}')
            result['status'] = 'failed'
            result['error'] = error_msg
            result['completed_at'] = datetime.now()
            
        except paramiko.SSHException as e:
            error_msg = f"SSH 连接错误: {str(e)}"
            logger.error(error_msg)
            if log_callback:
                log_callback('error', f'[错误] {error_msg}')
            result['status'] = 'failed'
            result['error'] = error_msg
            result['completed_at'] = datetime.now()
            
        except Exception as e:
            error_msg = f"采集失败: {str(e)}"
            logger.error(error_msg)
            if log_callback:
                log_callback('error', f'[错误] {error_msg}')
            result['status'] = 'failed'
            result['error'] = error_msg
            result['completed_at'] = datetime.now()
            
        finally:
            if ssh:
                ssh.close()
        
        return result
    
    def _read_channel_output(self, channel, max_wait: int = None) -> str:
        """读取 channel 输出"""
        if max_wait is None:
            max_wait = self.read_timeout
        
        output = ''
        start_time = time.time()
        
        while True:
            if channel.recv_ready():
                chunk = channel.recv(65535).decode('utf-8', errors='ignore')
                output += chunk
                start_time = time.time()  # 重置超时
            
            # 检查是否超时
            if time.time() - start_time > max_wait:
                break
            
            # 短暂休眠
            time.sleep(0.1)
        
        return output
    
    def save_to_file(self, result: Dict, output_dir: Path) -> Optional[Path]:
        """
        保存采集结果到文件
        
        Args:
            result: 采集结果
            output_dir: 输出目录
        
        Returns:
            保存的文件路径
        """
        if result['status'] != 'success':
            return None
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        device_name = result['device_name']
        filename = f"{device_name}_{timestamp}.log"
        filepath = output_dir / filename
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"设备名称: {device_name}\n")
            f.write(f"设备类型: {result['device_type']}\n")
            f.write(f"采集时间: {result['started_at']}\n")
            f.write(f"完成时间: {result['completed_at']}\n")
            f.write(f"\n{'='*80}\n\n")
            f.write(result['output'])
        
        logger.info(f"采集结果已保存到: {filepath}")
        return filepath
    
    def batch_collect(self, devices: List[Dict], output_dir: Path) -> List[Dict]:
        """
        批量采集设备信息
        
        Args:
            devices: 设备配置列表
            output_dir: 输出目录
        
        Returns:
            采集结果列表
        """
        results = []
        
        for device in devices:
            logger.info(f"\n开始采集设备: {device['device_name']}")
            result = self.collect_device_info(device)
            
            # 保存到文件
            if result['status'] == 'success':
                filepath = self.save_to_file(result, output_dir)
                result['log_file_path'] = str(filepath) if filepath else None
            
            results.append(result)
        
        return results
