import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

DB_PATH = "data_runtime/investments.db"
# 配置文件名，支持 .csv 或 .xlsx
CONFIG_EXCEL = "holdings.xlsx"
CONFIG_CSV = "holdings.csv"


def load_portfolio_config() -> Dict:
    """
    智能加载持仓配置：优先读取 Excel，若无则读取 CSV
    返回格式: {'portfolio': {code: shares}, 'cost_basis': {code: price}, 'names': {code: name}}
    """
    df = None
    source_file = ""

    # 1. 尝试读取 Excel
    if os.path.exists(CONFIG_EXCEL):
        try:
            df = pd.read_excel(CONFIG_EXCEL)
            source_file = CONFIG_EXCEL
        except Exception as e:
            print(f"⚠️ 读取 {CONFIG_EXCEL} 失败: {e}")

    # 2. 如果 Excel 不存在或失败，尝试读取 CSV
    if df is None and os.path.exists(CONFIG_CSV):
        try:
            df = pd.read_csv(CONFIG_CSV)
            source_file = CONFIG_CSV
        except Exception as e:
            print(f"⚠️ 读取 {CONFIG_CSV} 失败: {e}")

    if df is None:
        print(f"❌ 未找到配置文件 ({CONFIG_EXCEL} 或 {CONFIG_CSV})，请创建其中一个。")
        return {"portfolio": {}, "cost_basis": {}, "names": {}}

    print(f"✅ 已从 {source_file} 加载 {len(df)} 条持仓记录")

    # 数据清洗
    # 确保 code 是字符串，去除前后空格，防止 "513050 " 这种问题
    df['code'] = df['code'].astype(str).str.strip()

    # 确保数值列正确，填充空值为 0
    df['shares'] = pd.to_numeric(df['shares'], errors='coerce').fillna(0)
    df['cost_price'] = pd.to_numeric(df.get('cost_price', 0), errors='coerce').fillna(0)

    # 构建字典
    portfolio = dict(zip(df['code'], df['shares']))
    cost_basis = dict(zip(df['code'], df['cost_price']))

    # 处理名称 (如果有 name 列)
    names = {}
    if 'name' in df.columns:
        # 填充空名称为 "未知"
        df['name'] = df['name'].fillna("未知").astype(str)
        names = dict(zip(df['code'], df['name']))

    return {
        "portfolio": portfolio,
        "cost_basis": cost_basis,
        "names": names
    }


def get_market_data_range(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从数据库获取指定日期范围的价格数据"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT date, close_price 
        FROM daily_prices 
        WHERE code = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(code, start_date, end_date))
    conn.close()
    return df


def calculate_portfolio_metrics(target_date: str = None) -> Dict:
    """
    计算投资组合核心指标
    """
    config = load_portfolio_config()
    holdings = config.get("portfolio", {})
    cost_basis = config.get("cost_basis", {})
    names = config.get("names", {})

    if not holdings:
        return {"error": "持仓为空"}

    # 确定目标日期 (默认为数据库中最新日期)
    if not target_date:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM daily_prices")
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            target_date = result[0]
        else:
            return {"error": "数据库无价格数据，请先运行 data_fetch.py"}

    total_market_value = 0.0
    total_daily_profit = 0.0
    total_cost = 0.0
    details = []

    print(f"\n📊 投资组合日报 ({target_date})")
    print("-" * 85)
    # 格式化表头
    header = f"{'代码':<10} {'名称':<15} {'份额':>10} {'现价':>8} {'市值':>12} {'日涨跌%':>10} {'日盈亏':>12} {'总盈亏':>12}"
    print(header)
    print("-" * 85)

    for code, shares in holdings.items():
        if shares <= 0:
            continue

        fund_name = names.get(code, "未知")
        avg_cost = cost_basis.get(code, 0)

        # 1. 获取最新可用价格 (目标日期或之前最近一天)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, close_price FROM daily_prices 
            WHERE code = ? AND date <= ? 
            ORDER BY date DESC LIMIT 1
        """, (code, target_date))
        row_current = cursor.fetchone()

        if not row_current:
            print(f"⚠️ 跳过 {code}: 无价格数据")
            continue

        current_date, current_price = row_current

        # 2. 获取前一个交易日价格 (用于计算日盈亏)
        cursor.execute("""
            SELECT date, close_price FROM daily_prices 
            WHERE code = ? AND date < ? 
            ORDER BY date DESC LIMIT 1
        """, (code, current_date))
        row_prev = cursor.fetchone()
        conn.close()

        prev_price = row_prev[1] if row_prev else current_price

        # 3. 计算各项指标
        market_value = shares * current_price
        daily_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0
        daily_profit = shares * (current_price - prev_price)

        # 总盈亏计算
        total_invested = shares * avg_cost
        total_profit_val = shares * (current_price - avg_cost) if avg_cost > 0 else 0

        # 累加总计
        total_market_value += market_value
        total_daily_profit += daily_profit
        total_cost += total_invested

        # 打印单行详情
        print(f"{code:<10} {fund_name:<15} {shares:>10,.0f} {current_price:>8.3f} "
              f"{market_value:>12,.2f} {daily_change_pct:>9.2f}% {daily_profit:>12,.2f} {total_profit_val:>12,.2f}")

        details.append({
            "code": code,
            "name": fund_name,
            "shares": shares,
            "current_price": current_price,
            "market_value": market_value,
            "daily_change_pct": daily_change_pct,
            "daily_profit": daily_profit,
            "total_profit": total_profit_val,
            "cost_basis": avg_cost
        })

    print("-" * 85)
    total_return_pct = ((total_market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    daily_return_pct = (total_daily_profit / (total_market_value - total_daily_profit) * 100) if (
                                                                                                             total_market_value - total_daily_profit) > 0 else 0

    print(
        f"{'总计':<27} {total_market_value:>12,.2f}  {daily_return_pct:>9.2f}% {total_daily_profit:>12,.2f} {total_market_value - total_cost:>12,.2f}")
    print(f"💰 总投入成本: {total_cost:,.2f} | 累计收益率: {total_return_pct:.2f}%")

    return {
        "date": target_date,
        "total_market_value": total_market_value,
        "total_daily_profit": total_daily_profit,
        "total_cost": total_cost,
        "total_profit": total_market_value - total_cost,
        "total_return_pct": total_return_pct,
        "details": details
    }


if __name__ == "__main__":
    # 执行计算
    result = calculate_portfolio_metrics()

    if "error" in result:
        print(f"\n❌ 计算中断: {result['error']}")
    else:
        print("\n✅ 组合计算完成！您可以将此结果发送给大模型生成分析报告。")