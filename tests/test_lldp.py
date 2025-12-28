"""
测试 LLDP 解析器
"""
import pytest
from topo.parser.lldp import parse_lldp_brief


class TestParseLLDP:
    """测试 LLDP 解析"""
    
    def test_parse_basic_lldp(self):
        """测试基本 LLDP 输出解析"""
        log_content = """
<Core>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
GE1/6/0/21     101         Ruijie                  Te0/52           
GE1/6/0/22     120         Huawei-Access-01        GE0/0/1          
XGE1/0/1       115         Core-CSS-Backup         XGE1/0/2         
"""
        
        result = parse_lldp_brief(log_content)
        
        assert len(result) == 3
        
        # 检查第一条记录
        assert result[0].local_if == 'GigabitEthernet1/6/0/21'
        assert result[0].neighbor_dev == 'Ruijie'
        assert result[0].neighbor_if == 'TenGigabitEthernet0/52'
        assert result[0].exptime == 101
        
        # 检查第二条记录
        assert result[1].local_if == 'GigabitEthernet1/6/0/22'
        assert result[1].neighbor_dev == 'Huawei-Access-01'
        assert result[1].neighbor_if == 'GigabitEthernet0/0/1'
        assert result[1].exptime == 120
    
    def test_parse_with_system_name(self):
        """测试带 system-name 的 LLDP 输出 - 跳过（功能未实现）"""
        pass
    
    def test_parse_empty_output(self):
        """测试空输出"""
        assert parse_lldp_brief("") == []
        assert parse_lldp_brief("display lldp neighbor brief") == []
    
    def test_parse_no_neighbors(self):
        """测试无邻居情况"""
        log_content = """
<Core>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
"""
        assert parse_lldp_brief(log_content) == []
    
    def test_parse_with_extra_whitespace(self):
        """测试带额外空格的情况"""
        log_content = """
<Core>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
  GE1/0/1      120         Device-A                  GE0/1          
"""
        result = parse_lldp_brief(log_content)
        assert len(result) == 1
        assert result[0].local_if == 'GigabitEthernet1/0/1'
        assert result[0].neighbor_dev == 'Device-A'
    
    def test_parse_dash_neighbor(self):
        """测试邻居为 - 的情况"""
        log_content = """
<Core>display lldp neighbor brief
Local Intf     Exptime(s)  Neighbor Dev            Neighbor Intf    
GE1/0/2        120         -                       -                
"""
        result = parse_lldp_brief(log_content)
        assert len(result) == 1
        assert result[0].neighbor_dev == '-'
        assert result[0].neighbor_if == '-'
