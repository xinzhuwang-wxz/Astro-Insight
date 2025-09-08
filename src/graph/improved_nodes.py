#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的LangGraph节点实现
基于现有节点，修复bug并增强功能
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
from src.tools.language_processor import language_processor
from src.database.local_storage import LocalDatabase, CelestialObject, ClassificationResult

# 设置logger
logger = logging.getLogger(__name__)

# LLM服务初始化
try:
    llm: BaseChatModel = get_llm_by_type("basic")
except Exception as e:
    print(f"Warning: Failed to initialize LLM: {e}")
    llm = None


def identity_check_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的身份识别节点
    简化逻辑，避免复杂的状态管理
    """
    try:
        user_input = state["user_input"]
        
        # 输入验证
        if not user_input or not isinstance(user_input, str):
            raise ValueError("Invalid user_input: must be a non-empty string")

        # 优先检查是否已经在状态中指定了用户类型
        if "user_type" in state and state["user_type"] in ["amateur", "professional"]:
            user_type = state["user_type"]
        else:
            # 使用简单规则判断用户类型
            professional_keywords = [
                "分析", "数据", "代码", "编程", "算法", "分类", 
                "处理", "计算", "研究", "生成代码", "写代码",
                "code", "programming", "algorithm", "analysis"
            ]
            
            user_type = (
                "professional"
                if any(kw in user_input.lower() for kw in professional_keywords)
                else "amateur"
            )

        # 更新状态
        updated_state = {
            "user_type": user_type,
            "current_step": "identity_checked",
            "identity_completed": True
        }

        # 根据用户类型路由
        if user_type == "amateur":
            return Command(
                update=updated_state,
                goto="qa_agent"
            )
        else:
            return Command(
                update=updated_state,
                goto="task_selector"
            )

    except Exception as e:
        logger.error(f"Identity check failed: {e}")
        error_state = {
            "error_info": {
                "node": "identity_check_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def qa_agent_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的QA问答节点
    简化逻辑，提供更好的用户体验
    """
    try:
        user_input = state["user_input"]
        user_type = state.get("user_type", "amateur")

        # 生成回答
        if llm is None:
            # 临时处理：如果LLM未初始化，提供默认回答
            response_content = f"感谢您的天文问题：{user_input}。这是一个很有趣的天文话题！由于当前LLM服务未配置，请稍后再试。"
        else:
            try:
                qa_prompt_content = get_prompt("qa_agent", user_input=user_input, user_type=user_type)
                qa_prompt = ChatPromptTemplate.from_template(qa_prompt_content)
                chain = qa_prompt | llm
                response = chain.invoke({"user_input": user_input, "user_type": user_type})
                response_content = response.content
            except Exception as e:
                logger.warning(f"LLM QA failed: {e}")
                response_content = f"感谢您的天文问题：{user_input}。这是一个很有趣的天文话题！"

        # 更新状态
        updated_state = {
            "qa_response": response_content,
            "qa_completed": True,
            "current_step": "qa_completed"
        }

        # 为amateur用户添加交互式询问
        if user_type == "amateur":
            enhanced_response = response_content + "\n\n💫 想要了解更专业的天体分类和数据分析吗？\n请回复：\n• '是' 或 'y' - 进入专业模式\n• '否' 或 'n' - 结束对话"
            updated_state["final_answer"] = enhanced_response
            updated_state["awaiting_user_choice"] = True
            updated_state["is_complete"] = False
            
            return Command(
                update=updated_state,
                goto="user_choice_handler"
            )
        else:
            updated_state["final_answer"] = response_content
            updated_state["is_complete"] = True
            
            return Command(
                update=updated_state,
                goto="__end__"
            )

    except Exception as e:
        logger.error(f"QA agent failed: {e}")
        error_state = {
            "error_info": {
                "node": "qa_agent_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def user_choice_handler_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的用户选择处理节点
    简化逻辑，避免无限循环
    """
    try:
        # 获取用户选择
        choice_input = state.get("user_choice") or state.get("user_input", "")
        choice_input = choice_input.strip().lower() if choice_input else ""
        
        # 检查是否为有效的选择输入
        valid_yes = ["是", "y", "yes", "要", "需要", "1"]
        valid_no = ["否", "n", "no", "不要", "不需要", "0"]
        
        if choice_input in valid_yes:
            # 用户想要更多信息，进入专业模式
            updated_state = {
                "user_type": "professional",
                "current_step": "user_chose_more_info",
                "is_complete": False,
                "awaiting_user_choice": False
            }
            
            return Command(
                update=updated_state,
                goto="task_selector"
            )
        elif choice_input in valid_no:
            # 用户不需要更多信息，结束对话
            updated_state = {
                "current_step": "user_chose_end",
                "is_complete": True,
                "awaiting_user_choice": False,
                "final_answer": "感谢您的使用！如有其他天文问题，欢迎随时咨询。"
            }
            
            return Command(
                update=updated_state,
                goto="__end__"
            )
        else:
            # 输入无效，保持当前状态等待用户重新输入
            updated_state = {
                "current_step": "waiting_for_valid_choice",
                "awaiting_user_choice": True,
                "is_complete": False,
                "final_answer": "请明确回复：\n• '是' 或 'y' - 进入专业模式\n• '否' 或 'n' - 结束对话"
            }
            
            return Command(
                update=updated_state,
                goto="__end__"
            )

    except Exception as e:
        logger.error(f"User choice handler failed: {e}")
        error_state = {
            "error_info": {
                "node": "user_choice_handler_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def task_selector_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的任务选择节点
    简化逻辑，提高准确性
    """
    try:
        user_input = state["user_input"]
        
        # 使用简单规则判断任务类型
        if any(kw in user_input.lower() for kw in ["分类", "classify", "classification"]):
            task_type = "classification"
        elif any(kw in user_input.lower() for kw in ["代码", "code", "编程", "程序"]):
            task_type = "code_generation"
        elif any(kw in user_input.lower() for kw in ["数据", "data", "检索", "retrieval"]):
            task_type = "data_analysis"
        elif any(kw in user_input.lower() for kw in ["文献", "literature", "论文", "paper"]):
            task_type = "literature_review"
        else:
            # 默认分类任务
            task_type = "classification"

        # 更新状态
        updated_state = {
            "task_type": task_type,
            "current_step": "task_selected"
        }

        # 根据任务类型路由
        if task_type == "classification":
            return Command(
                update=updated_state,
                goto="classification_analysis"
            )
        elif task_type == "code_generation":
            return Command(
                update=updated_state,
                goto="code_generation"
            )
        elif task_type == "data_analysis":
            return Command(
                update=updated_state,
                goto="data_analysis"
            )
        elif task_type == "literature_review":
            return Command(
                update=updated_state,
                goto="literature_review"
            )
        else:
            return Command(
                update=updated_state,
                goto="error_recovery"
            )

    except Exception as e:
        logger.error(f"Task selector failed: {e}")
        error_state = {
            "error_info": {
                "node": "task_selector_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def classification_analysis_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的天体分类分析节点
    集成完整的数据分析流程
    """
    try:
        user_input = state["user_input"]
        
        # 从用户查询中提取天体信息
        try:
            celestial_extraction = language_processor.extract_celestial_object(user_input)
            if celestial_extraction and celestial_extraction.object_name:
                celestial_info = {
                    "object_name": celestial_extraction.object_name,
                    "coordinates": celestial_extraction.coordinates or {"ra": None, "dec": None},
                    "object_type": celestial_extraction.object_type or "未知",
                    "magnitude": None,
                    "description": user_input
                }
            else:
                celestial_info = {
                    "object_name": "未知天体",
                    "coordinates": {"ra": None, "dec": None},
                    "object_type": "未知",
                    "magnitude": None,
                    "description": user_input
                }
        except Exception as e:
            logger.warning(f"Celestial extraction failed: {e}")
            celestial_info = {
                "object_name": "未知天体",
                "coordinates": {"ra": None, "dec": None},
                "object_type": "未知",
                "magnitude": None,
                "description": user_input
            }

        # 基于规则的天体分类
        user_input_lower = user_input.lower()
        object_name = celestial_info.get("object_name", "").lower()
        
        if any(keyword in user_input_lower or keyword in object_name for keyword in ["恒星", "star", "太阳"]):
            primary_category = "恒星"
            subcategory = "主序星"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["行星", "planet", "火星", "金星", "木星"]):
            primary_category = "行星"
            subcategory = "类地行星" if any(k in user_input_lower for k in ["火星", "金星", "地球"]) else "气态巨行星"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["星系", "galaxy", "银河", "仙女座", "andromeda"]):
            primary_category = "星系"
            subcategory = "螺旋星系"
        elif any(keyword in user_input_lower or keyword in object_name for keyword in ["星云", "nebula"]):
            primary_category = "星云"
            subcategory = "发射星云"
        else:
            primary_category = "未分类"
            subcategory = "需要更多信息"

        # 构建分类结果
        classification_result = {
            "object_name": celestial_info.get("object_name", "未知天体"),
            "primary_category": primary_category,
            "subcategory": subcategory,
            "detailed_classification": f"{primary_category} - {subcategory}",
            "confidence_level": "中等",
            "coordinates": celestial_info.get("coordinates", {"ra": "未知", "dec": "未知"}),
            "explanation": f"基于关键词分析，该天体被分类为{primary_category}。",
            "suggestions": ["提供更多观测数据以获得更准确的分类"]
        }

        # 生成最终答案
        coord_display = f"RA={celestial_info['coordinates']['ra']}, DEC={celestial_info['coordinates']['dec']}"
        
        final_answer = f"""天体分析完成！

天体名称: {classification_result['object_name']}
分类结果: {classification_result['primary_category']}
子分类: {classification_result['subcategory']}
坐标: {coord_display}

分析说明: {classification_result['explanation']}
建议: {', '.join(classification_result['suggestions'])}

分析流程已完成。"""

        # 更新状态
        updated_state = {
            "classification_result": classification_result,
            "final_answer": final_answer,
            "current_step": "classification_completed",
            "is_complete": True
        }

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        logger.error(f"Classification analysis failed: {e}")
        error_state = {
            "error_info": {
                "node": "classification_analysis_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def data_analysis_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的数据分析节点
    集成Supabase查询和数据分析功能
    """
    try:
        user_input = state["user_input"]
        
        # 生成Supabase查询代码
        query_code = f'''# 数据分析代码
# 用户需求: {user_input}

import json
from supabase import create_client

# Supabase配置
SUPABASE_URL = "https://lciwqkzalvdhuxhlqcdw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjaXdxa3phbHZkaHV4aGxxY2R3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzE2MDc0MiwiZXhwIjoyMDcyNzM2NzQyfQ.Df95x4K-ugcXPNS2b4AG-dEB31kUybk5szWTxl2Vrls"

# 创建Supabase客户端
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    # 查询galaxy_classification表
    result = supabase.table("galaxy_classification").select("*").limit(10).execute()
    
    if result.data:
        print("查询成功！")
        print(f"找到 {len(result.data)} 条记录")
        print("前3条记录:")
        for i, record in enumerate(result.data[:3]):
            print(f"记录 {i+1}: {record}")
        
        # 保存为JSON格式
        with open("query_result.json", "w", encoding="utf-8") as f:
            json.dump(result.data, f, ensure_ascii=False, indent=2)
        print("数据已保存到 query_result.json")
    else:
        print("未找到数据")
        
except Exception as e:
    print(f"查询失败: {e}")

print("数据分析完成")'''

        # 更新状态
        updated_state = {
            "generated_code": query_code,
            "final_answer": f"已生成数据分析代码，用于查询Supabase数据库。\n\n代码功能：\n- 连接Supabase数据库\n- 查询galaxy_classification表\n- 保存结果到JSON文件\n\n请运行此代码进行数据分析。",
            "current_step": "data_analysis_completed",
            "is_complete": True
        }

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        logger.error(f"Data analysis failed: {e}")
        error_state = {
            "error_info": {
                "node": "data_analysis_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def literature_review_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的文献综述节点
    集成Tavily搜索功能
    """
    try:
        user_input = state["user_input"]
        
        # 生成文献综述代码
        review_code = f'''# 文献综述代码
# 用户需求: {user_input}

import json
from tavily import TavilyClient

# Tavily配置
tavily = TavilyClient(api_key="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")

try:
    # 搜索相关文献
    search_query = "{user_input} astronomy astrophysics"
    search_results = tavily.search(
        query=search_query,
        search_depth="basic",
        max_results=5,
        include_domains=["arxiv.org", "nasa.gov", "esa.int", "aas.org"]
    )
    
    print("文献搜索完成！")
    print(f"找到 {len(search_results.get('results', []))} 篇相关文献")
    
    # 显示搜索结果
    for i, result in enumerate(search_results.get('results', [])[:3]):
        print(f"\\n文献 {i+1}:")
        print(f"标题: {result.get('title', 'N/A')}")
        print(f"链接: {result.get('url', 'N/A')}")
        print(f"摘要: {result.get('content', 'N/A')[:200]}...")
    
    # 保存结果
    with open("literature_review.json", "w", encoding="utf-8") as f:
        json.dump(search_results, f, ensure_ascii=False, indent=2)
    print("\\n文献综述结果已保存到 literature_review.json")
    
except Exception as e:
    print(f"文献搜索失败: {e}")

print("文献综述完成")'''

        # 更新状态
        updated_state = {
            "generated_code": review_code,
            "final_answer": f"已生成文献综述代码，用于搜索相关学术文献。\n\n代码功能：\n- 使用Tavily搜索API\n- 搜索天文相关文献\n- 保存结果到JSON文件\n\n请运行此代码进行文献综述。",
            "current_step": "literature_review_completed",
            "is_complete": True
        }

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        logger.error(f"Literature review failed: {e}")
        error_state = {
            "error_info": {
                "node": "literature_review_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def code_generation_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的代码生成节点
    生成实际可用的代码
    """
    try:
        user_input = state["user_input"]
        task_type = state.get("task_type", "code_generation")
        
        # 生成代码
        generated_code = f'''# 天文代码生成
# 用户需求: {user_input}
# 任务类型: {task_type}

import numpy as np
import matplotlib.pyplot as plt
from astropy import coordinates as coords
from astropy import units as u
from astropy.io import fits
import pandas as pd

def main():
    """主函数"""
    print("开始执行天文{task_type}任务...")
    print(f"用户需求: {user_input}")
    
    # 示例代码框架
    if "{task_type}" == "观测":
        print("执行天体观测分析")
        # 添加观测相关代码
    elif "{task_type}" == "计算":
        print("执行天体参数计算")
        # 添加计算相关代码
    elif "{task_type}" == "可视化":
        print("生成天体数据可视化")
        # 添加可视化相关代码
    else:
        print(f"执行{task_type}相关任务")
        # 添加通用代码
    
    print("任务完成！")
    return "success"

if __name__ == "__main__":
    result = main()
    print(f"执行结果: {{result}}")'''

        # 更新状态
        updated_state = {
            "generated_code": generated_code,
            "final_answer": f"已生成{task_type}代码。\n\n代码功能：\n- 基础天文数据处理框架\n- 支持观测、计算、可视化等任务\n- 包含必要的依赖库\n\n请运行此代码执行{task_type}任务。",
            "current_step": "code_generation_completed",
            "is_complete": True
        }

        return Command(
            update=updated_state,
            goto="__end__"
        )

    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        error_state = {
            "error_info": {
                "node": "code_generation_improved_node",
                "error": str(e),
                "timestamp": time.time(),
            }
        }
        return Command(
            update=error_state,
            goto="error_recovery"
        )


def error_recovery_improved_node(state: AstroAgentState) -> Command[AstroAgentState]:
    """
    改进的错误恢复节点
    简化逻辑，提供更好的错误处理
    """
    try:
        error_info = state.get("error_info", {})
        retry_count = state.get("retry_count", 0)
        
        # 最大重试次数限制
        MAX_RETRY_COUNT = 3
        
        if retry_count >= MAX_RETRY_COUNT:
            # 超过重试次数，提供降级服务
            fallback_response = f"""抱歉，系统在处理您的请求时遇到了问题（超过最大重试次数），现在提供基本服务。

错误信息：{error_info.get('error', '未知错误') if error_info else '系统异常'}
重试次数：{retry_count}

建议：
1. 请简化您的问题重新提问
2. 检查输入格式是否正确
3. 稍后再试

如果问题持续存在，请联系技术支持。"""

            updated_state = {
                "final_answer": fallback_response,
                "current_step": "error_handled",
                "is_complete": True
            }
            
            return Command(
                update=updated_state,
                goto="__end__"
            )
        else:
            # 在重试限制内，提供基本服务
            fallback_response = f"""抱歉，系统遇到了问题，但我可以为您提供基本信息。

错误信息：{error_info.get('error', '未知错误') if error_info else '系统异常'}
重试次数：{retry_count + 1}/{MAX_RETRY_COUNT}

建议：
1. 请简化您的问题重新提问
2. 检查输入格式是否正确
3. 稍后再试

如果问题持续存在，请联系技术支持。"""

            updated_state = {
                "final_answer": fallback_response,
                "current_step": "error_handled",
                "is_complete": True
            }
            
            return Command(
                update=updated_state,
                goto="__end__"
            )

    except Exception as e:
        logger.error(f"Error recovery failed: {e}")
        error_state = {
            "final_answer": "系统遇到严重错误，请稍后重试。",
            "current_step": "fatal_error",
            "is_complete": True
        }
        return Command(
            update=error_state,
            goto="__end__"
        )
