# skills/macro_state/__init__.py
"""
宏观状态Skill模块

V7宏观状态诊断技能 - 单一入口

使用示例:
from skills.macro_state import macro_state_skill
from skills.base import SkillContext

# 检查数据时效
result = macro_state_skill.execute(SkillContext(
    extra_params={"mode": "check_status"}
))

# 查询最新状态
result = macro_state_skill.execute(SkillContext(
    extra_params={"mode": "latest"}
))

# 上传并分析
result = macro_state_skill.execute(SkillContext(
    extra_params={
        "mode": "upload_and_analyze",
        "file_path": "monthly_202604.csv",
        "data_type": "monthly"
    }
))
"""

from .skill import MacroStateSkill, macro_state_skill
from .service import MacroStateService, macro_state_service
from .data_manager import DataManager
from .factor_calculator import FactorCalculator
from .state_engine import StateEngine

__all__ = [
    'MacroStateSkill',
    'macro_state_skill',
    'MacroStateService',
    'macro_state_service',
    'DataManager',
    'FactorCalculator',
    'StateEngine'
]
