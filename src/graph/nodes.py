# Maxen Wong
# SPDX-License-Identifier: MIT

"""
Command语法节点实现
使用LangGraph 0.2+的Command语法重构核心节点
"""

from typing import Dict, Any, List, Optional, Union, Literal
import time
import logging
import json
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from src.graph.types import AstroAgentState, ExecutionStatus
from src.llms.llm import get_llm_by_type
from src.prompts.template import get_prompt


def track_node_execution(node_name: str):
    """节点执行跟踪装饰器"""
    def decorator(func):
        def wrapper(state: AstroAgentState) -> Command[AstroAgentState]:
            # 更新当前节点
            updated_state = state.copy()
            updated_state["current_node"] = node_name
            
            # 添加到节点历史（如果不在历史中）
            node_history = updated_state.get("node_history", [])
            if not node_history or node_history[-1] != node_name:
                node_history.append(node_name)
                updated_state["node_history"] = node_history
            
            # 输出节点信息
            print(f"\n🔍 当前节点: {node_name}")
            if len(node_history) > 1:
                print(f"📋 历史节点: {' → '.join(node_history[:-1])}")
            else:
                print(f"📋 历史节点: (起始节点)")
            
            # 执行原函数
            result = func(updated_state)
            
            # 如果返回的是Command对象，更新其状态
            if isinstance(result, Command):
                # 合并节点跟踪信息到Command的update中
                if result.update:
                    result.update.update({
                        "current_node": node_name,
                        "node_history": node_history
                    })
                else:
                    result.update = {
                        "current_node": node_name,
                        "node_history": node_history
                    }
            
            return result
        return wrapper
    return decorator
# from src.tools.language_processor import language_processor  # 暂时未使用
# 存储功能已移除 - 分类节点不再需要数据库存储


def _extract_celestial_name_simple(user_input: str) -> str:
    """从用户输入中提取天体名称 - 简单有效的方法（参考complete_simple_system.py）"""
    import re
    
    # 移除常见的分类关键词
    clean_input = user_input
    keywords_to_remove = [
        "分类", "classify", "这个天体", "这个", "天体", "celestial", "object",
        "是什么", "什么类型", "什么", "类型", "type", "分析", "analyze"
    ]
    
    for keyword in keywords_to_remove:
        clean_input = clean_input.replace(keyword, "")
    
    # 移除标点符号
    clean_input = re.sub(r'[：:，,。.！!？?]', '', clean_input)
    
    # 提取可能的天体名称
    # 匹配常见的天体命名模式
    patterns = [
        r'M\d+',  # 梅西耶天体
        r'NGC\s*\d+',  # NGC天体
        r'IC\s*\d+',  # IC天体
        r'HD\s*\d+',  # HD星表
        r'[A-Z][a-z]+\s*\d+',  # 星座+数字
        r'[A-Z][a-z]+',  # 星座名
        r'[A-Z]\d+',  # 单字母+数字
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_input, re.IGNORECASE)
        if match:
            return match.group().strip()
    
    # 如果没有匹配到模式，返回清理后的输入
    return clean_input.strip() if clean_input.strip() else ""


def extract_celestial_info_from_query(user_input: str, user_requirements: str = None) -> dict:
    """从用户查询中提取天体信息 - 使用简单有效的提取逻辑"""
    try:
        # 使用简单规则提取天体名称（参考complete_simple_system.py）
        celestial_name = _extract_celestial_name_simple(user_input)
        
        if not celestial_name:
            celestial_info = {
                "object_name": "未知天体",
                "coordinates": {"ra": None, "dec": None},
                "object_type": "未知",
                "magnitude": None,
                "description": user_input
            }
        else:
            # 构建天体信息
            celestial_info = {
                "object_name": celestial_name,
                "coordinates": {"ra": None, "dec": None},
                "object_type": "未知",
                "magnitude": None,
                "description": user_input
            }
        
        return celestial_info
    except Exception as e:
        logging.warning(f"提取天体信息失败: {e}")
        return {
            "object_name": "未知天体",
            "coordinates": {"ra": None, "dec": None},
            "object_type": "未知",
            "magnitude": None,
            "description": user_input
        }


def _classify_celestial_object_with_llm(user_input: str, celestial_info: dict, llm) -> dict:
    """使用LLM进行智能天体分类（参考complete_simple_system.py）"""
    try:
        object_name = celestial_info.get("object_name", "未知天体")
        
        # 构建分类提示词
        classification_prompt = f"""请对以下天体进行专业的天体分类。

天体名称: {object_name}
用户查询: {user_input}

请按照以下格式返回分类结果（JSON格式）：
{{
    "object_name": "天体名称",
    "primary_category": "主要类别",
    "subcategory": "子类别", 
    "detailed_classification": "详细分类",
    "confidence_level": "置信度",
    "scientific_name": "科学名称",
    "object_type": "天体类型",
    "description": "简要描述"
}}

主要类别选项：
- 恒星 (Star)
- 行星 (Planet) 
- 星系 (Galaxy)
- 星云 (Nebula)
- 星团 (Cluster)
- 小行星 (Asteroid)
- 彗星 (Comet)
- 双星 (Binary Star)
- 超新星 (Supernova)
- 深空天体 (Deep Sky Object)

请根据天体名称和查询内容进行准确分类："""

        # 调用LLM
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=classification_prompt)]
        response = llm.invoke(messages)
        
        # 解析响应
        response_content = response.content.strip()
        
        # 尝试解析JSON
        try:
            import json
            # 清理响应内容，移除markdown代码块格式
            if "```json" in response_content:
                response_content = response_content.split("```json")[1].split("```")[0]
            elif "```" in response_content:
                response_content = response_content.split("```")[1].split("```")[0]
            
            classification_data = json.loads(response_content)
            
            return {
                "classification_result": classification_data,
                "success": True,
                "method": "llm_classification"
            }
            
        except json.JSONDecodeError:
            # 如果JSON解析失败，使用规则分类作为后备
            return _classify_celestial_object_by_rules(user_input, celestial_info)
            
    except Exception as e:
        print(f"LLM分类失败: {e}")
        # 使用规则分类作为后备
        return _classify_celestial_object_by_rules(user_input, celestial_info)


def _analyze_data_for_visualization(data: dict) -> str:
    """分析数据特征，为可视化提供建议"""
    if not data:
        return "数据为空。"
    
    analysis_parts = []
    
    # 数据字段检查（已简化，不显示建议）
    if not analysis_parts:
        analysis_parts.append("数据字段完整")
    
    return "\n".join(analysis_parts)


def _classify_celestial_object_by_rules(user_input: str, celestial_info: dict) -> dict:
    """基于规则的天体分类"""
    try:
        # 简单的基于关键词的分类逻辑
        user_input_lower = user_input.lower()
        object_name = celestial_info.get("object_name", "").lower()
        
        # 分类逻辑
        if any(keyword in user_input_lower or keyword in object_name for keyword in ["恒星", "star", "太阳"]):
            primary_category = "恒星"
            subcategory = "主序星"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["行星", "planet", "火星", "金星", "木星"]):
            primary_category = "行星"
            subcategory = "类地行星" if any(k in user_input_lower for k in ["火星", "金星", "地球"]) else "气态巨行星"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["星系", "galaxy", "银河", "仙女座", "仙女座星系", "m31", "andromeda"]):
            primary_category = "星系"
            subcategory = "螺旋星系"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["星云", "nebula"]):
            primary_category = "星云"
            subcategory = "发射星云"
        elif "m87" in object_name or "m87" in user_input_lower:
            primary_category = "星系"
            subcategory = "椭圆星系"
        elif object_name.startswith("m") and object_name[1:].isdigit():
            # 梅西耶天体的一般分类
            primary_category = "深空天体"
            subcategory = "梅西耶天体"
        else:
            primary_category = "未分类"
            subcategory = "需要更多信息"
        
        return {
            "classification_result": {
                "object_name": celestial_info.get("object_name", "未知天体"),
                "primary_category": primary_category,
                "subcategory": subcategory,
                "detailed_classification": f"{primary_category} - {subcategory}",
                "confidence_level": "中等",
                "key_features": ["基于关键词分析"],
                "coordinates": celestial_info.get("coordinates", {"ra": "未知", "dec": "未知"}),
                "additional_info": {
                    "magnitude": celestial_info.get("magnitude", "未知"),
                    "distance": "未知",
                    "spectral_type": "未知",
                },
            },
            "explanation": f"基于关键词分析，该天体被分类为{primary_category}。",
            "suggestions": ["提供更多观测数据以获得更准确的分类"],
        }
    except Exception as e:
        logging.warning(f"基于规则的分类失败: {e}")
        return {
            "classification_result": {
                "object_name": "未知天体",
                "primary_category": "未分类",
                "subcategory": "分类失败",
                "detailed_classification": "无法分类",
                "confidence_level": "低",
                "key_features": ["分类失败"],
                "coordinates": {"ra": "未知", "dec": "未知"},
                "additional_info": {
                    "magnitude": "未知",
                    "distance": "未知",
                    "spectral_type": "未知",
                },
            },
            "explanation": "分类过程中发生错误。",
            "suggestions": ["请重新尝试或提供更多信息"],
        }


# 设置logger
logger = logging.getLogger(__name__)


# LLM服务初始化 - 使用豆包模型
try:
    llm: BaseChatModel = get_llm_by_type("basic")
except Exception as e:
    print(f"Warning: Failed to initialize LLM: {e}")
    llm = None


@track_node_execution("identity_check")
def identity_check_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    身份识别节点 - Command语法实现
    判断用户类型（amateur/professional）并直接路由到下一个节点
    """
    try:
        user_input = state["user_input"]  # 在下方prompt中，用户输入会被Python解释器立即替换为 user_input 变量的实际值
        
        # 输入验证
        if user_input is None or not isinstance(user_input, str):
            raise ValueError("Invalid user_input: must be a non-empty string")

        # 使用大模型进行身份识别 - 完全依赖LLM判断
        if llm:
            identity_prompt = f"""请仔细分析以下用户输入，判断用户是天文爱好者还是专业研究人员。

用户输入: {user_input}

判断标准：
- amateur（爱好者）：是否表明amateur(爱好者) 询问基础天文知识、概念解释、科普问题、学习性问题
  例如："什么是黑洞呀？"、"恒星是如何形成的呀？"、"银河系有多大呀？"、"这颗星好亮呀"、"有趣的天文现象"
  
- professional（专业用户）：是否表明professional(专业用户)，需要专业分析、数据处理、天体分类、数据检索、图表绘制等
  例如："M87属于什么类型？"、"分类这个天体：M87"、"获取SDSS星系数据"、"绘制天体位置图"、"分析M87的射电星系特征"、"M31的参考文献"、"M31的特征"、"M31的性质"、"M31相关文献"、"离M31最近的星系有哪些"、"提供坐标判断星系"

关键区别：
- 优先级最高的是身份识别，如果明确爱好者（amateur），按照amateur（爱好者）处理。 问"有多大"、"这颗星好亮"、"有趣的天文现象" → amateur（科普问题）
- 优先级最高的是身份识别，如果明确专业人士 (professional)，按照professional（专业用户）处理。问"属于什么类型"、"分类"、"分析特征" → professional（专业分类/分析）

请仔细分析用户的语言风格、问题深度和专业需求，然后只返回：amateur 或 professional
"""
            
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=identity_prompt)]
            response = llm.invoke(messages)  # 按prompt要求，只返回amateur 或 professional
            user_type = response.content.strip().lower()
                
            # 验证响应
            if user_type not in ["amateur", "professional"]:
                # 如果LLM返回的不是预期格式，尝试从文本中提取
                if "professional" in user_type or "专业" in user_type:
                    user_type = "professional"
                elif "amateur" in user_type or "爱好者" in user_type or "业余" in user_type:
                    user_type = "amateur"
                else:
                    user_type = "amateur"  # 默认为爱好者
        else:
            # 如果LLM不可用，报错而不是使用关键词判断
            raise Exception("LLM服务不可用，无法进行身份识别")

        # 更新状态 - 只更新必要的字段，避免字段冲突
        updated_state = {
            "user_type": user_type,
            "current_step": "identity_checked",
            "identity_completed": True
        }

        # 使用Command语法直接路由到下一个节点
        if user_type == "amateur":
            # 业余用户需要先进行QA问答
            return Command(
                update=updated_state,
                goto="qa_agent"
            )
        elif user_type == "professional":
            # 专业用户直接进入任务选择
            return Command(
                update=updated_state,
                goto="task_selector"
            )
        else:
            # 异常情况，默认为业余用户，进入QA问答
            updated_state["user_type"] = "amateur"
            return Command(
                update=updated_state,
                goto="qa_agent"
            )

    except Exception as e:
        # 错误处理 - 只更新必要的字段
        error_state = {
            "error_info": {
                "node": "identity_check_command_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        
        return Command(
            update=error_state,
            goto="error_recovery"
        )


# 存储功能已移除 - 分类节点不再需要数据库存储


# real_time_retrieval_command_node已删除 - 在builder.py中未使用


# 数据库存储功能已移除 - 分类节点不再需要数据存储


# 兼容版本的_node函数已删除 - 在builder.py中未使用


@track_node_execution("qa_agent")
def qa_agent_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    QA问答节点 - 简化版本，集成Tavily搜索，直接结束
    处理爱好者的天文问答，不再提供专业模式选择
    """
    try:
        user_input = state["user_input"]
        user_type = state.get("user_type", "amateur")

        # 集成Tavily搜索获取最新信息
        search_context = ""
        search_sources = []
        tavily_success = False
        try:
            from src.tools.tavily_search.tavily_search_api_wrapper import tavily_search
            search_query = f"天文 {user_input}"
            # 使用环境变量配置的max_results，不传参数让函数自动使用配置
            search_results = tavily_search(search_query)
            if search_results:
                # 将搜索结果作为上下文提供给LLM，让LLM智能整合
                search_context = "\n\n[最新网络信息参考] "
                for i, result in enumerate(search_results[:2], 1):
                    title = result.get('title', '无标题')
                    content = result.get('content', '无内容')[:100]
                    url = result.get('url', '')
                    search_context += f"{title}: {content}... "
                    
                    # 收集来源信息用于最后的参考列表（保持原始语言）
                    if url:
                        domain = result.get('domain', 'unknown')
                        # 保持原始标题，不进行翻译
                        search_sources.append(f"{title} ({domain})")
                
                search_context += "请将这些信息自然地整合到回答中，不要直接引用。"
                tavily_success = True
        except Exception as e:
            print(f"Tavily搜索失败: {e}")
            search_context = ""

        # 检查是否是天体分类问题
        is_classification_question = (
            "分类" in user_input or 
            "类型" in user_input or 
            "属于" in user_input or
            # "是什么" in user_input or  # “是什么” 适合检索任务
            state.get("current_step") == "simbad_query_failed"  # 如果SIMBAD查询失败，跳转到QA代理处理
        )
        
        # 使用prompt模板获取QA提示词
        try:
            if is_classification_question:
                # 使用专门的天体分类prompt
                qa_prompt_content = f"""作为专业天文学家，请回答以下天体分类问题：

用户问题：{user_input}
用户类型：{user_type}

请提供：
1. 天体的准确分类（主分类、子分类、详细分类）
2. 该天体的基本特征和性质
3. 在天文学中的重要性
4. 相关的观测特征

请用专业但易懂的语言回答，适合{user_type}用户的理解水平。"""
            else:
                qa_prompt_content = get_prompt(
                    "qa_agent", user_input=user_input, user_type=user_type
                )  # 如果用户输入不是分类问题，使用QA问答模板
            qa_prompt = ChatPromptTemplate.from_template(qa_prompt_content)
        except Exception:
            qa_prompt = None

        # 生成回答
        llm = get_llm_by_type("basic")
        if llm is None or qa_prompt is None:
            # 临时处理：如果LLM未初始化，提供默认回答
            response_content = f"感谢您的天文问题：{user_input}。这是一个很有趣的天文话题！由于当前LLM服务未配置，请稍后再试。"
        else:
            # 将搜索上下文添加到用户输入中
            enhanced_input = user_input + search_context
            chain = qa_prompt | llm
            response = chain.invoke({"user_input": enhanced_input, "user_type": user_type})
            # 确保 response_content 是字符串
            if hasattr(response, 'content'):
                response_content = str(response.content)
            else:
                response_content = str(response)

        # 直接使用LLM整合后的回答，不再添加原始搜索结果
        final_response = response_content
        
        # 如果 Tavily 搜索成功并返回了结果，添加参考来源
        if tavily_success and search_sources:
            final_response += "\n\n📚 参考来源：\n"
            for i, source in enumerate(search_sources[:3], 1):
                final_response += f"{i}. {source}\n"

        # 更新状态
        updated_state = state.copy()
        updated_state["qa_response"] = final_response
        updated_state["final_answer"] = final_response
        updated_state["current_step"] = "qa_completed"
        updated_state["is_complete"] = True
        updated_state["task_type"] = "qa"

        # 添加助手消息
        if "messages" not in updated_state:
            updated_state["messages"] = []
        updated_state["messages"].append({"role": "assistant", "content": final_response})  # 作用是记录对话历史

        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "qa_agent_command_node",
            "action": "generate_qa_response_with_search",
            "input": user_input,
            "output": final_response,
            "timestamp": time.time(),
        })
        
        updated_state["execution_history"] = execution_history

        # 直接结束，不再询问是否进入专业模式
        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        # 错误处理
        error_message = f"抱歉，处理您的问题时遇到了技术问题：{str(e)}。请稍后再试。"
        error_state = state.copy()
        error_state["final_answer"] = error_message
        error_state["qa_response"] = error_message
        error_state["error_info"] = {
            "node": "qa_agent_command_node",
            "error": str(e),
            "timestamp": time.time(),
        }
        error_state["retry_count"] = error_state.get("retry_count", 0) + 1
        
        return Command(
            update=error_state,
            goto="error_recovery"
        )


@track_node_execution("classification_config")
def classification_config_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    天体分类配置节点 - Command语法实现
    根据用户输入的天体信息进行天体分类，并完成实时数据检索和数据库存储
    """
    try:
        user_input = state["user_input"]
        user_requirements = state.get("user_requirements", user_input)
        
        # 从用户查询中提取天体信息
        celestial_info = extract_celestial_info_from_query(
            user_input, user_requirements
        )

        # 使用prompt模板获取配置提示词
        try:
            config_prompt_content = get_prompt(
                "classification_config",
                user_query=user_input,
                celestial_info=str(celestial_info),
                task_type="classification",
            )
        except Exception:
            config_prompt_content = None

        # 调用LLM进行天体分类
        llm = get_llm_by_type("basic")
        if llm is None:
            # 使用增强的基于规则的分类逻辑
            classification_result = _classify_celestial_object_by_rules(
                user_input, celestial_info
            )
        else:
            try:
                # 使用LLM进行智能天体分类（参考complete_simple_system.py）
                classification_result = _classify_celestial_object_with_llm(
                    user_input, celestial_info, llm
                    )
            except Exception:
                # LLM调用失败时使用基于规则的分类逻辑作为fallback
                classification_result = _classify_celestial_object_by_rules(
                    user_input, celestial_info
                )

        # === 集成实时数据检索功能 ===
        # 从分类结果中获取天体信息
        celestial_info_result = classification_result.get("classification_result", {})
        object_name = celestial_info_result.get("object_name", "Unknown")
        object_type = celestial_info_result.get("primary_category", "Unknown")
        coordinates = celestial_info_result.get("coordinates", {})
        
        # 尝试从SIMBAD获取实时数据
        from src.code_generation.templates import query_simbad_by_name
        
        simbad_result = query_simbad_by_name(object_name)
        
        # 如果SIMBAD查询失败，跳转到QA代理处理
        if not simbad_result.get('found', False):
            # 更新状态，跳转到QA代理
            updated_state = state.copy()
            updated_state["current_step"] = "simbad_query_failed"
            updated_state["simbad_failed_object"] = object_name
            updated_state["user_input"] = f"请找到{object_name}所属的分类，并做简单介绍"
            
            # 记录执行历史
            execution_history = updated_state.get("execution_history", [])
            execution_history.append({
                "node": "classification_config_command_node",
                "action": "simbad_query_failed_redirect_to_qa",
                "input": user_input,
                "output": f"SIMBAD查询失败，跳转到QA代理处理{object_name}分类",
                "timestamp": time.time(),
            })
            updated_state["execution_history"] = execution_history
            
            return Command(
                update=updated_state,
                goto="qa_agent"
            )
        
        if simbad_result.get('found', False):
            # 从SIMBAD获取到数据
            ra_val = simbad_result.get('coordinates', {}).get('ra', None)
            dec_val = simbad_result.get('coordinates', {}).get('dec', None)
            
            # 确保坐标值是数字类型
            try:
                ra_val = float(ra_val) if ra_val is not None else None
            except (ValueError, TypeError):
                ra_val = None
            try:
                dec_val = float(dec_val) if dec_val is not None else None
            except (ValueError, TypeError):
                dec_val = None
                
            real_coordinates = {"ra": ra_val, "dec": dec_val}
            real_magnitude = simbad_result.get('magnitude', None)
            object_name = simbad_result.get('object_name', object_name)
        else:
            # 如果SIMBAD没有找到，使用现有坐标或标记为未找到
            real_coordinates = coordinates if coordinates.get("ra") and coordinates.get("dec") else {"ra": None, "dec": None}
            real_magnitude = None
        
        # 构建检索结果（只显示真实查询的数据源和字段）
        data_sources = ["SIMBAD"] if simbad_result.get('found', False) else []
        retrieval_result = {
            "status": "success" if simbad_result.get('found', False) else "no_data",
            "data_sources_queried": data_sources,
            "total_records": 1 if simbad_result.get('found', False) else 0,
            "query_timestamp": time.time()
        }
        
        # 只添加SIMBAD实际返回的字段
        if simbad_result.get('found', False):
            retrieval_result["coordinates"] = real_coordinates
            retrieval_result["object_type"] = simbad_result.get('object_type', 'Unknown')
            if real_magnitude is not None:
                retrieval_result["magnitude"] = real_magnitude
        
        # 分类任务不需要存储数据，直接返回分析结果

        # 更新状态
        updated_state = state.copy()
        updated_state["classification_result"] = classification_result
        updated_state["retrieval_result"] = retrieval_result
        updated_state["classification_config"] = {
            "configured": True,
            "celestial_info": celestial_info,
            "classification_method": "llm_analysis" if llm else "rule_based",
            "timestamp": time.time(),
        }
        updated_state["current_step"] = "classification_and_storage_completed"
        updated_state["is_complete"] = True

        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "classification_config_command_node",
            "action": "celestial_classification_with_storage",
            "input": user_input,
            "output": f"Classified {object_name} as {object_type}, retrieved and stored data",
            "timestamp": time.time(),
        })
        updated_state["execution_history"] = execution_history

        # 初始化对话历史
        if "conversation_history" not in updated_state:
            updated_state["conversation_history"] = []

        # 添加分类结果到对话历史
        updated_state["conversation_history"].append({
            "type": "system",
            "content": f"天体分析完成：{object_name} - {object_type}",
            "timestamp": time.time(),
        })
        
        # 生成最终答案
        coord_display = f"RA={real_coordinates.get('ra', 'N/A')}, DEC={real_coordinates.get('dec', 'N/A')}"
        magnitude = real_magnitude if real_magnitude is not None else "N/A"
        
        # 分析数据特征，为可视化提供建议
        data_analysis = _analyze_data_for_visualization(retrieval_result)
        
        # 构建详细的分类结果显示
        simbad_classification = ""
        if simbad_result.get('found', False):
            # 获取分类信息
            main_cat = simbad_result.get('main_category', '')
            sub_cat = simbad_result.get('sub_category', '')
            detailed = simbad_result.get('detailed_classification', '')
            simbad_type = simbad_result.get('object_type', 'N/A')
            
            # 常识性验证：M31应该是旋涡星系，不是射电星系
            if object_name.upper() in ['M31', 'MESSIER 31', 'NGC 224', '仙女座星系']:
                if '射电星系' in sub_cat or '射电星系' in detailed:
                    # 修正为正确的分类
                    main_cat = '星系'
                    sub_cat = '旋涡星系'
                    detailed = '旋涡星系 (Spiral Galaxy)'
                    simbad_type = 'S'  # 旋涡星系的SIMBAD代码
            
            # 清理和构建层次结构 - 直接使用SIMBAD原始数据，不进行硬编码映射
            hierarchy = []
            
            # 直接使用SIMBAD返回的分类数据，保持原始准确性
            if main_cat and main_cat not in ['Unknown', 'N/A', '']:
                hierarchy.append(main_cat)
            
            if sub_cat and sub_cat not in ['Unknown', 'N/A', ''] and sub_cat != main_cat:
                hierarchy.append(sub_cat)
            
            if detailed and detailed not in ['Unknown', 'N/A', ''] and detailed != sub_cat and detailed != main_cat:
                hierarchy.append(detailed)
            
            # 去重处理：移除重复的层级
            unique_hierarchy = []
            for level in hierarchy:
                if level not in unique_hierarchy:
                    unique_hierarchy.append(level)
            hierarchy = unique_hierarchy
            
            # 构建缩进式层次结构
            hierarchy_tree = ""
            if hierarchy:
                for i, level in enumerate(hierarchy):
                    indent = "  " * i  # 每层缩进2个空格
                    hierarchy_tree += f"{indent}└─ {level}\n"
                hierarchy_tree = hierarchy_tree.rstrip()  # 移除最后的换行符
            else:
                hierarchy_tree = "└─ 未知类型"
            
            # 构建SIMBAD分类详情
            simbad_classification = f"""
SIMBAD分类详情:
- SIMBAD类型: {simbad_type}
- 分类层次:
{hierarchy_tree}
- 关键特征: {simbad_result.get('key_features', 'N/A')}
- 置信度: {simbad_result.get('confidence', 'N/A')}"""

        
        # 使用中文分类结果
        main_cat = simbad_result.get('main_category', '') if simbad_result.get('found', False) else ''
        chinese_classification = main_cat if main_cat and main_cat not in ['Unknown', 'N/A', ''] else '未知类型'
        
        final_answer = f"""天体分析完成！
        
天体名称: {object_name}
分类结果: {chinese_classification}{simbad_classification}
坐标: {coord_display}

{data_analysis}"""
        
        updated_state["final_answer"] = final_answer

        # 分类、检索和存储完成后，直接结束流程
        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        # 错误处理
        error_state = state.copy()
        error_state["error_info"] = {
            "node": "classification_config_command_node",
            "error": f"天体分析失败: {str(e)}",
            "timestamp": time.time(),
        }
        error_state["retry_count"] = error_state.get("retry_count", 0) + 1
        
        return Command(
            update=error_state,
            goto="error_recovery"
        )


# 第一个data_retrieval_command_node定义已删除 - 使用第二个版本（带装饰器）


# literature_review_command_node已删除 - 在builder.py中未使用


def error_recovery_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """错误恢复Command节点 - 处理系统错误和异常情况，最大重试3次"""
    try:
        error_info = state.get("error_info")
        retry_count = state.get("retry_count", 0)
        last_error_node = state.get("last_error_node")
        
        # 检查是否是同一个节点的重复错误，避免无限循环
        current_error_node = error_info.get("node") if error_info else None
        
        # 最大重试次数限制为3次
        MAX_RETRY_COUNT = 3
        
        if retry_count >= MAX_RETRY_COUNT or (current_error_node == last_error_node and retry_count > 0):
            # 超过重试次数或同一节点重复错误，提供降级服务并结束流程
            reason = "超过最大重试次数" if retry_count >= MAX_RETRY_COUNT else "检测到循环错误"
            
            fallback_response = f"""抱歉，系统在处理您的请求时遇到了问题（{reason}），现在提供基本服务。
            
错误节点：{current_error_node or '未知'}
错误信息：{error_info.get('error', '未知错误') if error_info else '系统异常'}
重试次数：{retry_count}

建议：
1. 请简化您的问题重新提问
2. 检查输入格式是否正确
3. 稍后再试

如果问题持续存在，请联系技术支持。"""

            # 只更新必要的字段，避免复制整个状态
            updated_state = {
                "qa_response": fallback_response,
                "final_answer": fallback_response,
                "current_step": "error_handled",
                "is_complete": True
            }

            # 处理messages
            if "messages" in state:
                updated_state["messages"] = state["messages"].copy()
            else:
                updated_state["messages"] = []
            updated_state["messages"].append(
                {"role": "assistant", "content": fallback_response}
            )
            
            # 不更新execution_history，避免字段冲突
            
            # 结束流程，不再重试
            return Command(
                update=updated_state,
                goto="__end__"
            )
        else:
            # 在重试限制内，根据错误来源进行有针对性的恢复
            updated_state = {
                "last_error_node": current_error_node,  # 记录当前错误节点
                "error_recovery_completed": True
            }

            # 不更新execution_history，避免字段冲突
            
            # 根据错误来源决定恢复策略
            error_node = error_info.get("node") if error_info else None
            
            # 由于已经合并了节点，现在只需要处理classification_config_command_node的错误
            if error_node == "classification_config_command_node":
                # 分类错误，重试分类（现在包含了完整的分析流程）
                updated_state["current_step"] = "classification_retry"
                return Command(
                    update=updated_state,
                    goto="classification_config"
                )
            else:
                # 其他错误或未知错误，提供降级服务并结束
                fallback_response = f"""抱歉，系统遇到了问题，但我可以为您提供基本信息。
                
错误信息：{error_info.get('error', '未知错误') if error_info else '系统异常'}
重试次数：{retry_count + 1}/{MAX_RETRY_COUNT}

建议：
1. 请简化您的问题重新提问
2. 检查输入格式是否正确
3. 稍后再试

如果问题持续存在，请联系技术支持。"""

                updated_state["qa_response"] = fallback_response
                updated_state["final_answer"] = fallback_response
                updated_state["current_step"] = "error_handled"
                updated_state["is_complete"] = True

                if "messages" not in updated_state:
                    updated_state["messages"] = []
                updated_state["messages"].append(
                    {"role": "assistant", "content": fallback_response}
                )
                
                return Command(
                    update=updated_state,
                    goto="__end__"
                )

    except Exception as e:
        # 错误恢复节点本身出错，直接标记完成
        error_state = state.copy()
        error_state["qa_response"] = "系统遇到严重错误，请稍后重试。"
        error_state["current_step"] = "fatal_error"
        error_state["is_complete"] = True
        return Command(
             update=error_state,
             goto="__end__"
         )


# code_generator_command_node已删除 - 在builder.py中未使用


@track_node_execution("task_selector")
def task_selector_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    任务选择节点 - Command语法实现
    根据用户输入选择具体的任务类型并直接路由
    """
    try:
        user_input = state["user_input"]
        user_type = state.get("user_type", "amateur")
        
        # 检查是否来自user_choice_handler，如果是则根据原始问题选择任务类型
        if state.get("from_user_choice", False):
            # 从执行历史中找到原始问题
            execution_history = state.get("execution_history", [])
            original_question = None
            for entry in reversed(execution_history):
                if (entry.get("node") in ["identity_check_command_node", "qa_agent_command_node"] and 
                    entry.get("action") in ["process_user_input", "generate_qa_response"] and
                    entry.get("input") and 
                    entry.get("input").lower() not in ["是", "y", "yes", "要", "需要", "1", "否", "n", "no", "不要", "不需要", "0"]):
                    original_question = entry.get("input")
                    break
            
            if original_question:
                user_input = original_question
            else:
                user_input = state["user_input"]
        else:
            # 获取LLM实例
            llm = get_llm_by_type("basic")

            # 使用prompt模板获取任务选择提示词
            try:
                task_prompt_content = get_prompt("task_selection", 
                                               user_input=user_input, 
                                               user_type=user_type)
                task_prompt = ChatPromptTemplate.from_template(task_prompt_content)
            except Exception as e:
                # 继续执行，不依赖prompt模板
                task_prompt = None

            # 使用大模型进行任务类型识别 - 完全依赖LLM判断
            if llm:  # {user_input} 会被Python解释器立即替换为 user_input 变量的实际值
                task_prompt = f"""请仔细分析以下专业用户输入，识别具体的任务类型。

用户输入: {user_input}

任务类型定义：
- classification: 天体分类任务（识别天体类型）
  例如："这是哪种天体？"、"M87属于什么类型？"、"分类这个天体"、"识别天体类型"
  
- retrieval: 数据检索任务（获取和分析数据）
  例如："分析M87的射电星系特征"、"获取星系数据"、"查询SDSS数据"、"检索天体信息"、"分析天体特征"、"研究天体性质"、"M31是什么"、"M31的参考文献"、"M31的特征"、"M31的性质"、"M31相关文献"、"离M31最近的星系有哪些"、"提供坐标判断星系"
  
- visualization: 绘制图表任务（生成图像和图表）
  例如："绘制天体位置图"、"生成光谱图"、"可视化数据"、"创建图表"、"制作图像"、"绘制分布图"

- multimark: 图片识别标注任务（分析天文图像并标注）
  例如："标注这张星系图像"、"识别图像中的天体"、"分析天文照片"、"标记图像中的对象"、"图像标注"、"图片分析"、"识别照片中的天体"

关键区别：
- classification: 问"是什么类型"、"属于什么分类"
- retrieval: 问"分析特征"、"研究性质"、"获取数据"、"提供坐标"、"星系的参考文献"、"提供特征"、"提供性质"、"提供最近的星系"、"分析星系坐标"
- visualization: 问"绘制"、"生成图表"、"可视化"
- multimark: 问"标注"、"识别图像"、"分析照片"、"标记图像"

请仔细分析用户的具体需求，然后只返回：classification、retrieval、visualization 或 multimark
"""
                
                from langchain_core.messages import HumanMessage
                messages = [HumanMessage(content=task_prompt)] 
                response = llm.invoke(messages)
                task_type = response.content.strip().lower()
                
                # 验证响应
                if task_type not in ["classification", "retrieval", "visualization", "multimark"]:
                    # 如果LLM返回的不是预期格式，尝试从文本中提取
                    if "classification" in task_type or "分类" in task_type:
                        task_type = "classification"
                    elif "retrieval" in task_type or "检索" in task_type or "数据" in task_type:
                        task_type = "retrieval"
                    elif "visualization" in task_type or "可视化" in task_type or "图表" in task_type:
                        task_type = "visualization"
                    elif "multimark" in task_type or "标注" in task_type or "图像" in task_type or "图片" in task_type:
                        task_type = "multimark"
                    else:
                        task_type = "classification"  # 默认为分类任务
            else:
                # 如果LLM不可用，报错而不是使用关键词判断
                raise Exception("LLM服务不可用，无法进行任务类型识别")
            
            updated_state = state.copy()

        # 更新状态
        updated_state = state.copy()
        updated_state["task_type"] = task_type
        updated_state["selected_task_type"] = task_type  # 为了兼容测试
        updated_state["current_step"] = "task_selected"
        updated_state["confidence"] = 0.8  # 基于规则的置信度
        
        # 清除临时标记，避免影响后续流程
        if "from_user_choice" in updated_state:
            del updated_state["from_user_choice"]
        if "default_task_type" in updated_state:
            del updated_state["default_task_type"]
        
        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "task_selector",
            "action": task_type,
            "input": user_input,
            "output": task_type,
            "timestamp": time.time()
        })
        updated_state["execution_history"] = execution_history
        
        # 路由逻辑 - 四个主要任务类型
        if task_type == "classification":
            return Command(
                update=updated_state,
                goto="classification_config"
            )
        elif task_type == "retrieval":
            return Command(
                update=updated_state,
                goto="data_retrieval"
            )
        elif task_type == "visualization":
            return Command(
                update=updated_state,
                goto="visualization"
            )
        elif task_type == "multimark":
            return Command(
                update=updated_state,
                goto="multimark"
            )
        else:
            # 默认分类任务
            updated_state["task_type"] = "classification"
            return Command(
                update=updated_state,
                goto="classification_config"
            )

    except Exception as e:
        # 错误处理
        error_state = state.copy()
        error_state["error_info"] = {
            "node": "task_selector_command_node",
            "error": str(e),
            "timestamp": time.time(),
        }
        error_state["retry_count"] = error_state.get("retry_count", 0) + 1
        
        return Command(
            update=error_state,
            goto="error_recovery"
        )


@track_node_execution("data_retrieval")
def data_retrieval_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    数据检索节点 - 处理专业用户的数据检索任务
    """
    try:
        user_input = state["user_input"]
        
        # 导入MCP检索客户端
        try:
            from ..mcp_retrieval.client import query_astro_data
        except ImportError as e:
            logger.error(f"无法导入MCP检索客户端: {e}")
            # 如果导入失败，使用备用方案
            updated_state = state.copy()
            updated_state["current_step"] = "data_retrieval_completed"
            updated_state["is_complete"] = True
            updated_state["final_answer"] = f"数据检索功能暂时不可用。\n\n您的请求：{user_input}\n\n错误信息：{str(e)}\n\n请检查MCP检索模块是否正确安装。"
            
            # 记录执行历史
            execution_history = updated_state.get("execution_history", [])
            execution_history.append({
                "node": "data_retrieval_command_node",
                "action": "import_error",
                "input": user_input,
                "output": f"导入错误: {str(e)}",
                "timestamp": time.time()
            })
            updated_state["execution_history"] = execution_history
            
            return Command(
                update=updated_state,
                goto="__end__"
            )
        
        # 使用MCP检索客户端执行查询
        logger.info(f"🔍 开始执行数据检索查询: {user_input}")
        
        try:
            # 调用MCP检索客户端
            retrieval_result = query_astro_data(user_input)
            logger.info("✅ 数据检索查询完成")
            
            # 构建最终答案
            final_answer = f"🔍 **数据检索结果**\n\n"
            final_answer += f"**查询内容**: {user_input}\n\n"
            final_answer += f"**检索结果**:\n{retrieval_result}\n\n"
            final_answer += "---\n"
            final_answer += "📊 **数据来源**: SIMBAD TAP服务\n"
            final_answer += "🛠️ **检索工具**: MCP检索客户端\n"
            final_answer += "✨ **功能特点**: 支持天体基础信息、文献查询、坐标搜索"
            
        except Exception as query_error:
            logger.error(f"数据检索查询执行失败: {query_error}")
            final_answer = f"❌ **数据检索失败**\n\n"
            final_answer += f"**查询内容**: {user_input}\n\n"
            final_answer += f"**错误信息**: {str(query_error)}\n\n"
            final_answer += "请检查：\n"
            final_answer += "- 网络连接是否正常\n"
            final_answer += "- SIMBAD TAP服务是否可用\n"
            final_answer += "- 查询格式是否正确\n\n"
            final_answer += "💡 **建议**: 尝试使用天体名称（如M13、Vega）或坐标进行查询"
        
        # 更新状态
        updated_state = state.copy()
        updated_state["current_step"] = "data_retrieval_completed"
        updated_state["is_complete"] = True
        updated_state["final_answer"] = final_answer
        updated_state["task_type"] = "data_retrieval"
        
        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "data_retrieval_command_node",
            "action": "mcp_data_retrieval",
            "input": user_input,
            "output": final_answer,
            "timestamp": time.time(),
            "details": {
                "retrieval_success": "error" not in final_answer.lower(),
                "result_length": len(final_answer)
            }
        })
        updated_state["execution_history"] = execution_history

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        # 错误处理
        error_state = state.copy()
        error_state["error_info"] = {
            "node": "data_retrieval_command_node",
            "error": str(e),
            "timestamp": time.time(),
        }
        error_state["final_answer"] = f"数据检索过程中发生错误：{str(e)}"
        error_state["is_complete"] = True
        
        return Command(
            update=error_state,
            goto="__end__"
        )


@track_node_execution("visualization")
def visualization_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    可视化节点 - 处理专业用户的图表绘制任务
    """
    try:
        user_input = state["user_input"]
        
        # 生成可视化代码
        visualization_code = f'''# 天文可视化代码
# 用户需求: {user_input}
# 请安装必要的依赖: pip install matplotlib numpy astropy

import matplotlib.pyplot as plt
import numpy as np
from astropy import coordinates as coords
from astropy import units as u

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 创建图形
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
fig.suptitle('天文数据可视化', fontsize=16)

# 示例数据
ra = np.random.uniform(0, 360, 100)
dec = np.random.uniform(-90, 90, 100)
magnitude = np.random.uniform(10, 20, 100)

# 散点图 - 坐标分布
axes[0, 0].scatter(ra, dec, c=magnitude, cmap='viridis', alpha=0.7)
axes[0, 0].set_xlabel('赤经 (度)')
axes[0, 0].set_ylabel('赤纬 (度)')
axes[0, 0].set_title('天体坐标分布')

# 柱状图 - 星等分布
axes[0, 1].hist(magnitude, bins=20, alpha=0.7, color='skyblue')
axes[0, 1].set_xlabel('星等')
axes[0, 1].set_ylabel('数量')
axes[0, 1].set_title('星等分布')

# 极坐标图 - 天空分布
ax_polar = fig.add_subplot(2, 2, 3, projection='polar')
ax_polar.scatter(np.radians(ra), dec, c=magnitude, cmap='plasma', alpha=0.7)
ax_polar.set_title('天空分布图')

# 线图 - 示例时间序列
time = np.linspace(0, 10, 100)
flux = np.sin(time) + 0.1 * np.random.randn(100)
axes[1, 1].plot(time, flux, 'b-', alpha=0.7)
axes[1, 1].set_xlabel('时间')
axes[1, 1].set_ylabel('流量')
axes[1, 1].set_title('光变曲线')

plt.tight_layout()
plt.savefig('astronomy_visualization.png', dpi=300, bbox_inches='tight')
plt.show()

print("可视化图表已保存为 astronomy_visualization.png")
'''
        
        # 更新状态
        updated_state = state.copy()
        updated_state["current_step"] = "visualization_completed"
        updated_state["is_complete"] = True
        updated_state["generated_code"] = visualization_code
        updated_state["final_answer"] = f"""图表绘制代码已生成！

您的请求：{user_input}

生成的Python代码：
```python
{visualization_code}
```

此代码包含：
- 📈 散点图 - 显示坐标分布
- 📊 柱状图 - 统计天体类型分布  
- 🌟 星等分布图 - 显示亮度分布
- 🗺️ 天空分布图 - 显示天体在天空中的位置

您可以直接运行此代码来生成可视化图表。"""
        
        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "visualization_command_node",
            "action": "generate_visualization_code",
            "input": user_input,
            "output": "可视化代码已生成",
            "timestamp": time.time()
        })
        updated_state["execution_history"] = execution_history

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        # 错误处理
        error_state = state.copy()
        error_state["error_info"] = {
            "node": "visualization_command_node",
            "error": str(e),
            "timestamp": time.time(),
        }
        error_state["final_answer"] = f"图表绘制过程中发生错误：{str(e)}"
        error_state["is_complete"] = True
        
        return Command(
            update=error_state,
            goto="__end__"
        )


@track_node_execution("multimark")
def multimark_command_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    多模态标注节点 - 处理天文图像的AI识别和标注任务
    """
    try:
        user_input = state["user_input"]
        
        # TODO: 实现multimark功能
        # 当前为fallback实现，等待后续开发
        fallback_message = f"""多模态标注功能开发中...

您的请求：{user_input}

功能说明：
       暂定中.....

当前状态：功能开发中，敬请期待！

如需使用，请联系开发团队获取最新版本。"""
        
        # 更新状态
        updated_state = state.copy()
        updated_state["current_step"] = "multimark_completed"
        updated_state["is_complete"] = True
        updated_state["final_answer"] = fallback_message
        
        # 记录执行历史
        execution_history = updated_state.get("execution_history", [])
        execution_history.append({
            "node": "multimark_command_node",
            "action": "multimark_fallback",
            "input": user_input,
            "output": "多模态标注功能开发中",
            "timestamp": time.time()
        })
        updated_state["execution_history"] = execution_history

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        # 错误处理
        error_state = state.copy()
        error_state["error_info"] = {
            "node": "multimark_command_node",
            "error": str(e),
            "timestamp": time.time(),
        }
        error_state["final_answer"] = f"多模态标注过程中发生错误：{str(e)}"
        error_state["is_complete"] = True
        
        return Command(
            update=error_state,
            goto="__end__"
        )


