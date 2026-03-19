# tests/test_stage1.py
from config.settings import settings
from utils.logger import logger


def main():
    logger.info("🚀 正在启动阶段 1 测试...")

    # 1. 测试配置读取
    logger.debug(f"项目名称: {settings.PROJECT_NAME}")
    logger.debug(f"环境: {settings.ENVIRONMENT}")

    # 2. 测试路径解析
    logger.info("📂 检查关键路径...")
    paths = {
        "外部数据目录": settings.DATA_EXTERNAL_DIR,
        "市场数据子目录": settings.MARKET_DATA_DIR,
        "运行时数据库": settings.DB_PATH,
        "报告输出目录": settings.REPORTS_DIR,
        "日志文件": settings.LOGS_DIR / "app.log"
    }

    for name, path in paths.items():
        if path.exists():
            logger.info(f"✅ {name}: {path} (存在)")
        else:
            logger.error(f"❌ {name}: {path} (缺失! 检查 ensure_directories)")

    # 3. 测试日志写入
    logger.warning("⚠️ 这是一条测试警告日志，请检查 data_runtime/logs/app.log 是否包含此内容。")
    logger.info("✨ 阶段 1 测试完成！基础设施已就绪。")


if __name__ == "__main__":
    main()