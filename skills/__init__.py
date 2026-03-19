# skills/__init__.py
from .market_data import get_market_data_skill
# 未来可以从其他模块导入
# from .news import get_news_skill
# from .financial_report import get_report_skill

# 所有可用技能的列表 (Agent 启动时会扫描这个列表)
AVAILABLE_SKILLS = [
    get_market_data_skill,
    # get_news_skill,
]

def get_skill_by_name(name: str):
    """
    根据名称查找技能。
    Agent 核心逻辑将调用此方法。
    """
    for skill in AVAILABLE_SKILLS:
        if skill.name == name:
            return skill
    raise ValueError(f"Skill '{name}' not found. Available skills: {[s.name for s in AVAILABLE_SKILLS]}")

__all__ = ["AVAILABLE_SKILLS", "get_skill_by_name"]