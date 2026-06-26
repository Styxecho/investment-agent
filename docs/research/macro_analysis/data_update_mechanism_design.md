# V7 宏观数据更新机制设计文档

## 一、问题分析

### 当前痛点
1. **数据来源不稳定**：Wind手工导出依赖人工，AkShare延迟7-30天
2. **更新频率不匹配**：月频数据每月10-15日发布，但手工更新容易遗漏
3. **数据质量风险**：不同来源的数据口径可能不一致
4. **缺乏自动化**：目前需要手动运行Python脚本更新

### 数据源评估

| 数据源 | 获取方式 | 延迟 | 成本 | 数据质量 | 推荐指数 |
|--------|----------|------|------|----------|----------|
| **Wind终端** | 手工导出CSV | 实时 | 高(付费) | ★★★★★ | ★★★★★ |
| **iFinD API** | API调用 | T+1 | 中(付费) | ★★★★☆ | ★★★★☆ |
| **AkShare** | Python库 | T+7~30 | 免费 | ★★★☆☆ | ★★★☆☆ |
| **国家统计局** | 官网爬虫 | T+1~3 | 免费 | ★★★★★ | ★★★★☆ |
| **央行官网** | 官网爬虫 | T+1~3 | 免费 | ★★★★★ | ★★★★☆ |
| **人工上传** | CSV导入 | 实时 | 免费 | ★★★★★ | ★★★★★ |

## 二、三层混合更新架构

```
┌─────────────────────────────────────────────────────────────┐
│                    数据更新调度器                              │
│                  (DataUpdateOrchestrator)                    │
└──────────────┬──────────────────────┬───────────────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌───────▼───────┐  ┌──────────▼──────────┐
    │   L1: 自动层         │  │  L2: 半自动层  │  │   L3: 手动层         │
    │  (Free APIs)        │  │ (Web Crawlers)│  │  (Manual Upload)    │
    └──────────┬──────────┘  └───────┬───────┘  └──────────┬──────────┘
               │                      │                      │
    ┌──────────▼──────────┐  ┌───────▼───────┐  ┌──────────▼──────────┐
    │ • AkShare           │  │ • 统计局爬虫   │  │ • Web界面上传       │
    │ • 备用API           │  │ • 央行爬虫     │  │ • CLI命令上传       │
    │ • 定时任务(每日)     │  │ • 定时任务(每周)│  │ • 邮件通知          │
    └─────────────────────┘  └───────────────┘  └─────────────────────┘
```

## 三、各层详细设计

### L1: 自动层 - AkShare免费API

**适用场景**：历史数据回填、非紧急的定期更新

**支持的指标**：
- PMI制造业：`ak.macro_china_pmi_yearly()`
- CPI同比：`ak.macro_china_cpi_yearly()`
- PPI同比：`ak.macro_china_ppi_yearly()`
- M2同比：`ak.macro_china_m2_yearly()`
- 社融规模：`ak.macro_china_shrzgm()`
- 工业增加值：`ak.macro_china_industrial_production_yearly()`

**限制**：
- 核心CPI：AkShare无直接接口，需从CPI和食品CPI推算
- DR007日频：AkShare有银行间利率，但可能不是DR007
- 数据延迟：通常晚7-30天

**实现方案**：
```python
class AkShareMacroProvider:
    """AkShare宏观数据提供者"""
    
    def fetch_pmi(self, start_date, end_date):
        df = ak.macro_china_pmi_yearly()
        # 标准化为内部格式
        return self._normalize(df, 'CN_PMI_MFG_M')
    
    def fetch_cpi(self, start_date, end_date):
        df = ak.macro_china_cpi_yearly()
        return self._normalize(df, 'CN_CPI_YOY_M')
    
    # ... 其他指标
```

**更新策略**：
- 频率：每日检查一次
- 逻辑：对比数据库最新日期与AkShare最新日期，如有新数据则自动导入
- 数据校验：与历史数据做环比合理性检查

### L2: 半自动层 - 定向爬虫

**适用场景**：比API更快获取官方发布数据

**目标网站**：
1. **国家统计局** (stats.gov.cn)
   - PMI：每月月底发布
   - CPI/PPI：每月10-15日发布
   - 工业增加值：每月15-20日发布

2. **中国人民银行** (pbc.gov.cn)
   - M2/M1/M0：每月10-15日发布
   - 社融规模：每月10-15日发布
   - 政策利率：随时可能调整

**实现方案**：
```python
class StatsGovCrawler:
    """国家统计局定向爬虫"""
    
    def crawl_pmi(self):
        """抓取最新PMI数据"""
        url = "https://www.stats.gov.cn/sj/zxfb/"
        # 解析HTML获取最新发布
        pass
    
    def crawl_cpi(self):
        """抓取最新CPI数据"""
        pass

class PbcGovCrawler:
    """人民银行定向爬虫"""
    
    def crawl_money_supply(self):
        """抓取货币供应量"""
        pass
    
    def crawl_social_financing(self):
        """抓取社融数据"""
        pass
```

**更新策略**：
- 频率：每周一、周四运行（数据通常在这两个时间段发布）
- 数据发布日历：
  - 每月10日左右：M2、社融、CPI、PPI
  - 每月最后一天：PMI
  - 每月15日左右：工业增加值
- 触发条件：发布日+1天自动运行

### L3: 手动层 - CSV上传

**适用场景**：最新数据即时更新、AkShare/爬虫失效时的兜底

**上传方式**：

#### 方式A: Web界面上传（推荐）
```python
# Streamlit界面
import streamlit as st

st.title("宏观数据更新")
uploaded_file = st.file_uploader("上传月度数据CSV", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    preview = validate_and_preview(df)
    if st.button("确认导入"):
        import_to_database(df)
        st.success("导入成功！")
        # 自动触发V7流水线重算
        recalculate_v7_pipeline()
```

#### 方式B: CLI命令上传
```bash
# 命令行上传
python -m scripts.update_macro_data \
    --file monthly_data_202604.csv \
    --type monthly \
    --auto-recalculate
```

#### 方式C: 邮件通知+上传
- 系统检测到自动层和半自动层都未能获取最新数据
- 发送邮件提醒用户手动上传
- 邮件包含模板CSV文件

**CSV格式规范**：
```csv
indicator_code,publish_date,value,frequency,period_type
CN_PMI_MFG_M,20260430,50.8,monthly,absolute
CN_CPI_YOY_M,20260430,0.8,monthly,yoy
CN_M2_YOY_M,20260430,8.5,monthly,yoy
```

## 四、更新调度器设计

### 核心类：`DataUpdateOrchestrator`

```python
class DataUpdateOrchestrator:
    """数据更新调度器"""
    
    def __init__(self):
        self.providers = {
            'akshare': AkShareMacroProvider(),
            'stats_gov': StatsGovCrawler(),
            'pbc_gov': PbcGovCrawler(),
            'manual': ManualUploadHandler(),
        }
        self.db = MacroDatabase()
    
    def check_for_updates(self):
        """检查所有指标是否有新数据"""
        updates_needed = []
        
        for indicator in self.get_all_indicators():
            latest_db = self.db.get_latest_date(indicator)
            expected_date = self.get_expected_release_date(indicator)
            
            if latest_db < expected_date:
                updates_needed.append({
                    'indicator': indicator,
                    'db_latest': latest_db,
                    'expected': expected_date,
                    'days_overdue': (today - expected_date).days
                })
        
        return updates_needed
    
    def execute_update(self, strategy='auto_first'):
        """执行更新
        
        strategy:
            - 'auto_first': 先尝试自动层，失败则尝试半自动层
            - 'manual': 仅等待手动上传
            - 'full': 所有层级都尝试
        """
        updates = self.check_for_updates()
        
        for update in updates:
            if strategy in ['auto_first', 'full']:
                # 尝试L1
                if self.try_l1_update(update):
                    continue
                
                # 尝试L2
                if strategy == 'full' and self.try_l2_update(update):
                    continue
            
            # 记录为待手动更新
            self.log_pending_manual_update(update)
    
    def get_update_report(self):
        """生成更新状态报告"""
        pass
```

### 发布日历管理

```python
class ReleaseCalendar:
    """数据发布日历"""
    
    CALENDAR = {
        'CN_PMI_MFG_M': {'day': -1, 'month_offset': 0},  # 每月最后一天
        'CN_CPI_YOY_M': {'day': 10, 'month_offset': 1}, # 次月10日
        'CN_PPI_YOY_M': {'day': 10, 'month_offset': 1},
        'CN_M2_YOY_M': {'day': 10, 'month_offset': 1},
        'CN_SFS_YOY_M': {'day': 10, 'month_offset': 1},
        'CN_IAV_YOY_M': {'day': 15, 'month_offset': 1},
    }
    
    def get_expected_date(self, indicator_code, base_date=None):
        """获取指标预期发布日期"""
        pass
```

## 五、数据质量校验

### 自动校验规则

1. **日期连续性检查**
   - 月频数据不应有缺失月份
   - 日频数据不应有连续5天以上缺失

2. **数值合理性检查**
   - PMI范围：30-70（超出则警告）
   - CPI/PPI同比：-10%~20%
   - M2同比：0%~30%
   - 环比突变：同比变化>5个百分点则标记审核

3. **跨指标一致性**
   - CPI与核心CPI方向不应长期背离
   - M2与社融方向通常一致

### 人工审核触发条件

```python
def should_trigger_manual_review(new_data):
    """判断是否需要人工审核"""
    checks = [
        # 检查1: 数值超出历史范围3个标准差
        abs(zscore(new_data.value)) > 3,
        
        # 检查2: 环比变化异常
        abs(mom_change) > historical_std * 2,
        
        # 检查3: 与关联指标背离
        direction_mismatch_with_related_indicator(),
        
        # 检查4: 与AkShare数据差异过大
        abs(self_value - akshare_value) > 0.5,
    ]
    
    return any(checks)
```

## 六、实施路线图

### Phase 1: 手动层（立即实施）
- [ ] 创建CSV上传脚本（命令行版）
- [ ] 添加数据校验逻辑
- [ ] 上传后自动触发V7流水线重算
- [ ] 创建上传模板生成器

### Phase 2: 自动层（1周内）
- [ ] 实现AkShare数据获取适配器
- [ ] 添加定时任务（每日检查）
- [ ] 实现数据对比与自动入库

### Phase 3: 半自动层（2周内）
- [ ] 实现统计局官网爬虫
- [ ] 实现央行官网爬虫
- [ ] 添加发布日历管理
- [ ] 实现邮件通知功能

### Phase 4: 调度器（3周内）
- [ ] 实现三层调度逻辑
- [ ] 添加更新报告生成
- [ ] 实现异常处理与告警
- [ ] 封装为Skill接口

## 七、CLI命令设计

```bash
# 检查更新状态
python -m scripts.macro_data status

# 手动上传月度数据
python -m scripts.macro_data upload-monthly --file data.csv

# 手动上传日度数据
python -m scripts.macro_data upload-daily --file data.csv

# 触发自动更新（尝试L1+L2）
python -m scripts.macro_data auto-update

# 强制重新计算V7流水线
python -m scripts.macro_data recalculate-v7

# 生成更新报告
python -m scripts.macro_data report

# 导出当前数据为CSV（备份）
python -m scripts.macro_data export --output backup.csv
```

## 八、Web界面原型（Streamlit）

```
┌─────────────────────────────────────┐
│  V7 宏观数据管理后台                 │
├─────────────────────────────────────┤
│                                     │
│ [数据更新状态]                       │
│ ┌──────────┬──────────┬──────────┐ │
│ │ 指标      │ 最新日期  │ 状态     │ │
│ ├──────────┼──────────┼──────────┤ │
│ │ PMI      │ 20260331 │ ✓ 已最新 │ │
│ │ CPI      │ 20260331 │ ✓ 已最新 │ │
│ │ M2       │ 20260331 │ ✓ 已最新 │ │
│ │ 社融     │ 20260331 │ ⚠ 待更新 │ │
│ └──────────┴──────────┴──────────┘ │
│                                     │
│ [上传新数据]                         │
│ ┌─────────────────────────────────┐ │
│ │ 📁 选择CSV文件...                │ │
│ │ 或拖拽文件到此处                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [预览与校验]                         │
│ ┌─────────────────────────────────┐ │
│ │ publish_date │ indicator │ value│ │
│ │ 20260430    │ PMI       │ 50.8 │ │
│ │ 20260430    │ CPI       │ 0.8  │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [✓ 数据校验通过]                    │
│                                     │
│ [确认导入并重新计算]                  │
│                                     │
└─────────────────────────────────────┘
```

## 九、关键设计决策

### 决策1: 自动更新失败时如何处理？
**方案**：标记为"待手动更新"，发送通知（邮件/日志），不阻塞其他指标更新

### 决策2: 多层数据冲突时以哪层为准？
**优先级**：手动上传 > 半自动爬虫 > 自动API > 历史数据
**原因**：人工审核的数据最可靠

### 决策3: 是否保留历史版本？
**方案**：保留，添加`is_revised`标记和`revision_note`
**原因**：宏观数据经常修订（尤其是工业增加值、GDP）

### 决策4: 日频数据如何处理？
**方案**：
- 日频原始数据：每日自动从AkShare获取（股票、债券、DR007等）
- 日频→月频聚合：在V7流水线中自动计算月度均值
- 月度数据：以手工上传为主

## 十、待讨论问题

1. **是否使用付费API（iFinD）？**
   - 优点：数据及时、质量高
   - 缺点：需要付费账号
   - 建议：优先实现免费方案，付费API作为可选增强

2. **爬虫的法律风险？**
   - 统计局和央行官网通常允许爬取公开数据
   - 建议：控制请求频率（每秒1次），遵守robots.txt

3. **数据存储在哪里？**
   - 当前：SQLite本地文件
   - 未来：是否需要迁移到PostgreSQL/MySQL？

4. **更新频率？**
   - 月频数据：每月10-15日检查一次
   - 日频数据：每日收盘后检查
   - 紧急更新：支持手动随时触发
