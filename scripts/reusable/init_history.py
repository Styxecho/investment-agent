# scripts/init_history.py
"""
投资组合历史数据初始化脚本

用途：
- 根据当前 holdings.csv 中的持仓，回溯计算指定日期范围内每个交易日的组合快照
- 逐步填充本地行情缓存，减少后续对 iFinD 的重复调用

执行方式：
    python scripts/init_history.py --start_date 20260101 --end_date 20260414

参数：
    --start_date: 开始日期（YYYYMMDD）
    --end_date:   结束日期（YYYYMMDD）

注意：
- 本脚本假设历史期间持仓结构与当前 holdings.csv 保持一致
- 实际执行中会利用已修复的缓存机制，行情数据会自动填充到本地 SQLite
- 若某日行情获取失败，会记录错误并继续处理后续日期
"""
import sys
import argparse
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
from agents.tools import _load_holdings_from_csv


def parse_args():
    parser = argparse.ArgumentParser(description="初始化投资组合历史快照数据")
    parser.add_argument("--start_date", required=True, help="开始日期 (YYYYMMDD)")
    parser.add_argument("--end_date", required=True, help="结束日期 (YYYYMMDD)")
    return parser.parse_args()


def run_history_init(start_date: str, end_date: str):
    """执行历史数据初始化"""
    logger.info(f"[InitHistory] 启动历史初始化：{start_date} ~ {end_date}")
    
    # 1. 读取持仓
    holdings = _load_holdings_from_csv()
    if not holdings:
        logger.error("[InitHistory] 未找到持仓数据，任务终止。")
        return 1
    
    logger.info(f"[InitHistory] 读取到 {len(holdings)} 条持仓记录")
    
    # 2. 获取交易日历
    calendar = TradeCalendarService()
    trading_days = calendar.get_trading_date_range(start_date, end_date)
    
    if not trading_days:
        logger.warning("[InitHistory] 指定范围内无交易日，任务结束。")
        return 0
    
    logger.info(f"[InitHistory] 共 {len(trading_days)} 个交易日需要处理")
    
    # 3. 初始化技能
    portfolio_skill = PortfolioSkill()
    snapshot_skill = SnapshotSkill()
    
    success_count = 0
    fail_count = 0
    
    for idx, trade_date in enumerate(trading_days, 1):
        logger.info(f"[InitHistory] 处理第 {idx}/{len(trading_days)} 个交易日：{trade_date}")
        
        try:
            # 3.1 计算组合（PortfolioSkill 内部自动获取行情）
            portfolio_context = SkillContext(
                target_date=trade_date,
                extra_params={"holdings": holdings}
            )
            portfolio_result = portfolio_skill.execute(portfolio_context)
            
            if portfolio_result.meta.status == "failed":
                logger.error(f"[InitHistory] {trade_date} 组合计算失败：{portfolio_result.meta.message}")
                fail_count += 1
                continue
            
            # 3.2 保存快照
            snapshot_context = SkillContext(
                target_date=trade_date,
                extra_params={
                    "portfolio_time_series": portfolio_result.data,
                    "portfolio_id": "default"
                }
            )
            snapshot_result = snapshot_skill.execute(snapshot_context)
            
            if snapshot_result.meta.status == "failed":
                logger.error(f"[InitHistory] {trade_date} 快照保存失败：{snapshot_result.meta.message}")
                fail_count += 1
                continue
            
            success_count += 1
            
            # 每 10 天输出一次进度
            if idx % 10 == 0 or idx == len(trading_days):
                logger.info(
                    f"[InitHistory] 进度：{idx}/{len(trading_days)} "
                    f"(成功 {success_count}，失败 {fail_count})"
                )
                
        except Exception as e:
            logger.exception(f"[InitHistory] {trade_date} 处理异常：{e}")
            fail_count += 1
            continue
    
    logger.info(
        f"[InitHistory] 任务完成。总计 {len(trading_days)} 个交易日，"
        f"成功 {success_count}，失败 {fail_count}。"
    )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    args = parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, "%Y%m%d")
        datetime.strptime(args.end_date, "%Y%m%d")
    except ValueError:
        logger.error("日期格式错误，应为 YYYYMMDD")
        sys.exit(1)
    
    if args.start_date > args.end_date:
        logger.error("开始日期不能晚于结束日期")
        sys.exit(1)
    
    try:
        exit_code = run_history_init(args.start_date, args.end_date)
        sys.exit(exit_code)
    except Exception as e:
        logger.exception(f"[InitHistory] 未预期错误：{e}")
        sys.exit(1)
