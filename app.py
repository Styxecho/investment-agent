# app.py
"""
【阶段 5 - MVP 交互界面】
智能投资助理 - Streamlit 入口文件。
当前为单文件模式，未来可根据复杂度重构为包。
"""
import streamlit as st
import sys
import os
from datetime import datetime

# --- 路径设置 ---
root_dir = os.path.abspath(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


# --- 导入核心组件 ---
@st.cache_resource(show_spinner=False)
def load_agent_app():
    """
    缓存加载 Agent 应用，避免每次交互都重新导入模块。
    """
    try:
        from agents.workflow import agent_app
        return agent_app
    except ImportError as e:
        st.error(f"❌ 无法加载 Agent: {e}")
        st.stop()


agent_app = load_agent_app()


# --- 核心逻辑函数 (未来可提取到 utils/) ---
def run_agent_query(prompt: str, thread_id: str):
    """
    调用 LangGraph Agent 并返回响应。
    """
    from langchain_core.messages import HumanMessage

    config = {"configurable": {"thread_id": thread_id}}
    input_messages = [HumanMessage(content=prompt)]

    response = agent_app.invoke({"messages": input_messages}, config=config)

    if "messages" in response and len(response["messages"]) > 0:
        last_msg = response["messages"][-1]
        return last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    return "未收到有效响应。"


# --- 页面配置 ---
st.set_page_config(page_title="📈 智能投资助理", page_icon="📊", layout="wide")

# --- 侧边栏 ---
with st.sidebar:
    st.title("⚙️ 控制中心")
    thread_id = st.text_input("会话 ID", value="mvp_session_01", help="修改以开启新对话")

    st.divider()
    if st.button("🗑️ 清除记忆"):
        if "messages" in st.session_state:
            st.session_state.messages = []
        st.rerun()

    st.markdown("**状态**:\n- 🟢 系统就绪\n- 🤖 Agent 已加载")

# --- 主界面 ---
st.title("📈 智能投资助理 MVP")
st.markdown("尝试提问：*'今天持仓盈亏如何？'* 或 *'分析一下 20240317 的表现'*")

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理输入
if prompt := st.chat_input("输入您的问题..."):
    # 用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI 响应
    with st.chat_message("assistant"):
        with st.spinner("🤔 正在分析市场数据..."):
            try:
                response_text = run_agent_query(prompt, thread_id)
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except Exception as e:
                error_text = f"❌ 出错了：{str(e)}"
                st.error(error_text)
                st.session_state.messages.append({"role": "assistant", "content": error_text})
                import traceback

                traceback.print_exc()

# 页脚
st.caption(f"运行时间：{datetime.now().strftime('%H:%M:%S')} | 线程：`{thread_id}`")