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

# Use last 252 days
lookback = 252
price_window = prices.iloc[-lookback:]
returns = price_window.pct_change().dropna()

cov = returns.cov() * 252
asset_codes = ['000985.CSI', 'CBA00601.CS', 'AU.SHF']
cov = cov.loc[asset_codes, asset_codes]
print('Covariance matrix:')
print(cov)
print('\nVolatilities:', np.sqrt(np.diag(cov)))

# Try different risk budgets for aggressive target
test_budgets = [
    (0.70, 0.20, 0.10),
    (0.75, 0.15, 0.10),
    (0.80, 0.15, 0.05),
    (0.85, 0.10, 0.05),
    (0.90, 0.08, 0.02),
]

from risk_budget_allocator.risk_budget import risk_budget_weights

for eq, bd, cm in test_budgets:
    rb = np.array([eq, bd, cm])
    w, _ = risk_budget_weights(cov.values, rb)
    sigma = np.sqrt(w @ cov.values @ w)
    print('\nRisk budget %.0f%%/%.0f%%/%.0f%% -> weights %.1f%%/%.1f%%/%.1f%%, vol %.2f%%' % (
        eq*100, bd*100, cm*100,
        w[0]*100, w[1]*100, w[2]*100, sigma*100
    ))

# For conservative target 15% equity / 78% bond / 5% commodity
test_conservative = [
    (0.30, 0.65, 0.05),
    (0.40, 0.55, 0.05),
    (0.50, 0.45, 0.05),
    (0.60, 0.35, 0.05),
]

print('\n--- Conservative targets ---')
for eq, bd, cm in test_conservative:
    rb = np.array([eq, bd, cm])
    w, _ = risk_budget_weights(cov.values, rb)
    sigma = np.sqrt(w @ cov.values @ w)
    print('Risk budget %.0f%%/%.0f%%/%.0f%% -> weights %.1f%%/%.1f%%/%.1f%%, vol %.2f%%' % (
        eq*100, bd*100, cm*100,
        w[0]*100, w[1]*100, w[2]*100, sigma*100
    ))
