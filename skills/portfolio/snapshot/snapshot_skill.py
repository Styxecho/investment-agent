# skills/portfolio/snapshot/snapshot_skill.py
"""
Snapshot Skill: 投资组合快照持久化
职责：接收 PortfolioSkill 的计算结果，将其保存到 SQLite 数据库中。
"""
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, date

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from data_external.db.repositories import PortfolioSnapshotRepository
from utils.logger import logger


class SnapshotSkill(BaseSkill):
    """
    组合快照归档技能。
    将 PortfolioSkill 输出的 PortfolioTimeSeries 或 PortfolioSnapshot 数据持久化到数据库。
    """

    def __init__(self):
        super().__init__(skill_dir=str(Path(__file__).parent))

    @property
    def name(self) -> str:
        return "portfolio_snapshot"

    @property
    def description(self) -> str:
        return (
            "将投资组合分析结果保存到数据库中，用于历史回溯和趋势分析。"
            "输入为 PortfolioSkill 的计算结果，输出为保存状态。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "portfolio_time_series": {
                "type": "object",
                "description": "PortfolioSkill 输出的时序计算结果（含 snapshots 列表）"
            },
            "portfolio_id": {
                "type": "string",
                "description": "组合标识符，默认 'default'"
            }
        }

    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行快照保存。

        预期 context.extra_params 中包含：
        - portfolio_time_series: dict (PortfolioTimeSeries 的 model_dump 结果)
        - portfolio_id: str (可选，默认 'default')
        """
        try:
            extra = context.extra_params or {}
            portfolio_id = extra.get("portfolio_id", "default")
            ts_data = extra.get("portfolio_time_series")

            if not ts_data:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=context.target_date,
                        message="缺少 portfolio_time_series 数据，无法保存快照。"
                    )
                )

            snapshots = ts_data.get("snapshots", [])
            if not snapshots:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=context.target_date,
                        message="portfolio_time_series 中无快照数据。"
                    )
                )

            repo = PortfolioSnapshotRepository()
            saved_count = 0

            for snapshot in snapshots:
                trade_date_str = snapshot.get("trade_date")
                if not trade_date_str:
                    logger.warning(f"[SnapshotSkill] 跳过无日期快照: {snapshot}")
                    continue

                # 解析日期
                if isinstance(trade_date_str, str):
                    trade_date = datetime.strptime(trade_date_str, "%Y%m%d").date()
                elif isinstance(trade_date_str, date):
                    trade_date = trade_date_str
                else:
                    logger.warning(f"[SnapshotSkill] 无法解析日期: {trade_date_str}")
                    continue

                repo.save_snapshot(
                    trade_date=trade_date,
                    snapshot_data=snapshot,
                    portfolio_id=portfolio_id
                )
                saved_count += 1

            summary = f"成功保存 {saved_count} 条组合快照 ({portfolio_id})。"
            logger.info(f"[SnapshotSkill] {summary}")

            return SkillResult(
                data={"saved_count": saved_count, "portfolio_id": portfolio_id},
                meta=SkillMeta(
                    source="db",
                    status="success",
                    target_date=context.target_date,
                    message=summary
                ),
                summary_hint=summary
            )

        except Exception as e:
            logger.exception(f"[SnapshotSkill] 保存快照失败: {e}")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="system_error",
                    status="failed",
                    target_date=context.target_date,
                    message=f"保存组合快照失败: {str(e)}"
                ),
                summary_hint="保存快照时发生系统错误。"
            )
