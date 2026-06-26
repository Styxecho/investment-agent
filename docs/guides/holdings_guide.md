# 持仓文件使用说明

## 📁 文件结构

项目中有两个持仓相关的 CSV 文件：

| 文件 | 用途 | 是否上传 Git | 更新方式 |
|------|------|-------------|----------|
| **`holdings_template.csv`** | 模板文件（包含示例持仓） | ✅ 是 | 仅当模板需要更新时 |
| **`holdings.csv`** | 你的实际持仓文件 | ❌ 否（已加入 .gitignore） | 你定期手动更新 |

## 📝 如何更新持仓

### 1. 打开持仓文件

用 Excel、记事本或任何 CSV 编辑器打开 `holdings.csv`

### 2. 文件格式

```csv
code,name,volume,cost_price,asset_type
600159.SH,贵州茅台，100,1500,stock
510300.SH,沪深 300ETF,500,3.8,etf
```

**字段说明**：
- `code` - 股票代码（如 `600159.SH` 或 `000001.SZ`）
- `name` - 资产名称（如 `贵州茅台`）
- `volume` - 持仓数量（如 `100` 股）
- `cost_price` - 持仓成本价（如 `1500` 元）
- `asset_type` - 资产类型（`stock`=股票，`etf`=ETF，`fund`=基金）

### 3. 添加新持仓

在文件末尾添加新行：
```csv
000858.SZ,五粮液，200,180,stock
```

### 4. 删除持仓

直接删除对应的行即可。

### 5. 更新持仓数量或成本

修改对应行的 `volume` 或 `cost_price` 值。

## 🤖 Agent 如何使用

### 自动读取

当你问 Agent 关于组合的问题时，它会自动读取 `holdings.csv`：

```
你：我的组合今天表现如何？
Agent: [自动读取 holdings.csv] → [获取行情数据] → [计算盈亏] → [返回结果]
```

### 示例问题

```
- "我的组合今天盈亏如何？"
- "分析一下 20260403 的表现"
- "我现在的持仓总市值是多少？"
- "哪个股票对我的组合贡献最大？"
```

## 🔧 故障排查

### 问题 1：Agent 说"未找到持仓数据"

**原因**：`holdings.csv` 文件不存在或为空

**解决**：
1. 确认 `holdings.csv` 存在于项目根目录
2. 如果不存在，复制模板：`cp holdings_template.csv holdings.csv`
3. 确保文件包含至少一条有效持仓记录

### 问题 2：持仓更新后 Agent 仍显示旧数据

**原因**：Streamlit 会话缓存

**解决**：
1. 在 Streamlit 界面点击"清除记忆"按钮
2. 或刷新浏览器页面
3. 或修改会话 ID 以开启新对话

### 问题 3：CSV 格式错误

**原因**：列名不匹配或字段缺失

**解决**：
1. 确保第一行是表头：`code,name,volume,cost_price,asset_type`
2. 确保每行都有 5 个字段
3. 使用 UTF-8 编码保存文件

## 📊 当前持仓示例

打开 `holdings.csv` 查看你当前的持仓：

```csv
code,name,volume,cost_price,asset_type
600159.SH,贵州茅台，100,1500,stock
510300.SH,沪深 300ETF,500,3.8,etf
```

**提示**：这是示例数据，请根据你的实际持仓更新！

## 🔒 隐私保护

`holdings.csv` 已加入 `.gitignore`，不会被上传到 Git：

```gitignore
# 忽略用户具体持仓，保留模板
*.csv
!holdings_template.csv
```

**注意**：
- ✅ `holdings_template.csv` - 会上传（作为模板示例）
- ❌ `holdings.csv` - 不会上传（你的个人隐私数据）

---

**最后更新**: 2026-04-04  
**文档版本**: v1.0
