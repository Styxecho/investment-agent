# agents/tools.py
"""
将 Skills 封装为 LangChain Tools (方案 A - 手动封装)
支持从 CSV 文件自动读取持仓数据
"""
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

from skills.base import SkillContext, SkillResult
from skills.market_data.skill import get_market_data_skill
from skills.portfolio.skill import PortfolioSkill
from config.settings import settings
from utils.logger import logger


def _get_current_trade_date() -> str:
    """获取当前交易日（YYYYMMDD 格式）"""
    return datetime.now().strftime("%Y%m%d")


def _format_skill_result(result: SkillResult) -> str:
    """将 SkillResult 格式化为自然语言字符串"""
    if result.meta.status == "failed":
        return f"错误：{result.meta.message}"
    
    # 优先使用 summary_hint（预生成的自然语言摘要）
    if result.summary_hint:
        return result.summary_hint
    
    # 否则返回数据字典的字符串表示
    return str(result.data)


def _load_holdings_from_csv(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    从 CSV 文件加载持仓数据
    
    Args:
        file_path: CSV 文件路径，如果为 None 则使用默认配置
    
    Returns:
        持仓列表，每项包含：asset_code, asset_name, volume, cost_price, asset_type
    """
    # 确定文件路径
    if file_path:
        csv_path = Path(file_path)
    else:
        # 优先使用实际持仓文件，如果不存在则使用模板
        csv_path = settings.HOLDINGS_ACTIVE
        if not csv_path.exists():
            logger.info(f"实际持仓文件不存在，使用模板文件：{settings.HOLDINGS_TEMPLATE}")
            csv_path = settings.HOLDINGS_TEMPLATE
    
    if not csv_path.exists():
        logger.error(f"持仓文件不存在：{csv_path}")
        return []
    
    holdings = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 标准化字段名
                holding = {
                    'asset_code': row.get('code', '').strip(),
                    'asset_name': row.get('name', '').strip(),
                    'volume': float(row.get('volume', 0)),
                    'cost_price': float(row.get('cost_price', 0)),
                    'asset_type': row.get('asset_type', 'stock').strip().upper()
                }
                
                # 验证必要字段
                if holding['asset_code'] and holding['volume'] > 0 and holding['cost_price'] > 0:
                    holdings.append(holding)
                else:
                    logger.warning(f"跳过无效持仓行：{row}")
        
        logger.info(f"从 CSV 加载了 {len(holdings)} 条持仓记录")
        
    except Exception as e:
        logger.error(f"读取 CSV 文件失败：{e}")
        return []
    
    return holdings


@tool
def get_market_data(symbol: str, asset_type: str = "stock", start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    获取 A 股股票、ETF 或公募基金在特定日期或日期范围的行情数据/净值。
    
    Args:
        symbol: 股票代码。例如：'000001' (平安银行), '600519' (贵州茅台), '000001.SZ', '003956.OF'
        asset_type: 资产类型。'stock' (股票), 'etf' (ETF), 'fund' (基金)。默认为 'stock'
        start_date: 开始日期（YYYYMMDD）。可选，如果不提供则使用 end_date 或当前日期
        end_date: 结束日期（YYYYMMDD）。可选，如果不提供则使用 start_date 或当前日期
    
    Returns:
        格式化的字符串，包含收盘价、昨收价、涨跌幅等信息（股票/ETF），或单位净值序列（基金）
    """
    # 确定查询日期
    target_date = _get_current_trade_date()
    if end_date:
        target_date = end_date
    elif start_date:
        target_date = start_date
    
    context = SkillContext(
        target_date=target_date,
        extra_params={
            "symbol": symbol,
            "asset_type": asset_type,
            "start_date": start_date,
            "end_date": end_date
        }
    )
    
    result = get_market_data_skill.execute(context)
    return _format_skill_result(result)


@tool
def analyze_portfolio(holdings_file_path: Optional[str] = None, trade_date: Optional[str] = None) -> str:
    """
    分析投资组合的当日表现。
    自动从 CSV 文件读取持仓数据（默认使用 holdings.csv，如果不存在则使用 holdings_template.csv）。
    
    Args:
        holdings_file_path: 持仓 CSV 文件路径。可选，默认为系统配置的 holdings.csv 或 holdings_template.csv
        trade_date: 交易日期 (YYYYMMDD)。可选，默认为当前日期
    
    Returns:
        格式化的字符串，包含总市值、当日盈亏、收益率、个股贡献等信息
    """
    # 从 CSV 文件加载持仓
    holdings = _load_holdings_from_csv(holdings_file_path)
    
    if not holdings:
        return "错误：未找到持仓数据。请确保 holdings.csv 或 holdings_template.csv 文件存在且包含有效持仓记录。"
    
    logger.info(f"分析投资组合，持仓数量：{len(holdings)}")
    
    context = SkillContext(
        target_date=trade_date or _get_current_trade_date(),
        extra_params={
            "holdings": holdings
        }
    )
    
    portfolio_skill = PortfolioSkill()
    result = portfolio_skill.execute(context)
    return _format_skill_result(result)


# 导出工具列表
ALL_TOOLS = [get_market_data, analyze_portfolio]
