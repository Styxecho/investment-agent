# skills/macro_state/service.py
"""
MacroStateService - Internal service layer

Coordinates:
- DataManager: CSV upload, validation, DB operations
- FactorCalculator: V7 factor computation
- StateEngine: Macro state synthesis

No external script dependencies.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import text

from .data_manager import DataManager, VALID_INDICATORS
from .factor_calculator import FactorCalculator
from .state_engine import StateEngine


class MacroStateService:
    """V7宏观状态服务（完全内嵌）"""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.factor_calculator = FactorCalculator()
        self.state_engine = StateEngine()
    
    # ==================== 数据上传 ====================
    
    def upload_data(self, file_path: str, data_type: str = "monthly", 
                   auto_recalc: bool = True) -> Dict:
        """
        上传CSV数据并可选自动重算
        
        Returns:
            {
                "success": bool,
                "imported_count": int,
                "errors": list,
                "warnings": list,
                "recalc_result": dict (if auto_recalc=True)
            }
        """
        try:
            # 1. 读取CSV
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 2. 校验
            errors, warnings, validated_df = self.data_manager.validate_csv(df, data_type)
            
            if errors:
                return {
                    "success": False,
                    "imported_count": 0,
                    "errors": errors,
                    "warnings": warnings,
                    "message": f"Validation failed: {len(errors)} errors"
                }
            
            # 3. 导入数据
            count = self.data_manager.import_data(validated_df, data_type)
            
            result = {
                "success": True,
                "imported_count": count,
                "errors": [],
                "warnings": warnings,
                "message": f"Imported {count} records"
            }
            
            # 4. 自动重算
            if auto_recalc:
                recalc_result = self.recalculate_v7()
                result["recalc_result"] = recalc_result
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "imported_count": 0,
                "errors": [str(e)],
                "warnings": [],
                "message": f"Upload failed: {str(e)}"
            }
    
    def preview_upload(self, file_path: str, data_type: str = "monthly") -> Dict:
        """
        预览上传数据（不上库）
        
        Returns:
            {
                "success": bool,
                "summary": dict,
                "errors": list,
                "warnings": list,
                "preview_data": list
            }
        """
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            errors, warnings, validated_df = self.data_manager.validate_csv(df, data_type)
            
            # 生成摘要
            summary = {
                "total_records": len(validated_df),
                "unique_indicators": validated_df['indicator_code'].nunique(),
                "date_range": f"{validated_df['publish_date'].min()} ~ {validated_df['publish_date'].max()}",
                "indicator_summary": validated_df.groupby('indicator_code').agg({
                    'publish_date': ['min', 'max', 'count'],
                    'value_num': ['min', 'max', 'mean']
                }).to_dict()
            }
            
            # 前5行预览
            preview = validated_df.head(5).to_dict('records')
            
            return {
                "success": len(errors) == 0,
                "summary": summary,
                "errors": errors,
                "warnings": warnings,
                "preview_data": preview
            }
            
        except Exception as e:
            return {
                "success": False,
                "summary": {},
                "errors": [str(e)],
                "warnings": [],
                "preview_data": []
            }
    
    # ==================== V7重算 ====================
    
    def recalculate(self) -> Dict:
        """
        重新计算V8因子和状态
        
        Returns:
            {
                "success": bool,
                "factor_count": int,
                "state_count": int,
                "message": str
            }
        """
        try:
            # 1. 清空旧数据
            self.data_manager.clear_factors_and_states()
            
            # 2. 加载原始数据
            indicator_codes = list(self.factor_calculator.indicators.keys())
            raw_data = self.data_manager.load_raw_data(indicator_codes)
            
            if not raw_data:
                return {
                    "success": False,
                    "factor_count": 0,
                    "state_count": 0,
                    "message": "No raw data found"
                }
            
            # 3. 计算因子
            factor_results = self.factor_calculator.calculate_all_factors(raw_data)
            self.data_manager.store_factors(factor_results)
            factor_count = sum(len(df) for df in factor_results.values() if df is not None)
            
            # 4. 计算状态
            state_count = self._compute_states(raw_data, factor_results)
            
            return {
                "success": True,
                "factor_count": factor_count,
                "state_count": state_count,
                "message": f"V8 recalculation complete: {factor_count} factors, {state_count} states"
            }
            
        except Exception as e:
            return {
                "success": False,
                "factor_count": 0,
                "state_count": 0,
                "message": f"Recalculation failed: {str(e)}"
            }
    
    def _compute_states(self, raw_data: Dict[str, pd.DataFrame], 
                       factor_results: Dict[str, pd.DataFrame]) -> int:
        """
        计算宏观状态（内部方法）
        """
        # 准备数据
        indicators = {
            'pmi': 'CN_PMI_MFG_M',
            'iav': 'CN_IAV_YOY_M',
            'ccpi': 'CN_CCPI_YOY_M',
            'ppi': 'CN_PPI_YOY_M',
            'm2': 'CN_M2_YOY_M',
            'sfs': 'CN_SFS_YOY_M',
        }
        
        factor_data = {}
        for key, code in indicators.items():
            if code in factor_results and factor_results[code] is not None:
                factor_data[key] = factor_results[code]
        
        # 获取公共日期
        # V8 Fix: 以PMI日期为基础，只与必须有数据的指标取交集（排除IAV）
        # IAV在1月可能缺失，不应因此排除整月记录
        if 'pmi' not in factor_data:
            return 0
        
        all_dates = set(factor_data['pmi'].index)
        for key in ['ccpi', 'ppi', 'm2']:
            if key in factor_data:
                all_dates = all_dates.intersection(set(factor_data[key].index))
        
        if not all_dates:
            return 0
        
        date_index = sorted(list(all_dates))
        
        # 加载日度数据（V8: 传入完整日频序列）
        omo_daily = self.data_manager.load_daily_series('CN_OMO_R007_D', forward_fill=True)
        dr007_daily = self.data_manager.load_daily_series('CN_DR007_D', forward_fill=False)
        svc_data = raw_data.get('CN_PMI_SVC_M')
        
        # 逐月计算状态
        results = []
        
        for date in date_index:
            # 准备各维度数据
            pmi_info = self._get_indicator_info(factor_data, 'pmi', date)
            iav_info = self._get_indicator_info(factor_data, 'iav', date)
            ccpi_info = self._get_indicator_info(factor_data, 'ccpi', date)
            ppi_info = self._get_indicator_info(factor_data, 'ppi', date)
            m2_info = self._get_indicator_info(factor_data, 'm2', date)
            sfs_info = self._get_indicator_info(factor_data, 'sfs', date)
            
            # 计算社融变化（用于财政干扰检测）
            if sfs_info and 'sfs' in factor_data:
                sfs_df = factor_data['sfs']
                idx = sfs_df.index.get_loc(date)
                if idx >= 1:
                    sfs_info['yoy_change'] = sfs_df.iloc[idx]['raw_value'] - sfs_df.iloc[idx-1]['raw_value']
                    sfs_info['cycle_change'] = sfs_df.iloc[idx]['cycle_value'] - sfs_df.iloc[idx-1]['cycle_value']
                else:
                    sfs_info['yoy_change'] = np.nan
                    sfs_info['cycle_change'] = np.nan
            
            # SVC
            svc_info = self._get_indicator_info({'svc': svc_data}, 'svc', date) if svc_data is not None else None
            
            # 提取threshold
            thresholds = {}
            for key, code in indicators.items():
                if code in factor_results and factor_results[code] is not None:
                    df = factor_results[code]
                    if date in df.index:
                        thresholds[key] = df.loc[date].get('threshold', np.nan)
            
            # 合成状态（V8: 传入日频序列）
            record = self.state_engine.synthesize_state(
                date, pmi_info, iav_info, ccpi_info, ppi_info,
                m2_info, sfs_info,
                omo_daily, dr007_daily,
                svc_info,
                thresholds
            )
            
            results.append(record)
        
        # 存储结果
        if results:
            df = pd.DataFrame(results)
            # Convert date to string format YYYYMMDD
            df['publish_date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
            df_for_db = df.drop('date', axis=1)
            self.data_manager.store_states(df_for_db)
            return len(results)
        
        return 0
    
    def _get_indicator_info(self, factor_data: Dict, key: str, date) -> Optional[Dict]:
        """获取指标信息"""
        if key not in factor_data or factor_data[key] is None:
            return None
        
        df = factor_data[key]
        if date not in df.index:
            return None
        
        row = df.loc[date]
        return {
            'raw': row.get('raw_value', np.nan),
            'cycle': row.get('cycle_value', np.nan),
            'trend': row.get('trend_value', np.nan),
            'factor_value': row.get('factor_value', np.nan),
            'z': row.get('factor_value', np.nan),  # factor_value 就是 Z-score
            'deviation': row.get('deviation', np.nan),
            'ma3_z': row.get('ma3_z', np.nan),
            'threshold': row.get('threshold', np.nan),
            'trend_dir': row.get('trend_direction', '→'),
            'raw_dir': row.get('raw_direction', '→'),
        }
    
    def _get_daily_value(self, daily_df: Optional[pd.DataFrame], date) -> Optional[float]:
        """从日度数据获取月度值"""
        if daily_df is None:
            return None
        
        # 查找同月的最后一个值
        month_data = daily_df[
            (daily_df.index.year == date.year) & 
            (daily_df.index.month == date.month)
        ]
        
        if len(month_data) > 0:
            return float(month_data.iloc[-1]['value'])
        
        return None
    
    # ==================== 状态查询 ====================
    
    def query_state(self, date: str) -> Optional[Dict]:
        """查询指定日期状态"""
        sql = """
        SELECT * FROM macro_state_detail
        WHERE publish_date = :date
        LIMIT 1
        """
        
        df = pd.read_sql(text(sql), self.data_manager.engine, params={"date": date})
        
        if len(df) == 0:
            return None
        
        row = df.iloc[0]
        return {
            "publish_date": str(row["publish_date"]),
            "macro_regime": row["macro_regime"],
            "growth_state": row["growth_state"],
            "inflation_state": row["inflation_state"],
            "liquidity_level": row["liquidity_level"],
            "warnings": row["warnings"],
            "pmi_raw": row["pmi_raw"],
            "ccpi_raw": row["ccpi_raw"],
            "ppi_raw": row["ppi_raw"],
            "m2_raw": row["m2_raw"],
            "sfs_raw": row.get("sfs_raw"),
        }
    
    def query_latest_state(self) -> Optional[Dict]:
        """查询最新状态"""
        sql = """
        SELECT * FROM macro_state_detail
        ORDER BY publish_date DESC
        LIMIT 1
        """
        
        df = pd.read_sql(text(sql), self.data_manager.engine)
        
        if len(df) == 0:
            return None
        
        return self.query_state(str(df.iloc[0]["publish_date"]))
    
    def check_data_freshness(self) -> Dict:
        """检查数据时效性"""
        status, db_latest, expected = self.data_manager.check_data_freshness()
        
        completeness = self.data_manager.check_data_completeness()
        
        return {
            "status": status,
            "db_latest": db_latest,
            "expected_date": expected,
            "missing_indicators": completeness.get('missing', []),
            "indicator_details": completeness.get('indicators', {})
        }
    
    def query_history(self, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> List[Dict]:
        """查询历史状态序列"""
        conditions = ["1=1"]
        params = {}
        
        if start_date:
            conditions.append("publish_date >= :start")
            params["start"] = start_date
        if end_date:
            conditions.append("publish_date <= :end")
            params["end"] = end_date
        
        where_clause = " AND ".join(conditions)
        
        sql = f"""
        SELECT 
            publish_date,
            growth_state,
            inflation_state,
            liquidity_level,
            macro_regime,
            warnings
        FROM macro_state_detail
        WHERE {where_clause}
        ORDER BY publish_date
        """
        
        df = pd.read_sql(text(sql), self.data_manager.engine, params=params)
        return df.to_dict('records')
    
    def generate_report(self, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Dict:
        """生成统计报告"""
        conditions = ["1=1"]
        params = {}
        
        if start_date:
            conditions.append("publish_date >= :start")
            params["start"] = start_date
        if end_date:
            conditions.append("publish_date <= :end")
            params["end"] = end_date
        
        where_clause = " AND ".join(conditions)
        
        # 象限分布
        regime_sql = f"""
        SELECT macro_regime, COUNT(*) as cnt
        FROM macro_state_detail
        WHERE {where_clause}
        GROUP BY macro_regime
        ORDER BY cnt DESC
        """
        
        regime_df = pd.read_sql(text(regime_sql), self.data_manager.engine, params=params)
        
        # 最新状态
        latest = self.query_latest_state()
        
        # WARNING统计
        warning_sql = f"""
        SELECT COUNT(*) as cnt
        FROM macro_state_detail
        WHERE {where_clause} AND warnings IS NOT NULL
        """
        
        warning_df = pd.read_sql(text(warning_sql), self.data_manager.engine, params=params)
        
        # 总月数
        total_sql = f"""
        SELECT COUNT(*) as cnt
        FROM macro_state_detail
        WHERE {where_clause}
        """
        
        total_df = pd.read_sql(text(total_sql), self.data_manager.engine, params=params)
        total_months = int(total_df.iloc[0]['cnt']) if len(total_df) > 0 else 0
        
        return {
            "total_months": total_months,
            "regime_distribution": regime_df.to_dict('records') if len(regime_df) > 0 else [],
            "dominant_regime": regime_df.iloc[0]['macro_regime'] if len(regime_df) > 0 else "N/A",
            "latest_state": latest,
            "warning_count": int(warning_df.iloc[0]['cnt']) if len(warning_df) > 0 else 0,
            "date_range": {"start": start_date, "end": end_date}
        }
    
    def generate_upload_template(self, year: int, month: int, 
                                data_type: str = "monthly") -> str:
        """生成上传模板"""
        # 简化版模板生成逻辑
        template_data = []
        
        for code, config in VALID_INDICATORS.items():
            if config['freq'] == data_type:
                template_data.append({
                    'indicator_code': code,
                    'publish_date': f"{year}{month:02d}01",  # 用户需调整为月末
                    'value': '',
                    'frequency': data_type,
                    'period_type': 'yoy' if 'YOY' in code else ('mom' if 'MOM' in code else 'absolute'),
                })
        
        df = pd.DataFrame(template_data)
        
        # 保存到模板目录
        template_dir = Path(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\templates')
        template_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = template_dir / f"macro_upload_template_{data_type}_{year}{month:02d}.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        return str(output_path)


    def export_to_csv(self, output_path: str = None) -> Dict:
        """
        将数据库中的宏观状态导出为CSV
        
        Args:
            output_path: CSV输出路径，默认放在macro_analysis目录下
        
        Returns:
            {"success": bool, "csv_path": str, "record_count": int, "message": str}
        """
        try:
            # 从数据库读取所有状态
            sql = "SELECT * FROM macro_state_detail ORDER BY publish_date"
            df = pd.read_sql(text(sql), self.data_manager.engine)
            
            if len(df) == 0:
                return {
                    "success": False,
                    "csv_path": None,
                    "record_count": 0,
                    "message": "No data in macro_state_detail"
                }
            
            # 默认路径
            if output_path is None:
                output_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_detail.csv'
            
            # 保存CSV
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            return {
                "success": True,
                "csv_path": output_path,
                "record_count": len(df),
                "message": f"Exported {len(df)} records to {output_path}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "csv_path": None,
                "record_count": 0,
                "message": f"Export failed: {str(e)}"
            }
    
    def export_only(self) -> Dict:
        """
        仅导出CSV，不重新计算（供外部脚本调用）
        """
        return self.export_to_csv()


# 单例实例
macro_state_service = MacroStateService()
