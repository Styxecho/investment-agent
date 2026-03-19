import os
import pandas as pd
from typing import Optional, List, Annotated
import operator

# --- LangChain & LangGraph 核心导入 ---
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# 从 langgraph.prebuilt 导入 create_react_agent
from langgraph.prebuilt import create_react_agent

# =================配置区域=================
DATA_DIR = "./data_external"
ALERT_THRESHOLD = 20
MODEL_NAME = "qwen2.5:3b"

# =================【写死指令区域】=================
USER_QUERY = "请检查文件 'fund_20260310.csv'，看看有没有基金回撤超过预警线？"


# ===============================================

# =================定义工具=================
@tool
def check_fund_drawdown(file_name: str) -> str:
    """
    读取指定文件名下的基金 CSV 数据，检查是否有基金回撤超过预设预警线。
    """
    safe_path = os.path.join(DATA_DIR, file_name)

    if not os.path.abspath(safe_path).startswith(os.path.abspath(DATA_DIR)):
        return "错误：非法的文件路径访问请求。"

    if not os.path.exists(safe_path):
        return f"错误：在 {DATA_DIR} 目录下未找到文件 '{file_name}'。"

    try:
        df = pd.read_csv(safe_path)
        required_cols = ['fund_name', 'fund_code', 'max_drawdown_pct']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return f"错误：CSV 文件缺少必要列: {', '.join(missing_cols)}"

        alert_funds = df[df['max_drawdown_pct'] > ALERT_THRESHOLD]

        if len(alert_funds) > 0:
            result = "⚠️【触发风控警报】⚠️\n"
            result += f"发现 {len(alert_funds)} 只基金回撤超过 {ALERT_THRESHOLD}%:\n"
            for _, row in alert_funds.iterrows():
                result += f"- {row['fund_name']} ({row['fund_code']}): 回撤 {row['max_drawdown_pct']}%\n"
            result += "建议立即复核持仓。"
            return result
        else:
            return f"✅【风控正常】\n所有基金回撤均在 {ALERT_THRESHOLD}% 以内。无需操作。"

    except Exception as e:
        return f"错误：读取或处理文件时发生异常 - {str(e)}"


# =================初始化模型=================
print(f"🚀 正在初始化本地模型: {MODEL_NAME} ...")
try:
    llm = ChatOllama(model=MODEL_NAME, temperature=0)
    print("✅ 模型连接成功")
except Exception as e:
    print(f"❌ 无法连接 Ollama: {e}")
    exit(1)

tools = [check_fund_drawdown]

# =================构建 Agent (无 Prompt 模板版)=================
system_instruction = f"""
你是一个专业的本地基金风控助手 (FundMonitor)。
工作目录限制在：{os.path.abspath(DATA_DIR)}。

任务流程:
1. 当用户要求检查基金回撤时，必须调用 `check_fund_drawdown` 工具。
2. 根据工具返回结果汇报。
3. 严禁心算，严禁访问互联网，严禁访问限制目录外的文件。
"""

print("🛠️  正在构建 ReAct Agent...")
try:
    # 【关键修正】
    # 1. 移除 prompt 参数 (避免变量名不匹配问题)
    # 2. 尝试使用 state_modifier (如果是新版)
    # 3. 如果 state_modifier 也报错，我们将采用“手动注入 SystemMessage”的策略

    # 先尝试带 state_modifier 的创建 (适用于较新的小版本)
    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=system_instruction
        )
        print("✅ Agent 构建成功 (使用 state_modifier)")
        use_system_injection = False
    except TypeError as te:
        if "state_modifier" in str(te):
            # 如果 state_modifier 也不支持，则不带 system instruction 创建
            # 我们将在 invoke 时手动注入 SystemMessage
            print("⚠️ 当前版本不支持 state_modifier，将采用手动注入 SystemMessage 模式")
            agent = create_react_agent(
                model=llm,
                tools=tools
                # 不加 prompt, 不加 state_modifier
            )
            use_system_injection = True
        else:
            raise te

except Exception as e:
    print(f"❌ 创建 Agent 失败: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

# =================执行单次任务=================
if __name__ == "__main__":
    print("\n" + "=" * 40)
    print(f"📝 执行指令: {USER_QUERY}")
    print("=" * 40 + "\n")
    print("🤖 Agent 正在思考并执行工具...\n")

    try:
        # 【关键修正】构造输入消息列表
        # 无论哪种模式，传入 {"messages": [...]} 都是最安全的
        input_messages = []

        if use_system_injection:
            # 模式 A: 手动注入 SystemMessage
            input_messages.append(SystemMessage(content=system_instruction))

        input_messages.append(HumanMessage(content=USER_QUERY))

        # 调用 Agent
        # 注意：这里必须传 {"messages": [...]}
        response = agent.invoke({"messages": input_messages})

        # 解析输出
        final_answer = "⚠️ 未获取到有效回答。"

        if isinstance(response, dict) and "messages" in response:
            messages = response["messages"]
            # 倒序查找最后一条 AI 生成的消息
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    final_answer = msg.content
                    break

            # 兜底：如果没找到 AIMessage
            if final_answer == "⚠️ 未获取到有效回答。" and len(messages) > 0:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    final_answer = last_msg.content

        print("\n" + "🔒" * 15)
        print("📊 风控分析报告")
        print("🔒" * 15)
        print(final_answer)
        print("🔒" * 15 + "\n")

    except Exception as e:
        print(f"\n❌ 执行过程中发生错误: {e}")
        import traceback

        traceback.print_exc()