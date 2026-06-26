# skills/macro_factor/__init__.py
"""
宏观因子Skill模块
"""

from .skill import MacroFactorSkill, macro_factor_skill
from .service import MacroFactorService, macro_factor_service
from .schema import FactorValue, FactorMatrix, FactorConfig

__all__ = [
    'MacroFactorSkill',
    'macro_factor_skill',
    'MacroFactorService', 
    'macro_factor_service',
    'FactorValue',
    'FactorMatrix',
    'FactorConfig'
]
