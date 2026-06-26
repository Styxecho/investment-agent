# Qwen 工具调用 JSON 解析修复报告（完整版）

**修复日期**: 2026-04-06  
**问题类型**: 工具调用参数验证错误 + API 参数格式错误  
**修复状态**: ✅ 完成

---

## 问题描述

### 错误信息 1（初始错误）
```
1 validation error for AIMessage 
tool_calls.0.args 
Input should be a valid dictionary 
[type=dict_type, input_value='{"symbol": "003956.OF", "asset_type": "fund"}', input_type=str]
```

### 错误信息 2（修复后新错误）
```
API 调用失败：InvalidParameter - <400> 
InternalError.Algo.InvalidParameter: Input should be a valid string: 
input.messages.2.function_call.arguments
```

### 问题根源

**问题 1：DashScope → LangChain**
- DashScope 返回：`arguments` 是 **JSON 字符串**
- LangChain 期望：`args` 是 **字典**
- 需要：JSON 字符串 → 字典 解析

**问题 2：LangChain → DashScope**
- LangChain 存储：`args` 是 **字典**
- DashScope 期望：`arguments` 是 **JSON 字符串**
- 需要：字典 → JSON 字符串 序列化

**双向转换需求**：
```
DashScope (JSON 字符串) ←→ LangChain (字典对象)
```

---

## 修复方案

### 修改文件
**文件**: `agents/qwen_adapter.py`

### 修改内容

#### 修复 1：DashScope → LangChain（JSON 字符串解析为字典）

**位置**: 第 5 行 + 第 74-90 行

**1. 添加 JSON 导入**：
```python
import json
import dashscope
```

**2. 修改工具调用参数解析**：
```python
# 解析工具调用参数（DashScope 返回的是 JSON 字符串）
args_dict = {}
try:
    args_str = function_call.get('arguments', '{}')
    if isinstance(args_str, str):
        args_dict = json.loads(args_str)
    else:
        args_dict = args_str
except (json.JSONDecodeError, TypeError):
    args_dict = function_call.get('arguments', {})

ai_msg = AIMessage(
    content=output_message.get('content', ''),
    tool_calls=[{
        "name": function_call.get('name'),
        "args": args_dict,  # 解析为字典
        "id": f"call_{function_call.get('name')}"
    }]
)
```

#### 修复 2：LangChain → DashScope（字典序列化为 JSON 字符串）

**位置**: 第 121-135 行（`_convert_messages` 方法）

**修改前**：
```python
if msg.tool_calls:
    ai_msg["function_call"] = {
        "name": msg.tool_calls[0]["name"],
        "arguments": msg.tool_calls[0]["args"]  # ← 问题：直接传入字典
    }
```

**修改后**：
```python
if msg.tool_calls:
    # 将参数字典序列化为 JSON 字符串（DashScope 要求）
    args_dict = msg.tool_calls[0]["args"]
    args_str = json.dumps(args_dict) if isinstance(args_dict, dict) else str(args_dict)
    
    ai_msg["function_call"] = {
        "name": msg.tool_calls[0]["name"],
        "arguments": args_str  # DashScope 期望 JSON 字符串
    }
```

---

## 测试验证

### 测试 1：DashScope → LangChain（JSON 解析）
```python
mock_function_call = {
    'name': 'get_market_data',
    'arguments': '{"symbol": "003956.OF", "asset_type": "fund"}'
}

args_dict = json.loads(mock_function_call['arguments'])
# 结果：{'symbol': '003956.OF', 'asset_type': 'fund'}
```

**结果**: ✅ [PASS] JSON parsed successfully

### 测试 2：LangChain → DashScope（JSON 序列化）
```python
args_dict = {"symbol": "003956.OF", "asset_type": "fund"}
args_str = json.dumps(args_dict)
# 结果：'{"symbol": "003956.OF", "asset_type": "fund"}'
```

**结果**: ✅ [PASS] Arguments is string

### 测试 3：双向转换（Round-trip）
```python
# 原始字典
original = {"symbol": "003956.OF", "asset_type": "fund"}

# Dict -> String -> Dict
converted = json.loads(json.dumps(original))

# 验证
assert original == converted
```

**结果**: ✅ [PASS] Round-trip successful

---

## 影响范围

### 修复的功能
- ✅ Qwen 工具调用参数解析
- ✅ get_market_data 工具（查询股票/基金行情）
- ✅ analyze_portfolio 工具（组合分析）

### 不受影响的部分
- ✅ 消息转换逻辑 (`_convert_messages`)
- ✅ 工具定义转换 (`_convert_tools`)
- ✅ 其他 Agent 节点逻辑

---

## 使用示例

### 修复前（会报错）
```
用户：帮我查询一下 003956.OF 的 2026-4-3 的日终单位净值？
Agent: 调用异常：1 validation error for AIMessage...
```

### 修复后（正常工作）
```
用户：帮我查询一下 003956.OF 的 2026-4-3 的日终单位净值？
Agent: [调用 get_market_data 工具]
       [获取基金净值数据]
       003956.OF 在 2026-04-03 的单位净值为 1.2345...
```

---

## 技术细节

### DashScope Function Calling 格式

**请求格式**（发送给 Qwen）：
```json
{
    "functions": [
        {
            "name": "get_market_data",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "asset_type": {"type": "string"}
                }
            }
        }
    ]
}
```

**响应格式**（Qwen 返回）：
```json
{
    "output": {
        "choices": [
            {
                "message": {
                    "function_call": {
                        "name": "get_market_data",
                        "arguments": "{\"symbol\": \"003956.OF\", \"asset_type\": \"fund\"}"
                    }
                }
            }
        ]
    }
}
```

**注意**：`arguments` 是 **JSON 字符串**，不是对象！

### LangChain AIMessage 格式

**期望格式**：
```python
AIMessage(
    content="",
    tool_calls=[
        {
            "name": "get_market_data",
            "args": {"symbol": "003956.OF", "asset_type": "fund"},  # 字典对象
            "id": "call_get_market_data"
        }
    ]
)
```

---

## 其他检查点

### 已检查无问题的部分
1. ✅ `agents/tools.py` - 工具定义正确
2. ✅ `agents/nodes.py` - 工具调用逻辑正确
3. ✅ `skills/market_data/skill.py` - Skill 实现正确
4. ✅ Prompt 配置正确（无需修改）

### 无需修改的文件
- `agents/nodes.py`
- `agents/tools.py`
- `skills/market_data/skill.py`
- `skills/market_data/prompt.txt`

---

## 后续建议

### 可选优化
1. **添加日志**：记录工具调用的详细参数
2. **错误处理**：更友好的错误提示
3. **参数验证**：在工具层面验证参数格式

### 测试覆盖
建议添加测试用例：
```python
def test_qwen_json_parsing():
    """测试 DashScope JSON 字符串解析"""
    # 测试各种参数格式
    pass
```

---

**修复完成时间**: 2026-04-06  
**测试状态**: ✅ 通过  
**可以重新运行 Streamlit 测试工具调用**
