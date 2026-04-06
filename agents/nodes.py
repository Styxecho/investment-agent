# agents/nodes.py
"""
定义 Agent 的具体执行节点。
集成 Qwen 模型和已封装好的 Skills 工具。
"""
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from agents.state import AgentState
from typing import Any

# --- 1. 导入已封装的工具 ---
from agents.tools import get_market_data, analyze_portfolio
# 将所有可用工具放入列表
tools = [get_market_data, analyze_portfolio]

# --- 2. 定义 System Prompt ---
SYSTEM_PROMPT = """
你是一个专业的投资助理。你的任务是根据用户的提问，调用工具查询数据并给出专业的分析。

可用工具：
- get_market_data: 获取股票或 ETF 的行情数据（收盘价、昨收价、涨跌幅）。当用户询问某只股票的价格、涨跌情况时使用。
- analyze_portfolio: 分析投资组合的当日表现。输入持仓列表，输出总市值、当日盈亏、收益率及个股贡献。

注意事项：
1. 如果用户询问"今天"、"昨天"或具体日期的数据，请推断出对应的 'YYYYMMDD' 格式日期。
2. 如果用户没有指定日期，工具会自动使用当前日期。
3. 必须依据工具返回的数据回答，严禁编造数字。
4. 回答时请使用清晰的 Markdown 格式（如表格、粗体）展示数据。
5. 如果工具报错，请如实告知用户。
"""

# --- 3. 定义节点函数 ---

def chat_node(state: AgentState, llm: Any) -> dict:
    """
    思考节点：参数 llm 由 workflow.py 通过 partial 注入 (已绑定工具)。
    """
    messages = state["messages"]

    # 注入 System Prompt
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    if not has_system:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # 使用传入的 llm 参数，而不是全局变量
    response = llm.invoke(messages)

    return {"messages": [response]}


def tool_node(state: AgentState) -> dict:
    """
    工具执行节点：使用全局 tools 列表
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 如果没有工具调用，直接返回空
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_outputs = []

    for tc in last_message.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_call_id = tc["id"]

        print(f"🧠 [Agent] 正在执行工具：{tool_name}, 参数：{tool_args}")

        # 路由到具体的工具函数
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        result_content = ""

        if selected_tool:
            try:
                # 直接 invoke 工具对象。LangChain 的 @tool 装饰器会自动处理参数字典到函数参数的映射
                result_content = selected_tool.invoke(tool_args)
            except Exception as e:
                result_content = f"工具执行异常：{str(e)}"
        else:
            result_content = f"错误：未找到名为 '{tool_name}' 的工具。"

        tool_outputs.append(ToolMessage(
            content=str(result_content),
            tool_call_id=tool_call_id,
            name=tool_name
        ))

    return {"messages": tool_outputs}
