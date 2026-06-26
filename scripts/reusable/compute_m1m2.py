#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from skills.macro_factor.pipeline import MacroFactorPipeline
from data_external.db.engine import engine
from sqlalchemy import text
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pipeline = MacroFactorPipeline()

logger.info('Computing CN_M1M2_DIFF_M (M1-M2 scissors)')

# Delete old data
with engine.connect() as conn:
    conn.execute(text("DELETE FROM macro_indicator_value WHERE indicator_code = 'CN_M1M2_DIFF_M'"))
    conn.execute(text("DELETE FROM macro_factor_value WHERE indicator_code = 'CN_M1M2_DIFF_M'"))
    conn.commit()

# Compute factor
count = pipeline.run('CN_M1M2_DIFF_M', '20150101', '20241231')
logger.info(f'CN_M1M2_DIFF_M: stored {count} factor records')

# Verify
df = pd.read_sql("""
    SELECT indicator_code, publish_date, factor_type, factor_value
    FROM macro_factor_value
    WHERE indicator_code = 'CN_M1M2_DIFF_M'
      AND publish_date IN ('20160229', '20161231', '20170228', '20171231', '20200331', '20211031')
    ORDER BY publish_date, factor_type
""", engine)
print('\nM1M2 Scissors Key Time Points Verification:')
print(df.to_string(index=False))
