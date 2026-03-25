# tests/conftest.py
import pytest
import pandas as pd
from datetime import datetime


# 这是一个 Fixture，可以在任何测试文件中通过参数 'mock_provider' 使用
@pytest.fixture
def mock_ifind_provider(mocker):
    """
    创建一个模拟的 IfindProvider 实例。
    它的所有方法都不会真正执行，而是返回预设的 DataFrame。
    """
    # 实例化这个模拟类
    mock_instance = mocker.MagicMock()

    # --- 预设假数据：历史行情 ---
    fake_history_data = pd.DataFrame({
        "date": ["2023-10-01", "2023-10-02"],
        "close": [100.5, 101.2],
        "open": [99.8, 100.5],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "volume": [10000, 12000]
    })
    fake_history_data["date"] = pd.to_datetime(fake_history_data["date"])
    fake_history_data.set_index("date", inplace=True)

    # 配置 fetch_history 方法返回这个假数据
    mock_instance.fetch_history.return_value = fake_history_data

    # --- 预设假数据：其他类型 (为未来扩展预留) ---
    # mock_instance.fetch_company_info.return_value = ...

    return mock_instance


@pytest.fixture
def mock_fs(mocker):
    """
    模拟文件系统操作 (os.path.exists, open, etc.)
    防止测试真的读写硬盘上的缓存文件。
    """
    # 这里可以根据需要模拟 os.path.exists 返回 False (模拟缓存未命中)
    # 或者返回 True (模拟缓存命中)
    # 为了简单，我们先不全局 patch，而是在具体测试中按需 patch
    pass