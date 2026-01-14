"""
Mermaid 拓扑图导出器
根据 develop.md 第 6.1 节实现
从 SQLite 读取 links，生成 Mermaid graph LR 格式
支持 Trunk 折叠和可信度样式
"""

import logging
from typing import List, Dict, Set, Optional
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class MermaidExporter:
    """Mermaid 拓扑图导出器"""
    
    def __init__(self, dao):
        """
        Args:
            dao: TopoDAO 实例
        """
        self.dao = dao
        self.nodes = set()  # 所有节点
        self.links = []  # 所有链路
    
    def export_device_topology(
        self, 
        device_name: str,
        output_file: str = None,
        max_phy_links: int = 30,
        include_confidence: List[str] = None
    ) -> str:
        """
        导出设备的拓扑图
        
        Args:
            device_name: 设备名称
            output_file: 输出文件路径（None 则仅返回内容）
            max_phy_links: 最大物理链路数（防止图过大）
            include_confidence: 包含的链路可信度列表（默认：trusted, suspect）
        
        Returns:
            Mermaid 代码字符串
        """
        if include_confidence is None:
            include_confidence = ['trusted', 'suspect']
        
        # 查询链路
        links = self.dao.links.get_by_device(device_name, confidence_filter=include_confidence)
        
        if not links:
            logger.warning(f"设备 {device_name} 没有找到链路")
            return ""
        
        logger.info(f"找到 {len(links)} 条链路")
        
        # 按链路类型分组
        trunk_links = []
        phy_links = []
        
        for link in links:
            if link['link_type'] == 'trunk':
                trunk_links.append(link)
            else:
                phy_links.append(link)
        
        # 限制物理链路数量
        if len(phy_links) > max_phy_links:
            logger.warning(f"物理链路数 {len(phy_links)} 超过限制 {max_phy_links}，将截断")
            phy_links = phy_links[:max_phy_links]
        
        # 生成 Mermaid 代码
        mermaid_code = self._generate_mermaid(
            trunk_links + phy_links,
            device_name
        )
        
        # 保存到文件
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(mermaid_code, encoding='utf-8')
            logger.info(f"✓ 拓扑图已保存到: {output_file}")
        
        return mermaid_code
    
    def _generate_mermaid(self, links: List[Dict], center_device: str = None) -> str:
        """
        生成 Mermaid 代码
        
        Args:
            links: 链路列表
            center_device: 中心设备名（用于突出显示）
        
        Returns:
            Mermaid 代码字符串
        """
        lines = []
        
        # 使用TB(从上到下)布局，更清晰
        lines.append("graph TB")
        lines.append("")
        
        # 收集节点和链路
        nodes = set()
        styled_links = []
        
        for link in links:
            src = self._sanitize_node_id(link['src_device'])
            dst = self._sanitize_node_id(link['dst_device'])
            nodes.add(src)
            nodes.add(dst)
            
            # 简化链路标签 - 只显示接口简称
            def simplify_interface(ifname):
                """简化接口名称"""
                if not ifname:
                    return ""
                # GigabitEthernet1/6/0/3 -> Gi1/6/0/3
                ifname = ifname.replace("GigabitEthernet", "Gi")
                ifname = ifname.replace("TenGigabitEthernet", "10Gi")
                ifname = ifname.replace("Ten-GigabitEthernet", "10Gi")
                ifname = ifname.replace("XGigabitEthernet", "XGi")
                # 如果是数字或MAC地址，保留
                return ifname
            
            src_if = simplify_interface(link['src_if'])
            dst_if = simplify_interface(link['dst_if'])
            
            # 构建简洁标签
            if link['link_type'] == 'trunk':
                label = f"{src_if}⇄{dst_if}"
            else:
                label = f"{src_if}"  # 只显示本地接口
            
            # 根据可信度选择箭头样式
            confidence = link.get('confidence', 'trusted')
            if confidence == 'suspect':
                arrow = "-.->|"  # 虚线
                link_class = "suspect"
            elif confidence == 'ignore':
                continue  # 跳过忽略的链路
            else:
                if link['link_type'] == 'trunk':
                    arrow = "==>|"  # 粗线
                    link_class = "trunk"
                else:
                    arrow = "-->|"  # 普通箭头
                    link_class = "trusted"
            
            styled_links.append({
                'src': src,
                'dst': dst,
                'arrow': arrow,
                'label': label,
                'class': link_class
            })
        
        # 定义节点（添加图标和样式）
        lines.append("    %% 节点定义")
        
        # 中心设备特殊样式
        center_id = self._sanitize_node_id(center_device) if center_device else None
        
        for node_id in sorted(nodes):
            display_name = node_id.replace('_', ' ')
            
            if node_id == center_id:
                # 中心核心交换机 - 使用六边形
                lines.append(f"    {node_id}{{{{{display_name}}}}}:::center")
            elif node_id == 'Unknown':
                # 未知设备 - 使用虚线框
                lines.append(f"    {node_id}[{display_name}]:::unknown")
            elif 'FW' in node_id or 'USG' in node_id:
                # 防火墙 - 使用菱形
                lines.append(f"    {node_id}{{{display_name}}}:::firewall")
            else:
                # 普通设备 - 圆角矩形
                lines.append(f"    {node_id}({display_name}):::normal")
        
        lines.append("")
        
        # 定义链路
        lines.append("    %% 链路定义")
        for link in styled_links:
            lines.append(
                f"    {link['src']} {link['arrow']}{link['label']}| {link['dst']}"
            )
        
        lines.append("")
        
        # 定义样式类 - 更丰富的配色方案
        lines.append("    %% 样式定义")
        lines.append("    classDef center fill:#1890ff,stroke:#0050b3,stroke-width:4px,color:#fff")
        lines.append("    classDef firewall fill:#faad14,stroke:#d48806,stroke-width:3px,color:#000")
        lines.append("    classDef normal fill:#f0f5ff,stroke:#69c0ff,stroke-width:2px,color:#000")
        lines.append("    classDef unknown fill:#f5f5f5,stroke:#d9d9d9,stroke-width:2px,stroke-dasharray: 5 5,color:#8c8c8c")
        lines.append("    classDef suspect fill:#fff1f0,stroke:#ff4d4f,stroke-width:2px")
        lines.append("    classDef trunk stroke:#52c41a,stroke-width:4px")
        
        return "\n".join(lines)
        return "\n".join(lines)
    
    def _sanitize_node_id(self, name: str) -> str:
        """
        清理节点 ID（Mermaid 不支持某些特殊字符）
        
        Args:
            name: 原始名称
        
        Returns:
            清理后的 ID
        """
        import re
        
        # 处理空名称
        if not name or not name.strip():
            return 'Unknown'
        
        # 只保留字母、数字和下划线，其他字符(包括#、&、-、.、空格等)替换为下划线
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        
        # 去除连续下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # 去除首尾下划线
        sanitized = sanitized.strip('_')
        
        # 确保以字母开头
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'Device_' + sanitized
        
        return sanitized or 'Unknown'
    
    def export_multi_device_topology(
        self,
        device_names: List[str],
        output_file: str = None,
        max_depth: int = 2
    ) -> str:
        """
        导出多设备（多跳）拓扑图
        
        Args:
            device_names: 设备名称列表
            output_file: 输出文件路径
            max_depth: 最大跳数（BFS 深度）
        
        Returns:
            Mermaid 代码字符串
        """
        # 使用 BFS 扩展到指定深度
        all_devices = set(device_names)
        visited = set()
        current_layer = set(device_names)
        
        for depth in range(max_depth):
            next_layer = set()
            
            for device in current_layer:
                if device in visited:
                    continue
                visited.add(device)
                
                # 查询邻居
                links = self.dao.links.get_by_device(device)
                for link in links:
                    if link['src_device'] == device:
                        neighbor = link['dst_device']
                    else:
                        neighbor = link['src_device']
                    
                    if neighbor not in visited:
                        next_layer.add(neighbor)
                        all_devices.add(neighbor)
            
            current_layer = next_layer
            if not current_layer:
                break
        
        logger.info(f"多跳拓扑包含 {len(all_devices)} 个设备")
        
        # 收集所有相关链路
        all_links = []
        for device in all_devices:
            links = self.dao.links.get_by_device(device)
            for link in links:
                # 避免重复（双向链路）
                if link not in all_links:
                    all_links.append(link)
        
        # 生成 Mermaid
        mermaid_code = self._generate_mermaid(all_links, center_device=device_names[0])
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(mermaid_code, encoding='utf-8')
            logger.info(f"✓ 多跳拓扑图已保存到: {output_file}")
        
        return mermaid_code


def export_topology(
    db_path: str,
    device_name: str,
    output_file: str = None,
    format: str = "mermaid"
) -> str:
    """
    导出拓扑图（便捷函数）
    
    Args:
        db_path: 数据库路径
        device_name: 设备名称
        output_file: 输出文件路径
        format: 输出格式（mermaid/markdown）
    
    Returns:
        拓扑图内容
    """
    from ..db.dao import TopoDAO
    
    with TopoDAO(db_path) as dao:
        exporter = MermaidExporter(dao)
        content = exporter.export_device_topology(device_name, output_file)
        
        # 如果是 markdown 格式，添加标题
        if format == "markdown":
            title = f"# {device_name} 网络拓扑\n\n"
            content = title + content
            
            if output_file and not output_file.endswith('.md'):
                output_file = output_file.replace('.mmd', '.md')
            
            if output_file:
                Path(output_file).write_text(content, encoding='utf-8')
        
        return content


if __name__ == "__main__":
    import sys
    import argparse
    
    # 允许独立运行
    try:
        from ..db.dao import TopoDAO
        from ..utils.logging_config import setup_logging
    except ImportError:
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
        from topo.db.dao import TopoDAO
        from topo.utils.logging_config import setup_logging
    
    setup_logging(level="INFO")
    
    parser = argparse.ArgumentParser(description="导出 Mermaid 拓扑图")
    parser.add_argument('device', help='设备名称')
    parser.add_argument('--db', default='topo.db', help='数据库路径')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--format', choices=['mermaid', 'markdown'], default='mermaid', help='输出格式')
    parser.add_argument('--max-links', type=int, default=30, help='最大物理链路数')
    
    args = parser.parse_args()
    
    # 默认输出文件
    if not args.output:
        suffix = '.md' if args.format == 'markdown' else '.mmd'
        args.output = f"outputs/{args.device}_topology{suffix}"
    
    content = export_topology(
        args.db,
        args.device,
        args.output,
        args.format
    )
    
    print(f"\n拓扑图预览:")
    print("="*60)
    print(content)
    print("="*60)
