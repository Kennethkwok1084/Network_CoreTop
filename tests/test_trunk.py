"""
测试 Trunk 解析器
"""
import pytest
from topo.parser.trunk import parse_trunks


class TestParseTrunks:
    """测试 Eth-Trunk 解析"""
    
    def test_parse_basic_trunk(self):
        """测试基本 Trunk 输出"""
        log_content = """
<Core>display eth-trunk
Eth-Trunk1's state information is:
WorkingMode: LACP      Hash arithmetic: According to SIP-XOR-DIP     
Least Active-linknumber: 1  Max Bandwidth-affected-linknumber: 8       
Operate status: up     Number Of Up Port In Trunk: 2                  
--------------------------------------------------------------------------------
PortName                      Status      Weight 
GigabitEthernet1/0/1          Up          1      
GigabitEthernet1/0/2          Up          1      

Eth-Trunk2's state information is:
WorkingMode: LACP      Hash arithmetic: According to SIP-XOR-DIP     
Operate status: down   Number Of Up Port In Trunk: 0                  
--------------------------------------------------------------------------------
PortName                      Status      Weight 
XGigabitEthernet1/0/10        Down        1      
"""
        
        result = parse_trunks(log_content)
        
        assert len(result) == 2
        
        # 检查 Trunk1
        trunk1 = result[0]
        assert trunk1['trunk_id'] == '1'
        assert trunk1['operate_status'] == 'up'
        assert len(trunk1['members']) == 2
        assert trunk1['members'][0] == 'GigabitEthernet1/0/1'
        assert trunk1['members'][1] == 'GigabitEthernet1/0/2'
        
        # 检查 Trunk2
        trunk2 = result[1]
        assert trunk2['trunk_id'] == '2'
        assert trunk2['operate_status'] == 'down'
        assert len(trunk2['members']) == 1
        assert trunk2['members'][0] == 'XGigabitEthernet1/0/10'
    
    def test_parse_empty_trunk(self):
        """测试空 Trunk"""
        log_content = """
<Core>display eth-trunk
Eth-Trunk10's state information is:
WorkingMode: LACP      
Operate status: down   Number Of Up Port In Trunk: 0                  
--------------------------------------------------------------------------------
PortName                      Status      Weight 
"""
        
        result = parse_trunks(log_content)
        assert len(result) == 1
        assert result[0]['trunk_id'] == '10'
        assert result[0]['members'] == []
    
    def test_parse_no_trunks(self):
        """测试无 Trunk 配置"""
        log_content = """
<Core>display eth-trunk
"""
        assert parse_trunks(log_content) == []
    
    def test_parse_multiple_trunks(self):
        """测试多个 Trunk"""
        log_content = """
Eth-Trunk1's state information is:
Operate status: up     
PortName                      Status      Weight 
GE1/0/1                       Up          1      

Eth-Trunk2's state information is:
Operate status: up     
PortName                      Status      Weight 
GE1/0/2                       Up          1      
GE1/0/3                       Up          1      

Eth-Trunk3's state information is:
Operate status: down   
PortName                      Status      Weight 
"""
        
        result = parse_trunks(log_content)
        assert len(result) == 3
        assert result[0]['trunk_id'] == '1'
        assert result[1]['trunk_id'] == '2'
        assert len(result[1]['members']) == 2
        assert result[2]['trunk_id'] == '3'
        assert result[2]['members'] == []
