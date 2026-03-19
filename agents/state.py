# agents/state.py
"""
定义 Agent 的运行状态 (State)。
LangGraph 依靠 State 在节点之间传递数据。
"""
from typing import Annotated, List, TypedDict
import operator
from langchain_core.messages import BaseMessage


# 定义消息列表的合并策略：新消息追加到列表末尾
def merge_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    return left + right


class AgentState(TypedDict):
    """
    Agent 的全局状态。
    messages: 存储对话历史 (System, Human, AI, Tool 消息)。
    """
    # 使用 Annotated 指定合并策略，确保多轮对话消息不丢失
    messages: Annotated[List[BaseMessage], operator.add]

    # 未来扩展字段示例:
    # current_date: str
    # debug_info: dict