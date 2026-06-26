# skills/macro_factor/skill.py
"""
MacroFactorSkill - 宏观因子计算与查询技能

对外接口：
1. compute模式：批量计算并存储因子值
2. query模式：查询已计算的因子值
"""

from typing import Dict, Any, Optional
import logging

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from .service import MacroFactorService
from .schema import ComputeRequest, QueryRequest

logger = logging.getLogger(__name__)


class MacroFactorSkill(BaseSkill):
    """
    宏观因子计算与查询技能
    
    使用示例：
    # 计算模式
    context = SkillContext(
        target_date="20241231",
        extra_params={
            "mode": "compute",
            "start_date": "20200101",
            "end_date": "20241231",
            "indicator_codes": ["CN_PMI_MFG_M", "CN_CPI_YOY_M"],
            "factor_types": ["level", "change"]
        }
    )
    result = macro_factor_skill.execute(context)
    
    # 查询模式
    context = SkillContext(
        target_date="20240331",
        extra_params={
            "mode": "query",
            "indicator_codes": [],
            "factor_types": ["level"]
        }
    )
    result = macro_factor_skill.execute(context)
    """
    
    def __init__(self):
        super().__init__(skill_dir=__file__)
        self.service = MacroFactorService()
    
    @property
    def name(self) -> str:
        return "macro_factor"
    
    @property
    def description(self) -> str:
        return (
            "计算和查询宏观经济指标的标准化因子值。"
            "支持两种模式："
            "1) compute: 批量计算指定日期范围内的因子（单边HP滤波 + Z-score），结果存入数据库；"
            "2) query: 查询已计算的特定日期因子值。"
            "每个指标输出水平因子（level，周期项的Z-score）和变化率因子（change，周期项增速的Z-score）。"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["compute", "query"],
                    "description": "compute=计算并存储, query=查询已存储"
                },
                "indicator_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "指标代码列表，为空则处理所有活跃指标"
                },
                "start_date": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "计算开始日期（YYYYMMDD），compute模式必需"
                },
                "end_date": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "计算结束日期（YYYYMMDD），compute模式必需"
                },
                "factor_types": {
                    "type": "array",
                    "items": {"enum": ["level", "change"]},
                    "default": ["level", "change"],
                    "description": "要计算或查询的因子类型"
                }
            },
            "required": ["mode"]
        }
    
    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行宏观因子计算或查询
        
        Args:
            context: SkillContext，extra_params包含mode等参数
            
        Returns:
            SkillResult
        """
        params = context.extra_params or {}
        mode = params.get("mode")
        
        if not mode:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="validation",
                    status="failed",
                    target_date=context.target_date,
                    message="缺少必需参数：mode（compute 或 query）"
                ),
                summary_hint="请指定模式：compute（计算）或 query（查询）"
            )
        
        try:
            if mode == "compute":
                return self._execute_compute(context, params)
            elif mode == "query":
                return self._execute_query(context, params)
            else:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=context.target_date,
                        message=f"未知模式：{mode}"
                    )
                )
        except Exception as e:
            logger.exception(f"[MacroFactorSkill] 执行错误: {e}")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="system_error",
                    status="failed",
                    target_date=context.target_date,
                    message=f"宏观因子服务错误：{str(e)}"
                ),
                summary_hint="系统错误，请稍后重试"
            )
    
    def _execute_compute(self, context: SkillContext, params: Dict) -> SkillResult:
        """执行批量计算"""
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        
        if not start_date or not end_date:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="validation",
                    status="failed",
                    target_date=context.target_date,
                    message="compute模式需要 start_date 和 end_date 参数"
                )
            )
        
        request = ComputeRequest(
            start_date=start_date,
            end_date=end_date,
            indicator_codes=params.get("indicator_codes"),
            factor_types=params.get("factor_types", ["level", "change"])
        )
        
        result = self.service.compute_factors(request)
        
        success_count = len(result["success"])
        fail_count = len(result["failed"])
        total = result["total_records"]
        
        status = "success" if fail_count == 0 else "partial"
        message = f"计算完成：成功 {success_count} 个指标，失败 {fail_count} 个，共 {total} 条记录"
        
        summary = f"宏观因子计算完成。处理了 {success_count} 个指标的历史数据（{start_date}-{end_date}），生成 {total} 条因子记录。"
        if fail_count > 0:
            summary += f" 失败指标：{', '.join(result['failed'].keys())}。"
        
        return SkillResult(
            data=result,
            meta=SkillMeta(
                source="calculation",
                status=status,
                target_date=context.target_date,
                message=message
            ),
            summary_hint=summary
        )
    
    def _execute_query(self, context: SkillContext, params: Dict) -> SkillResult:
        """执行查询"""
        target_date = params.get("target_date", context.target_date)
        
        request = QueryRequest(
            target_date=target_date,
            indicator_codes=params.get("indicator_codes"),
            factor_types=params.get("factor_types", ["level"])
        )
        
        matrix = self.service.query_factors(request)
        
        # 生成摘要
        factor_count = sum(len(v) for v in matrix.factors.values())
        indicator_count = len(matrix.factors)
        
        summary = f"{target_date} 宏观因子查询：{indicator_count} 个指标，{factor_count} 个因子值。"
        
        return SkillResult(
            data=matrix.model_dump(),
            meta=SkillMeta(
                source="database",
                status="success",
                target_date=target_date,
                message=f"查询成功：{indicator_count} 个指标"
            ),
            summary_hint=summary
        )


# 导出单例
macro_factor_skill = MacroFactorSkill()
