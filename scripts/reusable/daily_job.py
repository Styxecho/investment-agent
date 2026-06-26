# scripts/daily_job.py
"""
投资组合每日快照定时任务

用途：
- 每日自动计算投资组合表现
- 将结果保存到 portfolio_snapshot 表中
- 支持手动执行，也支持被操作系统定时任务调用

执行方式：
    python scripts/daily_job.py

退出码：
    0 - 成功（或今日非交易日，正常跳过）
    1 - 执行失败
"""
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from utils.trade_calendar import TradeCalendarService
from skills.base import SkillContext
from skills.portfolio.skill import PortfolioSkill
from skills.portfolio.snapshot.snapshot_skill import SnapshotSkill
from agents.tools import _load_holdings_from_csv, _get_current_trade_date


def run_daily_job():
    """执行每日快照任务"""
    # 1. 获取今天日期
    today_str = _get_current_trade_date()
    today_dt = datetime.strptime(today_str, "%Y%m%d")
    
    logger.info(f"[DailyJob] 启动每日快照任务：{today_str}")
    
    # 2. 判断是否为交易日
    calendar = TradeCalendarService()
    if not calendar.is_trading_day(today_str):
        logger.info(f"[DailyJob] {today_str} 非交易日，跳过执行。")
        return 0
    
    # 3. 读取持仓
    holdings = _load_holdings_from_csv()
    if not holdings:
        logger.error("[DailyJob] 未找到持仓数据，任务终止。")
        return 1
    
    logger.info(f"[DailyJob] 读取到 {len(holdings)} 条持仓记录")
    
    # 4. 构造上下文
    context = SkillContext(
        target_date=today_str,
        extra_params={"holdings": holdings}
    )
    
    # 5. 计算组合表现（PortfolioSkill 内部会自动调用 GetMarketDataSkill 获取行情）
    portfolio_skill = PortfolioSkill()
    portfolio_result = portfolio_skill.execute(context)
    
    if portfolio_result.meta.status == "failed":
        logger.error(f"[DailyJob] 组合计算失败：{portfolio_result.meta.message}")
        return 1
    
    logger.info(f"[DailyJob] 组合计算完成：{portfolio_result.summary_hint}")
    
    # 6. 保存快照
    snapshot_skill = SnapshotSkill()
    snapshot_context = SkillContext(
        target_date=today_str,
        extra_params={
            "portfolio_time_series": portfolio_result.data,
            "portfolio_id": "default"
        }
    )
    
    snapshot_result = snapshot_skill.execute(snapshot_context)
    
    if snapshot_result.meta.status == "failed":
        logger.error(f"[DailyJob] 快照保存失败：{snapshot_result.meta.message}")
        return 1
    
    logger.info(f"[DailyJob] 任务完成：{snapshot_result.summary_hint}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = run_daily_job()
        sys.exit(exit_code)
    except Exception as e:
        logger.exception(f"[DailyJob] 未预期错误：{e}")
        sys.exit(1)
