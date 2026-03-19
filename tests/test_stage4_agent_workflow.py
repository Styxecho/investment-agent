# tests/test_agent_workflow.py
"""
【阶段 4 集成测试】Agent 工作流交互测试脚本。
用于验证 LangGraph 流程、工具调用及 LLM 响应是否正常。
未来第 5/6 阶段将基于此逻辑封装为 API 或定时任务。
"""
import sys
import os

# --- 1. 路径设置：确保能导入根目录下的模块 ---
# 将项目根目录添加到 Python 路径
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from agents.workflow import agent_app
from langchain_core.messages import HumanMessage


def run_interactive_test():
    """
    启动一个简单的命令行交互循环，测试 Agent。
    """
    print("🤖 === 投资助理 Agent 测试模式 (按 'q' 退出) ===")
    print("💡 提示：尝试问 '今天盈亏如何？' 或 '帮我计算一下 20240316 的持仓'")

    # 配置线程 ID，用于 LangGraph 的记忆功能 (MemorySaver)
    # 每次运行脚本可以使用不同的 thread_id 来隔离会话，或者固定一个来测试多轮对话
    config = {"configurable": {"thread_id": "test_session_001"}}

    while True:
        try:
            user_input = input("\n👤 用户: ").strip()

            if user_input.lower() in ['q', 'quit', 'exit']:
                print("👋 再见！测试结束。")
                break

            if not user_input:
                continue

            # 构造输入消息
            messages = [HumanMessage(content=user_input)]

            print("🤖 思考中...", end="\r")

            # 调用 Agent 图
            # stream 模式可以实时看到节点执行过程（可选，这里直接用 invoke 获取最终结果）
            response = agent_app.invoke({"messages": messages}, config=config)

            # 提取最后一条 AI 消息
            final_message = response["messages"][-1]

            print(f"🤖 助理: {final_message.content}")

        except KeyboardInterrupt:
            print("\n👋 强制退出。")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_interactive_test()