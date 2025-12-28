"""
接口描述解析器
根据 develop.md 第 5.4 节实现
解析 `display interface description` 输出
"""

import re
from typing import Dict
from dataclasses import dataclass

try:
    from .normalize import normalize_ifname
except ImportError:
    from normalize import normalize_ifname


@dataclass
class InterfaceDesc:
    """接口描述信息"""
    name: str
    admin_status: str  # up/down
    protocol_status: str  # up/down
    description: str = ""


def parse_interface_description(text: str) -> Dict[str, InterfaceDesc]:
    """
    解析 display interface description 输出
    
    示例输出：
    ```
    Interface                      PHY   Protocol  Description
    GigabitEthernet1/6/0/21        up    up        To Building A Floor 3
    GigabitEthernet1/6/0/22        down  down      
    Eth-Trunk6                     up    up        Uplink to Core
    ```
    
    Args:
        text: 命令输出文本
    
    Returns:
        接口描述字典 {接口名: InterfaceDesc}
    """
    interfaces = {}
    lines = text.strip().split('\n')
    
    header_found = False
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        
        # 识别表头
        if 'Interface' in line and ('Protocol' in line or 'PHY' in line):
            header_found = True
            continue
        
        # 跳过分隔线
        if re.match(r'^[-=\s]+$', line):
            continue
        
        # 解析数据行
        if header_found:
            # 匹配接口名（开头）
            match = re.match(r'^([A-Za-z][\w\-/]+)\s+(up|down)\s+(up|down)\s*(.*)', line, re.IGNORECASE)
            if match:
                if_name = normalize_ifname(match.group(1))
                admin_status = match.group(2).lower()
                protocol_status = match.group(3).lower()
                description = match.group(4).strip()
                
                interfaces[if_name] = InterfaceDesc(
                    name=if_name,
                    admin_status=admin_status,
                    protocol_status=protocol_status,
                    description=description
                )
    
    return interfaces


if __name__ == "__main__":
    # 测试
    sample_output = """
Interface                      PHY   Protocol  Description
GigabitEthernet1/6/0/21        up    up        To Building A Floor 3
GigabitEthernet1/6/0/22        down  down      
Eth-Trunk6                     up    up        Uplink to Core
XGE1/0/1                       up    up        
    """
    
    print("=== Interface Description 解析测试 ===")
    interfaces = parse_interface_description(sample_output)
    for if_name, desc in interfaces.items():
        print(f"{if_name:35s} {desc.admin_status:5s}/{desc.protocol_status:5s} '{desc.description}'")
