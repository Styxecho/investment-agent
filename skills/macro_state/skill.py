# skills/macro_state/skill.py
"""
MacroStateSkill - V7宏观状态诊断技能（单一入口）

整合所有功能：
1. 数据检查 (check_status) - 返回最新数据时间点
2. 数据预览 (preview_upload) - 校验并预览CSV
3. 数据上传 (upload_and_analyze) - 导入+计算+分析
4. 状态查询 (query) - 查询指定日期状态
5. 最新状态 (latest) - 获取最新状态
6. 历史对比 (history_compare) - 与去年同期对比
7. 详细报告 (report) - 生成统计报告
8. 强制重算 (recalculate) - 重新执行完整pipeline

使用新的内嵌Service，不调用外部脚本。
"""

from typing import Dict, Any, Optional
import logging

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from .service import MacroStateService

logger = logging.getLogger(__name__)


class MacroStateSkill(BaseSkill):
    """
    V7宏观状态诊断技能（唯一入口）
    
    使用示例：
    # 检查数据时效
    context = SkillContext(extra_params={"mode": "check_status"})
    
    # 上传并自动分析
    context = SkillContext(extra_params={
        "mode": "upload_and_analyze",
        "file_path": "monthly_202604.csv",
        "data_type": "monthly"
    })
    
    # 查询最新状态
    context = SkillContext(extra_params={"mode": "latest"})
    
    # 查询指定日期
    context = SkillContext(extra_params={"mode": "query", "date": "20260331"})
    """
    
    def __init__(self):
        super().__init__(skill_dir=__file__)
        self.service = MacroStateService()
    
    @property
    def name(self) -> str:
        return "macro_state"
    
    @property
    def description(self) -> str:
        return (
            "V8宏观状态诊断技能。基于三维同构框架判定当前宏观状态。"
            "支持数据检查、上传、查询、报告、导出。"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [
                        "check_status", "preview_upload", "upload_and_analyze",
                        "query", "latest", "history_compare", "report", "recalculate", "export"
                    ],
                    "description": "操作模式"
                },
                "file_path": {"type": "string", "description": "CSV文件路径"},
                "data_type": {"type": "string", "enum": ["monthly", "daily"], "default": "monthly"},
                "date": {"type": "string", "pattern": "^\\d{8}$", "description": "查询日期"},
                "start_date": {"type": "string", "pattern": "^\\d{8}$"},
                "end_date": {"type": "string", "pattern": "^\\d{8}$"}
            },
            "required": ["mode"]
        }
    
    def execute(self, context: SkillContext) -> SkillResult:
        params = context.extra_params or {}
        mode = params.get("mode")
        
        if not mode:
            return self._error("缺少mode参数")
        
        try:
            if mode == "check_status":
                return self._check_status(context)
            elif mode == "preview_upload":
                return self._preview_upload(context, params)
            elif mode == "upload_and_analyze":
                return self._upload_and_analyze(context, params)
            elif mode == "query":
                return self._query(context, params)
            elif mode == "latest":
                return self._latest(context)
            elif mode == "history_compare":
                return self._history_compare(context, params)
            elif mode == "report":
                return self._report(context, params)
            elif mode == "recalculate":
                return self._recalculate(context)
            elif mode == "export":
                return self._export(context)
            else:
                return self._error(f"未知模式: {mode}")
                
        except Exception as e:
            logger.exception(f"[MacroStateSkill] 错误: {e}")
            return self._error(str(e))
    
    def _check_status(self, context: SkillContext) -> SkillResult:
        """检查数据时效性"""
        freshness = self.service.check_data_freshness()
        
        status = freshness["status"]
        db_latest = freshness["db_latest"]
        expected = freshness["expected_date"]
        missing = freshness["missing_indicators"]
        
        if status == "FRESH":
            message = f"数据已最新（截至{db_latest}）"
            summary = f"宏观数据已更新至{db_latest}，可直接查询当前状态。"
        elif status == "STALE":
            message = f"数据需要更新。最新数据：{db_latest}，预期：{expected}"
            summary = f"数据滞后，最新为{db_latest}，请上传{expected}数据。"
            if missing:
                summary += f" 缺失指标: {', '.join(missing)}"
        else:
            message = "数据库为空，请先上传数据"
            summary = "宏观数据库为空，请先上传CSV数据。"
        
        return SkillResult(
            data=freshness,
            meta=SkillMeta(
                source="check",
                status="success",
                target_date=context.target_date,
                message=message
            ),
            summary_hint=summary
        )
    
    def _preview_upload(self, context: SkillContext, params: Dict) -> SkillResult:
        """预览上传数据"""
        file_path = params.get("file_path")
        data_type = params.get("data_type", "monthly")
        
        if not file_path:
            return self._error("需要file_path参数")
        
        preview = self.service.preview_upload(file_path, data_type)
        
        return SkillResult(
            data=preview,
            meta=SkillMeta(
                source="preview",
                status="success" if preview["success"] else "failed",
                target_date=context.target_date,
                message=f"校验完成: {len(preview['errors'])} 错误, {len(preview['warnings'])} 警告"
            ),
            summary_hint=f"数据预览: {preview['summary'].get('total_records', 0)} 条记录"
        )
    
    def _upload_and_analyze(self, context: SkillContext, params: Dict) -> SkillResult:
        """上传并自动分析"""
        file_path = params.get("file_path")
        data_type = params.get("data_type", "monthly")
        
        if not file_path:
            return self._error("需要file_path参数")
        
        result = self.service.upload_data(file_path, data_type, auto_recalc=True)
        
        if result["success"]:
            # 获取最新状态
            latest = self.service.query_latest_state()
            
            summary = f"上传完成，导入{result['imported_count']}条记录。"
            if latest:
                summary += f" 最新状态（{latest.get('publish_date')}）: {latest.get('macro_regime')}"
            
            return SkillResult(
                data={"upload": result, "latest_state": latest},
                meta=SkillMeta(
                    source="upload",
                    status="success",
                    target_date=context.target_date,
                    message=result["message"]
                ),
                summary_hint=summary
            )
        else:
            return SkillResult(
                data=result,
                meta=SkillMeta(
                    source="upload",
                    status="failed",
                    target_date=context.target_date,
                    message=result["message"]
                ),
                summary_hint=f"上传失败: {result['message']}"
            )
    
    def _query(self, context: SkillContext, params: Dict) -> SkillResult:
        """查询指定日期"""
        date = params.get("date", context.target_date)
        
        state = self.service.query_state(date)
        
        if not state:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="query",
                    status="failed",
                    target_date=date,
                    message=f"未找到{date}的状态"
                ),
                summary_hint=f"{date}暂无宏观状态数据"
            )
        
        summary = (
            f"{date}: {state['growth_state']} | "
            f"{state['inflation_state']} | {state['liquidity_level']} → "
            f"{state['macro_regime']}"
        )
        
        if state.get("warnings"):
            summary += f" [WARN]"
        
        return SkillResult(
            data=state,
            meta=SkillMeta(
                source="query",
                status="success",
                target_date=date,
                message="查询成功"
            ),
            summary_hint=summary
        )
    
    def _latest(self, context: SkillContext) -> SkillResult:
        """获取最新状态"""
        state = self.service.query_latest_state()
        
        if not state:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="query",
                    status="failed",
                    target_date=context.target_date,
                    message="数据库为空"
                ),
                summary_hint="暂无宏观状态数据"
            )
        
        date = state.get("publish_date", "")
        regime = state.get("macro_regime", "")
        
        summary = f"最新宏观状态（{date}）: {regime}"
        if state.get("warnings"):
            summary += " [WARN]"
        
        return SkillResult(
            data=state,
            meta=SkillMeta(
                source="query",
                status="success",
                target_date=date,
                message=f"最新: {regime}"
            ),
            summary_hint=summary
        )
    
    def _history_compare(self, context: SkillContext, params: Dict) -> SkillResult:
        """与去年同期对比"""
        date = params.get("date", context.target_date)
        
        # 计算去年同期
        current_year = int(date[:4])
        current_month = int(date[4:6])
        last_year_date = f"{current_year-1}{date[4:]}"
        
        current = self.service.query_state(date)
        last_year = self.service.query_state(last_year_date)
        
        comparison = {
            "current_date": date,
            "current_state": current,
            "comparison_date": last_year_date,
            "comparison_state": last_year,
            "changes": {}
        }
        
        if current and last_year:
            changes = []
            if current.get("macro_regime") != last_year.get("macro_regime"):
                changes.append(f"象限: {last_year.get('macro_regime')} → {current.get('macro_regime')}")
            if current.get("growth_state") != last_year.get("growth_state"):
                changes.append(f"增长: {last_year.get('growth_state')} → {current.get('growth_state')}")
            if current.get("inflation_state") != last_year.get("inflation_state"):
                changes.append(f"通胀: {last_year.get('inflation_state')} → {current.get('inflation_state')}")
            
            comparison["changes"] = changes
        
        return SkillResult(
            data=comparison,
            meta=SkillMeta(
                source="analysis",
                status="success",
                target_date=date,
                message=f"对比完成"
            ),
            summary_hint=f"{date} vs {last_year_date}: {len(comparison['changes'])} 处变化"
        )
    
    def _report(self, context: SkillContext, params: Dict) -> SkillResult:
        """生成统计报告"""
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        
        report = self.service.generate_report(start_date, end_date)
        
        return SkillResult(
            data=report,
            meta=SkillMeta(
                source="analysis",
                status="success",
                target_date=context.target_date,
                message="报告生成成功"
            ),
            summary_hint=(
                f"宏观状态报告: {report.get('total_months', 0)}个月, "
                f"主导: {report.get('dominant_regime', 'N/A')}"
            )
        )
    
    def _recalculate(self, context: SkillContext) -> SkillResult:
        """强制重新计算V8并自动导出CSV"""
        result = self.service.recalculate()
        
        # 自动导出CSV
        export_result = None
        if result["success"]:
            export_result = self.service.export_to_csv()
        
        return SkillResult(
            data={"recalc": result, "export": export_result},
            meta=SkillMeta(
                source="calculation",
                status="success" if result["success"] else "failed",
                target_date=context.target_date,
                message=result["message"]
            ),
            summary_hint=(
                f"V8重算: {result.get('factor_count', 0)} 因子, "
                f"{result.get('state_count', 0)} 状态"
                + (f", CSV已导出" if export_result and export_result.get('success') else "")
            )
        )
    
    def _export(self, context: SkillContext) -> SkillResult:
        """仅导出CSV（不重新计算）"""
        result = self.service.export_only()
        
        return SkillResult(
            data=result,
            meta=SkillMeta(
                source="export",
                status="success" if result["success"] else "failed",
                target_date=context.target_date,
                message=result["message"]
            ),
            summary_hint=(
                f"导出: {result.get('record_count', 0)} 条记录"
                if result["success"]
                else f"导出失败: {result.get('message', '')}"
            )
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
macro_state_skill = MacroStateSkill()
