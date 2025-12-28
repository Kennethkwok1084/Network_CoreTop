"""
STP 解析器
根据 develop.md 第 5.5 节实现
解析 `display stp brief` 输出
"""

import re
from typing import List
from dataclasses import dataclass

try:
    from .normalize import normalize_ifname
except ImportError:
    from normalize import normalize_ifname


@dataclass
class STPPort:
    """STP 端口信息"""
    interface: str
    role: str  # ROOT/DESI/ALTE/BACK/MAST
    state: str  # Forwarding/Discarding/Blocked/Learning


def parse_stp_brief(text: str) -> List[STPPort]:
    """
    解析 display stp brief 输出
    
    示例输出：
    ```
    MSTID  Port                        Role  State
    0      GigabitEthernet1/6/0/21     DESI  Forwarding
    0      GigabitEthernet1/6/0/22     ALTE  Discarding
    0      Eth-Trunk6                  ROOT  Forwarding
    ```
    
    Args:
        text: 命令输出文本
    
    Returns:
        STP 端口列表
    """
    ports = []
    lines = text.strip().split('\n')
    
    header_found = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 识别表头
        if 'Port' in line and ('Role' in line or 'State' in line):
            header_found = True
            continue
        
        # 跳过分隔线
        if re.match(r'^[-=\s]+$', line):
            continue
        
        # 解析数据行
        if header_found:
            # 分割字段
            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 3:
                # 第一列可能是 MSTID，第二列是接口
                if re.match(r'^\d+$', parts[0]):
                    # 有 MSTID
                    interface = normalize_ifname(parts[1])
                    role = parts[2] if len(parts) >= 3 else "UNKN"
                    state = parts[3] if len(parts) >= 4 else "Unknown"
                else:
                    # 无 MSTID
                    interface = normalize_ifname(parts[0])
                    role = parts[1]
                    state = parts[2] if len(parts) >= 3 else "Unknown"
                
                ports.append(STPPort(
                    interface=interface,
                    role=role,
                    state=state
                ))
    
    return ports


def get_blocked_ports(stp_ports: List[STPPort]) -> List[str]:
    """
    获取被 STP 阻塞的端口
    
    Args:
        stp_ports: STP 端口列表
    
    Returns:
        阻塞端口接口名列表
    """
    blocked = []
    for port in stp_ports:
        if port.state in ['Discarding', 'Blocked', 'Blocking']:
            blocked.append(port.interface)
    return blocked


if __name__ == "__main__":
    # 测试
    sample_output = """
 MSTID  Port                        Role  State
 0      GigabitEthernet1/6/0/21     DESI  Forwarding
 0      GigabitEthernet1/6/0/22     ALTE  Discarding
 0      Eth-Trunk6                  ROOT  Forwarding
 0      XGE1/0/1                    DESI  Blocked
    """
    
    print("=== STP Brief 解析测试 ===")
    stp_ports = parse_stp_brief(sample_output)
    for port in stp_ports:
        status_icon = "🚫" if port.state in ['Discarding', 'Blocked'] else "✓"
        print(f"{status_icon} {port.interface:35s} {port.role:6s} {port.state}")
    
    blocked = get_blocked_ports(stp_ports)
    print(f"\n阻塞端口: {', '.join(blocked) if blocked else '无'}")
