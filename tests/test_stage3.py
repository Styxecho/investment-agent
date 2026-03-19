# test_flow.py (在项目根目录运行)
from skills.market_data.service import market_data_service

# 测试 1: 获取历史数据 (第一次会调 API 并存库)
print("--- 测试历史数据 ---")
df = market_data_service.get_daily_data("000001", "20231001", "20231010")
if df is not None:
    print(df.head())
else:
    print("无数据")

# 测试 2: 再次获取 (应该命中缓存)
print("\n--- 再次获取 (应命中缓存) ---")
df2 = market_data_service.get_daily_data("000001", "20231001", "20231010")

# # 测试 3: 获取实时数据
# print("\n--- 测试实时数据 ---")
# realtime = market_data_service.get_realtime_data("000001")
# print(realtime)