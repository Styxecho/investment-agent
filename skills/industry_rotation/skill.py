# skills/industry_rotation/skill.py
"""
IndustryRotationSkill - 行业轮动中观选池技能

Phase 2.4 核心技能，整合TIE映射、多周期动量、排名稳定性、宏观协同四个引擎，
生成可交易的行业候选池。

使用示例:
    # 检查数据完备性
    context = SkillContext(extra_params={"mode": "check_status", "date": "20260430"})
    
    # 运行完整pipeline
    context = SkillContext(extra_params={"mode": "run_pipeline", "date": "20260430"})
    
    # 查询最新候选池
    context = SkillContext(extra_params={"mode": "latest_pool"})
    
    # 查询指定日期候选池
    context = SkillContext(extra_params={"mode": "query_pool", "date": "20260430"})
"""

from typing import Dict, Any, Optional
import logging

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from .service import IndustryRotationService

logger = logging.getLogger(__name__)


class IndustryRotationSkill(BaseSkill):
    """行业轮动中观选池技能（Phase 2.4）"""
    
    def __init__(self):
        super().__init__(skill_dir=__file__)
        self.service = IndustryRotationService()
    
    @property
    def name(self) -> str:
        return "industry_rotation"
    
    @property
    def description(self) -> str:
        return (
            "行业轮动卫星策略中观选池技能（Phase 2.4）。"
            "基于TIE映射、多周期动量、排名稳定性和宏观协同，"
            "生成可交易的行业ETF候选池。"
            "支持完整pipeline执行、分步执行和结果查询。"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [
                        "check_status", "run_pipeline",
                        "tie_mapping", "momentum", "stability", "macro_synergy",
                        "latest_pool", "query_pool"
                    ],
                    "description": "操作模式"
                },
                "date": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "目标日期 YYYYMMDD（check_status/run_pipeline/query_pool需要）"
                }
            },
            "required": ["mode"]
        }
    
    def execute(self, context: SkillContext) -> SkillResult:
        params = context.extra_params or {}
        mode = params.get("mode")
        
        if not mode:
            return self._error("缺少mode参数")
        
        # 获取目标日期（如果未指定，使用context.target_date）
        target_date = params.get("date", context.target_date)
        
        try:
            if mode == "check_status":
                return self._check_status(context, target_date)
            elif mode == "run_pipeline":
                return self._run_pipeline(context, target_date)
            elif mode == "tie_mapping":
                return self._tie_mapping(context)
            elif mode == "momentum":
                return self._momentum(context, target_date)
            elif mode == "stability":
                return self._stability(context, params)
            elif mode == "macro_synergy":
                return self._macro_synergy(context, params)
            elif mode == "latest_pool":
                return self._latest_pool(context)
            elif mode == "query_pool":
                return self._query_pool(context, target_date)
            else:
                return self._error(f"未知模式: {mode}")
        
        except Exception as e:
            logger.exception(f"[IndustryRotationSkill] 错误: {e}")
            return self._error(str(e))
    
    def _check_status(self, context: SkillContext, target_date: str) -> SkillResult:
        """检查数据完备性"""
        issues = self.service.check_data_completeness(target_date)
        
        if issues:
            return SkillResult(
                data={"issues": issues, "complete": False},
                meta=SkillMeta(
                    source="check",
                    status="success",
                    target_date=target_date,
                    message=f"数据不完备，发现{len(issues)}个问题"
                ),
                summary_hint=f"数据不完备: {'; '.join(issues[:3])}"
            )
        
        return SkillResult(
            data={"issues": [], "complete": True},
            meta=SkillMeta(
                source="check",
                status="success",
                target_date=target_date,
                message="数据完备，可执行pipeline"
            ),
            summary_hint=f"{target_date}数据完备，可直接运行行业轮动pipeline"
        )
    
    def _run_pipeline(self, context: SkillContext, target_date: str) -> SkillResult:
        """运行完整pipeline"""
        result = self.service.run_full_pipeline(target_date, save_results=True)
        
        if not result.get('success'):
            return SkillResult(
                data=result,
                meta=SkillMeta(
                    source="pipeline",
                    status="failed",
                    target_date=target_date,
                    message=result.get('summary', 'Pipeline执行失败')
                ),
                summary_hint=result.get('summary', '执行失败')
            )
        
        final_pool = result.get('final_pool', [])
        macro_result = result.get('macro_result', {})
        
        # 生成自然语言摘要
        if macro_result.get('is_extreme'):
            summary = (
                f"{target_date} 极端象限({macro_result.get('current_regime')})，"
                f"清仓卫星仓位。"
            )
        else:
            # 取Top 5展示
            top5 = final_pool[:5] if len(final_pool) >= 5 else final_pool
            top5_str = ', '.join([
                f"{item.get('sw_name', item['index_code'])}"
                f"({item.get('composite_score_adj', item.get('composite_score', 0)):.2f})"
                for item in top5
            ])
            summary = (
                f"{target_date} 候选池{len(final_pool)}个行业，"
                f"宏观象限: {macro_result.get('current_regime', '未知')}。"
                f"Top5: {top5_str}"
            )
        
        return SkillResult(
            data=result,
            meta=SkillMeta(
                source="pipeline",
                status="success",
                target_date=target_date,
                message=result.get('summary', 'Pipeline执行成功')
            ),
            summary_hint=summary
        )
    
    def _tie_mapping(self, context: SkillContext) -> SkillResult:
        """仅运行TIE映射"""
        result = self.service.run_tie_only()
        
        coverage = result.get('coverage', {})
        tier_dist = result.get('tier_distribution', {})
        
        return SkillResult(
            data=result,
            meta=SkillMeta(
                source="tie_engine",
                status="success",
                target_date=context.target_date,
                message=f"TIE映射完成: {coverage.get('mapped_industries', 0)}个行业有映射"
            ),
            summary_hint=(
                f"TIE映射: Core={tier_dist.get('core', 0)}, "
                f"Backup={tier_dist.get('backup', 0)}, "
                f"覆盖{coverage.get('mapped_industries', 0)}/"
                f"{coverage.get('total_industries', 31)}行业"
            )
        )
    
    def _momentum(self, context: SkillContext, target_date: str) -> SkillResult:
        """仅运行动量计算"""
        result = self.service.run_momentum_only(target_date)
        
        latest_ym = result.get('latest_ym', '')
        scores = result.get('latest_monthly_scores', [])
        ma60_count = sum(1 for m in result.get('ma60_status', []) if m.get('above_ma60'))
        
        # Top 3展示
        top3 = scores[:3] if len(scores) >= 3 else scores
        top3_str = ', '.join([
            f"{s.get('sw_name', s['index_code'])}({s['rs_score']:.2f})"
            for s in top3
        ])
        
        return SkillResult(
            data=result,
            meta=SkillMeta(
                source="momentum_engine",
                status="success",
                target_date=target_date,
                message=f"动量计算完成，最新月份: {latest_ym}"
            ),
            summary_hint=(
                f"{latest_ym}动量: MA60上方{ma60_count}个，"
                f"Top3: {top3_str}"
            )
        )
    
    def _stability(self, context: SkillContext, params: Dict) -> SkillResult:
        """仅运行稳定性分析（需要前置的monthly_history和industry_mapping）"""
        # 稳定性分析需要前置结果，通常不在单独调用时使用
        # 这里返回提示信息
        return SkillResult(
            data={"note": "稳定性分析需要前置的动量历史数据和TIE映射结果"},
            meta=SkillMeta(
                source="stability_engine",
                status="success",
                target_date=context.target_date,
                message="请使用run_pipeline获取完整结果"
            ),
            summary_hint="稳定性分析需结合动量和TIE结果，建议运行完整pipeline"
        )
    
    def _macro_synergy(self, context: SkillContext, params: Dict) -> SkillResult:
        """仅运行宏观协同（需要前置的selected_pool）"""
        return SkillResult(
            data={"note": "宏观协同需要前置的优势池结果"},
            meta=SkillMeta(
                source="macro_synergy",
                status="success",
                target_date=context.target_date,
                message="请使用run_pipeline获取完整结果"
            ),
            summary_hint="宏观协同需结合优势池结果，建议运行完整pipeline"
        )
    
    def _latest_pool(self, context: SkillContext) -> SkillResult:
        """获取最新候选池"""
        pool = self.service.get_latest_pool(pool_type='final')
        latest_date = self.service.dm.get_latest_pool_date()
        
        if not pool:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="query",
                    status="failed",
                    target_date=context.target_date,
                    message="暂无候选池数据"
                ),
                summary_hint="数据库中暂无行业轮动候选池，请先运行pipeline"
            )
        
        top3 = pool[:3] if len(pool) >= 3 else pool
        top3_str = ', '.join([
            f"{item.get('sw_name', item.get('index_code', ''))}"
            f"({item.get('composite_score_adj', item.get('composite_score', 0)):.2f})"
            for item in top3
        ])
        
        return SkillResult(
            data={"pool": pool, "date": latest_date},
            meta=SkillMeta(
                source="query",
                status="success",
                target_date=latest_date or context.target_date,
                message=f"最新候选池({latest_date}): {len(pool)}个行业"
            ),
            summary_hint=f"最新候选池({latest_date}): {len(pool)}个，Top3: {top3_str}"
        )
    
    def _query_pool(self, context: SkillContext, target_date: str) -> SkillResult:
        """查询指定日期的候选池"""
        pool = self.service.get_pool_by_date(target_date, pool_type='final')
        
        if not pool:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="query",
                    status="failed",
                    target_date=target_date,
                    message=f"未找到{target_date}的候选池"
                ),
                summary_hint=f"{target_date}暂无候选池数据"
            )
        
        top3 = pool[:3] if len(pool) >= 3 else pool
        top3_str = ', '.join([
            f"{item.get('sw_name', item.get('index_code', ''))}"
            f"({item.get('composite_score_adj', item.get('composite_score', 0)):.2f})"
            for item in top3
        ])
        
        return SkillResult(
            data={"pool": pool, "date": target_date},
            meta=SkillMeta(
                source="query",
                status="success",
                target_date=target_date,
                message=f"{target_date}候选池: {len(pool)}个行业"
            ),
            summary_hint=f"{target_date}候选池: {len(pool)}个，Top3: {top3_str}"
        )
    
    def _error(self, message: str, target_date: str = "") -> SkillResult:
        """返回错误结果"""
        return SkillResult(
            data={},
            meta=SkillMeta(
                source="validation",
                status="failed",
                target_date=target_date,
                message=message
            ),
            summary_hint=f"错误: {message}"
        )


# 单例
industry_rotation_skill = IndustryRotationSkill()
