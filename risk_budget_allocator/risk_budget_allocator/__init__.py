"""
Risk Budget Allocator package.
"""

from .allocator import AssetAllocator
from .risk_budget_allocator_class import RiskBudgetAllocator
from .target_vol_allocator import TargetVolAllocator
from .manual_allocator import ManualAllocator
from .config import load_config, validate_config, init_user_config
from .report import generate_report

__all__ = [
    "AssetAllocator",
    "RiskBudgetAllocator",
    "TargetVolAllocator",
    "ManualAllocator",
    "load_config",
    "validate_config",
    "init_user_config",
    "generate_report",
]

__version__ = "0.1.0"
