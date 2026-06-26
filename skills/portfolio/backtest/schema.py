# skills/portfolio/backtest/schema.py
"""
BacktestSkill 数据契约
定义回测请求与结果的标准化数据结构
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pandas as pd
import json


class BacktestAsset(BaseModel):
    """回测组合中的单个资产"""
    code: str = Field(..., description="资产代码，如 510300.SH")
    weight: Optional[float] = Field(None, description="目标权重。None 表示由 method 自动计算")


class BacktestRequest(BaseModel):
    """回测请求"""
    assets: List[BacktestAsset] = Field(..., description="资产列表")
    start_date: str = Field(..., pattern=r"^\d{8}$", description="开始日期 YYYYMMDD")
    end_date: str = Field(..., pattern=r"^\d{8}$", description="结束日期 YYYYMMDD")
    method: str = Field("risk_parity", description="组合构建方法：risk_parity / risk_parity_target_vol / equal_weight / user_defined")
    rebalance_freq: str = Field("monthly", description="再平衡频率：none / monthly / quarterly")
    lookback_days: int = Field(252, description="协方差估计窗口（交易日）")
    initial_nav: float = Field(1.0, description="初始净值")
    target_volatility: Optional[float] = Field(None, description="目标年化波动率（risk_parity_target_vol 方法使用）")


class BacktestDailyRecord(BaseModel):
    """回测每日记录"""
    trade_date: str = Field(..., description="交易日期 YYYYMMDD")
    nav: float = Field(..., description="组合当日净值")
    daily_return: float = Field(..., description="当日收益率")
    asset_weights: Dict[str, float] = Field(default_factory=dict, description="每只资产当日市值权重")
    asset_returns: Dict[str, float] = Field(default_factory=dict, description="每只资产当日收益率")


class RebalanceEvent(BaseModel):
    """再平衡事件记录"""
    trade_date: str = Field(..., description="再平衡执行日期")
    target_weights: Dict[str, float] = Field(..., description="目标权重")
    prev_weights: Dict[str, float] = Field(..., description="再平衡前一日收盘权重")
    turnover: float = Field(..., description="当日换手率（权重变化绝对值之和 / 2）")


class PerformanceMetrics(BaseModel):
    """通用绩效指标（适用于任意净值序列）"""
    cumulative_return: float = Field(..., description="累计收益率")
    annualized_return: float = Field(..., description="年化收益率")
    annualized_volatility: float = Field(..., description="年化波动率")
    max_drawdown: float = Field(..., description="最大回撤")
    sharpe_ratio: float = Field(..., description="夏普比率（假设无风险利率为0）")
    calmar_ratio: float = Field(..., description="卡玛比率")
    sortino_ratio: float = Field(..., description="索提诺比率")
    win_rate_monthly: float = Field(..., description="月度正收益比例")
    annualized_turnover: float = Field(..., description="年化换手率")


class BacktestResult(BaseModel):
    """回测结果"""
    request: BacktestRequest
    metrics: PerformanceMetrics
    daily_records: List[BacktestDailyRecord]
    rebalance_events: List[RebalanceEvent]
    error_message: Optional[str] = Field(None, description="若回测失败，记录错误信息")
    
    def export_results(self, output_dir: str = "data_runtime/backtest", portfolio_name: str = "portfolio") -> Dict[str, Path]:
        """
        导出回测三样标准结果到文件
        
        1. metrics.json: 策略回测绩效指标
        2. rebalance_weights.csv: 再平衡日各资产权重序列
        3. daily_nav.csv: 日净值和日收益率序列
        
        :param output_dir: 输出目录
        :param portfolio_name: 组合名称（用于文件名前缀）
        :return: 导出的文件路径字典
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        result_paths = {}
        
        # 1. 导出绩效指标 (metrics.json)
        metrics_dict = self.metrics.model_dump()
        # 转换为可读格式（百分比等）
        for key in ['cumulative_return', 'annualized_return', 'annualized_volatility', 
                     'max_drawdown', 'win_rate_monthly', 'annualized_turnover']:
            if key in metrics_dict:
                metrics_dict[key] = f"{metrics_dict[key]:.4%}"
        
        metrics_file = output_path / f"{portfolio_name}_metrics.json"
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, ensure_ascii=False, indent=2)
        result_paths['metrics'] = metrics_file
        
        # 2. 导出再平衡权重 (rebalance_weights.csv)
        if self.rebalance_events:
            rows = []
            for event in self.rebalance_events:
                row = {"trade_date": event.trade_date}
                row.update(event.target_weights)
                rows.append(row)
            
            weights_df = pd.DataFrame(rows)
            weights_file = output_path / f"{portfolio_name}_rebalance_weights.csv"
            weights_df.to_csv(weights_file, index=False, encoding='utf-8-sig')
            result_paths['weights'] = weights_file
        
        # 3. 导出日净值序列 (daily_nav.csv)
        if self.daily_records:
            rows = []
            for record in self.daily_records:
                rows.append({
                    "trade_date": record.trade_date,
                    "nav": record.nav,
                    "daily_return": record.daily_return,
                })
            
            nav_df = pd.DataFrame(rows)
            nav_file = output_path / f"{portfolio_name}_daily_nav.csv"
            nav_df.to_csv(nav_file, index=False, encoding='utf-8-sig')
            result_paths['nav'] = nav_file
        
        return result_paths
