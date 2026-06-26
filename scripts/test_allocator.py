import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
sys.path.insert(0, r'D:\Study\Project\investment-agent\risk_budget_allocator')
from risk_budget_allocator import AssetAllocator
from risk_budget_allocator.config import load_config, validate_config
from skills.portfolio.allocation.data_adapter import load_index_prices
import pandas as pd

# Load default config
raw_config = load_config('config/allocation')
config = validate_config(raw_config)

# Load prices
codes = [a.code for a in config['assets'].assets]
prices = load_index_prices(codes)
print('Prices loaded:', prices.shape)
print('Latest prices:')
print(prices.tail())

# Allocate
allocator = AssetAllocator(config)
report = allocator.allocate(prices, target_date='20260624')

for r in report.results:
    print('\n%s (%s):' % (r.portfolio_name, r.portfolio_id))
    print('  Equity: %.2f%%' % (r.weights['equity'] * 100))
    print('  Bond: %.2f%%' % (r.weights['bond'] * 100))
    print('  Commodity: %.2f%%' % (r.weights['commodity'] * 100))
    print('  Cash: %.2f%%' % (r.weights['cash'] * 100))
    print('  Fallback: %s' % r.fallback)
    if r.warning:
        print('  Warning: %s' % r.warning)
