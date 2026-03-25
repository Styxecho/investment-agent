# config/types.py
"""
全局自定义 Pydantic 类型别名
"""
from typing import Annotated
from pydantic import PlainSerializer
from datetime import date

# 金融行业标准日期格式：YYYYMMDD (如 20260320)
DateStr = Annotated[
    date,
    PlainSerializer(lambda d: d.strftime("%Y%m%d"), return_type=str)
]