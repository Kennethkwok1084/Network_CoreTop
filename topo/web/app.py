#!/usr/bin/env python3
"""
Flask Web 应用
提供可视化界面查看拓扑、设备和异常
"""
from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import json
import tempfile
import os

from topo.db.dao import TopoDAO
from topo.exporter.mermaid import MermaidExporter
from topo.rules.detector import AnomalyDetector


def create_app(db_path="topo.db"):
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config['DATABASE'] = db_path
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    @app.route('/')
    def index():
        """首页 - 设备列表"""
        with TopoDAO(app.config['DATABASE']) as dao:
            devices = dao.devices.list_all()
            
            # 为每个设备添加统计信息
            for device in devices:
                links = dao.links.get_by_device(device['name'])
                anomalies = dao.anomalies.get_by_device(device['id'])
                device['link_count'] = len(links)
                device['anomaly_count'] = len(anomalies)
        
        return render_template('index.html', devices=devices)
    
    @app.route('/device/<device_name>')
    def device_detail(device_name):
        """设备详情页"""
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                return "设备不存在", 404
            
            # 获取链路
            links = dao.links.get_by_device(device_name)
            
            # 获取异常
            anomalies = dao.anomalies.get_by_device(device['id'])
            
            # 生成 Mermaid 图
            exporter = MermaidExporter(dao)
            mermaid_code = exporter.export_device_topology(
                device_name,
                output_file=None,  # 返回内容而不是保存
                max_phy_links=50
            )
        
        return render_template(
            'device_detail.html',
            device=device,
            links=links,
            anomalies=anomalies,
            mermaid_code=mermaid_code
        )
    
    @app.route('/anomalies')
    def anomalies():
        """异常列表页"""
        severity = request.args.get('severity', None)
        
        with TopoDAO(app.config['DATABASE']) as dao:
            all_anomalies = dao.anomalies.list_all(severity=severity)
            
            # 为每个异常添加设备名
            devices_cache = {}
            for anomaly in all_anomalies:
                dev_id = anomaly['device_id']
                if dev_id not in devices_cache:
                    # 这里需要通过ID查找设备，暂时使用名称
                    devices = dao.devices.list_all()
                    for d in devices:
                        devices_cache[d['id']] = d['name']
                
                anomaly['device_name'] = devices_cache.get(dev_id, f"ID:{dev_id}")
                
                # 解析 JSON 详情
                if anomaly['detail_json']:
                    anomaly['detail'] = json.loads(anomaly['detail_json'])
                else:
                    anomaly['detail'] = {}
        
        return render_template('anomalies.html', anomalies=all_anomalies, severity=severity)
    
    @app.route('/api/device/<device_name>/topology')
    def api_device_topology(device_name):
        """API: 获取设备拓扑 Mermaid 代码"""
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                return jsonify({'error': '设备不存在'}), 404
            
            exporter = MermaidExporter(dao)
            mermaid_code = exporter.export_device_topology(
                device_name,
                output_file=None,
                max_phy_links=int(request.args.get('max_links', 50))
            )
        
        return jsonify({'mermaid': mermaid_code})
    
    @app.route('/api/device/<device_name>/export/<format>')
    def api_device_export(device_name, format):
        """API: 导出设备拓扑"""
        if format not in ['mermaid', 'dot', 'pdf']:
            return jsonify({'error': '不支持的格式'}), 400
        
        with TopoDAO(app.config['DATABASE']) as dao:
            device = dao.devices.get_by_name(device_name)
            if not device:
                return jsonify({'error': '设备不存在'}), 404
            
            if format == 'mermaid':
                exporter = MermaidExporter(dao)
                content = exporter.export_device_topology(
                    device_name,
                    output_file=None,
                    max_phy_links=50
                )
                
                return content, 200, {
                    'Content-Type': 'text/plain; charset=utf-8',
                    'Content-Disposition': f'attachment; filename={device_name}_topology.mmd'
                }
            
            elif format == 'dot':
                from topo.exporter.pdf import PDFExporter
                pdf_exporter = PDFExporter(app.config['DATABASE'])
                
                # 生成临时文件
                fd, temp_path = tempfile.mkstemp(suffix='.dot')
                os.close(fd)
                
                try:
                    pdf_exporter._generate_dot_file(device_name, Path(temp_path), 50)
                    return send_file(
                        temp_path,
                        as_attachment=True,
                        download_name=f'{device_name}_topology.dot',
                        mimetype='text/vnd.graphviz'
                    )
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
    
    @app.route('/api/link/mark', methods=['POST'])
    def api_mark_link():
        """API: 标记链路可信度"""
        data = request.json
        
        required = ['device', 'src_if', 'dst_device', 'dst_if', 'confidence']
        if not all(k in data for k in required):
            return jsonify({'error': '缺少必需参数'}), 400
        
        if data['confidence'] not in ['trusted', 'suspect', 'ignore']:
            return jsonify({'error': '无效的可信度值'}), 400
        
        with TopoDAO(app.config['DATABASE']) as dao:
            dao.links.update_confidence(
                data['device'],
                data['src_if'],
                data['dst_device'],
                data['dst_if'],
                data['confidence']
            )
        
        return jsonify({'success': True})
    
    @app.route('/api/detect')
    def api_detect():
        """API: 运行异常检测"""
        with TopoDAO(app.config['DATABASE']) as dao:
            devices = dao.devices.get_all()
            detector = AnomalyDetector(dao)
            total = 0
            for device in devices:
                anomalies = detector.detect_all(device['id'])
                total += len(anomalies)
        
        return jsonify({
            'success': True,
            'count': total
        })
    
    return app


def main():
    """命令行启动"""
    import argparse
    
    parser = argparse.ArgumentParser(description='启动 Web 服务器')
    parser.add_argument('-d', '--database', default='topo.db', help='数据库路径')
    parser.add_argument('-p', '--port', type=int, default=5000, help='端口号')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    app = create_app(args.database)
    
    print(f"🚀 Web 服务器启动: http://{args.host}:{args.port}")
    print(f"📁 数据库: {args.database}")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
