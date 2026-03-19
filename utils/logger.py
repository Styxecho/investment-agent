import logging
import sys
from pathlib import Path
from config.settings import settings


def setup_logger(name: str = "investment_agent") -> logging.Logger:
    """
    配置并返回一个 logger 实例。
    日志将同时输出到：
    1. 控制台 (Console)
    2. 文件 (data_runtime/logs/app.log)
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 开发环境设为 DEBUG，生产环境可改为 INFO

    # 防止重复添加 handler (在多次导入时常见)
    if logger.handlers:
        return logger

    # 1. 创建格式器
    # 格式：[时间] [级别] [模块名] 消息
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 2. 控制台 Handler (高亮显示 ERROR 和 WARNING)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 3. 文件 Handler (记录所有 DEBUG 信息)
    # 确保日志目录存在 (虽然 settings 已经创建了，但双重保险)
    log_file = settings.LOGS_DIR / "app.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 创建一个默认 logger 供其他模块直接导入使用
logger = setup_logger()