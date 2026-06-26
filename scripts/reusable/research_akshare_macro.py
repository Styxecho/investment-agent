#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调研akshare获取宏观数据的可行性
"""

import akshare as ak
import pandas as pd

print("=== AkShare 宏观数据可用性调研 ===")
print()

# 1. PMI数据
print("1. PMI数据:")
try:
    pmi_df = ak.macro_china_pmi_yearly()
    print(f"   成功! 数据条数: {len(pmi_df)}")
    print(f"   列名: {pmi_df.columns.tolist()}")
    print(f"   最新数据: {pmi_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 2. CPI数据
print("2. CPI数据:")
try:
    cpi_df = ak.macro_china_cpi_yearly()
    print(f"   成功! 数据条数: {len(cpi_df)}")
    print(f"   列名: {cpi_df.columns.tolist()}")
    print(f"   最新数据: {cpi_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 3. PPI数据
print("3. PPI数据:")
try:
    ppi_df = ak.macro_china_ppi_yearly()
    print(f"   成功! 数据条数: {len(ppi_df)}")
    print(f"   列名: {ppi_df.columns.tolist()}")
    print(f"   最新数据: {ppi_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 4. M2数据
print("4. M2数据:")
try:
    m2_df = ak.macro_china_m2_yearly()
    print(f"   成功! 数据条数: {len(m2_df)}")
    print(f"   列名: {m2_df.columns.tolist()}")
    print(f"   最新数据: {m2_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 5. 社融数据
print("5. 社融数据:")
try:
    sfs_df = ak.macro_china_shrzgm()
    print(f"   成功! 数据条数: {len(sfs_df)}")
    print(f"   列名: {sfs_df.columns.tolist()}")
    print(f"   最新数据: {sfs_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 6. 工业增加值
print("6. 工业增加值:")
try:
    iav_df = ak.macro_china_industrial_production_yearly()
    print(f"   成功! 数据条数: {len(iav_df)}")
    print(f"   列名: {iav_df.columns.tolist()}")
    print(f"   最新数据: {iav_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()

# 7. DR007利率
print("7. DR007利率:")
try:
    dr007_df = ak.rate_interbank(
        market="上海银行同业拆借市场",
        symbol="Shibor人民币",
        indicator="7天",
        need_page=""
    )
    print(f"   成功! 数据条数: {len(dr007_df)}")
    print(f"   列名: {dr007_df.columns.tolist()}")
    print(f"   最新数据: {dr007_df.iloc[0].to_dict()}")
except Exception as e:
    print(f"   失败: {e}")

print()
print("=== 调研完成 ===")
