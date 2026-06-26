"""
Configuration loading for risk budget allocator.
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path

from .schema import AssetsConfig, PortfoliosConfig


PACKAGE_DIR = Path(__file__).parent.parent
DEFAULT_CONFIG_DIR = PACKAGE_DIR / "config"


def load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_configs(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge user config into default config."""
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def load_config(user_config_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Load default config and merge with user config if available.

    Args:
        user_config_dir: Directory containing user_assets.yaml and user_portfolios.yaml

    Returns:
        Merged configuration dictionary
    """
    default_assets = load_yaml(str(DEFAULT_CONFIG_DIR / "default_assets.yaml"))
    default_portfolios = load_yaml(str(DEFAULT_CONFIG_DIR / "default_portfolios.yaml"))

    config = {
        "assets": default_assets,
        "portfolios": default_portfolios,
    }

    if user_config_dir and os.path.exists(user_config_dir):
        user_assets_path = os.path.join(user_config_dir, "user_assets.yaml")
        user_portfolios_path = os.path.join(user_config_dir, "user_portfolios.yaml")

        if os.path.exists(user_assets_path):
            user_assets = load_yaml(user_assets_path)
            config["assets"] = merge_configs(config["assets"], user_assets)

        if os.path.exists(user_portfolios_path):
            user_portfolios = load_yaml(user_portfolios_path)
            config["portfolios"] = merge_configs(config["portfolios"], user_portfolios)

    return config


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate config and convert to schema objects."""
    assets_config = AssetsConfig(**config["assets"])
    portfolios_config = PortfoliosConfig(**config["portfolios"])

    # Validate risk budgets sum to 1 for non-manual portfolios
    for pid, portfolio in portfolios_config.portfolios.items():
        if portfolio.allocator == "manual":
            continue
        rb = portfolio.risk_budget
        total = rb.equity + rb.bond + rb.commodity
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Portfolio {pid} risk budget sums to {total}, expected 1.0")

    return {
        "assets": assets_config,
        "portfolios": portfolios_config,
    }


def init_user_config(target_dir: str = "config/allocation") -> None:
    """
    Copy default config files to user config directory.

    Args:
        target_dir: Target directory for user config files
    """
    os.makedirs(target_dir, exist_ok=True)

    target_assets = os.path.join(target_dir, "user_assets.yaml")
    target_portfolios = os.path.join(target_dir, "user_portfolios.yaml")

    if not os.path.exists(target_assets):
        with open(target_assets, "w", encoding="utf-8") as f:
            f.write("# User asset configuration\n")
            f.write("# Uncomment and modify to override defaults\n")
            f.write("# assets:\n")
            f.write("#   - code: \"000985.CSI\"\n")
            f.write("#     name: \"中证全指\"\n")
            f.write("#     asset_class: \"equity\"\n")

    if not os.path.exists(target_portfolios):
        with open(target_portfolios, "w", encoding="utf-8") as f:
            f.write("# User portfolio configuration\n")
            f.write("# Uncomment and modify to override defaults\n")
            f.write("# portfolios:\n")
            f.write("#   conservative:\n")
            f.write("#     risk_budget:\n")
            f.write("#       equity: 0.20\n")
            f.write("#       bond: 0.70\n")
            f.write("#       commodity: 0.10\n")
