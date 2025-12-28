"""
集成测试 - 端到端工作流
测试完整的导入 → 检测 → 导出流程
"""
import pytest
import tempfile
import os
from pathlib import Path
from topo.db.dao import TopoDAO
from topo.parser import LogParser
from topo.rules.detector import detect_all_anomalies
from topo.exporter.mermaid import MermaidExporter


class TestEndToEndWorkflow:
    """端到端工作流测试"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def sample_log(self, tmp_path):
        """创建示例日志文件"""
        log_content = """
<TestDevice>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
GE1/0/1        120         Switch-A                GE0/0/1          
GE1/0/2        115         Switch-B                GE0/0/1          

<TestDevice>display eth-trunk
Eth-Trunk1's state information is:
WorkingMode: LACP      
Operate status: up     Number Of Up Port In Trunk: 2                  
--------------------------------------------------------------------------------
PortName                      Status      Weight 
GigabitEthernet1/0/10         Up          1      
GigabitEthernet1/0/11         Up          1      

<TestDevice>display interface description
Interface                       PHY   Protocol  Description
GigabitEthernet1/0/1            up    up        To-Switch-A
GigabitEthernet1/0/2            up    up        To-Switch-B
Eth-Trunk1                      up    up        Uplink

<TestDevice>display stp brief
 MSTID  Port                        Role  STP State     Protection
   0    GigabitEthernet1/0/1        DESI  FORWARDING      NONE
   0    GigabitEthernet1/0/2        DESI  FORWARDING      NONE
"""
        log_file = tmp_path / "test.log"
        log_file.write_text(log_content, encoding='utf-8')
        return str(log_file)
    
    def test_full_workflow(self, temp_db, sample_log, tmp_path):
        """测试完整工作流"""
        # 1. 导入日志
        with TopoDAO(temp_db) as dao:
            parser = LogParser(dao)
            result = parser.import_log_file(sample_log, device_name="TestDevice")
            
            # 验证导入结果
            assert result['status'] == 'imported'
            assert result['device_name'] == 'TestDevice'
            assert result['lldp_count'] == 2
            assert result['trunk_count'] == 1
            assert result['interface_count'] >= 3
        
        # 2. 运行异常检测
        with TopoDAO(temp_db) as dao:
            anomalies = detect_all_anomalies(dao)
            
            # 应该没有异常（正常配置）
            # 注意：如果有异常，验证是否符合预期
        
        # 3. 导出 Mermaid
        output_file = tmp_path / "test_topology.mmd"
        with TopoDAO(temp_db) as dao:
            exporter = MermaidExporter(dao)
            exporter.export_device_topology(
                "TestDevice",
                output_file=str(output_file)
            )
        
        # 验证导出文件
        assert output_file.exists()
        content = output_file.read_text()
        assert "graph LR" in content
        assert "TestDevice" in content
        assert "Switch-A" in content
        assert "Switch-B" in content
    
    def test_incremental_import(self, temp_db, sample_log):
        """测试增量导入（重复导入应该被跳过）"""
        with TopoDAO(temp_db) as dao:
            parser = LogParser(dao)
            
            # 第一次导入
            result1 = parser.import_log_file(sample_log, device_name="TestDevice")
            assert result1['status'] == 'imported'
            file_hash = result1['hash']
            
            # 第二次导入同一文件（应该被跳过）
            result2 = parser.import_log_file(sample_log, device_name="TestDevice")
            assert result2['status'] == 'skipped'
            assert result2['hash'] == file_hash
            
            # 强制重新导入
            result3 = parser.import_log_file(sample_log, device_name="TestDevice", force=True)
            assert result3['status'] == 'imported'
    
    def test_anomaly_detection_loop(self, temp_db, tmp_path):
        """测试环路检测"""
        # 创建有环路的日志
        log_with_loop = """
<Problem>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
GE1/0/1        120         Switch-A                GE0/0/1          
GE1/0/1        115         Switch-B                GE0/0/1          
"""
        log_file = tmp_path / "problem.log"
        log_file.write_text(log_with_loop, encoding='utf-8')
        
        with TopoDAO(temp_db) as dao:
            parser = LogParser(dao)
            result = parser.import_log_file(str(log_file), device_name="Problem")
            
            # 应该检测到异常
            assert len(result.get('anomalies', [])) > 0
            
            # 验证是环路异常
            loop_anomaly = [a for a in result['anomalies'] if a['type'] == 'suspect_loop']
            assert len(loop_anomaly) > 0
