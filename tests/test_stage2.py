# tests/test_stage2_refactored.py
from skills import get_skill_by_name, AVAILABLE_SKILLS
from utils.logger import logger


def main():
    logger.info("🚀 启动阶段 2 (重构版)：Skill 架构测试")

    # 1. 列出所有可用技能
    logger.info(f"📦 已加载技能数量：{len(AVAILABLE_SKILLS)}")
    for skill in AVAILABLE_SKILLS:
        logger.info(f"   - 技能名：{skill.name}")
        logger.info(f"     描述：{skill.description[:50]}...")

    # 2. 获取 "get_market_data" 技能
    try:
        skill = get_skill_by_name("get_market_data")
        logger.info(f"✅ 成功找到技能：{skill.name}")

        # 3. 模拟 Agent 调用 (查询平安银行最近 5 天数据)
        logger.info("📡 模拟调用：获取 000001 历史数据...")
        result = skill.execute(
            symbol="000001",
            data_type="history",
            # 不传日期，测试默认逻辑
        )

        if "error" in result:
            logger.error(f"❌ 技能执行报错：{result['error']}")
        else:
            logger.info(f"✅ 技能执行成功！")
            logger.info(f"   数据条数：{result['count']}")
            logger.info(f"   保存路径：{result['file_path']}")
            logger.info(f"   数据预览：{result['preview']}")

        # 4. 模拟调用实时价格
        logger.info("⚡ 模拟调用：获取 000001 实时价格...")
        price_result = skill.execute(symbol="000001", data_type="realtime")
        logger.info(f"💰 实时价格结果：{price_result}")

        logger.info("✨ 阶段 2 (重构版) 测试成功！Skill 架构运行正常。")

    except Exception as e:
        logger.error(f"❌ 测试失败：{e}", exc_info=True)


if __name__ == "__main__":
    main()