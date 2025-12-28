"""
测试 normalize 模块
"""
import pytest
from topo.parser.normalize import normalize_ifname


class TestNormalizeInterfaceName:
    """测试接口名标准化"""
    
    def test_gigabit_ethernet_short(self):
        """测试 GE 缩写"""
        assert normalize_ifname("GE1/0/1") == "GigabitEthernet1/0/1"
        assert normalize_ifname("GE1/6/0/21") == "GigabitEthernet1/6/0/21"
    
    def test_xgigabit_ethernet_short(self):
        """测试 XGE 缩写"""
        assert normalize_ifname("XGE1/0/1") == "XGigabitEthernet1/0/1"
        assert normalize_ifname("XGE2/0/10") == "XGigabitEthernet2/0/10"
    
    def test_eth_trunk(self):
        """测试 Eth-Trunk"""
        assert normalize_ifname("Eth-Trunk1") == "Eth-Trunk1"
        assert normalize_ifname("Eth-Trunk100") == "Eth-Trunk100"
    
    def test_already_normalized(self):
        """测试已标准化的名称"""
        assert normalize_ifname("GigabitEthernet1/0/1") == "GigabitEthernet1/0/1"
        assert normalize_ifname("XGigabitEthernet1/0/1") == "XGigabitEthernet1/0/1"
