"""
统计局Excel解析器
支持国家统计局发布的宏观数据Excel格式
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings

from scripts.data_import.config import INDICATOR_MAP, VALIDATION_RULES

warnings.filterwarnings('ignore')


class StatsGovParser:
    """国家统计局数据解析器"""
    
    def __init__(self):
        self.source_name = "国家统计局"
        self.supported_formats = ['.xls', '.xlsx', '.csv']
    
    def parse(self, file_path: str) -> Tuple[List[Dict], List[str]]:
        """
        解析统计局Excel文件
        
        Returns:
            (records, errors)
            records: List[{'indicator_code': str, 'publish_date': str, 'value': float}]
        """
        records = []
        errors = []
        
        try:
            file_path = Path(file_path)
            
            # 根据文件类型选择读取方式
            if file_path.suffix in ['.xls', '.xlsx']:
                # 尝试读取所有sheet
                excel_file = pd.ExcelFile(file_path)
                
                for sheet_name in excel_file.sheet_names:
                    try:
                        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                        sheet_records, sheet_errors = self._parse_sheet(df, sheet_name)
                        records.extend(sheet_records)
                        errors.extend(sheet_errors)
                    except Exception as e:
                        errors.append(f"Sheet '{sheet_name}' 解析失败: {str(e)[:100]}")
                        
            elif file_path.suffix == '.csv':
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                sheet_records, sheet_errors = self._parse_dataframe(df, "CSV")
                records.extend(sheet_records)
                errors.extend(sheet_errors)
            
            return records, errors
            
        except Exception as e:
            return [], [f"文件解析失败: {str(e)[:150]}"]
    
    def _parse_sheet(self, df: pd.DataFrame, sheet_name: str) -> Tuple[List[Dict], List[str]]:
        """解析单个sheet"""
        records = []
        errors = []
        
        # 尝试多种解析策略
        strategies = [
            self._parse_type1,  # 时间序列格式：行=指标，列=时间
            self._parse_type2,  # 横截面格式：行=时间，列=指标
            self._parse_type3,  # 标准表格格式：indicator, date, value三列
        ]
        
        for strategy in strategies:
            try:
                strategy_records, strategy_errors = strategy(df)
                if strategy_records:
                    records.extend(strategy_records)
                    errors.extend(strategy_errors)
                    return records, errors
            except:
                continue
        
        # 如果所有策略都失败
        errors.append(f"Sheet '{sheet_name}': 无法识别数据格式")
        return records, errors
    
    def _parse_type1(self, df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        """
        解析类型1：行=指标，列=时间
        例如统计局常见的月度数据表格
        """
        records = []
        errors = []
        
        # 寻找表头行（包含"指标"、"时间"等关键词）
        header_row = None
        for idx, row in df.iterrows():
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if any(keyword in row_str for keyword in ['指标', '时间', '月份', '日期']):
                header_row = idx
                break
        
        if header_row is None:
            return [], []
        
        # 重新读取，使用找到的表头
        df_header = df.iloc[header_row+1:].reset_index(drop=True)
        df_header.columns = df.iloc[header_row]
        
        # 寻找指标列（通常是第一列）
        indicator_col = df_header.columns[0]
        
        # 遍历每一行（每个指标）
        for idx, row in df_header.iterrows():
            indicator_name = str(row[indicator_col]).strip()
            
            # 尝试匹配指标代码
            indicator_code = self._match_indicator(indicator_name)
            if not indicator_code:
                continue
            
            # 遍历每一列（每个时间点）
            for col in df_header.columns[1:]:
                try:
                    # 解析日期
                    date_str = self._parse_date(str(col))
                    if not date_str:
                        continue
                    
                    # 获取数值
                    value = row[col]
                    if pd.isna(value):
                        continue
                    
                    value = float(value)
                    
                    records.append({
                        'indicator_code': indicator_code,
                        'indicator_name': indicator_name,
                        'publish_date': date_str,
                        'value': value,
                        'source': self.source_name,
                        'frequency': VALIDATION_RULES.get(indicator_code, {}).get('freq', 'monthly')
                    })
                    
                except Exception:
                    continue
        
        return records, errors
    
    def _parse_type2(self, df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        """
        解析类型2：行=时间，列=指标
        """
        records = []
        errors = []
        
        # 寻找表头行
        header_row = None
        for idx, row in df.iterrows():
            if any(keyword in str(x) for x in row.values if pd.notna(x) 
                   for keyword in ['指标', 'PMI', 'CPI', 'PPI']):
                header_row = idx
                break
        
        if header_row is None:
            return [], []
        
        df_header = df.iloc[header_row+1:].reset_index(drop=True)
        df_header.columns = df.iloc[header_row]
        
        # 寻找日期列（通常是第一列）
        date_col = df_header.columns[0]
        
        # 遍历每一行（每个时间点）
        for idx, row in df_header.iterrows():
            date_str = self._parse_date(str(row[date_col]))
            if not date_str:
                continue
            
            # 遍历每一列（每个指标）
            for col in df_header.columns[1:]:
                try:
                    indicator_name = str(col).strip()
                    indicator_code = self._match_indicator(indicator_name)
                    if not indicator_code:
                        continue
                    
                    value = row[col]
                    if pd.isna(value):
                        continue
                    
                    value = float(value)
                    
                    records.append({
                        'indicator_code': indicator_code,
                        'indicator_name': indicator_name,
                        'publish_date': date_str,
                        'value': value,
                        'source': self.source_name,
                        'frequency': VALIDATION_RULES.get(indicator_code, {}).get('freq', 'monthly')
                    })
                    
                except Exception:
                    continue
        
        return records, errors
    
    def _parse_type3(self, df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        """
        解析类型3：标准三列格式
        必须有 indicator_code/date/value 或类似列名
        """
        records = []
        errors = []
        
        # 检查是否有标准列名
        col_names = [str(c).lower() for c in df.columns]
        
        has_indicator = any('indicator' in c or '指标' in c or 'code' in c for c in col_names)
        has_date = any('date' in c or '时间' in c or '日期' in c or 'publish' in c for c in col_names)
        has_value = any('value' in c or '数值' in c or '数据' in c for c in col_names)
        
        if not (has_indicator and has_date and has_value):
            return [], []
        
        # 找到实际列名
        indicator_col = next((c for c in df.columns if 'indicator' in str(c).lower() or '指标' in str(c)), df.columns[0])
        date_col = next((c for c in df.columns if 'date' in str(c).lower() or '时间' in str(c) or '日期' in str(c)), df.columns[1])
        value_col = next((c for c in df.columns if 'value' in str(c).lower() or '数值' in str(c)), df.columns[2])
        
        # 遍历数据行
        for idx, row in df.iterrows():
            try:
                indicator_code = str(row[indicator_code]).strip()
                
                # 如果是指标名称，尝试映射
                if indicator_code not in INDICATOR_MAP.values():
                    mapped = self._match_indicator(indicator_code)
                    if mapped:
                        indicator_code = mapped
                
                # 检查是否是有效的指标代码
                if indicator_code not in INDICATOR_MAP.values():
                    continue
                
                date_str = self._parse_date(str(row[date_col]))
                if not date_str:
                    continue
                
                value = float(row[value_col])
                
                records.append({
                    'indicator_code': indicator_code,
                    'indicator_name': indicator_code,
                    'publish_date': date_str,
                    'value': value,
                    'source': self.source_name,
                    'frequency': VALIDATION_RULES.get(indicator_code, {}).get('freq', 'monthly')
                })
                
            except Exception:
                continue
        
        return records, errors
    
    def _parse_dataframe(self, df: pd.DataFrame, sheet_name: str) -> Tuple[List[Dict], List[str]]:
        """解析CSV/DataFrame"""
        return self._parse_type3(df)
    
    def _match_indicator(self, name: str) -> Optional[str]:
        """根据指标名称匹配指标代码"""
        name = name.strip()
        
        # 直接匹配
        if name in INDICATOR_MAP:
            return INDICATOR_MAP[name]
        
        # 模糊匹配
        for key, code in INDICATOR_MAP.items():
            if key in name or name in key:
                return code
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """解析日期字符串为 YYYYMMDD 格式"""
        date_str = str(date_str).strip()
        
        # 尝试多种格式
        formats = [
            '%Y年%m月',
            '%Y-%m',
            '%Y/%m',
            '%Y.%m',
            '%Y%m',
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y%m%d',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # 取月末日期
                import calendar
                last_day = calendar.monthrange(dt.year, dt.month)[1]
                return f"{dt.year}{dt.month:02d}{last_day:02d}"
            except ValueError:
                continue
        
        return None


class PBCParser:
    """中国人民银行数据解析器"""
    
    def __init__(self):
        self.source_name = "中国人民银行"
        self.supported_formats = ['.xls', '.xlsx', '.csv']
    
    def parse(self, file_path: str) -> Tuple[List[Dict], List[str]]:
        """解析央行Excel文件"""
        # 央行的数据格式与统计局类似，可以复用大部分逻辑
        stats_parser = StatsGovParser()
        stats_parser.source_name = self.source_name
        return stats_parser.parse(file_path)


def auto_detect_parser(file_path: str) -> Tuple[Optional[object], List[str]]:
    """
    自动检测文件类型并返回合适的解析器
    
    Returns:
        (parser, errors)
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None, [f"文件不存在: {file_path}"]
    
    if file_path.suffix not in ['.xls', '.xlsx', '.csv']:
        return None, [f"不支持的文件格式: {file_path.suffix}"]
    
    # 目前使用通用解析器，自动识别格式
    return StatsGovParser(), []
