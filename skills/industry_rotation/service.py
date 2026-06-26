# skills/industry_rotation/service.py
"""
IndustryRotationService - 行业轮动中观选池业务编排层

整合TIE映射、动量计算、稳定性分析、宏观协同四个引擎，
提供完整的Phase 2.4候选池生成pipeline。
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .data_manager import IndustryRotationDataManager
from .tie_engine import TIEEngine
from .momentum_engine import MomentumEngine
from .stability_engine import StabilityEngine
from .macro_synergy import MacroSynergyEngine

logger = logging.getLogger(__name__)


class IndustryRotationService:
    """行业轮动服务编排层"""
    
    def __init__(self):
        self.dm = IndustryRotationDataManager()
        self.tie_engine = TIEEngine(self.dm)
        self.momentum_engine = MomentumEngine(self.dm)
        self.stability_engine = StabilityEngine(self.dm)
        self.macro_engine = MacroSynergyEngine(self.dm)
    
    def check_data_completeness(self, target_date: str) -> List[str]:
        """检查数据完备性"""
        return self.dm.check_data_completeness(target_date)
    
    def run_full_pipeline(self, target_date: str, 
                          save_results: bool = True) -> Dict[str, Any]:
        """
        执行完整的Phase 2.4候选池生成pipeline
        
        Args:
            target_date: 目标日期 YYYYMMDD
            save_results: 是否保存结果到数据库
        
        Returns:
            {
                'success': bool,
                'target_date': str,
                'tie_result': Dict,
                'momentum_result': Dict,
                'stability_result': Dict,
                'macro_result': Dict,
                'final_pool': List[Dict],
                'summary': str
            }
        """
        logger.info(f"=" * 60)
        logger.info(f"Phase 2.4 行业轮动候选池生成 - {target_date}")
        logger.info(f"=" * 60)
        
        # Step 1: 数据完备性检查
        issues = self.check_data_completeness(target_date)
        if issues:
            logger.error(f"数据不完备: {issues}")
            return {
                'success': False,
                'target_date': target_date,
                'error': '数据不完备',
                'issues': issues,
                'summary': f"数据不完备: {'; '.join(issues)}"
            }
        
        # Step 2: TIE映射
        logger.info("Step 1/4: TIE映射引擎")
        tie_result = self.tie_engine.run()
        
        # Step 3: 动量计算
        logger.info("Step 2/4: 多周期动量引擎")
        momentum_result = self.momentum_engine.run(target_date)
        
        # Step 4: 稳定性与优势池
        logger.info("Step 3/4: 排名稳定性引擎")
        stability_result = self.stability_engine.run(
            monthly_history=momentum_result['monthly_history'],
            industry_mapping=tie_result['industry_mapping']
        )
        
        # Step 5: 宏观协同
        logger.info("Step 4/4: 宏观协同引擎")
        macro_result = self.macro_engine.run(
            selected_pool=stability_result['selected_pool'],
            target_date=target_date
        )
        
        # Step 6: 保存结果
        if save_results and macro_result['final_pool']:
            self._save_results(target_date, macro_result, tie_result)
        
        # Step 7: 生成摘要
        summary = self._generate_summary(
            tie_result, momentum_result, stability_result, macro_result
        )
        
        logger.info(f"Pipeline完成: {summary}")
        
        return {
            'success': True,
            'target_date': target_date,
            'tie_result': tie_result,
            'momentum_result': momentum_result,
            'stability_result': stability_result,
            'macro_result': macro_result,
            'final_pool': macro_result['final_pool'],
            'summary': summary
        }
    
    def run_tie_only(self) -> Dict[str, Any]:
        """仅运行TIE映射"""
        return self.tie_engine.run()
    
    def run_momentum_only(self, target_date: str) -> Dict[str, Any]:
        """仅运行动量计算"""
        return self.momentum_engine.run(target_date)
    
    def run_stability_only(self, monthly_history, industry_mapping) -> Dict[str, Any]:
        """仅运行稳定性分析"""
        return self.stability_engine.run(monthly_history, industry_mapping)
    
    def run_macro_only(self, selected_pool: List[Dict], target_date: str) -> Dict[str, Any]:
        """仅运行宏观协同"""
        return self.macro_engine.run(selected_pool, target_date)
    
    def get_latest_pool(self, pool_type: str = 'final') -> Optional[List[Dict]]:
        """获取最新候选池"""
        latest_date = self.dm.get_latest_pool_date()
        if not latest_date:
            return None
        return self.dm.load_pool(latest_date, pool_type)
    
    def get_pool_by_date(self, date: str, pool_type: str = 'final') -> Optional[List[Dict]]:
        """获取指定日期的候选池"""
        return self.dm.load_pool(date, pool_type)
    
    def _save_results(self, target_date: str, macro_result: Dict, 
                     tie_result: Dict) -> None:
        """保存候选池到数据库"""
        final_pool = macro_result['final_pool']
        current_regime = macro_result.get('current_regime', '')
        
        # 保存最终候选池
        self.dm.save_pool(
            date=target_date,
            pool_type='final',
            industries=final_pool,
            macro_regime=current_regime
        )
        
        # 保存优势池（降权前）
        # 可以从stability_result获取，但这里简化处理
        
        logger.info(f"候选池已保存: {target_date}")
    
    def _generate_summary(self, tie_result, momentum_result, 
                         stability_result, macro_result) -> str:
        """生成执行摘要"""
        parts = []
        
        # TIE映射
        coverage = tie_result['coverage']
        parts.append(
            f"TIE映射: {coverage['mapped_industries']}/"
            f"{coverage['total_industries']}行业有ETF映射"
        )
        
        # 动量
        latest_ym = momentum_result.get('latest_ym', '')
        ma60_count = sum(1 for m in momentum_result.get('ma60_status', []) 
                        if m.get('above_ma60'))
        parts.append(f"动量: 最新{latest_ym}, MA60上方{ma60_count}个行业")
        
        # 稳定性
        pool_stats = stability_result.get('pool_stats', {})
        parts.append(
            f"优势池: {pool_stats.get('selected', 0)}/"
            f"{pool_stats.get('total', 0)}行业"
        )
        
        # 宏观协同
        if macro_result.get('is_extreme'):
            parts.append(f"宏观: 极端象限({macro_result['current_regime']})→清仓")
        else:
            final_pool = macro_result.get('final_pool', [])
            downsided = macro_result.get('downside_stats', {}).get('downsided', 0)
            parts.append(
                f"宏观: {macro_result.get('current_regime', '未知')}, "
                f"候选池{len(final_pool)}个, 降权{downsided}个"
            )
        
        return ' | '.join(parts)
