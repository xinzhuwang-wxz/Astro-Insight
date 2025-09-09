#!/usr/bin/env python3
"""
LangGraph Client for Astrophysics TAP Query System

这是一个LangGraph客户端，使用豆包API作为LLM，通过MCP适配器与天体物理学TAP查询服务器通信。
支持自然语言输入，自动选择合适的工具执行查询。
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    try:
        from langchain_community.chat_models import ChatOpenAI
    except ImportError:
        print("警告: 无法导入ChatOpenAI，请检查langchain安装")
        ChatOpenAI = None
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict, Annotated

try:
    from langchain_mcp_adapters.tools import MCPTool, load_mcp_tools
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
except ImportError:
    print("警告: langchain-mcp-adapters 或 mcp 未安装，请运行: pip install langchain-mcp-adapters mcp")
    MCPTool = None
    load_mcp_tools = None
    ClientSession = None
    stdio_client = None
    StdioServerParameters = None

# 导入项目配置系统
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.loader import load_yaml_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class State(TypedDict):
    """图状态定义"""
    messages: Annotated[List, add_messages]
    user_query: str
    selected_tools: List[str]
    query_results: Dict[str, Any]
    final_response: str

class AstrophysicsQueryClient:
    """
    天体物理学查询客户端
    
    使用LangGraph构建查询流程，集成豆包API和MCP工具
    """
    
    def __init__(self):
        logger.info("🏗️ 初始化天体物理学查询客户端...")
        self.llm = None
        self.mcp_tools = []
        self.graph = None
        
        self._setup_llm()
        self._setup_mock_tools()
        self._build_graph()
        
        logger.info("✅ 客户端初始化完成")
    
    async def initialize_mcp(self):
        """异步初始化MCP工具"""
        await self._setup_mcp_tools()
        # 重新构建图以使用MCP工具
        self._build_graph()
    
    def _setup_llm(self):
        """设置豆包API LLM"""
        try:
            # 从conf.yaml加载配置
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'conf.yaml')
            conf = load_yaml_config(config_path)
            basic_model_conf = conf.get('BASIC_MODEL', {})
            
            # 获取豆包API配置
            api_key = basic_model_conf.get('api_key')
            base_url = basic_model_conf.get('base_url', 'https://ark.cn-beijing.volces.com/api/v3')
            model = basic_model_conf.get('model', 'doubao-pro-4k')
            
            if not api_key:
                raise ValueError("请在conf.yaml文件中设置BASIC_MODEL.api_key")
            
            # 使用OpenAI兼容接口连接豆包，并绑定工具
            self.llm = ChatOpenAI(
                model=model,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=0.1,
                max_tokens=2000
            )
            logger.info(f"豆包API LLM 初始化成功 - 模型: {model}, 基础URL: {base_url}")
            
        except Exception as e:
            logger.error(f"LLM初始化失败: {str(e)}")
            raise
    
    async def _setup_mcp_tools(self):
        """设置MCP工具适配器"""
        if MCPTool is None or load_mcp_tools is None or ClientSession is None:
            logger.warning("MCP适配器不可用，将使用直接调用工具")
            self._setup_mock_tools()
            return
        
        try:
            # 创建MCP会话
            import shutil
            python_path = shutil.which('python')
            
            server_params = StdioServerParameters(
                command=python_path,
                args=['server.py']
            )
            
            # 创建异步会话并加载工具
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.mcp_tools = await load_mcp_tools(session=session)
                    logger.info(f"成功连接MCP服务器，获取到 {len(self.mcp_tools)} 个工具")
            
        except Exception as e:
            logger.error(f"MCP工具设置失败: {str(e)}")
            logger.info("使用直接调用工具代替")
            self._setup_mock_tools()
    
    def _setup_mock_tools(self):
        """设置真实工具（当MCP不可用时，直接调用工具函数）"""
        from langchain_core.tools import tool
        from .tools import get_object_by_identifier as _get_object_by_identifier
        from .tools import get_bibliographic_data as _get_bibliographic_data
        from .tools import search_objects_by_coordinates as _search_objects_by_coordinates
        
        @tool
        def get_object_by_identifier(object_id: str) -> str:
            """
            根据天体标识符获取基础天文数据
            
            这个工具用于查询天体的基本信息，包括：
            - 天体坐标（赤经、赤纬）
            - 主要标识符
            - 视差和径向速度
            - 星系尺寸和角度
            - 参考文献数量
            
            参数:
                object_id (str): 天体标识符，如 'M13', 'NGC 6205', 'Vega', 'Sirius' 等
            
            返回:
                str: 包含天体基础信息的JSON格式字符串
            
            使用场景:
            - 用户询问天体的基本信息
            - 需要获取天体的坐标和物理参数
            - 查询特定天体的基本属性
            """
            try:
                result = _get_object_by_identifier(object_id)
                return str(result)
            except Exception as e:
                return f"查询失败: {str(e)}"
        
        @tool
        def get_bibliographic_data(object_id: str) -> str:
            """
            根据天体标识符获取相关的参考文献和学术论文
            
            这个工具用于查询与特定天体相关的研究文献，包括：
            - 论文的BibCode标识符
            - 期刊名称
            - 论文标题
            - 发表年份
            - 卷号和页码
            - DOI链接
            
            参数:
                object_id (str): 天体标识符，如 'M13', 'NGC 6205', 'Vega' 等
            
            返回:
                str: 包含参考文献列表的JSON格式字符串
            
            使用场景:
            - 用户询问天体的研究文献
            - 需要查找相关的学术论文
            - 了解天体的研究历史
            """
            try:
                result = _get_bibliographic_data(object_id)
                return str(result)
            except Exception as e:
                return f"文献查询失败: {str(e)}"
        
        @tool
        def search_objects_by_coordinates(ra: float, dec: float, radius: float = 0.1) -> str:
            """
            根据天球坐标搜索附近的天体对象
            
            这个工具用于在指定坐标周围搜索天体，包括：
            - 搜索中心坐标（赤经、赤纬）
            - 搜索半径
            - 找到的天体列表
            - 每个天体的距离和类型
            
            参数:
                ra (float): 赤经坐标（度），范围0-360
                dec (float): 赤纬坐标（度），范围-90到90
                radius (float): 搜索半径（度），默认0.1度
            
            返回:
                str: 包含搜索结果的JSON格式字符串
            
            使用场景:
            - 用户提供坐标需要搜索附近天体
            - 需要了解某个区域的天体分布
            - 寻找特定坐标附近的天体对象
            """
            try:
                result = _search_objects_by_coordinates(ra, dec, radius)
                return str(result)
            except Exception as e:
                return f"坐标搜索失败: {str(e)}"
        
        self.mcp_tools = [get_object_by_identifier, get_bibliographic_data, search_objects_by_coordinates]
        logger.info("真实工具设置完成（直接调用工具函数）")
    
    def _build_graph(self):
        """构建LangGraph查询流程"""
        # 创建工具节点
        tool_node = ToolNode(self.mcp_tools)
        
        # 创建状态图
        workflow = StateGraph(State)
        
        # 添加节点 - 简化流程，让LLM直接选择工具
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", tool_node)
        
        # 设置边 - 简化的工作流
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent")
        
        # 编译图
        self.graph = workflow.compile()
        logger.info("LangGraph 查询流程构建完成")
    
    async def _agent_node(self, state: State) -> State:
        """智能代理节点 - 让LLM自己选择工具"""
        messages = state["messages"]
        
        # 构建系统提示，让LLM了解可用的工具
        system_prompt = """你是一个专业的天体物理学助手，可以访问以下工具来查询天体数据：

1. get_object_by_identifier(object_id: str) - 获取天体的基础信息
   - 用于查询天体的坐标、视差、径向速度等基本参数
   - 适用于：询问天体基本信息、坐标、物理参数等

2. get_bibliographic_data(object_id: str) - 获取天体的参考文献
   - 用于查询与天体相关的研究论文和学术文献
   - 适用于：询问研究文献、学术论文、研究历史等

3. search_objects_by_coordinates(ra: float, dec: float, radius: float) - 坐标搜索
   - 用于在指定坐标周围搜索天体
   - 适用于：提供坐标搜索天体、了解区域天体分布等

请根据用户的查询，选择合适的工具并调用。如果需要多个工具，可以依次调用。
"""
        
        # 添加系统消息
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        
        try:
            # 绑定工具到LLM并调用
            llm_with_tools = self.llm.bind_tools(self.mcp_tools)
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            # 只打印工具选择信息
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"🔧 选择工具: {[tool_call['name'] for tool_call in response.tool_calls]}")
            else:
                logger.info("📝 直接返回文本响应")
            
            state["messages"] = messages
            
        except Exception as e:
            logger.error(f"❌ 智能代理节点执行失败: {str(e)}")
            error_message = AIMessage(content=f"处理查询时出现错误: {str(e)}")
            messages.append(error_message)
            state["messages"] = messages
        
        return state
    
    def _should_continue(self, state: State) -> str:
        """判断是否继续执行工具"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # 如果最后一条消息包含工具调用，则继续
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        else:
            # 设置最终响应
            if hasattr(last_message, 'content') and last_message.content:
                state["final_response"] = last_message.content
            else:
                state["final_response"] = "查询完成，但没有返回结果"
            return "end"
    
    async def _analyze_query(self, state: State) -> State:
        """分析用户查询"""
        user_query = state["user_query"]
        
        system_prompt = """
你是一个天体物理学查询助手。分析用户的查询意图，确定需要什么类型的天文数据。

可用的查询类型：
1. 基础信息查询 - 获取天体的坐标、视差、径向速度等基本参数
2. 文献查询 - 获取与天体相关的研究论文和参考文献
3. 坐标搜索 - 根据天球坐标搜索附近的天体

请简要分析用户查询的意图。
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"用户查询: {user_query}")
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            analysis = response.content
            
            state["messages"].append(AIMessage(content=f"查询分析: {analysis}"))
            logger.info(f"查询分析完成: {analysis[:100]}...")
            
        except Exception as e:
            logger.error(f"查询分析失败: {str(e)}")
            state["messages"].append(AIMessage(content=f"查询分析失败: {str(e)}"))
        
        return state
    
    async def _select_tools(self, state: State) -> State:
        """选择合适的工具"""
        user_query = state["user_query"]
        
        # 工具选择逻辑
        selected_tools = []
        query_lower = user_query.lower()
        
        # 检查是否包含天体名称或标识符
        if any(keyword in query_lower for keyword in ['m13', 'ngc', 'vega', 'sirius', 'basic info', 'information']):
            selected_tools.append("get_object_by_identifier")
        
        # 检查是否需要文献信息
        if any(keyword in query_lower for keyword in ['reference', 'paper', 'bibliography', 'literature', 'publication']):
            selected_tools.append("get_bibliographic_data")
        
        # 检查是否是坐标搜索
        if any(keyword in query_lower for keyword in ['coordinate', 'ra', 'dec', 'search', 'nearby']):
            selected_tools.append("search_objects_by_coordinates")
        
        # 如果没有明确匹配，默认使用基础信息查询
        if not selected_tools:
            selected_tools.append("get_object_by_identifier")
        
        state["selected_tools"] = selected_tools
        logger.info(f"选择的工具: {selected_tools}")
        
        return state
    
    async def _generate_response(self, state: State) -> State:
        """生成最终响应"""
        user_query = state["user_query"]
        tool_results = state.get("query_results", {})
        
        system_prompt = """
你是一个专业的天体物理学助手。基于工具查询的结果，为用户提供清晰、准确的回答。

请：
1. 总结查询结果的关键信息
2. 用通俗易懂的语言解释天文数据
3. 如果有多个结果，进行适当的组织和分类
4. 保持科学严谨性的同时，确保可读性
"""
        
        # 构建包含工具结果的消息
        context = f"用户查询: {user_query}\n\n工具查询结果:\n"
        for tool_name, result in tool_results.items():
            context += f"\n{tool_name}: {result}\n"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            final_response = response.content
            
            state["final_response"] = final_response
            state["messages"].append(AIMessage(content=final_response))
            logger.info("最终响应生成完成")
            
        except Exception as e:
            logger.error(f"响应生成失败: {str(e)}")
            error_response = f"抱歉，响应生成时出现错误: {str(e)}"
            state["final_response"] = error_response
            state["messages"].append(AIMessage(content=error_response))
        
        return state
    
    async def query(self, user_input: str) -> str:
        """执行查询"""
        logger.info(f"🚀 执行查询: {user_input}")
        
        # 初始化状态
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "selected_tools": [],
            "query_results": {},
            "final_response": ""
        }
        
        try:
            # 执行图流程，设置递归限制
            config = {"recursion_limit": 10}
            result = await self.graph.ainvoke(initial_state, config=config)
            
            # 如果没有final_response，从最后一条消息中获取
            if not result.get("final_response"):
                messages = result.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content') and last_message.content:
                        result["final_response"] = last_message.content
            
            final_response = result.get("final_response", "查询完成，但没有返回结果")
            logger.info("✅ 查询完成")
            
            return final_response
            
        except Exception as e:
            logger.error(f"❌ 查询执行失败: {str(e)}")
            return f"查询执行失败: {str(e)}"
    
    def query_sync(self, user_input: str) -> str:
        """同步查询接口"""
        return asyncio.run(self.query(user_input))

async def main():
    """主函数 - 交互式查询界面"""
    print("=" * 60)
    print("🌟 天体物理学TAP查询系统 - LangGraph客户端")
    print("=" * 60)
    print("支持的查询类型:")
    print("1. 天体基础信息: 'Give me basic info about M13'")
    print("2. 参考文献: 'Find references for Vega'")
    print("3. 坐标搜索: 'Search objects near RA=250.4, DEC=36.5'")
    print("输入 'quit' 或 'exit' 退出")
    print("=" * 60)
    
    # 初始化客户端
    try:
        client = AstrophysicsQueryClient()
        print("✅ 客户端初始化成功")
    except Exception as e:
        print(f"❌ 客户端初始化失败: {str(e)}")
        return
    
    # 交互循环
    while True:
        try:
            user_input = input("\n🔍 请输入您的查询: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
            
            print("\n⏳ 正在处理查询...")
            response = await client.query(user_input)
            
            print("\n📋 查询结果:")
            print("-" * 40)
            print(response)
            print("-" * 40)
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 查询出错: {str(e)}")

def create_client():
    """创建客户端实例 - 用于非交互式调用"""
    try:
        return AstrophysicsQueryClient()
    except Exception as e:
        logger.error(f"客户端创建失败: {str(e)}")
        raise

def query_astro_data(user_input: str) -> str:
    """
    同步查询接口 - 用于集成到其他模块
    
    Args:
        user_input: 用户查询输入
        
    Returns:
        str: 查询结果
    """
    try:
        client = create_client()
        return client.query_sync(user_input)
    except Exception as e:
        logger.error(f"查询执行失败: {str(e)}")
        return f"数据检索失败: {str(e)}"

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序运行错误: {str(e)}")