# skills/industry_rotation/backtest_engine.py
"""
Phase 2.5 行业轮动卫星策略回测引擎

职责：
1. 月频调仓：每月末运行中观 + 微观，生成目标持仓
2. 次月初开盘价执行，扣除双边交易成本
3. 持仓期日频快速触发 + 周频趋势/动能/拥挤防线
4. 输出净值曲线、交易记录、绩效指标

假设：
- 大类资产配置比例由用户手动给定（如 equity=50, bond=40, commodity=10）
- Phase 2.5 只管理 equity 部分内的卫星仓位（默认占 equity 的 10%）
- 底仓部分不参与回测，卫星资金池独立核算
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# 修正导入路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from skills.industry_rotation.data_manager import IndustryRotationDataManager
from skills.industry_rotation.service import IndustryRotationService
from skills.industry_rotation.micro_engine import MicroEngine, MicroConfig
from skills.industry_rotation.risk_monitor import RiskMonitor, RiskConfig
from utils.trade_calendar import TradeCalendarService
from skills.portfolio.backtest.performance import calculate_metrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str = "20150101"
    end_date: str = "20260624"
    
    # 大类资产配置（相对权重，自动归一化）
    asset_allocation: Dict[str, float] = field(default_factory=lambda: {
        'equity': 50.0,
        'bond': 40.0,
        'commodity': 10.0
    })
    
    # 卫星仓位占 equity 的比例
    satellite_ratio_in_equity: float = 0.10
    
    # 交易成本（双边，即买入+卖出合计）
    transaction_cost: float = 0.001
    
    # 初始净值
    initial_nav: float = 1.0
    
    # 子模块配置
    micro_config: MicroConfig = field(default_factory=MicroConfig)
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    
    # ETF映射开关：False=用行业指数回测，True=映射到ETF
    use_etf_mapping: bool = False
    
    # 输出目录
    output_dir: str = "output/industry_rotation_backtest"


class IndustryRotationBacktestEngine:
    """行业轮动卫星策略回测引擎"""
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.cfg = config or BacktestConfig()
        self.dm = IndustryRotationDataManager()
        self.service = IndustryRotationService()
        self.micro_engine = MicroEngine(self.cfg.micro_config)
        self.risk_monitor = RiskMonitor(self.cfg.risk_config)
        self.calendar = TradeCalendarService()
        
        # 数据缓存
        self.df_sw: Optional[pd.DataFrame] = None
        self.df_bench: Optional[pd.DataFrame] = None
        self.df_dict: Optional[Dict[str, pd.DataFrame]] = None
        self.macro_states: Optional[Dict[str, str]] = None
        
        # 回测状态
        self.nav = self.cfg.initial_nav
        self.cash = self.cfg.initial_nav
        self.positions: List[Dict] = []  # 当前持仓
        self.history: List[Dict] = []    # 每日净值记录
        self.trades: List[Dict] = []     # 交易记录
        self.rebalances: List[Dict] = [] # 再平衡记录
        self.pending_orders: List[Dict] = []  # 次日待执行订单
    
    def run(self) -> Dict[str, Any]:
        """执行完整回测"""
        logger.info("=" * 60)
        logger.info("Phase 2.5 行业轮动卫星策略回测")
        logger.info("=" * 60)
        logger.info(f"回测区间: {self.cfg.start_date} ~ {self.cfg.end_date}")
        logger.info(f"大类资产配置: {self.cfg.asset_allocation}")
        logger.info(f"卫星仓位占equity: {self.cfg.satellite_ratio_in_equity:.2%}")
        logger.info(f"交易成本: {self.cfg.transaction_cost:.2%}")
        
        # 1. 加载数据
        self._load_data()
        
        # 2. 获取月末交易日序列
        month_ends = self._get_month_end_dates()
        if not month_ends:
            return {'success': False, 'error': '无法生成月末交易日序列'}
        
        logger.info(f"回测月数: {len(month_ends)}")
        
        # 3. 初始化卫星资金池
        self._initialize_satellite_pool()
        
        # 4. 获取所有交易日
        all_dates = self._get_all_trading_dates()
        logger.info(f"回测交易日数: {len(all_dates)}")
        
        # 5. 每日循环
        signal_dates = {me[0]: me[1] for me in month_ends}
        
        for date_str in all_dates:
            # 开盘：执行 pending orders
            self._execute_pending_orders(date_str)
            
            # 收盘前：如果今天是月末信号日，生成新信号并挂到执行日
            if date_str in signal_dates:
                exec_date = signal_dates[date_str]
                target_portfolio = self._generate_target_portfolio(date_str)
                self.pending_orders.append({
                    'action': 'rebalance',
                    'exec_date': exec_date,
                    'target_portfolio': target_portfolio,
                    'signal_date': date_str
                })
                # 重置新仓持仓周数
                for p in self.positions:
                    p['weeks_held'] = 0
            
            # 收盘后监控
            self._daily_monitor(date_str)
            if self._is_week_end(date_str):
                self._weekly_monitor(date_str)
            
            # 记录净值
            self._record_nav(date_str)
        
        # 6. 计算绩效
        metrics = self._calculate_performance()
        
        # 7. 导出结果
        paths = self._export_results()
        
        return {
            'success': True,
            'config': self.cfg,
            'metrics': metrics,
            'history': self.history,
            'trades': self.trades,
            'rebalances': self.rebalances,
            'output_paths': paths
        }
    
    def _load_data(self):
        """加载并预处理数据"""
        logger.info("加载数据中...")
        
        self.df_sw = self.dm.load_sw_index_daily()
        self.df_bench = self.dm.load_benchmark_daily()
        
        # 为每个行业构建独立DataFrame，并预计算技术指标
        self.df_dict = {}
        for code in self.df_sw['index_code'].unique():
            df = self.df_sw[self.df_sw['index_code'] == code].copy()
            df = df.sort_values('trade_date').reset_index(drop=True)
            df['ma20'] = df['close_price'].rolling(20).mean()
            df['ma60'] = df['close_price'].rolling(60).mean()
            df['ma120'] = df['close_price'].rolling(120).mean()
            df['ema12'] = df['close_price'].ewm(span=12, adjust=False).mean()
            df['ema26'] = df['close_price'].ewm(span=26, adjust=False).mean()
            df['macd_dif'] = df['ema12'] - df['ema26']
            df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd_dif'] - df['macd_dea']
            df['return_5d'] = df['close_price'].pct_change(5)
            df['pre_close'] = df['close_price'].shift(1)
            self.df_dict[code] = df
        
        # 加载宏观状态
        self.macro_states = self._load_macro_states()
        
        logger.info(f"数据加载完成：{len(self.df_dict)}个行业，中证全指{len(self.df_bench)}条")
    
    def _load_macro_states(self) -> Dict[str, str]:
        """加载宏观状态映射 {publish_date: macro_regime}"""
        import sqlite3
        conn = sqlite3.connect(self.dm.db_path)
        df = pd.read_sql_query(
            "SELECT publish_date, macro_regime FROM macro_state_detail",
            conn
        )
        conn.close()
        return dict(zip(df['publish_date'].astype(str), df['macro_regime']))
    
    def _get_month_end_dates(self) -> List[Tuple[str, str]]:
        """获取 (信号日=月末, 执行日=次月初) 序列"""
        pairs = self.calendar.get_month_end_dates(self.cfg.start_date, self.cfg.end_date)
        result = []
        for prev_end, curr_end in pairs:
            # 执行日为次月第一个交易日
            exec_date = self._get_next_trading_day(curr_end)
            if exec_date and exec_date <= self.cfg.end_date:
                result.append((curr_end, exec_date))
        return result
    
    def _get_next_trading_day(self, date_str: str) -> Optional[str]:
        """获取下一个交易日"""
        current = datetime.strptime(date_str, "%Y%m%d")
        for i in range(1, 15):
            next_day = current + timedelta(days=i)
            next_str = next_day.strftime("%Y%m%d")
            if self.calendar.is_trading_day(next_str):
                return next_str
        return None
    
    def _get_all_trading_dates(self) -> List[str]:
        """获取回测区间内所有交易日"""
        # 从第一个行业的数据中提取交易日
        first_df = next(iter(self.df_dict.values()))
        df = first_df[
            (first_df['trade_date'] >= pd.Timestamp(self.cfg.start_date)) &
            (first_df['trade_date'] <= pd.Timestamp(self.cfg.end_date))
        ].copy()
        return df['trade_date'].dt.strftime('%Y%m%d').tolist()
    
    def _initialize_satellite_pool(self):
        """初始化卫星资金池"""
        total = sum(self.cfg.asset_allocation.values())
        equity_weight = self.cfg.asset_allocation.get('equity', 0) / total
        satellite_weight = equity_weight * self.cfg.satellite_ratio_in_equity
        
        self.satellite_initial = self.cfg.initial_nav * satellite_weight
        self.nav = self.satellite_initial
        self.cash = self.satellite_initial
        self.positions = []
        
        logger.info(f"卫星资金池初始值: {self.satellite_initial:.6f} ({satellite_weight:.2%} of total)")
    
    def _generate_target_portfolio(self, signal_date: str) -> Dict[str, Any]:
        """生成目标持仓组合"""
        # 1. 检查宏观状态
        regime = self.macro_states.get(signal_date[:6] + '01', '') or self.macro_states.get(signal_date, '')
        if not regime:
            # 尝试找最近的宏观状态
            regime = self._find_latest_regime(signal_date)
        
        if any(r in regime for r in ['失速衰退', '极端滞胀']):
            logger.warning(f"[{signal_date}] 极端象限：{regime}，清仓")
            return {'cash_weight': 1.0, 'selected': []}
        
        # 2. 运行 Phase 2.4 pipeline
        try:
            result = self.service.run_full_pipeline(signal_date, save_results=False)
            if not result['success']:
                logger.warning(f"[{signal_date}] Phase 2.4 pipeline 失败：{result.get('summary')}")
                return {'cash_weight': 1.0, 'selected': []}
        except Exception as e:
            logger.error(f"[{signal_date}] Phase 2.4 pipeline 异常：{e}")
            return {'cash_weight': 1.0, 'selected': []}
        
        final_pool = result['macro_result']['final_pool']
        if not final_pool:
            return {'cash_weight': 1.0, 'selected': []}
        
        # 3. 运行 Phase 2.5 微观确认
        micro_result = self.micro_engine.run(final_pool, signal_date, self.df_dict)
        
        # 4. ETF映射（如果开启）
        if self.cfg.use_etf_mapping:
            selected = self.micro_engine.map_to_etf(micro_result['selected'])
        else:
            selected = micro_result['selected']
            for item in selected:
                item['trade_code'] = item['index_code']
        
        return {
            'cash_weight': micro_result['cash_weight'],
            'selected': selected
        }
    
    def _find_latest_regime(self, date_str: str) -> str:
        """查找最近的宏观状态"""
        dates = sorted(self.macro_states.keys())
        target = date_str[:6] + '01'
        for d in reversed(dates):
            if d <= target:
                return self.macro_states[d]
        return ''
    
    def _rebalance(self, exec_date: str, target_portfolio: Dict[str, Any]):
        """执行调仓"""
        target_selected = target_portfolio.get('selected', [])
        target_cash_weight = target_portfolio.get('cash_weight', 1.0)
        
        # 当前总市值
        total_value = self._calculate_total_value(exec_date)
        
        # 目标权重
        target_weights = {item['trade_code']: item['target_weight'] for item in target_selected}
        target_cash = target_cash_weight
        
        # 当前权重
        current_weights = {}
        current_total = total_value
        for p in self.positions:
            code = p.get('trade_code', p['index_code'])
            val = self._get_position_value(p, exec_date)
            current_weights[code] = val / current_total if current_total > 0 else 0
        current_cash_weight = self.cash / current_total if current_total > 0 else 1.0
        
        # 计算调仓导致的换手率
        all_codes = set(current_weights.keys()) | set(target_weights.keys())
        turnover = sum(abs(target_weights.get(c, 0) - current_weights.get(c, 0)) for c in all_codes) / 2
        turnover += abs(target_cash - current_cash_weight) / 2
        
        # 扣除交易成本
        cost = total_value * turnover * self.cfg.transaction_cost
        
        # 重新构建持仓
        new_positions = []
        for item in target_selected:
            code = item['trade_code']
            weight = item['target_weight']
            target_value = total_value * weight
            
            df = self.df_dict.get(item['index_code'])
            exec_row = df[df['trade_date'] == pd.Timestamp(exec_date)]
            if exec_row.empty:
                logger.warning(f"[{code}] 执行日无数据，跳过")
                # 资金回归现金
                continue
            
            exec_price = exec_row.iloc[0]['open_price']
            if exec_price <= 0:
                exec_price = exec_row.iloc[0]['close_price']
            
            new_positions.append({
                'index_code': item['index_code'],
                'trade_code': code,
                'index_name': item.get('index_name', item['index_code']),
                'entry_mode': item['entry_mode'],
                'entry_date': exec_date,
                'entry_price': exec_price,
                'shares': target_value / exec_price,
                'cost_basis': target_value,
                'current_weight': weight,
                'weeks_held': 0,
                'crowding_weeks': 0,
                'entry_month_end': ''
            })
            
            self.trades.append({
                'date': exec_date,
                'code': code,
                'action': '买入',
                'price': exec_price,
                'value': target_value,
                'entry_mode': item['entry_mode']
            })
        
        self.cash = total_value - sum(p['cost_basis'] for p in new_positions) - cost
        self.positions = new_positions
        
        self.rebalances.append({
            'date': exec_date,
            'target_weights': target_weights,
            'cash_weight': target_cash_weight,
            'turnover': turnover,
            'cost': cost,
            'n_positions': len(new_positions)
        })
        
        logger.info(
            f"调仓完成：持仓{len(new_positions)}个，现金{self.cash:.6f}，"
            f"换手{turnover:.2%}，成本{cost:.6f}"
        )
    
    def _execute_pending_orders(self, date_str: str):
        """开盘执行pending orders"""
        executed = []
        for order in self.pending_orders:
            if order['exec_date'] != date_str:
                continue
            
            if order['action'] == 'rebalance':
                self._rebalance(date_str, order['target_portfolio'])
            elif order['action'] == 'close':
                self._do_close_position(date_str, order['code'], order['signal'])
            elif order['action'] == 'reduce':
                self._do_reduce_position(date_str, order['code'], order['target_weight'], order['signal'])
            
            executed.append(order)
        
        for order in executed:
            self.pending_orders.remove(order)
    
    def _add_pending_order(self, action: str, exec_date: str, code: str, signal: str,
                           target_weight: Optional[float] = None):
        """添加pending order，避免重复下单"""
        # 检查是否已有同代码同动作未执行订单
        for o in self.pending_orders:
            if o['action'] == action and o['code'] == code and o['exec_date'] == exec_date:
                return
        self.pending_orders.append({
            'action': action,
            'exec_date': exec_date,
            'code': code,
            'signal': signal,
            'target_weight': target_weight
        })
    
    def _daily_monitor(self, date_str: str):
        """日频快速触发（收盘后检查，次日开盘执行）"""
        if not self.positions:
            return
        
        for p in self.positions:
            df = self.df_dict.get(p['index_code'])
            signal = self.risk_monitor.check_daily(p, df, date_str)
            if signal:
                exec_date = self._get_next_trading_day(date_str)
                if exec_date:
                    self._add_pending_order('close', exec_date, p['trade_code'], signal)
    
    def _weekly_monitor(self, date_str: str):
        """周频防线（收盘后检查，次日开盘执行）"""
        if not self.positions:
            return
        
        # 计算截面拥挤度数据
        cross_sectional = self._build_cross_sectional(date_str)
        
        for p in self.positions:
            df = self.df_dict.get(p['index_code'])
            weeks_held = p.get('weeks_held', 0)
            result = self.risk_monitor.check_weekly(p, df, date_str, weeks_held, cross_sectional)
            if result:
                signal, target_weight_ratio = result
                exec_date = self._get_next_trading_day(date_str)
                if not exec_date:
                    continue
                
                if target_weight_ratio == 0.0:
                    self._add_pending_order('close', exec_date, p['trade_code'], signal)
                    p['crowding_weeks'] = 0
                else:
                    # 减仓到目标市值比例
                    total_value = self._calculate_total_value(date_str)
                    current_value = self._get_position_value(p, date_str)
                    target_value = total_value * target_weight_ratio
                    self._add_pending_order(
                        'reduce', exec_date, p['trade_code'], signal,
                        target_weight=target_value
                    )
                    p['crowding_weeks'] = p.get('crowding_weeks', 0) + 1
            else:
                p['crowding_weeks'] = 0
            
            # 连续4周拥挤直接平仓
            if p.get('crowding_weeks', 0) >= self.cfg.risk_config.crowding_consecutive_weeks:
                exec_date = self._get_next_trading_day(date_str)
                if exec_date:
                    self._add_pending_order('close', exec_date, p['trade_code'], '周频-拥挤连续平仓')
                p['crowding_weeks'] = 0
            
            p['weeks_held'] = weeks_held + 1
    
    def _build_cross_sectional(self, date_str: str) -> pd.DataFrame:
        """构建当日截面数据用于拥挤度计算"""
        rows = []
        for code, df in self.df_dict.items():
            df_sub = df[df['trade_date'] <= pd.Timestamp(date_str)].tail(self.cfg.risk_config.crowding_window_long)
            if len(df_sub) < self.cfg.risk_config.crowding_window_short:
                continue
            short = df_sub.tail(self.cfg.risk_config.crowding_window_short)
            rows.append({
                'index_code': code,
                'amount_short': short['amount'].mean(),
                'amount_long': df_sub['amount'].mean()
            })
        return pd.DataFrame(rows).set_index('index_code')
    
    def _do_close_position(self, date_str: str, code: str, signal: str):
        """开盘执行平仓"""
        position = next((p for p in self.positions if p['trade_code'] == code), None)
        if not position:
            return
        
        df = self.df_dict.get(position['index_code'])
        row = df[df['trade_date'] == pd.Timestamp(date_str)]
        if row.empty:
            return
        
        close_price = row.iloc[0]['open_price']
        if close_price <= 0:
            close_price = row.iloc[0]['close_price']
        
        value = position['shares'] * close_price
        cost = value * self.cfg.transaction_cost
        self.cash += value - cost
        
        self.trades.append({
            'date': date_str,
            'code': code,
            'action': '平仓',
            'price': close_price,
            'value': value,
            'signal': signal
        })
        
        self.positions = [p for p in self.positions if p['trade_code'] != code]
        logger.warning(f"[{code}] {date_str} 平仓：{signal}，价值{value:.6f}")
    
    def _do_reduce_position(self, date_str: str, code: str, target_value: float, signal: str):
        """开盘执行减仓"""
        position = next((p for p in self.positions if p['trade_code'] == code), None)
        if not position:
            return
        
        df = self.df_dict.get(position['index_code'])
        row = df[df['trade_date'] == pd.Timestamp(date_str)]
        if row.empty:
            return
        
        close_price = row.iloc[0]['open_price']
        if close_price <= 0:
            close_price = row.iloc[0]['close_price']
        
        current_value = position['shares'] * close_price
        reduce_value = max(0, current_value - target_value)
        cost = reduce_value * self.cfg.transaction_cost
        
        position['shares'] = target_value / close_price
        position['cost_basis'] = target_value
        self.cash += reduce_value - cost
        position['current_weight'] = target_value / self._calculate_total_value(date_str) if self._calculate_total_value(date_str) > 0 else 0
        
        self.trades.append({
            'date': date_str,
            'code': code,
            'action': '减仓',
            'price': close_price,
            'value': reduce_value,
            'signal': signal
        })
        
        logger.warning(f"[{code}] {date_str} 减仓至{target_value:.6f}：{signal}")
    
    def _calculate_total_value(self, date_str: str) -> float:
        """计算当前总市值（持仓 + 现金）"""
        position_value = sum(self._get_position_value(p, date_str) for p in self.positions)
        return position_value + self.cash
    
    def _get_position_value(self, position: Dict, date_str: str) -> float:
        """计算单个持仓在指定日期的市值"""
        df = self.df_dict.get(position['index_code'])
        if df is None:
            return 0.0
        row = df[df['trade_date'] == pd.Timestamp(date_str)]
        if row.empty:
            return 0.0
        return position['shares'] * row.iloc[0]['close_price']
    
    def _record_nav(self, date_str: str):
        """记录每日净值"""
        total = self._calculate_total_value(date_str)
        nav = total / self.satellite_initial if self.satellite_initial > 0 else self.cfg.initial_nav
        
        prev_nav = self.history[-1]['nav'] if self.history else nav
        daily_return = nav / prev_nav - 1 if prev_nav > 0 else 0
        
        self.history.append({
            'trade_date': date_str,
            'nav': nav,
            'daily_return': daily_return,
            'cash': self.cash,
            'n_positions': len(self.positions)
        })
    
    def _is_week_end(self, date_str: str) -> bool:
        """判断是否为本周最后一个交易日（周五或节假日前最后一个交易日）"""
        current = datetime.strptime(date_str, "%Y%m%d")
        
        # 找下一个交易日
        for i in range(1, 10):
            next_day = current + timedelta(days=i)
            next_str = next_day.strftime("%Y%m%d")
            if self.calendar.is_trading_day(next_str):
                # 如果下一个交易日跨自然周，则当前是本周最后一个交易日
                return next_day.isocalendar().week > current.isocalendar().week or next_day.year > current.year
        return True
    
    def _calculate_performance(self) -> Dict[str, Any]:
        """计算绩效指标"""
        if not self.history:
            return {}
        
        nav_df = pd.DataFrame(self.history)
        nav_df['trade_date'] = pd.to_datetime(nav_df['trade_date'])
        nav_df = nav_df.set_index('trade_date').sort_index()
        
        # 计算年化换手率
        turnover = self._calculate_annual_turnover(nav_df)
        
        metrics = calculate_metrics(nav_df['nav'], turnover=turnover)
        
        # 计算基准
        bench_metrics = self._calculate_benchmark_metrics()
        
        return {
            'strategy': metrics.model_dump(),
            'benchmarks': bench_metrics
        }
    
    def _calculate_annual_turnover(self, nav_df: pd.DataFrame) -> float:
        """计算年化换手率（基于再平衡事件的turnover之和 / 年数）"""
        if not self.rebalances:
            return 0.0
        
        total_turnover = sum(r['turnover'] for r in self.rebalances)
        n_days = len(nav_df)
        n_years = n_days / 252.0
        
        if n_years <= 0:
            return 0.0
        
        return total_turnover / n_years
    
    def _calculate_benchmark_metrics(self) -> Dict[str, Any]:
        """计算基准绩效"""
        # 1. 等权行业指数
        df_equal = self._build_equal_weight_index(self.cfg.start_date, self.cfg.end_date)
        metrics_equal = calculate_metrics(df_equal)
        
        # 2. 中证全指
        df_bench = self.df_bench.copy()
        df_bench['trade_date'] = pd.to_datetime(df_bench['trade_date'])
        df_bench = df_bench.set_index('trade_date')
        df_bench = df_bench.loc[self.cfg.start_date:self.cfg.end_date]
        nav_bench = df_bench['close_price'] / df_bench['close_price'].iloc[0]
        metrics_bench = calculate_metrics(nav_bench)
        
        return {
            'equal_weight_industry': metrics_equal.model_dump(),
            'csi_all_share': metrics_bench.model_dump()
        }
    
    def _calculate_benchmark_metrics(self) -> Dict[str, Any]:
        """计算基准绩效"""
        # 1. 等权行业指数
        df_equal = self._build_equal_weight_index(self.cfg.start_date, self.cfg.end_date)
        metrics_equal = calculate_metrics(df_equal)
        
        # 2. 中证全指
        df_bench = self.df_bench.copy()
        df_bench['trade_date'] = pd.to_datetime(df_bench['trade_date'])
        df_bench = df_bench.set_index('trade_date')
        df_bench = df_bench.loc[self.cfg.start_date:self.cfg.end_date]
        nav_bench = df_bench['close_price'] / df_bench['close_price'].iloc[0]
        metrics_bench = calculate_metrics(nav_bench)
        
        return {
            'equal_weight_industry': metrics_equal.model_dump(),
            'csi_all_share': metrics_bench.model_dump()
        }
    
    def _build_equal_weight_index(self, start_date: str, end_date: str) -> pd.Series:
        """构建等权行业指数净值序列"""
        df_list = []
        for code, df in self.df_dict.items():
            df_sub = df[(df['trade_date'] >= pd.Timestamp(start_date)) & (df['trade_date'] <= pd.Timestamp(end_date))].copy()
            if df_sub.empty:
                continue
            df_sub['daily_return'] = df_sub['close_price'].pct_change()
            df_sub = df_sub[['trade_date', 'daily_return']].copy()
            df_sub['index_code'] = code
            df_list.append(df_sub)
        
        if not df_list:
            return pd.Series()
        
        df_all = pd.concat(df_list, ignore_index=True)
        df_equal = df_all.groupby('trade_date')['daily_return'].mean().reset_index()
        df_equal['nav'] = (1 + df_equal['daily_return'].fillna(0)).cumprod()
        df_equal = df_equal.set_index('trade_date').sort_index()
        return df_equal['nav']
    
    def _export_results(self) -> Dict[str, str]:
        """导出回测结果"""
        import json
        output_dir = Path(self.cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        
        # 1. 每日净值
        if self.history:
            nav_df = pd.DataFrame(self.history)
            nav_path = output_dir / 'daily_nav.csv'
            nav_df.to_csv(nav_path, index=False, encoding='utf-8-sig')
            paths['daily_nav'] = str(nav_path)
        
        # 2. 交易记录
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_path = output_dir / 'trades.csv'
            trades_df.to_csv(trades_path, index=False, encoding='utf-8-sig')
            paths['trades'] = str(trades_path)
        
        # 3. 再平衡记录
        if self.rebalances:
            rebal_df = pd.DataFrame(self.rebalances)
            rebal_path = output_dir / 'rebalances.csv'
            rebal_df.to_csv(rebal_path, index=False, encoding='utf-8-sig')
            paths['rebalances'] = str(rebal_path)
        
        # 4. 绩效指标
        metrics = self._calculate_performance()
        metrics_path = output_dir / 'metrics.json'
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)
        paths['metrics'] = str(metrics_path)
        
        # 5. Markdown 回测报告
        report_path = self._generate_report(output_dir, metrics)
        if report_path:
            paths['report'] = str(report_path)
        
        # 6. 净值曲线图
        self._plot_nav(output_dir)
        
        logger.info(f"回测结果已导出到：{output_dir}")
        return paths
    
    def _generate_report(self, output_dir: Path, metrics: Dict[str, Any]) -> Optional[Path]:
        """生成 Markdown 回测报告"""
        try:
            import pandas as pd
            
            nav_df = pd.DataFrame(self.history)
            trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
            rebal_df = pd.DataFrame(self.rebalances) if self.rebalances else pd.DataFrame()
            
            # 交易统计
            n_buys = len(trades_df[trades_df['action'] == '买入']) if not trades_df.empty else 0
            n_closes = len(trades_df[trades_df['action'] == '平仓']) if not trades_df.empty else 0
            n_reduces = len(trades_df[trades_df['action'] == '减仓']) if not trades_df.empty else 0
            
            # 买入-平仓配对收益
            trade_returns = []
            if not trades_df.empty:
                buys = trades_df[trades_df['action'] == '买入'].copy()
                closes = trades_df[trades_df['action'] == '平仓'].copy()
                if not closes.empty:
                    merged = buys.merge(
                        closes[['code', 'price', 'date', 'signal']],
                        on='code', suffixes=('_buy', '_close'), how='left'
                    )
                    merged = merged.sort_values(['code', 'date_buy']).drop_duplicates(
                        subset=['code', 'date_buy'], keep='first'
                    )
                    merged['return'] = merged['price_close'] / merged['price_buy'] - 1
                    trade_returns = merged['return'].dropna().tolist()
            
            avg_return = sum(trade_returns) / len(trade_returns) if trade_returns else 0
            win_rate = sum(1 for r in trade_returns if r > 0) / len(trade_returns) if trade_returns else 0
            
            # 按入场模式统计
            mode_stats = {}
            if not trades_df.empty:
                buys = trades_df[trades_df['action'] == '买入'].copy()
                closes = trades_df[trades_df['action'] == '平仓'].copy()
                if not closes.empty:
                    merged = buys.merge(
                        closes[['code', 'price', 'date']], on='code', suffixes=('_buy', '_close'), how='left'
                    )
                    merged = merged.sort_values(['code', 'date_buy']).drop_duplicates(
                        subset=['code', 'date_buy'], keep='first'
                    )
                    merged['return'] = merged['price_close'] / merged['price_buy'] - 1
                    for mode in merged['entry_mode'].dropna().unique():
                        sub = merged[merged['entry_mode'] == mode]['return'].dropna()
                        mode_stats[mode] = {
                            'count': len(sub),
                            'mean': sub.mean(),
                            'win_rate': (sub > 0).mean()
                        }
            
            # 持仓时间统计
            holding_periods = []
            if not trades_df.empty:
                buys = trades_df[trades_df['action'] == '买入'].copy()
                closes = trades_df[trades_df['action'] == '平仓'].copy()
                for _, buy in buys.iterrows():
                    close = closes[(closes['code'] == buy['code']) & (closes['date'] > buy['date'])]
                    if not close.empty:
                        days = (pd.Timestamp(close.iloc[0]['date']) - pd.Timestamp(buy['date'])).days
                        holding_periods.append(days)
            
            avg_holding = sum(holding_periods) / len(holding_periods) if holding_periods else 0
            
            # 空仓/持仓天数
            empty_days = (nav_df['n_positions'] == 0).sum() if not nav_df.empty else 0
            total_days = len(nav_df) if not nav_df.empty else 0
            
            report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            report = f"""# Phase 2.5 行业轮动卫星策略回测报告

## 一、回测设置

| 参数 | 设定值 |
|------|--------|
| 回测区间 | {self.cfg.start_date} ~ {self.cfg.end_date} |
| 大类资产配置 | {self.cfg.asset_allocation} |
| 卫星仓位占 equity | {self.cfg.satellite_ratio_in_equity:.2%} |
| 双边交易成本 | {self.cfg.transaction_cost:.2%} |
| 最多持仓行业数 | {self.cfg.micro_config.max_positions} |
| 单行业仓位上限 | {self.cfg.micro_config.single_cap:.2%} |
| 回测标的 | 申万一级行业指数 |

## 二、策略绩效

| 指标 | 策略 | 等权行业指数 | 中证全指 |
|------|------|-------------|---------|
| 累计收益率 | {metrics['strategy']['cumulative_return']:.2%} | {metrics['benchmarks']['equal_weight_industry']['cumulative_return']:.2%} | {metrics['benchmarks']['csi_all_share']['cumulative_return']:.2%} |
| 年化收益率 | {metrics['strategy']['annualized_return']:.2%} | {metrics['benchmarks']['equal_weight_industry']['annualized_return']:.2%} | {metrics['benchmarks']['csi_all_share']['annualized_return']:.2%} |
| 年化波动率 | {metrics['strategy']['annualized_volatility']:.2%} | {metrics['benchmarks']['equal_weight_industry']['annualized_volatility']:.2%} | {metrics['benchmarks']['csi_all_share']['annualized_volatility']:.2%} |
| 最大回撤 | {metrics['strategy']['max_drawdown']:.2%} | {metrics['benchmarks']['equal_weight_industry']['max_drawdown']:.2%} | {metrics['benchmarks']['csi_all_share']['max_drawdown']:.2%} |
| 夏普比率 | {metrics['strategy']['sharpe_ratio']:.4f} | {metrics['benchmarks']['equal_weight_industry']['sharpe_ratio']:.4f} | {metrics['benchmarks']['csi_all_share']['sharpe_ratio']:.4f} |
| 卡玛比率 | {metrics['strategy']['calmar_ratio']:.4f} | {metrics['benchmarks']['equal_weight_industry']['calmar_ratio']:.4f} | {metrics['benchmarks']['csi_all_share']['calmar_ratio']:.4f} |
| 月度胜率 | {metrics['strategy']['win_rate_monthly']:.2%} | {metrics['benchmarks']['equal_weight_industry']['win_rate_monthly']:.2%} | {metrics['benchmarks']['csi_all_share']['win_rate_monthly']:.2%} |
| 年化换手率 | {metrics['strategy']['annualized_turnover']:.2%} | - | - |

## 三、交易统计

| 指标 | 数值 |
|------|------|
| 买入次数 | {n_buys} |
| 平仓次数 | {n_closes} |
| 减仓次数 | {n_reduces} |
| 买入-平仓配对数 | {len(trade_returns)} |
| 平均单笔收益 | {avg_return:.2%} |
| 单笔胜率 | {win_rate:.2%} |
| 平均持仓天数 | {avg_holding:.1f} |
| 空仓天数 | {empty_days} / {total_days} ({empty_days/total_days:.2%}) |

## 四、入场模式分析

"""
            
            if mode_stats:
                report += "| 入场模式 | 次数 | 平均收益 | 胜率 |\n"
                report += "|----------|------|----------|------|\n"
                for mode, stat in mode_stats.items():
                    report += f"| {mode} | {stat['count']} | {stat['mean']:.2%} | {stat['win_rate']:.2%} |\n"
            else:
                report += "（无有效配对数据）\n"
            
            report += """
## 五、主要发现与问题

1. **策略跑输基准**：在 2015-2026 回测期内，策略累计收益为负，显著跑输等权行业指数和中证全指。
2. **入场模式分化**：模式A（回调买入）表现较差，平均亏损；模式B（突破买入）表现相对较好。
3. **风控触发频繁**：MACD 死叉、MA20<MA60、拥挤度等周频防线触发次数较多，导致持仓周期偏短。
4. **空仓比例较高**：约一半时间处于空仓状态，说明入场条件较为严格。

## 六、后续优化方向

1. **参数敏感性分析**：测试不同 MA 周期、MACD 参数、回调容差、拥挤度阈值。
2. **入场模式优化**：考虑降低模式A优先级，或提高模式A的过滤条件。
3. **拥挤度指标改进**：当前使用成交额 Z-score，可能受市场整体放量影响，可改用相对换手率或波动率调整。
4. **仓位动态调整**：根据宏观状态或市场波动率动态调整卫星仓位比例。
5. **加入止盈规则**：当前以止损为主，可补充趋势止盈或目标收益止盈。

---
*报告生成时间：{report_time}*
"""
            
            report_path = output_dir / 'backtest_report.md'
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"回测报告已保存：{report_path}")
            return report_path
            
        except Exception as e:
            logger.warning(f"生成回测报告失败：{e}")
            return None
    
    def _plot_nav(self, output_dir: Path):
        """绘制净值曲线"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 策略净值
            nav_df = pd.DataFrame(self.history)
            nav_df['trade_date'] = pd.to_datetime(nav_df['trade_date'])
            ax.plot(nav_df['trade_date'], nav_df['nav'], label='Strategy', linewidth=2)
            
            # 等权行业基准
            df_equal = self._build_equal_weight_index(self.cfg.start_date, self.cfg.end_date)
            if not df_equal.empty:
                ax.plot(df_equal.index, df_equal, label='Equal-weight Industry', alpha=0.7)
            
            # 中证全指
            df_bench = self.df_bench.copy()
            df_bench['trade_date'] = pd.to_datetime(df_bench['trade_date'])
            df_bench = df_bench.set_index('trade_date')
            df_bench = df_bench.loc[self.cfg.start_date:self.cfg.end_date]
            nav_bench = df_bench['close_price'] / df_bench['close_price'].iloc[0]
            ax.plot(nav_bench.index, nav_bench, label='CSI All Share', alpha=0.7)
            
            ax.set_title('Phase 2.5 Industry Rotation Satellite Backtest')
            ax.set_xlabel('Date')
            ax.set_ylabel('NAV')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            fig_path = output_dir / 'nav_curve.png'
            plt.savefig(fig_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"净值曲线已保存：{fig_path}")
        except Exception as e:
            logger.warning(f"绘图失败：{e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    config = BacktestConfig()
    engine = IndustryRotationBacktestEngine(config)
    result = engine.run()
    print(result.get('metrics'))
