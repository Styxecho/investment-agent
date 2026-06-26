# scripts/fetch_history_data.py
"""
批量拉取历史行情数据
按年份逐步拉取，避免触发 iFinD 限制
"""
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_external.db.engine import SessionLocal
from data_external.db.models import StockDaily, FundDaily
from data_external.db.repositories import MarketDataRepository, FundRepository
from skills.market_data.provider.ifind_provider import ifind_provider
from config.enums import AssetType
from utils.logger import logger


# 组合 A + B 的所有资产（去重）
ALL_ASSETS = [
    # 组合 A
    {"code": "510300.SH", "name": "沪深300ETF华泰柏瑞", "type": AssetType.ETF},
    {"code": "510500.SH", "name": "中证500ETF南方", "type": AssetType.ETF},
    {"code": "512100.SH", "name": "中证1000ETF南方", "type": AssetType.ETF},
    {"code": "159531.SZ", "name": "中证2000ETF南方", "type": AssetType.ETF},
    {"code": "588000.SH", "name": "科创50ETF华夏", "type": AssetType.ETF},
    {"code": "159920.SZ", "name": "恒生ETF华夏", "type": AssetType.ETF},
    {"code": "513010.SH", "name": "恒生科技ETF易方达", "type": AssetType.ETF},
    {"code": "513100.SH", "name": "纳指ETF国泰", "type": AssetType.ETF},
    {"code": "513500.SH", "name": "标普500ETF博时", "type": AssetType.ETF},
    {"code": "518880.SH", "name": "黄金ETF华安", "type": AssetType.ETF},
    {"code": "511260.SH", "name": "十年国债ETF国泰", "type": AssetType.ETF},
    {"code": "159972.SZ", "name": "5年地方债ETF鹏华", "type": AssetType.ETF},
    {"code": "511360.SH", "name": "短融ETF海富通", "type": AssetType.ETF},
    # 组合 B 独有的
    {"code": "510880.SH", "name": "红利ETF华泰柏瑞", "type": AssetType.ETF},
    {"code": "512890.SH", "name": "红利低波ETF华泰柏瑞", "type": AssetType.ETF},
    {"code": "159201.SZ", "name": "自由现金流ETF华夏", "type": AssetType.ETF},
    {"code": "561580.SH", "name": "央企红利ETF华泰柏瑞", "type": AssetType.ETF},
    {"code": "513920.SH", "name": "港股通央企红利ETF华安", "type": AssetType.ETF},
    {"code": "159545.SZ", "name": "恒生红利低波ETF易方达", "type": AssetType.ETF},
]


def clear_existing_data(asset_code: str, start_date: str, end_date: str):
    """清理指定资产在日期范围内的历史数据"""
    asset_type = AssetType.from_code_suffix(asset_code)
    
    db = SessionLocal()
    try:
        if asset_type == AssetType.FUND:
            db.query(FundDaily).filter(
                FundDaily.fund_code == asset_code,
                FundDaily.trade_date >= datetime.strptime(start_date, "%Y%m%d").date(),
                FundDaily.trade_date <= datetime.strptime(end_date, "%Y%m%d").date()
            ).delete(synchronize_session=False)
        else:
            db.query(StockDaily).filter(
                StockDaily.symbol == asset_code,
                StockDaily.trade_date >= datetime.strptime(start_date, "%Y%m%d").date(),
                StockDaily.trade_date <= datetime.strptime(end_date, "%Y%m%d").date()
            ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"[FetchHistory] 已清理 {asset_code} {start_date}~{end_date} 的历史数据")
    except Exception as e:
        db.rollback()
        logger.error(f"[FetchHistory] 清理数据失败: {e}")
    finally:
        db.close()


def fetch_and_save_asset(asset: dict, year: int):
    """拉取单只资产一年的数据并保存"""
    code = asset["code"]
    name = asset["name"]
    asset_type = asset["type"]
    
    start_date = f"{year}0101"
    end_date = f"{year}1231"
    if year == 2026:
        end_date = "20260417"  # 当前日期
    
    logger.info(f"[FetchHistory] 开始拉取 {name} ({code}) {year}年数据...")
    
    try:
        # 1. 清理旧数据
        clear_existing_data(code, start_date, end_date)
        
        # 2. 拉取新数据
        if asset_type == AssetType.FUND:
            # 基金使用 fetch_fund_nav
            df = ifind_provider.fetch_fund_nav(code, start_date, end_date)
            if df is not None and not df.empty:
                FundRepository.save_fund_nav(df, code)
                logger.info(f"[FetchHistory] ✅ {name} ({code}) 成功保存 {len(df)} 条基金净值记录")
            else:
                logger.warning(f"[FetchHistory] ⚠️ {name} ({code}) 无数据返回")
        else:
            # 股票/ETF 使用 fetch_history（现在会自动拉取复权因子）
            df = ifind_provider.fetch_history(code, start_date, end_date, asset_type)
            if df is not None and not df.empty:
                MarketDataRepository.save_daily_data(df, code)
                logger.info(f"[FetchHistory] ✅ {name} ({code}) 成功保存 {len(df)} 条行情记录")
            else:
                logger.warning(f"[FetchHistory] ⚠️ {name} ({code}) 无数据返回")
                
    except Exception as e:
        logger.error(f"[FetchHistory] ❌ {name} ({code}) 拉取失败: {e}")


def fetch_year_data(year: int):
    """拉取指定年份的所有资产数据"""
    logger.info(f"\n{'='*60}")
    logger.info(f"[FetchHistory] 开始拉取 {year} 年数据")
    logger.info(f"{'='*60}\n")
    
    # 确保 iFinD 已连接
    if not ifind_provider.connect():
        logger.error("[FetchHistory] iFinD 连接失败，无法拉取数据")
        return
    
    total = len(ALL_ASSETS)
    success = 0
    
    for i, asset in enumerate(ALL_ASSETS, 1):
        logger.info(f"\n[FetchHistory] 进度: {i}/{total}")
        fetch_and_save_asset(asset, year)
        success += 1
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[FetchHistory] {year}年数据拉取完成: {success}/{total} 只资产")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量拉取历史行情数据")
    parser.add_argument("--year", type=int, default=2026, help="要拉取的年份")
    args = parser.parse_args()
    
    fetch_year_data(args.year)
