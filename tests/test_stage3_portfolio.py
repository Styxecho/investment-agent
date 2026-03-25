# tests/test_stage3_portfolio.py
import os
import sys
import pandas as pd

# 动态添加项目根目录到路径，确保 import 正常
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from archive.loader import HoldingsLoader
from skills.portfolio.calculator import PortfolioService


def run_test():
    print("🚀 开始阶段 3 测试：组合损益计算")

    csv_path = os.path.join(project_root, 'holdings_template.csv')

    if not os.path.exists(csv_path):
        print(f"❌ 错误：未找到持仓文件 {csv_path}")
        return

    try:
        loader = HoldingsLoader(csv_path)
        calculator = PortfolioService(loader)

        # 测试：不传日期，默认今天；或者您可以传一个具体的 '20240317' 测试历史数据
        df = calculator.calculate_pnl(target_date=None)

        if df is not None and not df.empty:
            print("\n📊 组合明细表:")
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1000)
            # 浮点数格式化显示
            print(df.to_string(index=False, float_format="%.2f"))
            print("\n✅ 阶段 3 测试成功！组合引擎已就绪。")
        else:
            print("\n⚠️ 计算结果为空，可能是日期无数据或 CSV 为空。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_test()