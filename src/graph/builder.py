# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    identity_check_command_node,
    qa_agent_command_node,
    user_choice_handler_command_node,
    task_selector_command_node,
    classification_config_command_node,
    data_retrieval_node,
    literature_review_node,
    code_generator_command_node,
    code_executor_command_node,
    review_loop_command_node,
    error_recovery_command_node
)
from .types import AstroAgentState


def route_after_identity_check(state: AstroAgentState) -> str:
    """身份识别后的路由逻辑 - 简化版本，避免重复调用"""
    user_type = state.get("user_type", "amateur")
    
    # 简化路由逻辑：根据用户类型直接路由，不再检查identity_completed状态
    if user_type == "professional":
        return "task_selector"
    else:
        # amateur用户或未知类型都进入QA流程
        return "qa_agent"


def route_after_qa(state: AstroAgentState) -> str:
    """QA节点后的路由逻辑 - 简化版本，避免重复调用"""
    user_type = state.get("user_type", "amateur")
    
    # 简化路由逻辑：根据用户类型直接路由，不进行复杂的状态检查
    if user_type == "professional":
        return "task_selector"
    else:
        # amateur用户进入用户选择处理
        return "user_choice_handler"


def route_after_task_selection(state: AstroAgentState) -> str:
    """任务选择后的路由逻辑"""
    task_type = state.get("task_type", "classification")
    
    if task_type == "classification":
        return "classification_config"
    elif task_type == "code_generation":
        return "classification_config"
    elif task_type == "analysis":
        return "classification_config"
    elif task_type == "data_retrieval":
        return "data_retrieval"
    elif task_type == "literature_review":
        return "literature_review"
    else:
        return "error_recovery"


def route_after_code_execution(state: AstroAgentState) -> str:
    """代码执行后的路由逻辑"""
    execution_result = state.get("execution_result")
    retry_count = state.get("retry_count", 0)
    
    if execution_result and execution_result.get("status") == "success":
        return "review_loop"
    elif retry_count < 3:
        return "code_generator"  # 重新生成代码
    else:
        return "error_recovery"


def route_after_review(state: AstroAgentState) -> str:
    """审查后的路由逻辑"""
    current_step = state.get("current_step")
    retry_count = state.get("retry_count", 0)
    
    if current_step == "review_completed":
        return END
    elif current_step == "review_retry" and retry_count < 3:
        return "code_generator"  # 重新生成代码
    else:
        return "error_recovery"


def route_after_error_recovery(state: AstroAgentState) -> str:
    """错误恢复后的路由逻辑 - 简化版本，避免循环调用"""
    retry_count = state.get("retry_count", 0)
    error_info = state.get("error_info")
    
    # 如果重试次数已达上限或没有错误信息，直接结束
    if retry_count >= 3 or not error_info:
        return END
    
    # 简化逻辑：错误恢复后直接结束，避免重新进入其他节点造成循环
    return END


def check_for_errors(state: AstroAgentState) -> str:
    """检查是否有错误需要处理 - 简化版本"""
    error_info = state.get("error_info")
    retry_count = state.get("retry_count", 0)
    
    # 如果任务已完成，直接结束
    if state.get("is_complete"):
        return END
    
    # 如果有错误且重试次数未达上限，进行错误恢复
    if error_info and retry_count < 3:
        return "error_recovery"
    
    # 其他情况直接结束，避免无限循环
    return END


def _build_astro_graph():
    """构建天文科研Agent的状态图"""
    graph = StateGraph(AstroAgentState)
    
    # 添加节点 - 使用Command版本的节点以支持新版langgraph
    graph.add_node("identity_check", identity_check_command_node)
    graph.add_node("qa_agent", qa_agent_command_node)
    graph.add_node("user_choice_handler", user_choice_handler_command_node)
    graph.add_node("task_selector", task_selector_command_node)
    graph.add_node("classification_config", classification_config_command_node)
    graph.add_node("data_retrieval", data_retrieval_node)
    graph.add_node("literature_review", literature_review_node)
    graph.add_node("code_generator", code_generator_command_node)
    graph.add_node("code_executor", code_executor_command_node)
    graph.add_node("review_loop", review_loop_command_node)
    graph.add_node("error_recovery", error_recovery_command_node)
    
    # 设置入口点
    graph.set_entry_point("identity_check")
    
    # 添加条件边
    graph.add_conditional_edges(
        "identity_check",
        route_after_identity_check,
        {
            "qa_agent": "qa_agent",
            "task_selector": "task_selector",
            "error_recovery": "error_recovery"
        }
    )
    
    # QA问答后的条件路由
    graph.add_conditional_edges(
        "qa_agent",
        route_after_qa,
        {
            "task_selector": "task_selector",
            "user_choice_handler": "user_choice_handler",
            END: END
        }
    )
    
    # user_choice_handler 的条件边配置
    graph.add_conditional_edges(
        "user_choice_handler",
        lambda state: state.get("current_step", "unknown"),
        {
            "user_chose_more_info": "task_selector",
            "user_chose_end": END,
            "invalid_choice_exit": END,
            "waiting_for_valid_choice": END  # 无效输入时结束，等待用户重新开始对话
        }
    )
    
    # 任务选择后的路由
    graph.add_conditional_edges(
        "task_selector",
        route_after_task_selection,
        {
            "classification_config": "classification_config",
            "data_retrieval": "data_retrieval",
            "literature_review": "literature_review",
            "error_recovery": "error_recovery"
        }
    )
    
    # 注意：classification_config 使用Command语法
    # 它的路由由Command对象的goto字段控制，不需要预定义边
    
    # 数据检索和文献综述直接结束
    graph.add_edge("data_retrieval", END)
    graph.add_edge("literature_review", END)
    
    # 代码生成后执行
    graph.add_edge("code_generator", "code_executor")
    
    # 代码执行后的路由
    graph.add_conditional_edges(
        "code_executor",
        route_after_code_execution,
        {
            "review_loop": "review_loop",
            "code_generator": "code_generator",
            "error_recovery": "error_recovery"
        }
    )
    
    # 审查后的路由
    graph.add_conditional_edges(
        "review_loop",
        route_after_review,
        {
            END: END,
            "code_generator": "code_generator",
            "error_recovery": "error_recovery"
        }
    )
    
    # 错误恢复后的路由 - 简化版本，只允许结束，避免循环调用
    graph.add_conditional_edges(
        "error_recovery",
        route_after_error_recovery,
        {
            END: END
        }
    )
    
    return graph


def build_graph_with_memory():
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    # TODO: be compatible with SQLite / PostgreSQL
    memory = MemorySaver()

    # build state graph
    builder = _build_astro_graph()
    return builder.compile(checkpointer=memory)


def build_graph():
    """Build and return the agent workflow graph without memory."""
    # build state graph
    builder = _build_astro_graph()
    return builder.compile()


# 移除全局图实例，每次调用build_graph()都创建新的图实例
# graph = build_graph()
