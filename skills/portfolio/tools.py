# skills/portfolio/tools.py
"""
定义供大模型调用的组合分析工具。
遵循 Function Calling / MCP 标准格式。
"""
from typing import Optional, Dict, Any
import json
from datetime import datetime
from config.settings import settings

from skills.portfolio.loader import HoldingsLoader
from skills.portfolio.calculator import PortfolioService
from utils.logger import logger

from langchain_core.tools import tool


DEFAULT_HOLDINGS_PATH = str(settings.HOLDINGS_TEMPLATE)


def get_portfolio_pnl_tool_definition() -> Dict:
    """
    返回工具的定义描述 (JSON Schema)，用于注册到大模型系统中。
    """
    return {
        "type": "function",
        "function": {
            "name": "calculate_portfolio_pnl",
            "description": "计算用户当前持仓在指定日期的损益情况（盈亏金额、收益率、总市值）。如果不指定日期，默认计算最新可用数据（通常为今日）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "查询日期，格式为 'YYYYMMDD' (例如 '20240317')。如果用户未提及具体日期，此参数可为空或省略，系统将自动使用最新日期。",
                        "pattern": "^\\d{8}$"
                    },
                    "holdings_file_path": {
                        "type": "string",
                        "description": "持仓文件的路径。默认为系统配置的默认模板路径。",
                        "default": DEFAULT_HOLDINGS_PATH
                    }
                },
                "required": []  # 所有参数均为可选
            }
        }
    }


def execute_calculate_portfolio_pnl(arguments: Dict[str, Any]) -> str:
    """
    执行工具的具体逻辑。
    接收大模型解析后的参数，运行计算，并返回格式化的文本结果（供模型阅读）。
    """
    target_date = arguments.get("target_date")
    # 如果模型没传路径，或者传了 None，则使用配置文件中的默认路径
    file_path = arguments.get("holdings_file_path") or DEFAULT_HOLDINGS_PATH

    logger.info(f"工具调用：calculate_portfolio_pnl, 日期={target_date}, 文件={file_path}")

    try:
        # 1. 初始化服务
        # holdings_loader 接受 string 或 Path，这里传入 string 最稳妥
        loader = HoldingsLoader(file_path)
        service = PortfolioService(loader)

        # 2. 执行计算
        df = service.calculate_pnl(target_date=target_date)

        if df.empty:
            return "未找到任何持仓数据或指定日期无市场数据。"

        # 3. 格式化输出为 Markdown 表格
        display_cols = ['code', 'name', 'current_price', 'volume', 'market_value', 'profit_loss', 'profit_ratio(%)']
        available_cols = [c for c in display_cols if c in df.columns]

        # 检查 to_markdown 依赖 (tabulate 库)
        try:
            markdown_table = df[available_cols].to_markdown(index=False, float_format="%.2f")
        except ImportError:
            logger.warning("tabulate 库未安装，使用普通文本表格代替。建议安装: pip install tabulate")
            markdown_table = df[available_cols].to_string(index=False, float_format="%.2f")

        # 计算汇总
        total_mv = df['market_value'].sum()
        total_pl = df['profit_loss'].sum()
        total_cost = (df['cost_price'] * df['volume']).sum()
        total_ratio = (total_pl / total_cost * 100) if total_cost > 0 else 0

        summary_text = (
            f"\n\n**组合汇总 ({target_date or '最新日期'}):**\n"
            f"- **总市值**: {total_mv:,.2f} 元\n"
            f"- **总盈亏**: {total_pl:,.2f} 元\n"
            f"- **总收益率**: {total_ratio:.2f}%"
        )

        result_text = f"以下是您的持仓损益详情:\n\n{markdown_table}{summary_text}"
        return result_text

    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        return f"错误：找不到持仓文件 '{file_path}'。请确认文件是否存在于项目根目录下。"
    except Exception as e:
        logger.error(f"计算失败: {e}", exc_info=True)
        return f"错误：计算过程中发生异常 - {str(e)}"


@tool
def calculate_portfolio_pnl(target_date: Optional[str] = None, holdings_file_path: Optional[str] = None) -> str:
    """
    计算用户当前持仓在指定日期的损益情况（盈亏金额、收益率、总市值）。

    Args:
        target_date: 查询日期，格式为 'YYYYMMDD' (例如 '20240317')。如果不传，默认计算最新数据。
        holdings_file_path: 持仓文件的路径。默认为系统配置路径。

    Returns:
        格式化的 Markdown 字符串，包含持仓明细表格和汇总数据。
    """
    # 构造参数字典，复用现有的 execute 函数
    args = {
        "target_date": target_date,
        "holdings_file_path": holdings_file_path
    }
    # 过滤掉 None 值，避免干扰默认逻辑 (可选，视 execute 函数内部逻辑而定，通常 get 方法能处理 None)
    # 但为了稳妥，我们直接传给 execute，因为它内部用了 .get()

    return execute_calculate_portfolio_pnl(args)


# 确保导出
__all__ = ["calculate_portfolio_pnl", "get_portfolio_pnl_tool_definition", "execute_calculate_portfolio_pnl"]
# ================= 新增部分结束 =================
