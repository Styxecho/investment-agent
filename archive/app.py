import os
import pandas as pd
import streamlit as st
from typing import List

# --- LangChain & LangGraph 核心导入 ---
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 从 langgraph.prebuilt 导入 create_react_agent
from langgraph.prebuilt import create_react_agent

# =================页面配置=================
st.set_page_config(
    page_title="FundMonitor 风控助手",
    page_icon="🛡️",
    layout="wide"
)

# =================侧边栏配置=================
with st.sidebar:
    st.title("⚙️ 系统配置")

    DATA_DIR = st.text_input("数据目录", value="./data_external")
    ALERT_THRESHOLD = st.number_input("预警阈值 (%)", value=20.0, step=0.1)
    MODEL_NAME = st.text_input("Ollama 模型名称", value="qwen2.5:3b")

    st.markdown("---")
    st.info(
        "💡 提示：\n1. 确保 Ollama 服务已启动\n2. 确保模型已下载 (`ollama pull {model}`)\n3. 数据目录下需包含 CSV 文件")

    if st.button("🗑️ 清空对话历史"):
        st.session_state.messages = []
        st.session_state.agent_ready = False
        st.rerun()


# =================定义工具 (带缓存装饰器)=================
# 注意：在 Streamlit 中，工具定义最好放在主逻辑外或受控范围内
@tool
def check_fund_drawdown(file_name: str) -> str:
    """
    读取指定文件名下的基金 CSV 数据，检查是否有基金回撤超过预设预警线。
    """
    # 使用侧边栏配置的目录
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


# =================初始化 Session State=================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    st.session_state.agent = None
    st.session_state.agent_error = None


# =================初始化 Agent (单次运行)=================
def init_agent():
    try:
        llm = ChatOllama(model=MODEL_NAME, temperature=0)
        # 简单测试连接
        llm.invoke("Hi")

        system_instruction = f"""
你是一个专业的本地基金风控助手 (FundMonitor)。
工作目录限制在：{os.path.abspath(DATA_DIR)}。
当前预警阈值为：{ALERT_THRESHOLD}%。

任务流程:
1. 当用户要求检查基金回撤时，必须调用 `check_fund_drawdown` 工具。
2. 根据工具返回结果汇报。
3. 严禁心算，严禁访问互联网，严禁访问限制目录外的文件。
4. 回答要简洁专业。
"""
        tools = [check_fund_drawdown]

        # 尝试构建 Agent
        try:
            agent = create_react_agent(
                model=llm,
                tools=tools,
                state_modifier=system_instruction
            )
            return agent, None
        except TypeError as te:
            if "state_modifier" in str(te):
                # 降级模式
                agent = create_react_agent(model=llm, tools=tools)
                # 将 system_instruction 存入 session_state 供后续手动注入使用
                st.session_state.system_instruction = system_instruction
                st.session_state.use_system_injection = True
                return agent, None
            else:
                raise te

    except Exception as e:
        return None, str(e)


# 每次配置变化时重新初始化 Agent
if st.session_state.agent is None or st.session_state.get('last_model') != MODEL_NAME or st.session_state.get(
        'last_dir') != DATA_DIR:
    with st.spinner("🚀 正在初始化模型和 Agent..."):
        agent, error = init_agent()
        if error:
            st.session_state.agent_error = error
            st.session_state.agent = None
        else:
            st.session_state.agent = agent
            st.session_state.last_model = MODEL_NAME
            st.session_state.last_dir = DATA_DIR
            st.session_state.agent_error = None

# =================主界面=================
st.title("🛡️ FundMonitor 智能风控助手")
st.caption("基于 LangGraph + Ollama 的本地化基金数据分析 Agent")

# 显示错误信息
if st.session_state.agent_error:
    st.error(f"❌ **Agent 初始化失败**: {st.session_state.agent_error}")
    st.info("💡 请检查侧边栏的模型名称是否正确，以及 Ollama 服务是否正常运行。")
    st.stop()

# 渲染历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# =================处理用户输入=================
if prompt := st.chat_input("请输入指令，例如：'检查 fund_20260310.csv 的风控情况'"):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 生成回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤖 **Agent 正在思考并调用工具...**")

        try:
            # 构造输入消息列表
            input_messages = []

            # 处理 System Message 注入逻辑
            if st.session_state.get('use_system_injection', False):
                sys_inst = st.session_state.get('system_instruction', "")
                input_messages.append(SystemMessage(content=sys_inst))

            # 添加历史对话 (过滤掉 role 字段，只保留 LangChain 消息对象)
            # 注意：st.session_state.messages 存的是 dict，我们需要转回 LangChain 对象
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    input_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    # 这里简化处理，实际生产中可能需要区分 ToolMessage
                    # 但 create_react_agent 通常能处理简单的 AI 历史
                    # 为了严谨，我们只把当前的 prompt 作为最新输入，
                    # 如果需要完整多轮记忆，需要更复杂的状态管理。
                    # *修正策略*：Streamlit 的 chat_message 通常只存文本。
                    # 为了保持 ReAct 的完整性，最稳妥的方式是：
                    # 每次只传当前的 HumanMessage，依靠 Agent 内部状态？
                    # 不，create_react_agent 是无状态的图，必须传入完整 messages 列表。
                    # 因此，我们需要在 session_state 中存储完整的 LangChain 消息对象，而不仅仅是 dict。
                    pass

                    # 【重要修正】：为了支持多轮对话中的工具调用历史，
            # 我们应该在 session_state 中直接存储 LangChain 的消息对象列表，而不是简单的 dict。
            # 但为了兼容上面的渲染逻辑，我们做一个转换。
            # 更好的做法：重构 session_state 存储结构。

            # 让我们采用最简单的“无状态”模拟“有状态”：
            # 每次只发送当前的 HumanMessage + (可选) SystemMessage。
            # 如果用户问“刚才那个文件...”，Agent 如果没有历史记录是答不上来的。
            # 所以必须传递历史。

            # 重新构建完整的 LangChain 消息列表用于 invoke
            full_langchain_messages = []
            if st.session_state.get('use_system_injection', False):
                full_langchain_messages.append(SystemMessage(content=st.session_state.get('system_instruction', "")))

            # 从 session_state 恢复历史 (假设我们存的是 LangChain 对象)
            # 为了代码简洁，我们修改 session_state 的存储方式：直接存 LangChain 对象列表
            # 但上面渲染代码用的是 dict。
            # 折中方案：只在 session_state 存 dict 用于展示，每次 invoke 时重新构建？
            # 不行，ToolMessage 的复杂结构很难通过 dict 完美还原。

            # **最终方案**：
            # 在 session_state 中专门维护一个 `lc_messages` 列表 (LangChain Messages)。
            if "lc_messages" not in st.session_state:
                st.session_state.lc_messages = []

            # 同步：如果这是第一轮，lc_messages 为空
            # 将新的 HumanMessage 加入 lc_messages
            new_human_msg = HumanMessage(content=prompt)

            if st.session_state.get('use_system_injection', False):
                # 如果是手动注入模式，SystemMessage 不存入 lc_messages 永久历史，只在 invoke 时临时加
                temp_invoke_messages = [SystemMessage(content=st.session_state.get('system_instruction', ""))]
                temp_invoke_messages.extend(st.session_state.lc_messages)
                temp_invoke_messages.append(new_human_msg)
                invoke_input = {"messages": temp_invoke_messages}
            else:
                # 如果用了 state_modifier，SystemMessage 在图内部
                st.session_state.lc_messages.append(new_human_msg)
                invoke_input = {"messages": st.session_state.lc_messages}

            # 调用 Agent
            response = st.session_state.agent.invoke(invoke_input)

            # 获取响应中的 messages
            if isinstance(response, dict) and "messages" in response:
                response_messages = response["messages"]

                # 提取最后一条 AI 消息作为展示
                final_ai_content = "⚠️ 未获取到回答。"
                for msg in reversed(response_messages):
                    if isinstance(msg, AIMessage):
                        final_ai_content = msg.content
                        break

                # 更新历史：
                # 我们需要将这一轮产生的所有 NEW 消息追加到 lc_messages 中
                # 如何判断哪些是新的？response_messages 包含了输入的 messages + 新生成的。
                # 简单做法：直接用 response_messages 替换/更新 lc_messages
                # 但要注意 SystemMessage 的问题。

                if st.session_state.get('use_system_injection', False):
                    # 手动注入模式下，response_messages 第一个可能是 SystemMessage (取决于实现) 或者没有
                    # 我们只保留 Human, AIMessage, ToolMessage
                    clean_messages = [m for m in response_messages if not isinstance(m, SystemMessage)]
                    st.session_state.lc_messages = clean_messages
                else:
                    st.session_state.lc_messages = response_messages

                # 更新用于展示的 messages (dict 格式)
                st.session_state.messages.append({"role": "assistant", "content": final_ai_content})

                # 渲染回答
                message_placeholder.markdown(final_ai_content)
            else:
                message_placeholder.markdown("❌ 响应格式异常")

        except Exception as e:
            message_placeholder.markdown(f"❌ **执行错误**: {str(e)}")
            # 调试信息
            with st.expander("查看详细错误"):
                st.exception(e)