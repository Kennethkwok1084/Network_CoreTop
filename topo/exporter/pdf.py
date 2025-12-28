#!/usr/bin/env python3
"""
PDF 导出模块

支持两种导出路径：
1. Mermaid → SVG → PDF（推荐，需要 mmdc 命令）
2. Graphviz DOT → PDF（备选，需要 dot 命令）
"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .mermaid import MermaidExporter

logger = logging.getLogger(__name__)


class PDFExporter:
    """PDF 导出器"""
    
    def __init__(self, db_path: str = "topo.db"):
        """
        初始化导出器
        
        Args:
            db_path: 数据库文件路径
        """
        from topo.db.dao import TopoDAO
        
        self.db_path = db_path
        self.dao = TopoDAO(db_path)
        self.mermaid_exporter = MermaidExporter(self.dao)
        
        # 检测可用的转换工具
        self.has_mmdc = shutil.which('mmdc') is not None
        self.has_dot = shutil.which('dot') is not None
        
        if not self.has_mmdc and not self.has_dot:
            logger.warning(
                "未检测到 mmdc 或 dot 命令，PDF 导出功能不可用。\n"
                "安装方法：\n"
                "  - Mermaid CLI: npm install -g @mermaid-js/mermaid-cli\n"
                "  - Graphviz: sudo apt install graphviz 或 brew install graphviz"
            )
    
    def export_device_topology_pdf(
        self,
        device_name: str,
        output_path: Optional[str] = None,
        max_phy_links: int = 50,
        method: str = 'auto'
    ) -> str:
        """
        导出指定设备的拓扑到 PDF
        
        Args:
            device_name: 中心设备名
            output_path: 输出文件路径（None=自动生成）
            max_phy_links: 最大物理链路数量（防止图过大）
            method: 转换方法 ('auto', 'mermaid', 'graphviz')
        
        Returns:
            输出文件路径
        
        Raises:
            RuntimeError: 无可用的转换工具
        """
        # 自动选择方法
        if method == 'auto':
            if self.has_mmdc:
                method = 'mermaid'
            elif self.has_dot:
                method = 'graphviz'
            else:
                raise RuntimeError("未检测到 mmdc 或 dot 命令，无法生成 PDF")
        
        # 生成输出路径
        if output_path is None:
            output_path = f"{device_name}_topology.pdf"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 根据方法选择转换流程
        if method == 'mermaid':
            return self._export_via_mermaid(device_name, output_file, max_phy_links)
        elif method == 'graphviz':
            return self._export_via_graphviz(device_name, output_file, max_phy_links)
        else:
            raise ValueError(f"不支持的转换方法: {method}")
    
    def _export_via_mermaid(
        self,
        device_name: str,
        output_file: Path,
        max_phy_links: int
    ) -> str:
        """
        通过 Mermaid CLI 导出 PDF
        
        流程：Mermaid (.mmd) → SVG → PDF
        
        Args:
            device_name: 中心设备名
            output_file: 输出文件路径
            max_phy_links: 最大物理链路数量
        
        Returns:
            输出文件路径
        """
        if not self.has_mmdc:
            raise RuntimeError("未安装 mermaid-cli (mmdc)，请运行: npm install -g @mermaid-js/mermaid-cli")
        
        # 生成临时 Mermaid 文件
        temp_mmd = output_file.with_suffix('.mmd')
        self.mermaid_exporter.export_device_topology(
            device_name,
            output_path=str(temp_mmd),
            max_phy_links=max_phy_links
        )
        
        try:
            # 使用 mmdc 转换为 PDF
            logger.info(f"正在使用 mmdc 转换 {temp_mmd.name} → {output_file.name}...")
            cmd = [
                'mmdc',
                '-i', str(temp_mmd),
                '-o', str(output_file),
                '-t', 'neutral',  # 主题
                '-b', 'white',    # 背景色
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"mmdc 转换失败: {result.stderr}")
                raise RuntimeError(f"PDF 生成失败: {result.stderr}")
            
            logger.info(f"✓ 已生成 PDF: {output_file}")
            return str(output_file)
        
        finally:
            # 清理临时文件
            if temp_mmd.exists():
                temp_mmd.unlink()
    
    def _export_via_graphviz(
        self,
        device_name: str,
        output_file: Path,
        max_phy_links: int
    ) -> str:
        """
        通过 Graphviz 导出 PDF
        
        流程：DOT → PDF
        
        Args:
            device_name: 中心设备名
            output_file: 输出文件路径
            max_phy_links: 最大物理链路数量
        
        Returns:
            输出文件路径
        """
        if not self.has_dot:
            raise RuntimeError("未安装 Graphviz (dot)，请运行: sudo apt install graphviz 或 brew install graphviz")
        
        # 生成临时 DOT 文件
        temp_dot = output_file.with_suffix('.dot')
        self._generate_dot_file(device_name, temp_dot, max_phy_links)
        
        try:
            # 使用 dot 转换为 PDF
            logger.info(f"正在使用 dot 转换 {temp_dot.name} → {output_file.name}...")
            cmd = [
                'dot',
                '-Tpdf',
                str(temp_dot),
                '-o', str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"dot 转换失败: {result.stderr}")
                raise RuntimeError(f"PDF 生成失败: {result.stderr}")
            
            logger.info(f"✓ 已生成 PDF: {output_file}")
            return str(output_file)
        
        finally:
            # 清理临时文件
            if temp_dot.exists():
                temp_dot.unlink()
    
    def _generate_dot_file(
        self,
        device_name: str,
        output_file: Path,
        max_phy_links: int
    ):
        """
        生成 Graphviz DOT 格式文件
        
        Args:
            device_name: 中心设备名
            output_file: 输出文件路径
            max_phy_links: 最大物理链路数量
        """
        # 获取链路数据
        links = self.dao.links.get_by_device(device_name)
        
        # 限制物理链路数量
        phy_links = [l for l in links if l['link_type'] != 'trunk']
        if len(phy_links) > max_phy_links:
            logger.warning(
                f"设备 {device_name} 有 {len(phy_links)} 条物理链路，"
                f"超过限制 {max_phy_links}，已截断"
            )
            links = phy_links[:max_phy_links] + [l for l in links if l['link_type'] == 'trunk']
        
        # 生成 DOT 内容
        lines = [
            'digraph topology {',
            '  rankdir=LR;',
            '  node [shape=box, style=rounded];',
            ''
        ]
        
        # 收集所有节点
        nodes = {device_name}
        for link in links:
            dst = link['dst_device']
            # 处理空名称或特殊字符
            if not dst or not dst.strip() or set(dst.strip()) <= {'-', '_', ' ', '.'}:
                dst = 'Unknown'
            nodes.add(dst)
        
        # 定义节点样式
        for node in sorted(nodes):
            if node == device_name:
                lines.append(f'  "{node}" [style="rounded,filled", fillcolor=lightblue];')
            else:
                lines.append(f'  "{node}";')
        
        lines.append('')
        
        # 定义边
        for link in links:
            src = link['src_device']
            dst = link['dst_device']
            
            # 处理空名称
            if not dst or not dst.strip() or set(dst.strip()) <= {'-', '_', ' ', '.'}:
                dst = 'Unknown'
            
            src_if = link['src_if']
            dst_if = link['dst_if'] if link['dst_if'] else '?'
            
            # 标签
            label = f"{src_if} ↔ {dst_if}"
            
            # 样式
            style_attrs = []
            
            if link['confidence'] == 'trusted':
                style_attrs.append('style=solid')
            elif link['confidence'] == 'suspect':
                style_attrs.append('style=dashed')
                style_attrs.append('color=orange')
            elif link['confidence'] == 'ignore':
                continue  # 跳过忽略的链路
            
            if link['link_type'] == 'trunk':
                style_attrs.append('penwidth=2')
            
            style_str = ', '.join(style_attrs) if style_attrs else ''
            
            lines.append(f'  "{src}" -> "{dst}" [label="{label}", {style_str}];')
        
        lines.append('}')
        
        # 写入文件
        output_file.write_text('\n'.join(lines), encoding='utf-8')
        logger.info(f"已生成 DOT 文件: {output_file} ({len(links)} 条链路)")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='导出设备拓扑到 PDF')
    parser.add_argument('device', help='中心设备名')
    parser.add_argument(
        '-o', '--output',
        help='输出文件路径（默认：<device>_topology.pdf）'
    )
    parser.add_argument(
        '-d', '--database',
        default='topo.db',
        help='数据库路径（默认：topo.db）'
    )
    parser.add_argument(
        '-m', '--method',
        choices=['auto', 'mermaid', 'graphviz', 'dot-only'],
        default='auto',
        help='转换方法（默认：auto，dot-only 仅生成 .dot 文件）'
    )
    parser.add_argument(
        '--max-links',
        type=int,
        default=50,
        help='最大物理链路数量（默认：50）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    exporter = PDFExporter(args.database)
    
    # 处理 dot-only 模式
    if args.method == 'dot-only':
        output_dot = args.output or f"{args.device}_topology.dot"
        exporter._generate_dot_file(args.device, Path(output_dot), args.max_links)
        print(f"✓ 已生成 DOT 文件: {output_dot}")
        return
    
    try:
        output = exporter.export_device_topology_pdf(
            args.device,
            args.output,
            args.max_links,
            args.method
        )
        print(f"✓ 已生成 PDF: {output}")
    except Exception as e:
        logger.error(f"导出失败: {e}")
        import sys
        sys.exit(1)


if __name__ == '__main__':
    main()
