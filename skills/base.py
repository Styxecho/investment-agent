# skills/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from pathlib import Path
import json


# -----------------------------------------------------------------------------
# 1. 定义标准化的数据契约 (Data Contracts)
# -----------------------------------------------------------------------------

class SkillMeta(BaseModel):
    """
    技能执行的元数据。
    用于追踪数据来源、状态以及给 LLM 的关键提示。
    """
    source: str = Field(..., description="数据来源: 'cache', 'api', 'mock', 'calculation'")
    status: str = Field(..., description="执行状态: 'success', 'failed', 'partial'")
    target_date: str = Field(..., description="数据对应的目标日期 (YYYYMMDD)")
    message: Optional[str] = Field(None, description="给 LLM 的简短提示或错误信息")


class SkillResult(BaseModel):
    """
    所有技能执行后的标准返回结构。
    将业务数据与元数据分离，便于下游处理。
    """
    data: Dict[str, Any] = Field(default_factory=dict, description="核心业务数据 (如行情字典、计算结果)")
    meta: SkillMeta = Field(..., description="执行元数据")
    summary_hint: Optional[str] = Field(None, description="可选：预生成的自然语言摘要，供 LLM 参考")

    class Config:
        # 允许在模型中使用任意类型，防止嵌套 pandas DataFrame 时报错（虽然建议转为 dict）
        arbitrary_types_allowed = True


class SkillContext(BaseModel):
    """
    传递给技能 execute 方法的上下文对象。
    显式包含 target_date，避免技能内部依赖系统时间。
    """
    target_date: str = Field(..., description="目标日期 (YYYYMMDD)")
    # 以下字段为可选，根据具体技能需求由上游填充
    holdings: Optional[Dict[str, Any]] = Field(None, description="持仓数据字典")
    market_data: Optional[Dict[str, Any]] = Field(None, description="前置步骤获取的行情数据")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="其他动态参数")


# -----------------------------------------------------------------------------
# 2. 定义技能基类 (Base Skill)
# -----------------------------------------------------------------------------

class BaseSkill(ABC):
    """
    所有 Agent 技能的基类。
    融合了 OpenCLAW 理念：
    1. 纯函数逻辑 (输入 Context -> 输出 Result)
    2. 自带 Prompt 模板 (自动加载 prompt.txt)
    3. 标准化契约 (SkillResult)
    """

    def __init__(self, skill_dir: Optional[str] = None):
        """
        初始化技能。
        :param skill_dir: 技能所在的目录路径，用于自动加载 prompt.txt。
                          子类通常在 __init__ 中传入 __file__.parent
        """
        self.skill_dir = Path(skill_dir) if skill_dir else Path(__file__).parent
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """
        自动加载同目录下的 prompt.txt。
        如果文件不存在，返回默认提示。
        """
        prompt_path = self.skill_dir / "prompt.txt"
        if prompt_path.exists():
            try:
                return prompt_path.read_text(encoding='utf-8')
            except Exception as e:
                return f"Error loading prompt: {str(e)}"
        return "No specific prompt instructions provided for this skill."

    @property
    @abstractmethod
    def name(self) -> str:
        """技能的唯一标识符，Agent 通过它来调用"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        技能的详细描述。
        用途 1: 写入 System Prompt，告诉 LLM 什么时候用这个技能。
        用途 2: 结合 parameters，让 LLM 生成正确的调用参数。
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        定义技能需要的参数及其类型 (JSON Schema 格式)。
        注意：虽然 execute 接收 SkillContext，但这里定义的参数是用于 LLM 理解它需要提供什么信息来构建 Context。
        通常这里定义业务参数，如 'stock_code', 'date' 等。
        """
        pass

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行技能的核心逻辑。

        设计原则：
        1. 纯函数倾向：输入确定，输出确定。不修改全局状态。
        2. 防御性编程：内部捕获异常，返回 status='failed' 的 SkillResult，而不是抛出异常中断流程。
        3. 显式日期：必须使用 context.target_date，严禁使用 datetime.now()。

        :param context: 包含 target_date 和其他必要数据的上下文对象。
        :return: SkillResult 对象，包含数据和元数据。
        """
        pass