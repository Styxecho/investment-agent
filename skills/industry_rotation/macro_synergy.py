# skills/industry_rotation/macro_synergy.py
"""
宏观协同引擎

基于当前宏观象限，对优势池行业进行协同性降权处理。
严格遵循Phase 2.4/2.5方法论V5.0。
"""

import pandas as pd
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# 极端象限定义：清仓
EXTREME_REGIMES = ['失速衰退', '极端滞胀']

# 降权系数
DOWNSIDE_WEIGHT = 0.8

# 行业周期敏感度标签（静态预设，基于常识）
# TODO: 未来应替换为基于历史Beta或营收对GDP弹性的量化计算
CYCLE_SENSITIVITY = {
    # === 高敏感度（强周期） ===
    '801050': 'high',   # 有色金属
    '801040': 'high',   # 钢铁
    '801950': 'high',   # 煤炭
    '801710': 'high',   # 建筑材料
    '801890': 'high',   # 机械设备
    '801880': 'high',   # 汽车
    '801180': 'high',   # 房地产
    '801720': 'high',   # 建筑装饰
    '801140': 'high',   # 轻工制造
    
    # === 中敏感度（科技制造） ===
    '801030': 'medium', # 基础化工
    '801730': 'medium', # 电力设备
    '801080': 'medium', # 电子
    '801750': 'medium', # 计算机
    '801760': 'medium', # 传媒
    '801770': 'medium', # 通信
    '801230': 'medium', # 综合
    
    # === 低敏感度（防御型） ===
    '801120': 'low',    # 食品饮料
    '801150': 'low',    # 医药生物
    '801160': 'low',    # 公用事业
    '801170': 'low',    # 交通运输
    '801780': 'low',    # 银行
    '801790': 'low',    # 非银金融
    '801200': 'low',    # 商贸零售
    '801970': 'low',    # 环保
    '801980': 'low',    # 美容护理
    '801130': 'low',    # 纺织服饰
    '801210': 'low',    # 社会服务
    '801010': 'low',    # 农林牧渔
}


class MacroSynergyEngine:
    """宏观协同引擎"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def run(self, selected_pool: List[Dict], target_date: str) -> Dict[str, Any]:
        """
        执行宏观协同处理
        
        Args:
            selected_pool: stability_engine输出的优势池
            target_date: 目标日期 YYYYMMDD
        
        Returns:
            {
                'is_extreme': bool,
                'current_regime': str,
                'final_pool': List[Dict],  # 降权后的候选池
                'downside_stats': {
                    'total': N,
                    'downsided': N,
                    'cleared': bool
                }
            }
        """
        if not selected_pool:
            return {
                'is_extreme': False,
                'current_regime': '',
                'final_pool': [],
                'downside_stats': {'total': 0, 'downsided': 0, 'cleared': False}
            }
        
        # Step 1: 读取宏观状态
        macro_state = self.dm.load_macro_state(target_date)
        
        if not macro_state:
            logger.warning(f"未找到{target_date}的宏观状态，跳过宏观协同")
            return {
                'is_extreme': False,
                'current_regime': '未知',
                'final_pool': selected_pool,
                'downside_stats': {'total': len(selected_pool), 'downsided': 0, 'cleared': False}
            }
        
        current_regime = macro_state.get('macro_regime', '')
        is_extreme = any(regime in current_regime for regime in EXTREME_REGIMES)
        
        logger.info(f"当前宏观象限: {current_regime}, 极端象限: {is_extreme}")
        
        # Step 2: 极端象限 → 清仓
        if is_extreme:
            final_pool = []
            for item in selected_pool:
                item_copy = dict(item)
                item_copy['composite_score_adj'] = -999
                item_copy['action'] = '清仓'
                item_copy['downside_reason'] = f'极端象限: {current_regime}'
                final_pool.append(item_copy)
            
            return {
                'is_extreme': True,
                'current_regime': current_regime,
                'final_pool': final_pool,
                'downside_stats': {'total': len(selected_pool), 'downsided': len(selected_pool), 'cleared': True}
            }
        
        # Step 3: 非极端象限 → 判断偏好并降权
        preference = self._get_regime_preference(current_regime)
        preferred_sensitivity = preference['preferred']
        downside_target = preference['downside_target']
        reason = preference['reason']
        
        logger.info(f"象限偏好: {reason}")
        
        final_pool = []
        n_downsided = 0
        
        for item in selected_pool:
            item_copy = dict(item)
            sw_code = str(item['index_code']).replace('.SI', '')
            sensitivity = CYCLE_SENSITIVITY.get(sw_code, 'medium')
            
            # 应用降权
            if downside_target and sensitivity == downside_target:
                item_copy['composite_score_adj'] = round(
                    item['composite_score'] * DOWNSIDE_WEIGHT, 4
                )
                item_copy['downside_reason'] = (
                    f'不匹配{downside_target}敏感度，降权{DOWNSIDE_WEIGHT}'
                )
                item_copy['action'] = '持有(降权)'
                n_downsided += 1
            else:
                item_copy['composite_score_adj'] = item['composite_score']
                item_copy['downside_reason'] = '匹配偏好或无需降权'
                item_copy['action'] = '持有'
            
            item_copy['sensitivity'] = sensitivity
            final_pool.append(item_copy)
        
        # 按调整后的composite_score排序
        final_pool.sort(key=lambda x: x['composite_score_adj'], reverse=True)
        
        return {
            'is_extreme': False,
            'current_regime': current_regime,
            'final_pool': final_pool,
            'downside_stats': {
                'total': len(final_pool),
                'downsided': n_downsided,
                'cleared': False
            }
        }
    
    def _get_regime_preference(self, regime: str) -> Dict[str, Any]:
        """根据象限判断偏好"""
        if any(r in regime for r in ['强势复苏', '完美扩张', '过热']):
            return {
                'preferred': 'high',
                'downside_target': 'low',
                'reason': f'{regime}: 偏好顺周期，防御型降权'
            }
        elif any(r in regime for r in ['宽衰退', '弱复苏']):
            return {
                'preferred': 'low',
                'downside_target': 'high',
                'reason': f'{regime}: 偏好防御型，强周期降权'
            }
        elif '滞胀' in regime:
            return {
                'preferred': 'low',
                'downside_target': 'medium',
                'reason': f'{regime}: 偏好上游资源/红利，成长型降权'
            }
        else:
            return {
                'preferred': None,
                'downside_target': None,
                'reason': f'{regime}: 无显著偏好，不做降权'
            }
