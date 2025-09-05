# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    identity_check_node,
    qa_agent_node,
    task_selector_node,
    classification_config_node,
    data_retrieval_node,
    literature_review_node,
    code_generator_node,
    code_executor_node,
    review_loop_node,
    error_recovery_node
)
from .types import AstroAgentState


def route_after_identity_check(state: AstroAgentState) -> str:
    """身份识别后的路由逻辑"""
    user_type = state.get("user_type")
    
    # 添加调试信息
    print(f"[DEBUG] route_after_identity_check: user_type = {user_type}")
    print(f"[DEBUG] route_after_identity_check: state keys = {list(state.keys())}")
    
    if user_type == "amateur":
        print(f"[DEBUG] Routing to qa_agent")
        return "qa_agent"
    elif user_type == "professional":
        print(f"[DEBUG] Routing to task_selector")
        return "task_selector"  # 专业用户直接进入任务选择
    else:
        print(f"[DEBUG] Routing to error_recovery (user_type not recognized)")
        return "error_recovery"


def route_after_qa(state: AstroAgentState) -> str:
    """QA节点后的路由逻辑"""
    user_type = state.get("user_type")
    current_step = state.get("current_step")
    
    if user_type == "professional" and current_step == "qa_completed_continue":
        return "task_selector"
    else:
        return END


def route_after_task_selection(state: AstroAgentState) -> str:
    """任务选择后的路由逻辑"""
    task_type = state.get("task_type")
    print(f"[DEBUG] route_after_task_selection: task_type = {task_type}")
    
    if task_type == "classification":
        print(f"[DEBUG] route_after_task_selection: routing to classification_config")
        return "classification_config"
    elif task_type == "code_generation":
        print(f"[DEBUG] route_after_task_selection: routing to classification_config (code_generation)")
        return "classification_config"  # 代码生成任务也使用分类配置节点
    elif task_type == "analysis":
        print(f"[DEBUG] route_after_task_selection: routing to classification_config (analysis)")
        return "classification_config"  # 分析任务也使用分类配置节点
    elif task_type == "data_retrieval" or task_type == "retrieval":
        print(f"[DEBUG] route_after_task_selection: routing to data_retrieval")
        return "data_retrieval"
    elif task_type == "literature_review" or task_type == "literature":
        print(f"[DEBUG] route_after_task_selection: routing to literature_review")
        return "literature_review"
    else:
        print(f"[DEBUG] route_after_task_selection: routing to error_recovery (unknown task_type)")
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


def check_for_errors(state: AstroAgentState) -> str:
    """检查是否有错误需要处理"""
    error_info = state.get("error_info")
    retry_count = state.get("retry_count", 0)
    
    if error_info and retry_count < 3:
        return "error_recovery"
    elif state.get("is_complete"):
        return END
    else:
        # 根据当前步骤继续执行
        current_step = state.get("current_step", "start")
        if current_step == "start":
            return "identity_check"
        else:
            return END


def _build_astro_graph():
    """构建天文科研Agent的状态图"""
    graph = StateGraph(AstroAgentState)
    
    # 添加节点
    graph.add_node("identity_check", identity_check_node)
    graph.add_node("qa_agent", qa_agent_node)
    graph.add_node("task_selector", task_selector_node)
    graph.add_node("classification_config", classification_config_node)
    graph.add_node("data_retrieval", data_retrieval_node)
    graph.add_node("literature_review", literature_review_node)
    graph.add_node("code_generator", code_generator_node)
    graph.add_node("code_executor", code_executor_node)
    graph.add_node("review_loop", review_loop_node)
    graph.add_node("error_recovery", error_recovery_node)
    
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
            END: END
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
    
    # 配置完成后直接结束（专业用户分类任务到此完成）
    graph.add_edge("classification_config", "code_generator")
    
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
    
    # 错误恢复后的路由
    graph.add_conditional_edges(
        "error_recovery",
        check_for_errors,
        {
            "identity_check": "identity_check",
            "error_recovery": "error_recovery",
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
