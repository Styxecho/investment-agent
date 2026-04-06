# agents/qwen_adapter.py
"""
DashScope Qwen API 适配器（最小化 MVP 版本）
"""
import json
import dashscope
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from utils.logger import logger


class QwenChatModel:
    """
    Qwen 聊天模型适配器
    功能：调用 DashScope API，支持工具绑定和调用
    """
    
    def __init__(self, model_name: str, api_key: str, temperature: float = 0):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.tools = []
        
        # 设置 API Key
        dashscope.api_key = api_key
    
    def bind_tools(self, tools: List[BaseTool]) -> 'QwenChatModel':
        """绑定工具列表"""
        self.tools = tools
        return self
    
    def invoke(self, messages: List) -> AIMessage:
        """
        调用 Qwen API
        
        Args:
            messages: LangChain 消息列表
        
        Returns:
            AIMessage 对象
        """
        # 1. 转换消息格式
        dashscope_messages = self._convert_messages(messages)
        
        # 2. 准备工具定义（如果有）
        functions = None
        if self.tools:
            functions = self._convert_tools(self.tools)
        
        # 3. 调用 API
        try:
            logger.info(f"[Qwen] 调用模型：{self.model_name}")
            
            response = dashscope.Generation.call(
                model=self.model_name,
                messages=dashscope_messages,
                functions=functions,
                temperature=self.temperature,
                result_format='message'  # 返回消息格式
            )
            
            # 4. 解析响应
            if response.status_code == 200:
                output_message = response.output.choices[0].message
                
                # 检查是否有工具调用
                function_call = None
                try:
                    function_call = output_message.get('function_call', None)
                except (KeyError, TypeError, AttributeError):
                    pass
                
                if function_call:
                    # 有工具调用
                    logger.info(f"[Qwen] 检测到工具调用：{function_call.get('name')}")
                    
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
                            "args": args_dict,
                            "id": f"call_{function_call.get('name')}"
                        }]
                    )
                else:
                    # 无工具调用，普通回复
                    ai_msg = AIMessage(content=output_message.get('content', ''))
                
                logger.info(f"[Qwen] 响应成功")
                return ai_msg
            else:
                logger.error(f"[Qwen] API 调用失败：{response.code} - {response.message}")
                return AIMessage(content=f"API 调用失败：{response.code} - {response.message}")
                
        except Exception as e:
            logger.exception(f"[Qwen] 调用异常：{e}")
            return AIMessage(content=f"调用异常：{str(e)}")
    
    def _convert_messages(self, messages: List) -> List[Dict[str, str]]:
        """将 LangChain 消息转为 DashScope 格式"""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                # 检查是否有工具调用
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # 添加 AI 消息（包含工具调用）
                    ai_msg = {"role": "assistant", "content": msg.content}
                    if msg.tool_calls:
                        # 将参数字典序列化为 JSON 字符串（DashScope 要求）
                        args_dict = msg.tool_calls[0]["args"]
                        args_str = json.dumps(args_dict) if isinstance(args_dict, dict) else str(args_dict)
                        
                        ai_msg["function_call"] = {
                            "name": msg.tool_calls[0]["name"],
                            "arguments": args_str  # DashScope 期望 JSON 字符串
                        }
                    result.append(ai_msg)
                else:
                    result.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                # 工具响应消息
                result.append({
                    "role": "function",
                    "name": msg.name,
                    "content": msg.content
                })
        return result
    
    def _convert_tools(self, tools: List[BaseTool]) -> List[Dict[str, Any]]:
        """将 LangChain Tool 转为 DashScope Function 格式"""
        functions = []
        for tool in tools:
            func_def = {
                "name": tool.name,
                "description": tool.description,
            }
            
            # 添加参数 schema（如果有）
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    func_def["parameters"] = tool.args_schema.schema()
                except Exception:
                    # 如果 schema 获取失败，使用空参数
                    func_def["parameters"] = {"type": "object", "properties": {}}
            else:
                func_def["parameters"] = {"type": "object", "properties": {}}
            
            functions.append(func_def)
        
        logger.debug(f"[Qwen] 绑定工具：{[t.name for t in tools]}")
        return functions
