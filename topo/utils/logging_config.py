"""
日志配置模块
统一配置所有模块的日志输出
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    level: str = "INFO",
    log_file: str = None,
    console: bool = True,
    format_string: str = None
):
    """
    配置全局日志
    
    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径（None 则不写文件）
        console: 是否输出到控制台
        format_string: 自定义日志格式
    """
    if format_string is None:
        format_string = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    
    # 设置根日志级别
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[]
    )
    
    logger = logging.getLogger()
    logger.handlers.clear()  # 清除已有 handler
    
    # 控制台输出
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件输出
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"日志文件: {log_file}")
    
    # 设置第三方库日志级别（避免过多噪音）
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    return logger


def get_default_log_file() -> str:
    """
    获取默认日志文件路径
    
    Returns:
        日志文件路径
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    return str(log_dir / f"topo_{timestamp}.log")


if __name__ == "__main__":
    # 测试日志配置
    logger = setup_logging(level="DEBUG", log_file=get_default_log_file())
    
    logger.debug("这是调试信息")
    logger.info("这是一般信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    
    # 测试子模块日志
    module_logger = logging.getLogger('topo.parser.file_reader')
    module_logger.info("子模块日志测试")
