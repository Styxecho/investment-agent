import os
import sys
from typing import Annotated, TypedDict, Dict, Any

# --- 关键步骤：确保能导入 skills 模块 ---
# 将当前脚本所在目录添加到系统路径，以便能 import skills
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 现在可以导入您写好的 Skill 了！
from skills.calculator import calculate_portfolio_metrics, load_portfolio_config

from langgraph.graph import StateGraph, END
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate

# --- 配置部分 ---
LLM_MODEL = "qwen2.5:7b"


# --- 1. 定义状态 (State) ---
class AgentState(TypedDict):
    """定义工作流中传递的数据结构"""
    metrics_result: Dict[str, Any]  # 直接从 skill 获取的计算结果
    report_text: str  # AI 生成的报告
    error_message: str


# --- 2. 定义节点 (Nodes) ---

def node_calculate_wrapper(state: AgentState) -> AgentState:
    """
    节点 A: 包装器 - 直接调用已定义的 Skill
    不再重复写 pandas/sqlite 逻辑，而是复用 skills/calculator.py
    """
    print("🔄 [步骤 1/2] 调用 Skill: calculate_portfolio_metrics ...")

    try:
        # 【核心复用点】直接调用您写好的函数
        result = calculate_portfolio_metrics()

        if "error" in result:
            return {
                **state,
                "metrics_result": {},
                "error_message": f"Skill 计算报错: {result['error']}"
            }

        print(f"✅ Skill 执行成功：总市值 {result.get('total_market_value', 0):,.2f}")

        return {
            **state,
            "metrics_result": result,
            "error_message": ""
        }

    except Exception as e:
        return {
            **state,
            "metrics_result": {},
            "error_message": f"调用 Skill 异常: {str(e)}"
        }


def node_generate_report(state: AgentState) -> AgentState:
    """
    节点 B: 调用 LLM 生成报告
    """
    if state["error_message"]:
        print("⚠️ 上一步计算失败，跳过 AI 生成。")
        return {**state, "report_text": "因数据计算失败，无法生成报告。", "error_message": state["error_message"]}

    print("🤖 [步骤 2/2] 呼叫 AI 撰写报告...")

    metrics = state["metrics_result"]
    details = metrics.get("details", [])

    # 构造 Prompt (逻辑不变，只是数据来源变成了 skill 的返回值)
    holdings_str = "\n".join([
        f"- {item['name']} ({item['code']}): 现价 {item['current_price']:.3f}, 今日 {item['daily_change_pct']:.2f}%, 日盈/亏 {item['daily_profit']:,.2f}, 总盈/亏 {item['total_profit']:,.2f}"
        for item in details
    ])

    prompt_template = """
    你是一位专业、冷静且富有洞察力的私人投资顾问。
    请根据以下用户的 ETF 投资组合数据，撰写一份《每日投资日报》。

    【数据概览】
    - 日期：{date}
    - 组合总市值：{total_market_value:,.2f} 元
    - 今日盈亏：{total_daily_profit:,.2f} 元 ({daily_return_pct})
    - 累计投入：{total_cost:,.2f} 元
    - 累计总盈亏：{total_profit:,.2f} 元 ({total_return_pct})

    【持仓明细】
    {holdings_table}

    【写作要求】
    1. **语气风格**：专业、客观、有温度。
    2. **结构**：今日综述 -> 亮点与不足 -> 操作建议。
    3. **格式**：Markdown，适当使用 Emoji。
    4. **长度**：300-500 字。

    请开始撰写：
    """

    full_prompt = prompt_template.format(
        date=metrics['date'],
        total_market_value=metrics['total_market_value'],
        total_daily_profit=metrics['total_daily_profit'],
        daily_return_pct=metrics['daily_return_pct'],
        total_cost=metrics['total_cost'],
        total_profit=metrics['total_profit'],
        total_return_pct=metrics['total_return_pct'],
        holdings_table=holdings_str
    )

    try:
        llm = Ollama(model=LLM_MODEL)
        report = llm.invoke(full_prompt)
        print("✅ AI 报告生成成功！")
        return {**state, "report_text": report, "error_message": ""}

    except Exception as e:
        return {**state, "report_text": "", "error_message": f"AI 生成失败: {str(e)}"}


# --- 3. 构建工作流 ---

def create_workflow():
    workflow = StateGraph(AgentState)

    # 添加节点 (现在节点内部只是简单的函数调用)
    workflow.add_node("calculator_skill", node_calculate_wrapper)
    workflow.add_node("reporter", node_generate_report)

    workflow.set_entry_point("calculator_skill")
    workflow.add_edge("calculator_skill", "reporter")
    workflow.add_edge("reporter", END)

    return workflow.compile()


# --- 4. 运行入口 ---

if __name__ == "__main__":
    print("🚀 启动智能投资助手 (模块化版) ...")

    app = create_workflow()
    initial_state = {
        "metrics_result": {},
        "report_text": "",
        "error_message": ""
    }

    final_state = app.invoke(initial_state)

    print("\n" + "=" * 60)
    print("📰 您的每日投资日报")
    print("=" * 60)

    if final_state["error_message"]:
        print(f"⚠️ 系统警告: {final_state['error_message']}")

    if final_state["report_text"]:
        print(final_state["report_text"])

    print("=" * 60)