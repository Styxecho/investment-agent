"""
Analysis router
"""
from typing import Optional
from fastapi import APIRouter
from dashboard.backend.schemas import NarrativeResponse
from dashboard.backend.services.state_service import get_state_by_date

router = APIRouter(prefix="/analysis", tags=["analysis"])


# Templates for narrative generation
REGIME_TEMPLATES = {
    "完美扩张": "当前处于{regime}阶段。增长维度{growth_state}，通胀保持{inflation_state}，流动性{liquidity_state}。这是一个经济景气度较高、企业盈利改善、市场流动性充裕的环境，通常有利于风险资产表现。",
    "强势复苏": "当前处于{regime}阶段。经济正在加速复苏，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。此时企业盈利修复确定性高，成长风格通常占优。",
    "弱复苏": "当前处于{regime}阶段。经济虽有复苏迹象但力度偏弱，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。市场可能呈现结构性行情，需精选板块。",
    "宽衰退": "当前处于{regime}阶段。经济处于衰退期，但流动性宽松提供支撑，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。防御性板块和价值风格相对占优。",
    "失速衰退": "当前处于{regime}阶段。经济衰退且流动性收紧，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。这是风险最高的宏观环境，建议降低仓位、增配避险资产。",
    "典型滞胀": "当前处于{regime}阶段。经济停滞而通胀高企，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。类现金资产和抗通胀品种相对占优。",
    "极端滞胀": "当前处于{regime}阶段。经济衰退且高通胀，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。这是最为恶劣的宏观组合，建议大幅减仓。",
    "过热期": "当前处于{regime}阶段。经济扩张但通胀压力显现，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。需警惕政策收紧风险，周期板块可能最后冲顶。",
    "类衰退过渡": "当前处于{regime}阶段。经济处于衰退边缘，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。市场方向不明，建议观望或小幅试探。",
    "震荡/观望": "当前处于{regime}阶段。宏观信号混合，{growth_state}，通胀{inflation_state}，流动性{liquidity_state}。缺乏明确的趋势性机会，建议控制仓位、灵活应对。",
}

DIMENSION_TEMPLATES = {
    "growth": {
        "overview": "增长方面，制造业PMI为{pmi_raw}，处于{pmi_level}区间；工业增加值周期项为{iav_cycle}，显示{iav_level}态势。整体增长动能{growth_assessment}。",
        "assessment": {
            "扩张": "较强",
            "中性": "平稳",
            "收缩": "偏弱",
        }
    },
    "inflation": {
        "overview": "通胀方面，核心CPI同比{ccpi_raw}%，处于{inf_level}水平；PPI方向{ppi_dir}。{cost_divergence_hint}",
        "cost_divergence": "上下游价格传导出现背离，需关注中游企业盈利压力。",
        "no_divergence": "上下游价格走势一致，传导顺畅。",
    },
    "liquidity": {
        "overview": "流动性方面，M2周期项{m2_cycle}，社融周期项{sfs_cycle}，整体处于{liq_level}状态。短端利率{short_rate_hint}。",
        "tight": "处于相对高位",
        "loose": "处于相对低位",
        "neutral": "保持平稳",
    }
}

STRATEGY_TEMPLATES = {
    "完美扩张": ["顺周期板块（消费、金融、周期）通常表现较好", "可适当提升仓位", "关注估值修复机会"],
    "强势复苏": ["成长风格占优", "关注盈利修复确定性高的行业", "可适当承担风险"],
    "弱复苏": ["结构性行情为主", "精选细分板块", "控制总体仓位"],
    "宽衰退": ["防御性板块（公用事业、必选消费）相对占优", "价值风格优于成长", "保持中等偏低仓位"],
    "失速衰退": ["大幅降低权益仓位", "增配债券、黄金等避险资产", "现金为王"],
    "典型滞胀": ["类现金资产和抗通胀品种", "减少权益 exposure", "关注大宗商品"],
    "极端滞胀": ["大幅减仓或清仓", "配置黄金、抗通胀债券", "等待环境改善"],
    "过热期": ["周期板块可能最后冲顶", "警惕政策收紧风险", "逐步降低仓位"],
    "类衰退过渡": ["观望为主", "小幅试探性布局", "等待明确信号"],
    "震荡/观望": ["控制仓位", "灵活应对", "关注结构性机会"],
}


@router.get("/narrative/{date}", response_model=NarrativeResponse)
async def generate_narrative(date: str):
    """Generate narrative analysis for specific date"""
    state = get_state_by_date(date)
    
    if state is None:
        return {
            "date": date,
            "regime": "未知",
            "overview": "该日期无数据",
            "growth_detail": "",
            "inflation_detail": "",
            "liquidity_detail": "",
            "warnings": [],
        }
    
    regime = state["regime"]
    growth = state["growth"]
    inflation = state["inflation"]
    liquidity = state["liquidity"]
    warnings = state["warnings"]
    
    # Generate overview
    overview_template = REGIME_TEMPLATES.get(regime, REGIME_TEMPLATES["震荡/观望"])
    overview = overview_template.format(
        regime=regime,
        growth_state=growth["state"],
        inflation_state=inflation["state"],
        liquidity_state=liquidity["state"],
    )
    
    # Generate dimension details
    growth_detail = _generate_growth_detail(state)
    inflation_detail = _generate_inflation_detail(state)
    liquidity_detail = _generate_liquidity_detail(state)
    
    # Strategy implication
    strategy_points = STRATEGY_TEMPLATES.get(regime, [])
    strategy_text = "\n".join([f"• {point}" for point in strategy_points])
    
    return {
        "date": date,
        "regime": regime,
        "overview": overview,
        "growth_detail": growth_detail,
        "inflation_detail": inflation_detail,
        "liquidity_detail": liquidity_detail,
        "warnings": warnings,
        "strategy_implication": strategy_text,
    }


def _generate_growth_detail(state):
    """Generate growth dimension detail"""
    raw = state["growth"]["raw_values"]
    factor = state["growth"]["factor_values"]
    
    pmi = raw.get("pmi", "N/A")
    pmi_level = "扩张" if pmi and pmi >= 50 else "收缩" if pmi else "未知"
    
    iav = raw.get("iav", "N/A")
    iav_cycle = factor.get("iav_z", "N/A")
    iav_level = "扩张" if iav_cycle and iav_cycle >= 0 else "收缩" if iav_cycle else "未知"
    
    assessment = DIMENSION_TEMPLATES["growth"]["assessment"].get(
        state["growth"]["level"], "平稳"
    )
    
    return DIMENSION_TEMPLATES["growth"]["overview"].format(
        pmi_raw=pmi if pmi != "N/A" else "无数据",
        pmi_level=pmi_level,
        iav_cycle=iav_cycle if iav_cycle != "N/A" else "无数据",
        iav_level=iav_level,
        growth_assessment=assessment,
    )


def _generate_inflation_detail(state):
    """Generate inflation dimension detail"""
    raw = state["inflation"]["raw_values"]
    
    ccpi = raw.get("ccpi", "N/A")
    inf_level = state["inflation"]["level"]
    
    # Check for cost divergence in warnings
    has_divergence = any("成本传导背离" in w for w in state["warnings"])
    divergence_hint = (
        DIMENSION_TEMPLATES["inflation"]["cost_divergence"] 
        if has_divergence 
        else DIMENSION_TEMPLATES["inflation"]["no_divergence"]
    )
    
    return DIMENSION_TEMPLATES["inflation"]["overview"].format(
        ccpi_raw=ccpi if ccpi != "N/A" else "无数据",
        inf_level=inf_level,
        ppi_dir=state["inflation"]["direction"],
        cost_divergence_hint=divergence_hint,
    )


def _generate_liquidity_detail(state):
    """Generate liquidity dimension detail"""
    factor = state["liquidity"]["factor_values"]
    
    m2_cycle = factor.get("m2_z", "N/A")
    sfs_cycle = factor.get("sfs_z", "N/A")
    liq_level = state["liquidity"]["level"]
    
    return DIMENSION_TEMPLATES["liquidity"]["overview"].format(
        m2_cycle=m2_cycle if m2_cycle != "N/A" else "无数据",
        sfs_cycle=sfs_cycle if sfs_cycle != "N/A" else "无数据",
        liq_level=liq_level,
        short_rate_hint="保持稳定",
    )
