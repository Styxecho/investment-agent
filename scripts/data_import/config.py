"""
宏观数据导入配置
定义各数据源Excel的格式映射
"""

# 指标代码映射
INDICATOR_MAP = {
    # 统计局 - PMI
    '制造业采购经理指数': 'CN_PMI_MFG_M',
    '制造业PMI': 'CN_PMI_MFG_M',
    '非制造业商务活动指数': 'CN_PMI_SVC_M',
    '非制造业PMI': 'CN_PMI_SVC_M',
    '综合PMI产出指数': 'CN_PMI_COMP_M',
    '综合PMI': 'CN_PMI_COMP_M',
    
    # 统计局 - 价格
    '居民消费价格指数(上年同月=100)': 'CN_CPI_YOY_M',
    'CPI同比': 'CN_CPI_YOY_M',
    '居民消费价格指数(上月=100)': 'CN_CPI_MOM_M',
    'CPI环比': 'CN_CPI_MOM_M',
    '工业生产者出厂价格指数(上年同月=100)': 'CN_PPI_YOY_M',
    'PPI同比': 'CN_PPI_YOY_M',
    '工业生产者出厂价格指数(上月=100)': 'CN_PPI_MOM_M',
    'PPI环比': 'CN_PPI_MOM_M',
    
    # 统计局 - 工业
    '规模以上工业增加值同比增长': 'CN_IAV_YOY_M',
    '工业增加值同比': 'CN_IAV_YOY_M',
    
    # 央行 - 货币
    '货币供应量(M2)同比增长': 'CN_M2_YOY_M',
    'M2同比': 'CN_M2_YOY_M',
    '货币供应量(M1)同比增长': 'CN_M1_YOY_M',
    'M1同比': 'CN_M1_YOY_M',
    '货币供应量(M0)同比增长': 'CN_M0_YOY_M',
    'M0同比': 'CN_M0_YOY_M',
    
    # 央行 - 社融
    '社会融资规模存量同比增长': 'CN_SFS_YOY_M',
    '社融存量同比': 'CN_SFS_YOY_M',
    '社会融资规模增量': 'CN_SFS_FLOW_M',
    '社融当月值': 'CN_SFS_FLOW_M',
}

# 数据源配置
DATA_SOURCES = {
    'stats_gov': {
        'name': '国家统计局',
        'url': 'https://data.stats.gov.cn',
        'file_patterns': ['*.xls', '*.xlsx', '*.csv'],
        'sheet_name': 0,  # 第一个sheet
        'header_row': 0,  # 第一行为表头
        'date_format': '%Y年%m月',
        'indicators': [
            'CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M',
            'CN_CPI_YOY_M', 'CN_CPI_MOM_M', 
            'CN_PPI_YOY_M', 'CN_PPI_MOM_M',
            'CN_IAV_YOY_M'
        ]
    },
    'pbc': {
        'name': '中国人民银行',
        'url': 'http://www.pbc.gov.cn',
        'file_patterns': ['*.xls', '*.xlsx', '*.csv'],
        'sheet_name': 0,
        'header_row': 0,
        'date_format': '%Y.%m',
        'indicators': [
            'CN_M2_YOY_M', 'CN_M1_YOY_M', 'CN_M0_YOY_M',
            'CN_SFS_YOY_M', 'CN_SFS_FLOW_M'
        ]
    },
    'custom_csv': {
        'name': '自定义CSV',
        'file_patterns': ['*.csv'],
        'required_columns': ['indicator_code', 'publish_date', 'value'],
        'indicators': 'all'
    }
}

# 数据校验规则
VALIDATION_RULES = {
    'CN_PMI_MFG_M': {'min': 30, 'max': 70, 'freq': 'monthly'},
    'CN_PMI_SVC_M': {'min': 30, 'max': 70, 'freq': 'monthly'},
    'CN_PMI_COMP_M': {'min': 30, 'max': 70, 'freq': 'monthly'},
    'CN_IAV_YOY_M': {'min': -20, 'max': 30, 'freq': 'monthly'},
    'CN_CPI_YOY_M': {'min': -5, 'max': 15, 'freq': 'monthly'},
    'CN_CCPI_YOY_M': {'min': -5, 'max': 15, 'freq': 'monthly'},
    'CN_CPI_MOM_M': {'min': -5, 'max': 10, 'freq': 'monthly'},
    'CN_CCPI_MOM_M': {'min': -5, 'max': 10, 'freq': 'monthly'},
    'CN_PPI_YOY_M': {'min': -15, 'max': 20, 'freq': 'monthly'},
    'CN_PPI_MOM_M': {'min': -10, 'max': 10, 'freq': 'monthly'},
    'CN_M0_YOY_M': {'min': -10, 'max': 50, 'freq': 'monthly'},
    'CN_M1_YOY_M': {'min': -10, 'max': 50, 'freq': 'monthly'},
    'CN_M2_YOY_M': {'min': 0, 'max': 40, 'freq': 'monthly'},
    'CN_SFS_YOY_M': {'min': -20, 'max': 50, 'freq': 'monthly'},
    'CN_SFS_FLOW_M': {'min': 0, 'max': 100000, 'freq': 'monthly'},
}

# 发布日历（大致时间，用于检查数据是否已发布）
PUBLISH_SCHEDULE = {
    'CN_PMI_MFG_M': {'day': 31, 'note': '每月最后一天'},
    'CN_PMI_SVC_M': {'day': 31, 'note': '每月最后一天'},
    'CN_PMI_COMP_M': {'day': 31, 'note': '每月最后一天'},
    'CN_CPI_YOY_M': {'day': 9, 'note': '每月9-11日'},
    'CN_PPI_YOY_M': {'day': 9, 'note': '每月9-11日'},
    'CN_IAV_YOY_M': {'day': 15, 'note': '每月中旬'},
    'CN_M2_YOY_M': {'day': 10, 'note': '每月10-15日'},
    'CN_M1_YOY_M': {'day': 10, 'note': '每月10-15日'},
    'CN_M0_YOY_M': {'day': 10, 'note': '每月10-15日'},
    'CN_SFS_YOY_M': {'day': 10, 'note': '每月10-15日'},
    'CN_SFS_FLOW_M': {'day': 10, 'note': '每月10-15日'},
}
