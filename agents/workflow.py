# agents/workflow.py
"""
构建 LangGraph 工作流 (集成 Qwen 云端大模型 via DashScope)
"""
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from functools import partial

from agents.state import AgentState
from agents.nodes import chat_node, tool_node
from agents.qwen_adapter import QwenChatModel
from config.settings import settings

# --- 0. 导入工具 ---
from agents.tools import ALL_TOOLS


def build_agent_graph():
    """
    创建并编译 Agent 图。
    """
    # --- 1. 初始化 LLM ---
    print(f"[LOAD] Loading model: {settings.QWEN_MODEL}")
    
    # 检查 API Key 配置
    if not settings.QWEN_API_KEY or settings.QWEN_API_KEY == 'YOUR_API_KEY_HERE':
        raise ValueError("QWEN_API_KEY 未配置，请检查 .env 文件")
    
    # 创建 Qwen 适配器实例
    llm = QwenChatModel(
        model_name=settings.QWEN_MODEL,
        api_key=settings.QWEN_API_KEY,
        temperature=0,
    )

    # --- 2. 绑定工具 ---
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    # --- 3. 配置节点 (依赖注入) ---
    configured_chat_node = partial(chat_node, llm=llm_with_tools)
    configured_tool_node = tool_node

    # --- 4. 初始化图 ---
    workflow = StateGraph(AgentState)

    # --- 5. 添加节点 ---
    # 注意：这里的名称 "chatbot" 和 "tools" 必须与 should_continue 返回的字符串完全一致
    workflow.add_node("chatbot", configured_chat_node)
    workflow.add_node("tools", configured_tool_node)

    # --- 6. 设置入口点 ---
    workflow.set_entry_point("chatbot")

    # --- 7. 定义条件边 (路由逻辑) ---
    def should_continue(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]

        # 如果有工具调用，返回 "tools" (必须匹配 add_node 中的名称)
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"

        # 否则结束，返回 "__end__" (或者直接返回 END 常量，但在 path 函数中通常返回字符串)
        # 在新版中，如果返回 END 常量对象也可以，但返回字符串 "tools" 或 "__end__" 最稳妥
        return "__end__"

    # 【关键修复】新版 API：只保留 source 和 path，删除 mapping
    workflow.add_conditional_edges(
        source="chatbot",
        path=should_continue
        # ❌ 删除了 mapping 参数
    )

    # --- 8. 工具执行完后，回到 chatbot ---
    workflow.add_edge("tools", "chatbot")

    # --- 9. 编译图 ---
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    print("[OK] Agent workflow build completed!")
    return app


# 实例化
agent_app = build_agent_graph()
