import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
sys.path.insert(0, r'D:\Study\Project\investment-agent\risk_budget_allocator')
from risk_budget_allocator import RiskBudgetAllocator
from risk_budget_allocator.config import load_config, validate_config
from skills.portfolio.allocation.data_adapter import load_index_prices
import numpy as np

raw_config = load_config('config/allocation')
config = validate_config(raw_config)

codes = [a.code for a in config['assets'].assets]
prices = load_index_prices(codes)

# Get returns window
lookback = config['assets'].data.lookback_days
price_window = prices.iloc[-lookback:]
returns = price_window.pct_change().dropna()

print('Asset codes:', codes)
print('Volatilities (annualized):')
print((returns.std() * np.sqrt(252)))
print('\nCorrelation:')
print(returns.corr())

allocator = RiskBudgetAllocator(config)
report = allocator.allocate(prices, target_date='20260522')

for r in report.results:
    print('\n%s:' % r.portfolio_name)
    print('  Risk budget:', r.risk_budget)
    print('  Raw weights:', r.raw_weights)
    print('  Final weights:', r.weights)
    print('  Fallback:', r.fallback)
