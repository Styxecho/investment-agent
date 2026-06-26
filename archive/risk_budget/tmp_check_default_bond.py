import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
sys.path.insert(0, r'D:\Study\Project\investment-agent\risk_budget_allocator')
from risk_budget_allocator import AssetAllocator
from risk_budget_allocator.config import load_config, validate_config
from skills.portfolio.allocation.data_adapter import load_index_prices

raw_config = load_config('config/allocation')
config = validate_config(raw_config)

codes = [a.code for a in config['assets'].assets]
print('Configured asset codes:', codes)
prices = load_index_prices(codes)
print('Prices shape:', prices.shape)
print('Latest date:', prices.index[-1])
print('Missing:', prices.isna().sum().to_dict())

allocator = AssetAllocator(config)
report = allocator.allocate(prices, target_date='20260624')
for r in report.results:
    print(f"{r.portfolio_id}: eq={r.weights['equity']:.2%} bond={r.weights['bond']:.2%} comm={r.weights['commodity']:.2%} cash={r.weights['cash']:.2%}")
