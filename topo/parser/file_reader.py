"""
文件读取和编码探测
根据 develop.md 第 3 节实现
- 自动探测 UTF-8/UTF-16 编码
- 按命令提示符分割多段命令输出
"""

import re
import hashlib
import logging
from typing import List, Tuple, Optional
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 文件大小限制（默认 100MB）
MAX_FILE_SIZE = 100 * 1024 * 1024


def detect_encoding(file_path: str) -> str:
    """
    探测文件编码
    
    Args:
        file_path: 文件路径
    
    Returns:
        编码名称：'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk'
    """
    # 读取文件前几个字节检测 BOM
    with open(file_path, 'rb') as f:
        raw = f.read(4)
    
    # UTF-16 BOM
    if raw.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    if raw.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    if raw.startswith(b'\xff\xfe\x00\x00'):
        return 'utf-32-le'
    if raw.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32-be'
    
    # UTF-8 BOM
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    
    # 尝试 UTF-8 解码
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    
    # 尝试 GBK（中文 Windows）
    try:
        with open(file_path, 'r', encoding='gbk') as f:
            f.read(1024)
        return 'gbk'
    except UnicodeDecodeError:
        pass
    
    # 默认 UTF-8
    return 'utf-8'


def read_file(file_path: str, max_size: int = MAX_FILE_SIZE) -> str:
    """
    读取文件内容（自动探测编码，带大小保护）
    
    Args:
        file_path: 文件路径
        max_size: 最大文件大小（字节），默认 100MB
    
    Returns:
        文件内容字符串
    
    Raises:
        ValueError: 文件过大时抛出异常
    """
    # 检查文件大小
    file_size = Path(file_path).stat().st_size
    if file_size > max_size:
        raise ValueError(
            f"文件过大: {file_size / 1024 / 1024:.2f}MB > {max_size / 1024 / 1024:.2f}MB 限制。"
            "请分割文件或调整 max_size 参数。"
        )
    
    encoding = detect_encoding(file_path)
    logger.info(f"读取文件 {file_path}（编码: {encoding}, 大小: {file_size / 1024:.2f}KB）")
    
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        # 检查是否有解码错误（替换字符）
        if '�' in content:
            logger.warning(f"文件 {file_path} 存在编码错误，部分字符已替换为 �")
        
        return content
    except UnicodeDecodeError as e:
        logger.error(f"文件 {file_path} 解码失败: {e}")
        # 降级为二进制读取并尝试多种编码
        logger.warning("尝试使用 latin-1 编码降级读取...")
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def calculate_file_hash(file_path: str) -> str:
    """
    计算文件 SHA256 哈希（用于去重）
    
    Args:
        file_path: 文件路径
    
    Returns:
        SHA256 哈希值（16 进制字符串）
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def split_command_blocks(text: str) -> List[Tuple[str, str]]:
    """
    按命令提示符分割日志为多个命令块
    
    华为设备命令提示符示例：
    - <Huawei>display lldp neighbor brief
    - [Huawei]display interface description
    - [~Huawei]display stp brief
    
    Args:
        text: 完整日志文本
    
    Returns:
        [(命令, 输出内容), ...]
    """
    blocks = []
    
    # 匹配命令提示符 + 命令行
    # 支持 <device>, [device], [~device] 等格式
    pattern = r'[<\[][\~]?[\w\-]+[>\]]\s*(display\s+.+?)(?=\r?\n)'
    
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    
    for i, match in enumerate(matches):
        command = match.group(1).strip()
        start_pos = match.end()
        
        # 找到下一个命令的起始位置
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(text)
        
        output = text[start_pos:end_pos].strip()
        blocks.append((command, output))
    
    return blocks


def extract_device_name_from_file(file_path: str) -> Optional[str]:
    """
    从文件名或内容中提取设备名
    
    文件名建议格式：{device}_{yyyymmdd_hhmm}.log
    
    Args:
        file_path: 文件路径
    
    Returns:
        设备名（如果能提取）
    """
    filename = Path(file_path).stem
    
    # 尝试从文件名提取（下划线分隔）
    if '_' in filename:
        parts = filename.split('_')
        return parts[0]
    
    # 返回文件名本身
    return filename


if __name__ == "__main__":
    # 测试编码探测
    print("=== 文件读取测试 ===")
    
    # 创建测试文件
    test_file = "/tmp/test_log.txt"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("""<Huawei>display lldp neighbor brief
Local Intf    Exptime  Neighbor Dev            Neighbor Intf
GE1/6/0/21    101      Ruijie                  Te0/52

[Huawei]display interface description
Interface                      PHY   Protocol  Description
GigabitEthernet1/6/0/21        up    up        To Building A
""")
    
    # 测试编码探测
    encoding = detect_encoding(test_file)
    print(f"✓ 探测编码: {encoding}")
    
    # 测试读取
    content = read_file(test_file)
    print(f"✓ 读取内容长度: {len(content)} 字符")
    
    # 测试哈希
    file_hash = calculate_file_hash(test_file)
    print(f"✓ 文件哈希: {file_hash[:16]}...")
    
    # 测试命令块分割
    blocks = split_command_blocks(content)
    print(f"\n✓ 分割为 {len(blocks)} 个命令块:")
    for cmd, output in blocks:
        print(f"  - {cmd}")
        print(f"    输出长度: {len(output)} 字符")
    
    # 测试设备名提取
    device_name = extract_device_name_from_file("/data/Core_CSS_20231228.log")
    print(f"\n✓ 从文件名提取设备: {device_name}")
