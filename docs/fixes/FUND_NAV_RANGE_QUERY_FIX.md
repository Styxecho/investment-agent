# 公募基金净值查询功能修复报告

**修复日期**: 2026-04-06  
**问题类型**: 工具调用参数缺失 + 日期范围查询支持  
**修复状态**: ✅ 完成

---

## 问题描述

用户尝试查询 003956.OF（易方达蓝筹精选）在 2026-04-01 至 2026-04-03 的日终单位净值，但遇到以下问题：

1. **工具参数缺失**: `get_market_data` 工具不支持日期范围查询
2. **API 调用格式错误**: iFinD API 需要特定的参数格式
3. **Service 层逻辑**: 需要支持日期范围查询和单日查询两种模式

**预期 API 调用**:
```python
THS_DS('003956.OF',
       'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund',
       ';;',  # ← 关键修复：2 个分号对应 3 个指标
       'block:latest',
       '2026-04-01',
       '2026-04-03')
```

**预期返回**:
- 2026-04-01: 2.1462
- 2026-04-02: 2.1514
- 2026-04-03: 2.1354

---

## 修复内容

### 0. jsonparam 格式修复（关键）

**文件**: `skills/market_data/provider/ifind_provider.py`  
**位置**: 第 264-283 行

**问题**:
- `jsonIndicator` 有 3 个指标（用 2 个分号分隔）
- `jsonparam` 应该是 `';;'`（2 个分号，对应 3 个指标的空参数）
- 原代码使用 `jsonparam=''`（空字符串），导致 API 调用失败

**修复**:
```python
# 根据 jsonIndicator 中的分号数量生成 jsonparam
indicator_count = request_indicator.count(';') + 1
jsonparam = ';' * (indicator_count - 1)

# 示例：
# 'ths_unit_nv_fund' → indicator_count=1 → jsonparam=''
# 'a;b' → indicator_count=2 → jsonparam=';'
# 'a;b;c' → indicator_count=3 → jsonparam=';;'
```

**验证**:
```python
assert call_args[1]['jsonparam'] == ';;'  # ✅ 正确
```

---

### 1. 修改 `agents/tools.py`

**位置**: 第 90-111 行

**修改前**:
```python
@tool
def get_market_data(symbol: str, asset_type: str = "stock") -> str:
    """获取单日行情数据"""
    context = SkillContext(
        target_date=_get_current_trade_date(),
        extra_params={"symbol": symbol, "asset_type": asset_type}
    )
```

**修改后**:
```python
@tool
def get_market_data(symbol: str, asset_type: str = "stock", 
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> str:
    """
    获取 A 股股票、ETF 或公募基金在特定日期或日期范围的行情数据/净值。
    
    Args:
        symbol: 股票代码（如 '003956.OF'）
        asset_type: 资产类型（'stock', 'etf', 'fund'）
        start_date: 开始日期（YYYYMMDD，可选）
        end_date: 结束日期（YYYYMMDD，可选）
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
```

**改进**:
- ✅ 添加 `start_date` 和 `end_date` 参数
- ✅ 支持日期范围查询
- ✅ 自动确定目标日期

---

### 2. 修改 `skills/market_data/service.py`

**位置**: 第 231-377 行（`_get_fund_daily_data` 方法）

**关键修改**:

#### A. 支持日期范围参数
```python
def _get_fund_daily_data(self, context, fund_code, target_date):
    # 检查是否指定了日期范围
    start_date = context.extra_params.get('start_date')
    end_date = context.extra_params.get('end_date')
    
    if start_date and end_date:
        # 用户指定了日期范围
        query_start = start_date
        query_end = end_date
    else:
        # 单日查询，需要获取 T-1 日
        prev_trading_date = self.trade_calendar.get_previous_trading_date(target_date)
        query_start = prev_trading_date
        query_end = target_date
```

#### B. 修改查询逻辑
```python
# 查询缓存或 API
df_cached = self.fund_repo.get_fund_nav(fund_code, query_start, query_end)

# 调用 Provider
df_new = self.provider.fetch_fund_nav(
    fund_code=fund_code,
    start_date=query_start,
    end_date=query_end
)
```

#### C. 修改结果处理
```python
# 日期范围查询
if start_date and end_date:
    data_list = df_result.to_dict('records')
    hint = f"{fund_code} 在 {start_date} 至 {end_date} 期间共 {len(data_list)} 个交易日："
    for i, row in enumerate(data_list):
        hint += f" {row.get('trade_date')}={row.get('unit_nav'):.4f}"
    
    return SkillResult(
        data={'nav_series': data_list},
        summary_hint=hint
    )
else:
    # 单日查询（原有逻辑）
    ...
```

**改进**:
- ✅ 区分日期范围查询和单日查询
- ✅ 范围查询返回所有交易日净值序列
- ✅ 单日查询返回当日净值和涨跌幅

---

### 3. 创建测试文件

#### 文件 1: `tests/market_data/test_ifind_fund_nav.py`

**测试内容**:
- `test_fetch_fund_nav_range`: 测试日期范围查询
- `test_fetch_fund_nav_single_date`: 测试单日查询
- `test_service_get_fund_nav_range`: 测试 Service 层范围查询
- `test_service_get_fund_nav_single`: 测试 Service 层单日查询

**预期数据**:
```python
{
    "20260401": 2.1462,
    "20260402": 2.1514,
    "20260403": 2.1354
}
```

**注意**: 实际数据需要 iFinD 连接，测试会在不可用时跳过。

#### 文件 2: `tests/market_data/test_fund_nav_integration.py`

**测试内容**（Mock 测试）:
- `test_ifind_api_call_format`: 验证 API 调用格式
- `test_service_date_range_query`: 验证 Service 层范围查询
- `test_service_single_date_query`: 验证 Service 层单日查询

**测试结果**:
```
✅ test_ifind_api_call_format PASSED
✅ test_service_date_range_query PASSED
✅ test_service_single_date_query PASSED
```

---

## 测试验证

### 测试 1: API 调用格式验证
```python
# 验证 iFinD API 调用参数
assert call_args[1]['thscode'] == '003956.OF'
assert call_args[1]['jsonIndicator'] == 'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund'
assert call_args[1]['globalparam'] == 'block:latest'
assert call_args[1]['begintime'] == '2026-04-01'
assert call_args[1]['endtime'] == '2026-04-03'
```

**结果**: ✅ PASSED

### 测试 2: 日期范围查询
```python
context = SkillContext(
    target_date='20260403',
    extra_params={
        'symbol': '003956.OF',
        'asset_type': 'fund',
        'start_date': '20260401',
        'end_date': '20260403'
    }
)

result = service.get_daily_data(context, '003956.OF', AssetType.FUND)

# 验证返回 3 条记录
assert len(result.data['nav_series']) == 3
assert [item['unit_nav'] for item in result.data['nav_series']] == [2.1462, 2.1514, 2.1354]
```

**结果**: ✅ PASSED

### 测试 3: 单日查询
```python
context = SkillContext(
    target_date='20260403',
    extra_params={'symbol': '003956.OF', 'asset_type': 'fund'}
)

result = service.get_daily_data(context, '003956.OF', AssetType.FUND)

# 验证包含目标日期净值
assert '20260403' in result.summary_hint or '2.1354' in result.summary_hint
```

**结果**: ✅ PASSED

---

## 使用示例

### 示例 1: 日期范围查询

**用户提问**:
```
帮我查询一下 003956.OF 在 2026-4-1 到 2026-4-3 的日终单位净值
```

**Agent 响应**:
```
003956.OF 在 20260401 至 20260403 期间共 3 个交易日：
 20260401=2.1462, 20260402=2.1514, 20260403=2.1354
```

### 示例 2: 单日查询

**用户提问**:
```
003956.OF 在 2026-4-3 的净值是多少？
```

**Agent 响应**:
```
003956.OF 在 20260403 单位净值为 2.1354, 较前一交易日下跌 0.74%
```

---

## 技术细节

### iFinD API 调用格式

**函数签名**:
```python
THS_DS(
    thscode='003956.OF',
    jsonIndicator='ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund',
    jsonparam='',
    globalparam='block:latest',
    begintime='2026-04-01',
    endtime='2026-04-03'
)
```

**返回字段**:
- `time`: 日期
- `thscode`: 基金代码
- `ths_unit_nv_fund`: 单位净值
- `ths_accum_unit_nv_fund`: 累计单位净值
- `ths_adjustment_nv_fund`: 复权单位净值

### 数据标准化

**列名映射**:
```python
column_mapping = {
    'time': 'trade_date',
    'thscode': 'fund_code',
    'ths_unit_nv_fund': 'unit_nav',
    'ths_accum_unit_nv_fund': 'accumulated_nav',
    'ths_adjustment_nv_fund': 'adjusted_nav'
}
```

**日期格式**:
- 输入：`'2026-04-01'`
- 输出：`'20260401'` 或 `datetime` 对象

---

## 注意事项

### 1. iFinD 连接要求
- 需要配置 `IFIND_USERNAME` 和 `IFIND_PIN`
- 需要同花顺终端运行
- 网络环境要求稳定

### 2. 日期格式
- 用户输入：`2026-4-1`, `20260401`, `2026-04-01` 均可
- 内部处理：统一转换为 `YYYYMMDD` 格式
- API 调用：转换为 `YYYY-MM-DD` 格式

### 3. 交易日历
- 单日查询自动获取 T-1 交易日
- 范围查询使用用户指定的日期
- 节假日通过 CSV 文件维护

---

## 测试覆盖率

| 测试文件 | 测试用例 | 状态 |
|----------|----------|------|
| `test_ifind_fund_nav.py` | 4 个 | ⚠️ 需要 iFinD 连接 |
| `test_fund_nav_integration.py` | 3 个 | ✅ 全部通过 |

**建议**: 
- Mock 测试用于日常回归
- 集成测试在有 iFinD 环境时运行

---

## 后续优化建议

1. **缓存优化**: 批量查询时减少重复 API 调用
2. **错误处理**: 更友好的错误提示（如数据不存在）
3. **性能优化**: 多线程获取多只基金净值
4. **数据验证**: 添加净值异常波动检测

---

**修复完成时间**: 2026-04-06  
**测试状态**: ✅ 3/3 Mock 测试通过  
**可以开始使用日期范围查询功能**
