"""
Eth-Trunk 解析器
根据 develop.md 第 5.3 节实现
解析 `display eth-trunk` 输出
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field

try:
    from .normalize import normalize_ifname, is_trunk_interface
except ImportError:
    from normalize import normalize_ifname, is_trunk_interface


@dataclass
class EthTrunk:
    """Eth-Trunk 信息"""
    name: str
    mode: str = "NORMAL"  # NORMAL/LACP
    oper_status: str = "up"
    members: List[str] = field(default_factory=list)  # 成员接口列表


def parse_eth_trunk(text: str) -> List[EthTrunk]:
    """
    解析 display eth-trunk 输出
    
    示例输出：
    ```
    Eth-Trunk6   NORMAL   1   1000M(a)  1000M(a)  up
      Port Status
      GE1/6/0/19    Product: GigabitEthernet     Status: up
      GE1/6/0/20    Product: GigabitEthernet     Status: up
    
    Eth-Trunk10  LACP     1   10G(a)    10G(a)    up
      Port Status
      XGE1/0/1      Product: XGigabitEthernet    Status: up
    ```
    
    Args:
        text: 命令输出文本
    
    Returns:
        Eth-Trunk 列表
    """
    trunks = []
    lines = text.strip().split('\n')
    
    current_trunk = None
    in_member_section = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 匹配 Trunk 头行（Eth-Trunk开头）
        match_trunk = re.match(r'(Eth-Trunk\d+)\s+(\w+)\s+.*\s+(up|down)', line, re.IGNORECASE)
        if match_trunk:
            # 保存前一个 Trunk
            if current_trunk:
                trunks.append(current_trunk)
            
            trunk_name = normalize_ifname(match_trunk.group(1))
            mode = match_trunk.group(2).upper()
            status = match_trunk.group(3).lower()
            
            current_trunk = EthTrunk(name=trunk_name, mode=mode, oper_status=status)
            in_member_section = False
            continue
        
        # 进入成员列表区域
        if 'Port Status' in line or 'Member' in line:
            in_member_section = True
            continue
        
        # 解析成员接口
        if in_member_section and current_trunk:
            # 匹配类似：GE1/6/0/19    Product: GigabitEthernet     Status: up
            match_member = re.match(r'([A-Z][A-Za-z0-9\-/]+)\s+.*Status:\s*(up|down)', line, re.IGNORECASE)
            if match_member:
                member_if = normalize_ifname(match_member.group(1))
                current_trunk.members.append(member_if)
            # 或简单匹配接口名
            elif re.match(r'^[A-Z][A-Za-z0-9\-/]+', line):
                parts = line.split()
                if parts:
                    member_if = normalize_ifname(parts[0])
                    current_trunk.members.append(member_if)
    
    # 保存最后一个 Trunk
    if current_trunk:
        trunks.append(current_trunk)
    
    return trunks


if __name__ == "__main__":
    # 测试
    sample_output = """
Eth-Trunk6   NORMAL   1   1000M(a)  1000M(a)  up
  Port Status
  GE1/6/0/19    Product: GigabitEthernet     Status: up
  GE1/6/0/20    Product: GigabitEthernet     Status: up

Eth-Trunk10  LACP     1   10G(a)    10G(a)    up
  Port Status
  XGE1/0/1      Product: XGigabitEthernet    Status: up
  XGE1/0/2      Product: XGigabitEthernet    Status: down
    """
    
    print("=== Eth-Trunk 解析测试 ===")
    trunks = parse_eth_trunk(sample_output)
    for trunk in trunks:
        print(f"\n{trunk.name} (Mode: {trunk.mode}, Status: {trunk.oper_status})")
        print(f"  Members: {', '.join(trunk.members)}")
