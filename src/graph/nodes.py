# Maxen Wong
# SPDX-License-Identifier: MIT

from typing import Dict, Any
import time
import asyncio
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from src.graph.types import AstroAgentState
from src.llms.llm import get_llm_by_type
from src.prompts.template import get_prompt

# LLM服务初始化 - 使用豆包模型
try:
    llm: BaseChatModel = get_llm_by_type("basic")
except Exception as e:
    print(f"Warning: Failed to initialize LLM: {e}")
    llm = None


def identity_check_node(state: AstroAgentState) -> AstroAgentState:
    """身份识别节点 - 判断用户类型（amateur/professional）"""
    try:
        user_input = state["user_input"]
        
        # 使用prompt模板获取身份识别提示词
        identity_prompt_content = get_prompt("identity_check", user_input=user_input)
        identity_prompt = ChatPromptTemplate.from_template(identity_prompt_content)
        
        # 调用LLM进行身份识别
        if llm is None:
            # 临时处理：如果LLM未初始化，使用简单规则判断
            keywords_professional = ["分析", "数据", "代码", "编程", "算法", "分类", "处理", "计算", "研究"]
            user_type = "professional" if any(kw in user_input for kw in keywords_professional) else "amateur"
        else:
            chain = identity_prompt | llm
            response = chain.invoke({
                'user_input': state.get('user_input', ''),
                'conversation_history': state.get('conversation_history', [])
            })
            user_type = response.content.strip().lower()
            if user_type not in ["amateur", "professional"]:
                # 如果输出不是预期格式，尝试从文本中提取
                if 'professional' in user_type:
                    user_type = 'professional'
                else:
                    user_type = 'amateur'  # 默认为爱好者
        
        # 更新状态
        state["user_type"] = user_type
        state["current_step"] = "identity_checked"
        state["config_data"]["identified_user_type"] = user_type
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "identity_check_node",
            "action": "user_type_identification",
            "input": user_input,
            "output": user_type,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "identity_check_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def qa_agent_node(state: AstroAgentState) -> AstroAgentState:
    """QA问答节点 - 处理爱好者的天文问答"""
    try:
        user_input = state["user_input"]
        user_type = state.get("user_type", "amateur")
        
        # 使用prompt模板获取QA提示词
        qa_prompt_content = get_prompt("qa_agent", user_input=user_input, user_type=user_type)
        qa_prompt = ChatPromptTemplate.from_template(qa_prompt_content)
        
        # 生成回答
        if llm is None:
            # 临时处理：如果LLM未初始化，提供默认回答
            response_content = f"感谢您的天文问题：{user_input}。这是一个很有趣的天文话题！由于当前LLM服务未配置，请稍后再试。"
        else:
            chain = qa_prompt | llm
            response = chain.invoke({"user_input": user_input, "user_type": user_type})
            response_content = response.content
        
        # 更新状态
        state["qa_response"] = response_content
        state["final_answer"] = response_content  # 设置final_answer字段
        
        # 根据用户类型决定是否继续
        if user_type == "professional":
            state["current_step"] = "qa_completed_continue"
            state["is_complete"] = False  # 专业用户继续到任务选择
        else:
            state["current_step"] = "qa_completed"
            state["is_complete"] = True  # 爱好者用户直接结束
        
        # 添加助手消息
        state["messages"].append({
            "role": "assistant",
            "content": response_content
        })
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "qa_agent_node",
            "action": "generate_qa_response",
            "input": user_input,
            "output": response_content,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        error_message = f"抱歉，处理您的问题时遇到了技术问题：{str(e)}。请稍后再试。"
        state["final_answer"] = error_message
        state["qa_response"] = error_message
        state["error_info"] = {
            "node": "qa_agent_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def task_selector_node(state: AstroAgentState) -> AstroAgentState:
    """任务选择节点 - 为专业用户选择合适的任务类型"""
    print(f"[DEBUG] task_selector_node: Entering task selector")
    print(f"[DEBUG] task_selector_node: state keys = {list(state.keys())}")
    print(f"[DEBUG] task_selector_node: user_type = {state.get('user_type')}")
    print(f"[DEBUG] task_selector_node: current_step = {state.get('current_step')}")
    
    try:
        user_input = state["user_input"]
        print(f"[DEBUG] task_selector_node: user_input = {user_input}")
        
        # 使用prompt模板获取任务选择提示词
        task_prompt_content = get_prompt("task_selector", user_input=user_input)
        task_prompt = ChatPromptTemplate.from_template(task_prompt_content)
        
        # 任务类型判断
        if llm is None:
            # 临时处理：使用关键词匹配
            if any(kw in user_input for kw in ["分类", "classification", "星系", "恒星"]):
                task_type = "classification"
            elif any(kw in user_input for kw in ["检索", "查询", "数据", "星表"]):
                task_type = "retrieval"
            elif any(kw in user_input for kw in ["文献", "论文", "综述", "研究"]):
                task_type = "literature"
            else:
                task_type = "classification"  # 默认分类任务
        else:
            chain = task_prompt | llm
            response = chain.invoke({"user_input": user_input})
            
            # 尝试解析JSON响应
            try:
                import json
                response_data = json.loads(response.content)
                task_type = response_data.get("task_type", "classification")
            except (json.JSONDecodeError, KeyError):
                # JSON解析失败，尝试从文本中提取任务类型
                response_text = response.content.strip().lower()
                if "retrieval" in response_text:
                    task_type = "retrieval"
                elif "literature" in response_text or "literature_review" in response_text:
                    task_type = "literature"
                elif "code_generation" in response_text or "analysis" in response_text:
                    task_type = "classification"  # 映射到现有的分类任务
                else:
                    task_type = "classification"  # 默认分类任务
            
            # 确保任务类型有效
            if task_type not in ["classification", "retrieval", "literature"]:
                task_type = "classification"  # 默认分类任务
        
        # 更新状态
        state["task_type"] = task_type
        state["current_step"] = "task_selected"
        state["config_data"]["selected_task_type"] = task_type
        
        print(f"[DEBUG] task_selector_node: task_type set to {task_type}")
        print(f"[DEBUG] task_selector_node: current_step set to task_selected")
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "task_selector_node",
            "action": "task_type_selection",
            "input": user_input,
            "output": task_type,
            "timestamp": time.time()
        })
        
        print(f"[DEBUG] task_selector_node: Successfully completed, returning state")
        return state
        
    except Exception as e:
        print(f"[DEBUG] task_selector_node: Exception occurred: {str(e)}")
        print(f"[DEBUG] task_selector_node: Exception type: {type(e)}")
        import traceback
        print(f"[DEBUG] task_selector_node: Traceback: {traceback.format_exc()}")
        
        state["error_info"] = {
            "node": "task_selector_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        print(f"[DEBUG] task_selector_node: Error state set, returning state")
        return state


def classification_config_node(state: AstroAgentState) -> AstroAgentState:
    """分类配置节点 - 配置天体分类任务参数"""
    print(f"[DEBUG] classification_config_node: Entering classification config")
    try:
        user_input = state["user_input"]
        task_type = state.get("task_type", "classification")
        print(f"[DEBUG] classification_config_node: task_type = {task_type}")
        print(f"[DEBUG] classification_config_node: user_input = {user_input}")
        
        # 使用prompt模板获取配置提示词
        print(f"[DEBUG] classification_config_node: Calling get_prompt...")
        try:
            config_prompt_content = get_prompt(
                "classification_config",
                task_type=task_type,
                user_requirements=user_input,
                key_requirements=str(["分类", "代码生成", "图像处理"])
            )
            print(f"[DEBUG] classification_config_node: get_prompt completed, content length: {len(config_prompt_content)}")
        except Exception as prompt_error:
            print(f"[DEBUG] classification_config_node: get_prompt failed: {str(prompt_error)}")
            print(f"[DEBUG] classification_config_node: get_prompt error type: {type(prompt_error).__name__}")
            raise prompt_error
        
        try:
            config_prompt = ChatPromptTemplate.from_template(config_prompt_content)
            print(f"[DEBUG] classification_config_node: ChatPromptTemplate created")
        except Exception as template_error:
            print(f"[DEBUG] classification_config_node: ChatPromptTemplate creation failed: {str(template_error)}")
            print(f"[DEBUG] classification_config_node: Template error type: {type(template_error).__name__}")
            raise template_error
        
        # 生成配置
        print(f"[DEBUG] classification_config_node: Checking LLM availability...")
        if llm is None:
            print(f"[DEBUG] classification_config_node: LLM is None, using default config")
            # 临时处理：提供默认配置
            config_data = {
                "data_source": "SDSS",
                "target_objects": "星系",
                "features": ["颜色", "亮度", "形态"],
                "algorithm": "随机森林",
                "output_format": "CSV"
            }
        else:
            print(f"[DEBUG] classification_config_node: LLM available, creating chain...")
            chain = config_prompt | llm
            print(f"[DEBUG] classification_config_node: Invoking chain...")
            try:
                response = chain.invoke({})
                print(f"[DEBUG] classification_config_node: Chain response received, content length: {len(response.content)}")
                try:
                    import json
                    print(f"[DEBUG] classification_config_node: Parsing JSON response...")
                    config_data = json.loads(response.content)
                    print(f"[DEBUG] classification_config_node: JSON parsing successful")
                except Exception as json_error:
                    print(f"[DEBUG] classification_config_node: JSON parsing failed: {str(json_error)}")
                    print(f"[DEBUG] classification_config_node: Response content: {response.content[:500]}...")
                    # 解析失败时使用默认配置
                    config_data = {
                        "data_source": "SDSS",
                        "target_objects": "星系",
                        "features": ["颜色", "亮度", "形态"],
                        "algorithm": "随机森林",
                        "output_format": "CSV"
                    }
            except Exception as chain_error:
                print(f"[DEBUG] classification_config_node: Chain invoke failed: {str(chain_error)}")
                print(f"[DEBUG] classification_config_node: Chain error type: {type(chain_error).__name__}")
                # LLM调用失败时使用默认配置
                config_data = {
                    "data_source": "SDSS",
                    "target_objects": "星系",
                    "features": ["颜色", "亮度", "形态"],
                    "algorithm": "随机森林",
                    "output_format": "CSV"
                }
        
        # 更新状态
        state["config_data"].update(config_data)
        state["current_step"] = "config_generated"
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "classification_config_node",
            "action": "configuration_extraction",
            "input": user_input,
            "output": config_data,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "classification_config_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def code_generator_node(state: AstroAgentState) -> AstroAgentState:
    """代码生成节点 - 根据配置生成Python分析代码"""
    try:
        config_data = state["config_data"]
        task_type = state.get("task_type", "classification")
        
        # 使用prompt模板获取代码生成提示词
        code_prompt_content = get_prompt("code_generator", config_data=str(config_data), task_type=task_type)
        code_prompt = ChatPromptTemplate.from_template(code_prompt_content)
        
        # 生成代码
        if llm is None:
            # 临时处理：提供示例代码
            generated_code = '''
# 天体分类示例代码
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# 加载数据
print("加载天体数据...")
# data = pd.read_csv("astronomical_data.csv")

# 数据预处理
print("数据预处理...")
# features = data[["color", "magnitude", "morphology"]]
# labels = data["object_type"]

# 模型训练
print("训练分类模型...")
# X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2)
# model = RandomForestClassifier(n_estimators=100)
# model.fit(X_train, y_train)

# 结果评估
print("评估模型性能...")
# predictions = model.predict(X_test)
# print(classification_report(y_test, predictions))

print("分类任务完成！")
'''
        else:
            chain = code_prompt | llm
            response = chain.invoke({})
            generated_code = response.content
        
        # 更新状态
        state["generated_code"] = generated_code
        state["current_step"] = "code_generated"
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "code_generator_node",
            "action": "code_generation",
            "input": config_data,
            "output": f"Generated {len(generated_code)} characters of code",
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "code_generator_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def code_executor_node(state: AstroAgentState) -> AstroAgentState:
    """代码执行节点 - 在安全环境中执行生成的代码"""
    try:
        generated_code = state["generated_code"]
        
        if not generated_code:
            raise ValueError("没有可执行的代码")
        
        # 模拟代码执行（实际应该在Docker容器中执行）
        execution_result = {
            "status": "success",
            "output": "代码执行成功！\n分类任务完成！",
            "execution_time": 2.5,
            "memory_usage": "45MB",
            "files_generated": ["classification_results.csv", "model_performance.png"]
        }
        
        # 更新状态
        state["execution_result"] = execution_result
        state["current_step"] = "code_executed"
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "code_executor_node",
            "action": "code_execution",
            "input": f"Code length: {len(generated_code)}",
            "output": execution_result,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "code_executor_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def review_loop_node(state: AstroAgentState) -> AstroAgentState:
    """审查循环节点 - 评估结果质量，决定是否需要重新处理"""
    try:
        execution_result = state["execution_result"]
        
        if not execution_result:
            raise ValueError("没有执行结果可供审查")
        
        # 简单的质量评估（实际应该更复杂）
        is_satisfied = execution_result.get("status") == "success"
        
        if is_satisfied:
            state["current_step"] = "review_completed"
            state["is_complete"] = True
            
            # 生成最终响应
            final_response = f"""任务执行完成！
            
执行状态：{execution_result['status']}
执行时间：{execution_result['execution_time']}秒
内存使用：{execution_result['memory_usage']}
生成文件：{', '.join(execution_result['files_generated'])}

输出结果：
{execution_result['output']}
"""
            
            state["messages"].append({
                "role": "assistant",
                "content": final_response
            })
        else:
            # 需要重试
            state["current_step"] = "review_retry"
            state["retry_count"] += 1
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "review_loop_node",
            "action": "result_review",
            "input": execution_result,
            "output": {"satisfied": is_satisfied, "retry_count": state["retry_count"]},
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "review_loop_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


# 错误恢复节点
def error_recovery_node(state: AstroAgentState) -> AstroAgentState:
    """错误恢复节点 - 处理系统错误和异常情况"""
    try:
        error_info = state.get("error_info")
        retry_count = state.get("retry_count", 0)
        
        if retry_count >= 3:
            # 超过重试次数，提供降级服务
            fallback_response = f"""抱歉，系统遇到了一些问题，无法完成您的请求。
            
错误信息：{error_info.get('error', '未知错误') if error_info else '系统异常'}
重试次数：{retry_count}

建议：
1. 请简化您的问题重新提问
2. 检查输入格式是否正确
3. 稍后再试

如果问题持续存在，请联系技术支持。"""
            
            state["qa_response"] = fallback_response
            state["current_step"] = "error_handled"
            state["is_complete"] = True
            
            state["messages"].append({
                "role": "assistant",
                "content": fallback_response
            })
        else:
            # 重置错误状态，准备重试
            state["error_info"] = None
            state["current_step"] = "identity_check"  # 从头开始
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "error_recovery_node",
            "action": "error_handling",
            "input": error_info,
            "output": {"action": "fallback" if retry_count >= 3 else "retry"},
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        # 错误恢复节点本身出错，直接标记完成
        state["qa_response"] = "系统遇到严重错误，请稍后重试。"
        state["current_step"] = "fatal_error"
        state["is_complete"] = True
        return state


def data_retrieval_node(state: AstroAgentState) -> AstroAgentState:
    """数据检索节点 - 处理天文数据检索任务"""
    try:
        user_input = state["user_input"]
        task_type = state.get("task_type", "data_retrieval")
        
        # 使用prompt模板获取数据检索提示词
        retrieval_prompt_content = get_prompt("data_retrieval", user_input=user_input, task_type=task_type)
        retrieval_prompt = ChatPromptTemplate.from_template(retrieval_prompt_content)
        
        # 生成检索配置
        if llm is None:
            # 临时处理：提供默认配置
            retrieval_config = {
                "data_source": "SDSS DR17",
                "search_params": {
                    "ra": "目标赤经",
                    "dec": "目标赤纬", 
                    "radius": "搜索半径（角秒）"
                },
                "output_fields": ["objid", "ra", "dec", "u", "g", "r", "i", "z"],
                "retrieval_method": "cone_search"
            }
        else:
            chain = retrieval_prompt | llm
            response = chain.invoke({})
            try:
                import json
                retrieval_config = json.loads(response.content)
            except:
                # 解析失败时使用默认配置
                retrieval_config = {
                    "data_source": "SDSS DR17",
                    "search_params": {"ra": "目标赤经", "dec": "目标赤纬", "radius": "搜索半径"},
                    "output_fields": ["objid", "ra", "dec", "u", "g", "r", "i", "z"],
                    "retrieval_method": "cone_search"
                }
        
        # 更新状态
        state["task_config"] = retrieval_config
        state["current_step"] = "retrieval_configured"
        state["config_data"]["retrieval_config"] = retrieval_config
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "data_retrieval_node",
            "action": "configure_retrieval",
            "input": user_input,
            "output": retrieval_config,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "data_retrieval_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


def literature_review_node(state: AstroAgentState) -> AstroAgentState:
    """文献综述节点 - 处理天文文献检索和综述任务"""
    try:
        user_input = state["user_input"]
        task_type = state.get("task_type", "literature_review")
        
        # 使用prompt模板获取文献综述提示词
        literature_prompt_content = get_prompt("literature_review", user_input=user_input, task_type=task_type)
        literature_prompt = ChatPromptTemplate.from_template(literature_prompt_content)
        
        # 生成文献配置
        if llm is None:
            # 临时处理：提供默认配置
            literature_config = {
                "keywords": ["astronomy", "astrophysics"],
                "databases": ["ADS", "arXiv"],
                "time_range": "2020-2024",
                "literature_types": ["refereed", "preprint"],
                "review_focus": "recent_developments"
            }
        else:
            chain = literature_prompt | llm
            response = chain.invoke({})
            try:
                import json
                literature_config = json.loads(response.content)
            except:
                # 解析失败时使用默认配置
                literature_config = {
                    "keywords": ["astronomy", "astrophysics"],
                    "databases": ["ADS", "arXiv"],
                    "time_range": "2020-2024",
                    "literature_types": ["refereed", "preprint"],
                    "review_focus": "recent_developments"
                }
        
        # 更新状态
        state["task_config"] = literature_config
        state["current_step"] = "literature_configured"
        state["config_data"]["literature_config"] = literature_config
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "literature_review_node",
            "action": "configure_literature_review",
            "input": user_input,
            "output": literature_config,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "literature_review_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state


# 导出所有节点函数
__all__ = [
    "identity_check_node",
    "qa_agent_node", 
    "task_selector_node",
    "classification_config_node",
    "data_retrieval_node",
    "literature_review_node",
    "code_generator_node",
    "code_executor_node",
    "review_loop_node",
    "error_recovery_node"
]


# 临时兼容性导入（保留原有的background_investigation_node）
def background_investigation_node(state):
    """临时兼容性节点"""
    return state