"""
接口名标准化模块
根据 develop.md 第 5.1 节实现
- GE → GigabitEthernet
- XGE → XGigabitEthernet
- 去除多余空格，统一斜杠格式
"""

import re


def normalize_ifname(name: str) -> str:
    """
    标准化接口名称
    
    Args:
        name: 原始接口名，如 "GE1/6/0/21" 或 "Eth-Trunk6"
    
    Returns:
        标准化后的接口名，如 "GigabitEthernet1/6/0/21" 或 "Eth-Trunk6"
    
    Examples:
        >>> normalize_ifname("GE1/6/0/21")
        'GigabitEthernet1/6/0/21'
        >>> normalize_ifname("XGE 1/0/1")
        'XGigabitEthernet1/0/1'
        >>> normalize_ifname("eth-trunk6")
        'Eth-Trunk6'
    """
    if not name:
        return ""
    
    # 去除多余空格
    normalized = name.strip().replace(" ", "")
    
    # GE → GigabitEthernet（区分大小写）
    normalized = re.sub(r"^GE(?!th)", "GigabitEthernet", normalized, flags=re.IGNORECASE)
    
    # XGE → XGigabitEthernet
    normalized = re.sub(r"^XGE", "XGigabitEthernet", normalized, flags=re.IGNORECASE)
    
    # Te → TenGigabitEthernet (锐捷等设备)
    normalized = re.sub(r"^Te(?!n)", "TenGigabitEthernet", normalized, flags=re.IGNORECASE)
    
    # Eth-Trunk 统一首字母大写
    normalized = re.sub(r"^eth-trunk", "Eth-Trunk", normalized, flags=re.IGNORECASE)
    
    # 统一斜杠为 /
    normalized = normalized.replace("\\", "/")
    
    return normalized


def is_trunk_interface(name: str) -> bool:
    """
    判断是否为 Trunk 接口
    
    Args:
        name: 接口名称
    
    Returns:
        True 如果是 Trunk 接口
    """
    normalized = normalize_ifname(name)
    return normalized.startswith("Eth-Trunk")


def extract_trunk_id(name: str) -> int:
    """
    从 Trunk 接口名提取 ID
    
    Args:
        name: Trunk 接口名，如 "Eth-Trunk6"
    
    Returns:
        Trunk ID，如 6
    
    Raises:
        ValueError: 如果不是有效的 Trunk 接口名
    """
    normalized = normalize_ifname(name)
    match = re.search(r"Eth-Trunk(\d+)", normalized, re.IGNORECASE)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid trunk interface name: {name}")


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("GE1/6/0/21", "GigabitEthernet1/6/0/21"),
        ("XGE 1/0/1", "XGigabitEthernet1/0/1"),
        ("eth-trunk6", "Eth-Trunk6"),
        ("Eth-Trunk10", "Eth-Trunk10"),
        ("Te0/52", "TenGigabitEthernet0/52"),
        ("GE 1/0/0", "GigabitEthernet1/0/0"),
    ]
    
    print("接口名标准化测试：")
    for original, expected in test_cases:
        result = normalize_ifname(original)
        status = "✓" if result == expected else "✗"
        print(f"{status} {original:20s} → {result:30s} (expected: {expected})")
    
    # 测试 Trunk 判断
    print("\nTrunk 接口判断：")
    print(f"Eth-Trunk6: {is_trunk_interface('Eth-Trunk6')}")
    print(f"GE1/0/0: {is_trunk_interface('GE1/0/0')}")
    
    # 测试 Trunk ID 提取
    print("\nTrunk ID 提取：")
    print(f"Eth-Trunk6 → {extract_trunk_id('Eth-Trunk6')}")
    print(f"eth-trunk10 → {extract_trunk_id('eth-trunk10')}")
