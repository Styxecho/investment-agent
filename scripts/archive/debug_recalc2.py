import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import traceback

try:
    from skills.macro_state.data_manager import DataManager
    from skills.macro_state.factor_calculator import FactorCalculator
    from skills.macro_state.state_engine import StateEngine
    
    print('Step 1: Loading data...')
    dm = DataManager()
    dm.clear_factors_and_states()
    
    indicator_codes = list(FactorCalculator().indicators.keys())
    raw_data = dm.load_raw_data(indicator_codes)
    print(f'Loaded {len(raw_data)} indicators')
    
    print('\nStep 2: Calculating factors...')
    fc = FactorCalculator()
    factor_results = fc.calculate_all_factors(raw_data)
    print(f'Calculated {len(factor_results)} factors')
    
    print('\nStep 3: Storing factors...')
    dm.store_factors(factor_results)
    print('Stored!')
    
    print('\nStep 4: Computing states...')
    from skills.macro_state.service import MacroStateService
    service = MacroStateService()
    state_count = service._compute_states(raw_data, factor_results)
    print(f'Computed {state_count} states')
    
except Exception as e:
    print('ERROR:', e)
    traceback.print_exc()
