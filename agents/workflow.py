# agents/workflow.py
"""
构建 LangGraph 工作流 (适配最新版 LangGraph API)。
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from functools import partial

from agents.state import AgentState
from agents.nodes import chat_node, tool_node
from config.settings import settings

# --- 0. 导入工具 ---
from skills.portfolio.tools import calculate_portfolio_pnl

ALL_TOOLS = [calculate_portfolio_pnl]


def build_agent_graph():
    """
    创建并编译 Agent 图。
    """
    # --- 1. 初始化 LLM ---
    print(f"🚀 正在加载模型: {settings.OLLAMA_MODEL}")
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
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

    print("✅ Agent 工作流构建完成！")
    return app


# 实例化
agent_app = build_agent_graph()