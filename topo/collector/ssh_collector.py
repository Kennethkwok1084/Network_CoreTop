"""
SSH 自动采集模块
通过 SSH 连接交换机自动执行命令并采集配置
"""
import paramiko
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class SSHCollector:
    """SSH 采集器"""
    
    # 华为交换机默认采集命令
    HUAWEI_COMMANDS = [
        "screen-length 0 temporary",
        "display lldp neighbor brief",
        "display lldp neighbor",
        "display eth-trunk",
        "display interface description",
        "display stp brief",
        "display device",
        "display version",
    ]
    
    def __init__(self, host: str, port: int = 22, username: str = "", 
                 password: str = "", private_key: Optional[str] = None,
                 enable_password: Optional[str] = None):
        """
        初始化 SSH 采集器
        
        Args:
            host: 设备 IP 地址
            port: SSH 端口
            username: 用户名
            password: 密码
            private_key: SSH 私钥路径
            enable_password: 特权模式密码
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.enable_password = enable_password
        
        self.client: Optional[paramiko.SSHClient] = None
        self.shell = None
    
    def connect(self, timeout: int = 10) -> bool:
        """
        建立 SSH 连接
        
        Returns:
            连接是否成功
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': timeout,
                'look_for_keys': False,
                'allow_agent': False,
            }
            
            # 使用密钥或密码
            if self.private_key:
                connect_kwargs['key_filename'] = self.private_key
            else:
                connect_kwargs['password'] = self.password
            
            self.client.connect(**connect_kwargs)
            
            # 创建交互式 shell
            self.shell = self.client.invoke_shell()
            time.sleep(1)
            
            # 清空初始输出
            if self.shell.recv_ready():
                self.shell.recv(65535)
            
            logger.info(f"成功连接到 {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"连接失败 {self.host}: {e}")
            return False
    
    def execute_command(self, command: str, wait_time: float = 2.0) -> str:
        """
        执行单条命令
        
        Args:
            command: 要执行的命令
            wait_time: 等待响应时间（秒）
        
        Returns:
            命令输出
        """
        if not self.shell:
            raise RuntimeError("未建立连接")
        
        # 发送命令
        self.shell.send(command + '\n')
        time.sleep(wait_time)
        
        # 接收输出
        output = ""
        while self.shell.recv_ready():
            chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
            output += chunk
            time.sleep(0.1)
        
        return output
    
    def collect_huawei_config(self, commands: Optional[List[str]] = None) -> Dict[str, str]:
        """
        采集华为交换机配置
        
        Args:
            commands: 自定义命令列表（默认使用 HUAWEI_COMMANDS）
        
        Returns:
            {命令: 输出} 字典
        """
        if commands is None:
            commands = self.HUAWEI_COMMANDS
        
        results = {}
        
        for cmd in commands:
            try:
                logger.info(f"执行命令: {cmd}")
                output = self.execute_command(cmd)
                results[cmd] = output
                
            except Exception as e:
                logger.error(f"命令执行失败 '{cmd}': {e}")
                results[cmd] = f"ERROR: {str(e)}"
        
        return results
    
    def get_full_log(self, commands: Optional[List[str]] = None) -> str:
        """
        获取完整日志（合并所有命令输出）
        
        Returns:
            完整日志文本
        """
        results = self.collect_huawei_config(commands)
        
        log_parts = []
        log_parts.append(f"# 自动采集日志 - {self.host}")
        log_parts.append(f"# 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_parts.append("")
        
        for cmd, output in results.items():
            log_parts.append(f"# ========== {cmd} ==========")
            log_parts.append(output)
            log_parts.append("")
        
        return "\n".join(log_parts)
    
    def test_connection(self) -> Dict[str, any]:
        """
        测试连接并获取设备基本信息
        
        Returns:
            {
                'success': bool,
                'device_name': str,
                'model': str,
                'version': str,
                'error': str
            }
        """
        result = {
            'success': False,
            'device_name': '',
            'model': '',
            'version': '',
            'error': ''
        }
        
        try:
            if not self.connect():
                result['error'] = '连接失败'
                return result
            
            # 尝试获取设备信息
            output = self.execute_command('display version', wait_time=3.0)
            
            # 简单解析（可根据实际输出格式调整）
            lines = output.split('\n')
            for line in lines:
                if 'Huawei' in line and 'Software' in line:
                    # 提取设备名
                    parts = line.split()
                    if len(parts) >= 2:
                        result['device_name'] = parts[1]
                
                if 'Version' in line:
                    result['version'] = line.strip()
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        finally:
            self.close()
        
        return result
    
    def close(self):
        """关闭连接"""
        if self.shell:
            self.shell.close()
        if self.client:
            self.client.close()
        
        logger.info(f"断开连接: {self.host}")
    
    def __enter__(self):
        """上下文管理器：进入"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出"""
        self.close()


def test_ssh_connection(host: str, port: int, username: str, 
                       password: str, **kwargs) -> Dict[str, any]:
    """
    快速测试 SSH 连接
    
    Returns:
        测试结果字典
    """
    collector = SSHCollector(host, port, username, password, **kwargs)
    return collector.test_connection()


if __name__ == "__main__":
    # 测试示例
    import sys
    
    if len(sys.argv) < 4:
        print("用法: python -m topo.collector.ssh_collector <host> <username> <password>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    with SSHCollector(host, 22, username, password) as collector:
        log = collector.get_full_log()
        
        # 保存到文件
        filename = f"{host}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(log)
        
        print(f"✓ 采集完成: {filename}")
