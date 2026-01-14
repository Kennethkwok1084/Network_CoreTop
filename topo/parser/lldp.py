"""
LLDP 邻居解析器
根据 develop.md 第 5.2 节实现
解析 `display lldp neighbor brief` 和 `display lldp neighbor system-name`
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from .normalize import normalize_ifname
except ImportError:
    from normalize import normalize_ifname


@dataclass
class LLDPNeighbor:
    """LLDP 邻居记录"""
    local_if: str
    neighbor_dev: str
    neighbor_if: Optional[str] = None
    exptime: Optional[int] = None


def parse_lldp_brief(text: str) -> List[LLDPNeighbor]:
    """
    解析 display lldp neighbor brief 输出
    
    示例输出：
    ```
    Local Intf       Neighbor Dev             Neighbor Intf             Exptime(s)
    GE1/6/0/3        ZXR10                    gei-0/4/0/20              105
    GE1/6/0/6        Ruijie                   Te0/52                    114
    ```
    
    Args:
        text: 命令输出文本
    
    Returns:
        LLDP 邻居列表
    """
    neighbors = []
    lines = text.strip().split('\n')
    
    # 查找表头行
    header_found = False
    for line in lines:
        # 跳过空行
        if not line.strip():
            continue
        
        # 识别表头
        if 'Local Intf' in line or 'Local Int' in line:
            header_found = True
            continue
        
        # 跳过分隔线
        if re.match(r'^[-=\s]+$', line):
            continue
        
        # 解析数据行
        if header_found:
            # 分割字段（至少 2 列空格）
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 3:
                local_if = normalize_ifname(parts[0])
                neighbor_dev = parts[1]
                neighbor_if = normalize_ifname(parts[2]) if len(parts) >= 3 else None
                exptime_str = parts[3] if len(parts) >= 4 else None
                
                # 尝试解析 exptime
                exptime = None
                if exptime_str:
                    try:
                        exptime = int(exptime_str)
                    except ValueError:
                        pass
                
                neighbors.append(LLDPNeighbor(
                    local_if=local_if,
                    neighbor_dev=neighbor_dev,
                    neighbor_if=neighbor_if,
                    exptime=exptime
                ))
    
    return neighbors


def parse_lldp_system_name(text: str) -> Dict[str, str]:
    """
    解析 display lldp neighbor system-name 输出
    提取更精确的设备名（sysname）
    
    示例输出：
    ```
    System Name: Core_CSS
    Port ID    : GE1/6/0/21
    ```
    
    Args:
        text: 命令输出文本
    
    Returns:
        设备名映射 {接口: 系统名}
    """
    mapping = {}
    lines = text.strip().split('\n')
    
    current_sysname = None
    for line in lines:
        # 匹配 System Name
        match_sys = re.search(r'System\s+Name\s*:\s*(.+)', line, re.IGNORECASE)
        if match_sys:
            current_sysname = match_sys.group(1).strip()
            continue
        
        # 匹配 Port ID
        match_port = re.search(r'Port\s+ID\s*:\s*(\S+)', line, re.IGNORECASE)
        if match_port and current_sysname:
            local_if = normalize_ifname(match_port.group(1))
            mapping[local_if] = current_sysname
    
    return mapping


if __name__ == "__main__":
    # 测试 LLDP brief 解析
    sample_brief = """
Local Intf    Exptime  Neighbor Dev            Neighbor Intf
GE1/6/0/21    101      Ruijie                  Te0/52
GE1/6/0/21    102      Huawei-Switch           GE0/0/0
XGE 1/0/1     120      Core_CSS                XGE1/0/2
    """
    
    print("=== LLDP Brief 解析测试 ===")
    neighbors = parse_lldp_brief(sample_brief)
    for n in neighbors:
        print(f"  {n.local_if:30s} → {n.neighbor_dev:20s} {n.neighbor_if or 'N/A':20s} (exp:{n.exptime})")
    
    # 测试 LLDP system-name 解析
    sample_sysname = """
LLDP neighbor-information of port 1[GE1/6/0/21]:
System Name: Building-A-Access-01
Port ID    : GE1/0/48
    """
    
    print("\n=== LLDP System Name 解析测试 ===")
    sysname_map = parse_lldp_system_name(sample_sysname)
    for intf, sysname in sysname_map.items():
        print(f"  {intf:30s} → {sysname}")
