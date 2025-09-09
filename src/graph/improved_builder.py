#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的LangGraph图构建器
基于现有节点，构建更稳定的图结构
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .improved_nodes import (
    identity_check_improved_node,
    qa_agent_improved_node,
    user_choice_handler_improved_node,
    task_selector_improved_node,
    classification_analysis_improved_node,
    data_analysis_improved_node,
    literature_review_improved_node,
    code_generation_improved_node,
    error_recovery_improved_node
)
from .types import AstroAgentState


def route_after_identity_check(state: AstroAgentState) -> str:
    """身份识别后的路由逻辑"""
    user_type = state.get("user_type", "amateur")
    
    if user_type == "professional":
        return "task_selector"
    else:
        return "qa_agent"


def route_after_qa(state: AstroAgentState) -> str:
    """QA节点后的路由逻辑"""
    user_type = state.get("user_type", "amateur")
    
    if user_type == "professional":
        return "task_selector"
    else:
        return "user_choice_handler"


def route_after_user_choice(state: AstroAgentState) -> str:
    """用户选择后的路由逻辑"""
    current_step = state.get("current_step", "unknown")
    
    if current_step == "user_chose_more_info":
        return "task_selector"
    elif current_step == "user_chose_end":
        return END
    else:
        return END


def route_after_task_selection(state: AstroAgentState) -> str:
    """任务选择后的路由逻辑"""
    task_type = state.get("task_type", "classification")
    
    if task_type == "classification":
        return "classification_analysis"
    elif task_type == "code_generation":
        return "code_generation"
    elif task_type == "data_analysis":
        return "data_analysis"
    elif task_type == "literature_review":
        return "literature_review"
    else:
        return "error_recovery"


def route_after_error_recovery(state: AstroAgentState) -> str:
    """错误恢复后的路由逻辑"""
    return END


def build_improved_graph():
    """构建改进的天文科研Agent状态图"""
    graph = StateGraph(AstroAgentState)
    
    # 添加节点
    graph.add_node("identity_check", identity_check_improved_node)
    graph.add_node("qa_agent", qa_agent_improved_node)
    graph.add_node("user_choice_handler", user_choice_handler_improved_node)
    graph.add_node("task_selector", task_selector_improved_node)
    graph.add_node("classification_analysis", classification_analysis_improved_node)
    graph.add_node("data_analysis", data_analysis_improved_node)
    graph.add_node("literature_review", literature_review_improved_node)
    graph.add_node("code_generation", code_generation_improved_node)
    graph.add_node("error_recovery", error_recovery_improved_node)
    
    # 设置入口点
    graph.set_entry_point("identity_check")
    
    # 添加条件边
    graph.add_conditional_edges(
        "identity_check",
        route_after_identity_check,
        {
            "qa_agent": "qa_agent",
            "task_selector": "task_selector"
        }
    )
    
    graph.add_conditional_edges(
        "qa_agent",
        route_after_qa,
        {
            "task_selector": "task_selector",
            "user_choice_handler": "user_choice_handler",
            END: END
        }
    )
    
    graph.add_conditional_edges(
        "user_choice_handler",
        route_after_user_choice,
        {
            "task_selector": "task_selector",
            END: END
        }
    )
    
    graph.add_conditional_edges(
        "task_selector",
        route_after_task_selection,
        {
            "classification_analysis": "classification_analysis",
            "data_analysis": "data_analysis",
            "literature_review": "literature_review",
            "code_generation": "code_generation",
            "error_recovery": "error_recovery"
        }
    )
    
    # 所有分析节点都直接结束
    graph.add_edge("classification_analysis", END)
    graph.add_edge("data_analysis", END)
    graph.add_edge("literature_review", END)
    graph.add_edge("code_generation", END)
    
    # 错误恢复节点直接结束
    graph.add_conditional_edges(
        "error_recovery",
        route_after_error_recovery,
        {
            END: END
        }
    )
    
    return graph


def build_improved_graph_with_memory():
    """构建带内存的改进图"""
    memory = MemorySaver()
    builder = build_improved_graph()
    return builder.compile(checkpointer=memory)


def build_improved_graph_without_memory():
    """构建不带内存的改进图"""
    builder = build_improved_graph()
    return builder.compile()
