# skills/industry_rotation/data_manager.py
"""
IndustryRotation数据管理层

职责：
1. 读取index_daily（申万行业指数 + 中证全指）
2. 读取etf_universe.csv
3. 读取ETF/申万成分股权重文件
4. 读取宏观状态
5. 检查数据完备性
6. 写入结果到数据库（候选池）

不职责：
- 不从外部API抓取数据（独立维护）
- 不做计算逻辑
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

DB_PATH = Path('data_external/db/external_data.db')
ETF_UNIVERSE_PATH = Path('data_external/reference/etf_universe.csv')
COMPONENTS_DIR = Path('data_external/reference/index_components')
SW_MAPPING_PATH = Path('data_external/reference/sw_industry_mapping.csv')


class IndustryRotationDataManager:
    """行业轮动数据管理器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.etf_universe_path = ETF_UNIVERSE_PATH
        self.components_dir = COMPONENTS_DIR
        self.sw_mapping_path = SW_MAPPING_PATH
    
    # ==================== 数据检查 ====================
    
    def check_data_completeness(self, target_date: str) -> List[str]:
        """
        检查数据完备性
        
        Returns:
            issues: 空列表=完备，否则返回问题列表
        """
        issues = []
        
        # 1. 检查申万行业指数
        latest_sw = self._get_latest_date('index_daily', '801%.SI')
        if not latest_sw or latest_sw < target_date:
            issues.append(f"申万行业指数数据缺失: 最新={latest_sw}, 需要>={target_date}")
        
        # 2. 检查中证全指
        latest_bench = self._get_latest_date('index_daily', '000985.CSI')
        if not latest_bench or latest_bench < target_date:
            issues.append(f"中证全指数据缺失: 最新={latest_bench}, 需要>={target_date}")
        
        # 3. 检查ETF列表
        if not self.etf_universe_path.exists():
            issues.append(f"ETF列表文件缺失: {self.etf_universe_path}")
        
        # 4. 检查成分股权重文件
        if not self.components_dir.exists():
            issues.append(f"成分股权重目录缺失: {self.components_dir}")
        else:
            sw_files = list(self.components_dir.glob('sw_*.xls'))
            idx_files = list(self.components_dir.glob('*_index_weight.*'))
            if len(sw_files) < 31:
                issues.append(f"申万行业成分股文件不足: {len(sw_files)}/31")
            if len(idx_files) < 50:  # 至少50个指数权重文件
                issues.append(f"ETF跟踪指数权重文件不足: {len(idx_files)}个")
        
        # 5. 检查宏观状态
        latest_macro = self._get_latest_macro_date()
        target_ym = target_date[:6]
        if not latest_macro or latest_macro < target_ym:
            issues.append(f"宏观状态数据缺失: 最新={latest_macro}, 需要>={target_ym}")
        
        # 6. 检查行业映射表
        if not self.sw_mapping_path.exists():
            issues.append(f"申万行业映射表缺失: {self.sw_mapping_path}")
        
        return issues
    
    def _get_latest_date(self, table: str, code_pattern: str) -> Optional[str]:
        """获取某表某代码的最新日期"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT MAX(trade_date) FROM {table} 
                WHERE index_code LIKE ?
            """, (code_pattern,))
            result = cursor.fetchone()
            conn.close()
            return str(result[0]) if result and result[0] else None
        except Exception:
            return None
    
    def _get_latest_macro_date(self) -> Optional[str]:
        """获取最新宏观状态日期"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(publish_date) FROM macro_state_detail")
            result = cursor.fetchone()
            conn.close()
            return str(result[0]) if result and result[0] else None
        except Exception:
            return None
    
    # ==================== 数据读取 ====================
    
    def load_sw_index_daily(self) -> pd.DataFrame:
        """读取申万行业指数日频数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("""
            SELECT index_code, trade_date, close_price 
            FROM index_daily 
            WHERE index_code LIKE '801%.SI'
            ORDER BY index_code, trade_date
        """, conn)
        conn.close()
        
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
        return df.dropna()
    
    def load_benchmark_daily(self) -> pd.DataFrame:
        """读取中证全指日频数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("""
            SELECT index_code, trade_date, close_price 
            FROM index_daily 
            WHERE index_code = '000985.CSI'
            ORDER BY trade_date
        """, conn)
        conn.close()
        
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
        return df.dropna()
    
    def load_etf_universe(self) -> pd.DataFrame:
        """读取ETF列表"""
        df = pd.read_csv(self.etf_universe_path, encoding='utf-8-sig')
        return df
    
    def load_sw_industry_mapping(self) -> pd.DataFrame:
        """读取申万行业映射表"""
        if not self.sw_mapping_path.exists():
            return pd.DataFrame(columns=['sw_code', 'sw_name', 'sector_group'])
        return pd.read_csv(self.sw_mapping_path, encoding='utf-8-sig', dtype=str)
    
    def load_sw_components(self, sw_code: str) -> pd.DataFrame:
        """读取申万行业成分股"""
        file_path = self.components_dir / f'sw_{sw_code}.xls'
        if not file_path.exists():
            return pd.DataFrame()
        
        df = pd.read_excel(file_path, dtype=str)
        # 列: 日期, 指数代码, 指数名称, 成分股代码, 成分股简称, 权重%
        # 成分股代码在第4列(索引3)
        if len(df.columns) >= 6:
            df.columns = ['date', 'idx_code', 'idx_name', 'stock_code', 'stock_name', 'weight']
            df['stock_code'] = df['stock_code'].astype(str).str.strip().str.zfill(6)
        return df
    
    def load_etf_components(self, index_code: str) -> Optional[pd.DataFrame]:
        """读取ETF跟踪指数成分股权重"""
        base_code = index_code.split('.')[0] if '.' in str(index_code) else str(index_code)
        
        # 查找匹配文件
        for ext in ['.xls', '.xlsx']:
            pattern = f'{base_code}_*index_weight{ext}'
            files = list(self.components_dir.glob(pattern))
            if files:
                file_path = files[0]
                try:
                    df = pd.read_excel(file_path, dtype=str)
                    # 自动识别列：第2列=成分券代码，最后一列=权重
                    if len(df.columns) >= 6:
                        code_col = df.columns[1]  # 第2列（索引1）
                        weight_col = df.columns[-1]  # 最后1列
                        df = df[[code_col, weight_col]].copy()
                        df.columns = ['stock_code', 'weight']
                        df['stock_code'] = df['stock_code'].astype(str).str.strip().str.zfill(6)
                        df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
                        return df.dropna()
                except Exception:
                    continue
        return None
    
    def load_macro_state(self, date: str) -> Optional[Dict]:
        """读取指定日期的宏观状态，支持YYYYMMDD或YYYYMM格式"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 先尝试精确匹配
            cursor.execute("""
                SELECT publish_date, growth_state, inflation_state, 
                       liquidity_state, macro_regime
                FROM macro_state_detail
                WHERE publish_date = ?
            """, (date,))
            row = cursor.fetchone()
            
            # 如果没有精确匹配且date是YYYYMM格式，尝试前缀匹配
            if not row and len(date) == 6:
                cursor.execute("""
                    SELECT publish_date, growth_state, inflation_state, 
                           liquidity_state, macro_regime
                    FROM macro_state_detail
                    WHERE publish_date LIKE ?
                    ORDER BY publish_date DESC
                    LIMIT 1
                """, (date + '%',))
                row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return {
                    'publish_date': row[0],
                    'growth_state': row[1],
                    'inflation_state': row[2],
                    'liquidity_state': row[3],
                    'macro_regime': row[4]
                }
            return None
        except Exception:
            return None
    
    # ==================== 数据写入 ====================
    
    def save_pool(self, date: str, pool_type: str, industries: List[Dict], 
                  macro_regime: str) -> bool:
        """保存候选池到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS industry_rotation_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date VARCHAR(8) NOT NULL,
                    pool_type VARCHAR(20),
                    industries TEXT,
                    macro_regime VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, pool_type)
                )
            """)
            
            # 插入或更新
            import json
            industries_json = json.dumps(industries, ensure_ascii=False)
            
            cursor.execute("""
                INSERT OR REPLACE INTO industry_rotation_pool 
                (date, pool_type, industries, macro_regime)
                VALUES (?, ?, ?, ?)
            """, (date, pool_type, industries_json, macro_regime))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存候选池失败: {e}")
            return False
    
    def load_pool(self, date: str, pool_type: str = 'final') -> Optional[List[Dict]]:
        """从数据库读取候选池"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT industries FROM industry_rotation_pool
                WHERE date = ? AND pool_type = ?
            """, (date, pool_type))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                import json
                return json.loads(row[0])
            return None
        except Exception:
            return None
    
    def get_latest_pool_date(self) -> Optional[str]:
        """获取最新候选池日期"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM industry_rotation_pool")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result and result[0] else None
        except Exception:
            return None
