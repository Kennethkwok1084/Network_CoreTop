"""
测试数据库 DAO 层
"""
import pytest
import tempfile
import os
from topo.db.dao import TopoDAO


class TestDeviceDAO:
    """测试设备 DAO"""
    
    @pytest.fixture
    def dao(self):
        """创建临时数据库"""
        # 使用临时文件
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        dao = TopoDAO(path)
        yield dao
        
        # 清理
        dao.close()
        os.unlink(path)
    
    def test_upsert_device(self, dao):
        """测试插入设备"""
        dev_id = dao.devices.upsert("Core", mgmt_ip="192.168.1.1", model="S12700")
        assert dev_id is not None
        assert dev_id > 0
        
        # 查询设备
        device = dao.devices.get_by_name("Core")
        assert device is not None
        assert device['name'] == "Core"
        assert device['mgmt_ip'] == "192.168.1.1"
        assert device['model'] == "S12700"
    
    def test_upsert_duplicate_device(self, dao):
        """测试重复插入（应该更新）"""
        # 第一次插入
        dev_id1 = dao.devices.upsert("Core", mgmt_ip="192.168.1.1")
        
        # 第二次插入同名设备（应该更新）
        dev_id2 = dao.devices.upsert("Core", mgmt_ip="192.168.1.100", model="S12700")
        
        assert dev_id1 == dev_id2
        
        # 验证更新成功
        device = dao.devices.get_by_name("Core")
        assert device['mgmt_ip'] == "192.168.1.100"
        assert device['model'] == "S12700"
    
    def test_list_all_devices(self, dao):
        """测试列出所有设备"""
        dao.devices.upsert("Core1")
        dao.devices.upsert("Core2")
        dao.devices.upsert("Access1")
        
        devices = dao.devices.list_all()
        assert len(devices) == 3
        
        names = [d['name'] for d in devices]
        assert "Core1" in names
        assert "Core2" in names
        assert "Access1" in names


class TestLinkDAO:
    """测试链路 DAO"""
    
    @pytest.fixture
    def dao(self):
        """创建临时数据库"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        dao = TopoDAO(path)
        yield dao
        
        dao.close()
        os.unlink(path)
    
    def test_upsert_link(self, dao):
        """测试插入链路"""
        dao.links.upsert(
            "Core", "GigabitEthernet1/0/1",
            "Access", "GigabitEthernet0/0/1",
            link_type="phy",
            confidence="trusted"
        )
        dao.commit()
        
        links = dao.links.get_by_device("Core")
        assert len(links) == 1
        assert links[0]['src_device'] == "Core"
        assert links[0]['dst_device'] == "Access"
    
    def test_upsert_duplicate_link(self, dao):
        """测试重复插入链路（应该更新）"""
        # 第一次插入
        dao.links.upsert(
            "Core", "GE1/0/1", "Access", "GE0/0/1",
            confidence="suspect"
        )
        dao.commit()
        
        # 第二次插入（应该更新可信度）
        dao.links.upsert(
            "Core", "GE1/0/1", "Access", "GE0/0/1",
            confidence="trusted"
        )
        dao.commit()
        
        links = dao.links.get_by_device("Core")
        assert len(links) == 1
        assert links[0]['confidence'] == "trusted"
    
    def test_update_confidence(self, dao):
        """测试更新链路可信度"""
        dao.links.upsert("Core", "GE1/0/1", "Access", "GE0/0/1")
        dao.commit()
        
        dao.links.update_confidence("Core", "GE1/0/1", "Access", "GE0/0/1", "suspect")
        dao.commit()
        
        links = dao.links.get_by_device("Core")
        assert links[0]['confidence'] == "suspect"
    
    def test_get_by_device(self, dao):
        """测试按设备查询链路"""
        dao.links.upsert("Core", "GE1/0/1", "Access1", "GE0/0/1")
        dao.links.upsert("Core", "GE1/0/2", "Access2", "GE0/0/1")
        dao.links.upsert("Access1", "GE0/0/2", "Server1", "eth0")
        dao.commit()
        
        # 查询 Core 相关链路
        core_links = dao.links.get_by_device("Core")
        assert len(core_links) == 2
        
        # 查询 Access1 相关链路（包括作为源和目的）
        access_links = dao.links.get_by_device("Access1")
        assert len(access_links) == 2  # 一条作为 dst，一条作为 src


class TestImportDAO:
    """测试导入记录 DAO"""
    
    @pytest.fixture
    def dao(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        dao = TopoDAO(path)
        yield dao
        
        dao.close()
        os.unlink(path)
    
    def test_check_hash_exists(self, dao):
        """测试检查哈希是否存在"""
        test_hash = "abc123def456"
        
        # 首次检查应该不存在
        assert dao.imports.check_hash_exists(test_hash) is False
        
        # 记录导入
        dao.imports.record_import("Core", "test.log", test_hash)
        dao.commit()
        
        # 再次检查应该存在
        assert dao.imports.check_hash_exists(test_hash) is True
    
    def test_record_import(self, dao):
        """测试记录导入"""
        dao.imports.record_import("Core", "core.log", "hash1")
        dao.imports.record_import("Access", "access.log", "hash2")
        dao.commit()
        
        recent = dao.imports.list_recent(limit=10)
        assert len(recent) == 2
        
        # 检查两条记录都存在
        device_names = {r['device_name'] for r in recent}
        assert "Core" in device_names
        assert "Access" in device_names
