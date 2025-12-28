#!/usr/bin/env python3
"""
CLI 主入口
使用 Click 实现统一的命令行接口
"""
import click
from pathlib import Path

# 设置日志
from topo.utils.logging_config import setup_logging
setup_logging()


@click.group()
@click.option('--database', '-d', default='topo.db', help='数据库文件路径')
@click.pass_context
def cli(ctx, database):
    """GCC 核心交换机拓扑自动化工具"""
    ctx.ensure_object(dict)
    ctx.obj['database'] = database


@cli.command()
@click.argument('log_file', type=click.Path(exists=True))
@click.option('--device', '-n', help='设备名称（默认从文件名提取）')
@click.option('--force', '-f', is_flag=True, help='强制重新导入（忽略哈希检查）')
@click.pass_context
def import_log(ctx, log_file, device, force):
    """
    导入华为交换机日志文件
    
    示例:
        topo import data/raw/Core_CSS_20231228.log
        topo import data/raw/Core_CSS_20231228.log --device Core
        topo import data/raw/Core_CSS_20231228.log --force
    """
    from topo.parser import LogParser
    
    db_path = ctx.obj['database']
    parser = LogParser(db_path)
    
    click.echo(f"正在导入日志文件: {log_file}")
    
    try:
        result = parser.import_log_file(log_file, device_name=device, force=force)
        
        if result['status'] == 'skipped':
            click.secho(f"✓ 文件已导入过，跳过（哈希: {result['hash'][:8]}）", fg='yellow')
            click.echo(f"  使用 --force 选项可强制重新导入")
        else:
            click.secho(f"✓ 导入成功！", fg='green')
            click.echo(f"  设备名: {result['device_name']}")
            click.echo(f"  LLDP 邻居: {result['lldp_count']} 条")
            click.echo(f"  Trunk 配置: {result['trunk_count']} 个")
            click.echo(f"  接口配置: {result['interface_count']} 个")
            click.echo(f"  STP Blocked: {result['stp_blocked_count']} 个")
            click.echo(f"  链路: {result['link_count']} 条")
            
            if result.get('anomalies'):
                click.echo(f"\n检测到异常:")
                for anomaly in result['anomalies']:
                    severity_color = 'red' if anomaly['severity'] == 'error' else 'yellow'
                    click.secho(
                        f"  [{anomaly['severity'].upper()}] {anomaly['type']}: {anomaly.get('detail', '')}",
                        fg=severity_color
                    )
    
    except Exception as e:
        click.secho(f"✗ 导入失败: {e}", fg='red', err=True)
        raise click.Abort()


@cli.command()
@click.option('--anomalies', '-a', is_flag=True, help='仅显示有异常的设备')
@click.pass_context
def list_devices(ctx, anomalies):
    """
    列出所有设备
    
    示例:
        topo list
        topo list --anomalies
    """
    from topo.db.dao import TopoDAO
    
    db_path = ctx.obj['database']
    
    with TopoDAO(db_path) as dao:
        devices = dao.devices.list_all()
        
        if not devices:
            click.echo("数据库中没有设备")
            return
        
        click.echo(f"共 {len(devices)} 个设备:\n")
        
        for dev in devices:
            # 获取异常信息
            dev_anomalies = dao.anomalies.get_by_device(dev['id'])
            
            if anomalies and not dev_anomalies:
                continue
            
            # 设备基本信息
            name_color = 'red' if dev_anomalies else 'green'
            click.secho(f"• {dev['name']}", fg=name_color, bold=True)
            
            if dev['mgmt_ip']:
                click.echo(f"  管理IP: {dev['mgmt_ip']}")
            if dev['model']:
                click.echo(f"  型号: {dev['model']}")
            
            # 统计链路数量
            links = dao.links.get_by_device(dev['name'])
            click.echo(f"  链路: {len(links)} 条")
            
            # 显示异常
            if dev_anomalies:
                click.echo(f"  异常: {len(dev_anomalies)} 个")
                for anomaly in dev_anomalies[:3]:  # 最多显示3个
                    severity_color = 'red' if anomaly['severity'] == 'error' else 'yellow'
                    click.secho(
                        f"    - [{anomaly['severity']}] {anomaly['type']}",
                        fg=severity_color
                    )
                if len(dev_anomalies) > 3:
                    click.echo(f"    ... 还有 {len(dev_anomalies) - 3} 个异常")
            
            click.echo()


@cli.command()
@click.argument('device')
@click.option('--format', '-f', type=click.Choice(['mermaid', 'markdown', 'pdf-graphviz', 'pdf-mermaid', 'dot']), 
              default='mermaid', help='输出格式')
@click.option('--output', '-o', help='输出文件路径（默认: <device>_topology.<ext>）')
@click.option('--max-links', type=int, default=50, help='最大物理链路数量（防止图过大）')
@click.pass_context
def export(ctx, device, format, output, max_links):
    """
    导出设备拓扑图
    
    示例:
        topo export Core
        topo export Core --format mermaid -o outputs/core.mmd
        topo export Core --format markdown
        topo export Core --format pdf-graphviz -o outputs/core.pdf
        topo export Core --format dot
    """
    from topo.db.dao import TopoDAO
    from topo.exporter.mermaid import MermaidExporter
    from topo.exporter.pdf import PDFExporter
    
    db_path = ctx.obj['database']
    
    # 检查设备是否存在
    with TopoDAO(db_path) as dao:
        dev = dao.devices.get_by_name(device)
        if not dev:
            click.secho(f"✗ 设备 '{device}' 不存在", fg='red', err=True)
            raise click.Abort()
    
    # 根据格式选择导出器
    if format in ['mermaid', 'markdown']:
        dao = TopoDAO(db_path)
        exporter = MermaidExporter(dao)
        
        # 确定输出路径
        if output is None:
            ext = 'md' if format == 'markdown' else 'mmd'
            output = f"{device}_topology.{ext}"
        
        click.echo(f"正在导出 Mermaid 拓扑图...")
        exporter.export_device_topology(
            device,
            output_file=output,
            max_phy_links=max_links
        )
        
        click.secho(f"✓ 已导出: {output}", fg='green')
        
        # 显示文件大小
        size = Path(output).stat().st_size
        click.echo(f"  文件大小: {size} 字节")
        
        dao.close()
    
    elif format in ['pdf-graphviz', 'pdf-mermaid']:
        pdf_exporter = PDFExporter(db_path)
        
        # 确定输出路径
        if output is None:
            output = f"{device}_topology.pdf"
        
        # 选择转换方法
        method = 'graphviz' if format == 'pdf-graphviz' else 'mermaid'
        
        click.echo(f"正在导出 PDF 拓扑图（使用 {method}）...")
        
        try:
            pdf_exporter.export_device_topology_pdf(
                device,
                output_path=output,
                max_phy_links=max_links,
                method=method
            )
            
            click.secho(f"✓ 已导出: {output}", fg='green')
            
            # 显示文件大小
            size = Path(output).stat().st_size
            click.echo(f"  文件大小: {size / 1024:.1f} KB")
        
        except RuntimeError as e:
            click.secho(f"✗ {e}", fg='red', err=True)
            raise click.Abort()
    
    elif format == 'dot':
        pdf_exporter = PDFExporter(db_path)
        
        # 确定输出路径
        if output is None:
            output = f"{device}_topology.dot"
        
        click.echo(f"正在生成 Graphviz DOT 文件...")
        pdf_exporter._generate_dot_file(device, Path(output), max_links)
        
        click.secho(f"✓ 已导出: {output}", fg='green')
        
        # 显示文件大小
        size = Path(output).stat().st_size
        click.echo(f"  文件大小: {size} 字节")


@cli.command()
@click.argument('device')
@click.argument('src_if')
@click.argument('dst_device')
@click.argument('dst_if')
@click.argument('confidence', type=click.Choice(['trusted', 'suspect', 'ignore']))
@click.pass_context
def mark(ctx, device, src_if, dst_device, dst_if, confidence):
    """
    标记链路的可信度
    
    示例:
        topo mark Core GigabitEthernet1/6/0/21 Ruijie TenGigabitEthernet0/52 trusted
        topo mark Problem GigabitEthernet1/0/1 Switch-A TenGigabitEthernet0/1 suspect
        topo mark Core GigabitEthernet1/0/1 Unknown - ignore
    """
    from topo.db.dao import TopoDAO
    
    db_path = ctx.obj['database']
    
    with TopoDAO(db_path) as dao:
        # 检查链路是否存在
        links = dao.links.get_by_device(device)
        link_found = any(
            l['src_device'] == device and l['src_if'] == src_if and
            l['dst_device'] == dst_device and l['dst_if'] == dst_if
            for l in links
        )
        
        if not link_found:
            click.secho(f"✗ 链路不存在: {device} {src_if} → {dst_device} {dst_if}", fg='red', err=True)
            raise click.Abort()
        
        # 更新可信度
        dao.links.update_confidence(device, src_if, dst_device, dst_if, confidence)
        
        click.secho(f"✓ 已更新链路可信度为: {confidence}", fg='green')
        click.echo(f"  {device} {src_if} → {dst_device} {dst_if}")


@cli.command()
@click.option('--severity', '-s', type=click.Choice(['warning', 'error']), help='按严重级别过滤')
@click.pass_context
def anomalies(ctx, severity):
    """
    列出所有检测到的异常
    
    示例:
        topo anomalies
        topo anomalies --severity error
    """
    from topo.db.dao import TopoDAO
    
    db_path = ctx.obj['database']
    
    with TopoDAO(db_path) as dao:
        all_anomalies = dao.anomalies.list_all(severity=severity)
        
        if not all_anomalies:
            click.echo("未检测到异常")
            return
        
        click.echo(f"共检测到 {len(all_anomalies)} 个异常:\n")
        
        for anomaly in all_anomalies:
            # 获取设备名
            device = dao.devices.get_by_name(anomaly['device_id'])  # 这里需要修正
            device_name = device['name'] if device else f"ID:{anomaly['device_id']}"
            
            severity_color = 'red' if anomaly['severity'] == 'error' else 'yellow'
            
            click.secho(
                f"[{anomaly['severity'].upper()}] {anomaly['type']}",
                fg=severity_color,
                bold=True
            )
            click.echo(f"  设备: {device_name}")
            click.echo(f"  时间: {anomaly['created_at']}")
            
            if anomaly['detail_json']:
                import json
                detail = json.loads(anomaly['detail_json'])
                click.echo(f"  详情: {json.dumps(detail, ensure_ascii=False, indent=4)}")
            
            click.echo()


@cli.command()
@click.pass_context
def history(ctx):
    """
    查看导入历史记录
    
    示例:
        topo history
    """
    from topo.db.dao import TopoDAO
    
    db_path = ctx.obj['database']
    
    with TopoDAO(db_path) as dao:
        imports = dao.imports.list_recent(limit=20)
        
        if not imports:
            click.echo("无导入记录")
            return
        
        click.echo(f"最近 {len(imports)} 次导入:\n")
        
        for imp in imports:
            click.secho(f"• {imp['device_name']}", fg='cyan', bold=True)
            click.echo(f"  文件: {imp['source_file']}")
            click.echo(f"  时间: {imp['imported_at']}")
            click.echo(f"  哈希: {imp['hash'][:16]}...")
            click.echo()


if __name__ == '__main__':
    cli(obj={})
