#!/usr/bin/env python3
"""
Web UI 启动脚本
"""
import os
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# 使用虚拟环境 Python
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists():
    os.chdir(PROJECT_ROOT)
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), "-m", "topo.web.app"] + sys.argv[1:])
else:
    # 直接运行
    from topo.web.app import main
    main()
