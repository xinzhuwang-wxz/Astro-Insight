#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的天文科研Agent系统工作流模块
基于改进的节点，提供更稳定的工作流
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.graph.types import AstroAgentState, create_initial_state, validate_state
from src.graph.improved_builder import build_improved_graph_with_memory, build_improved_graph_without_memory
from src.config import load_yaml_config

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ImprovedAstroWorkflow:
    """
    改进的天文科研Agent工作流类
    
    基于改进的节点，提供更稳定的工作流程，包括：
    - 简化的图构建和初始化
    - 用户会话管理
    - 任务执行和状态跟踪
    - 错误处理和恢复
    """

    def __init__(self, config_path: Optional[str] = None, use_memory: bool = True):
        """
        初始化工作流

        Args:
            config_path: 配置文件路径，默认使用项目根目录的conf.yaml
            use_memory: 是否使用内存存储会话状态
        """
        self.config = load_yaml_config(config_path)
        self.use_memory = use_memory
        self.graph = None
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._initialize_graph()

    def _initialize_graph(self):
        """初始化LangGraph图"""
        try:
            if self.use_memory:
                self.graph = build_improved_graph_with_memory()
                logger.info("使用内存存储的图初始化完成")
            else:
                self.graph = build_improved_graph_without_memory()
                logger.info("不使用内存存储的图初始化完成")
        except Exception as e:
            logger.error(f"图初始化失败: {e}")
            raise

    def create_session(self, session_id: str, user_input: str, user_context: Optional[Dict[str, Any]] = None) -> AstroAgentState:
        """
        创建新的会话

        Args:
            session_id: 会话ID
            user_input: 用户输入
            user_context: 用户上下文信息（可选）

        Returns:
            初始状态对象
        """
        try:
            # 创建初始状态
            initial_state = create_initial_state(session_id, user_input)
            
            # 添加用户上下文
            if user_context:
                for key, value in user_context.items():
                    if key != "session_id":
                        initial_state[key] = value
            
            # 存储会话信息
            self.sessions[session_id] = {
                "current_state": initial_state,
                "created_at": datetime.now(),
                "last_updated": datetime.now()
            }
            
            logger.info(f"会话创建成功: {session_id}")
            return initial_state
            
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise

    def execute_workflow(
        self,
        session_id: str,
        user_input: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AstroAgentState:
        """
        执行完整的工作流程

        Args:
            session_id: 会话ID
            user_input: 用户输入
            user_context: 用户上下文信息（可选）

        Returns:
            最终状态对象
        """
        start_time = time.time()
        logger.info(f"开始执行工作流 - 会话: {session_id}")

        try:
            # 创建或获取会话
            if session_id not in self.sessions:
                initial_state = self.create_session(
                    session_id, user_input, user_context
                )
            else:
                # 更新现有会话
                session = self.sessions[session_id]
                initial_state = session["current_state"].copy()
                initial_state["user_input"] = user_input
                if user_context:
                    # 只更新非session_id字段
                    for key, value in user_context.items():
                        if key != "session_id":
                            initial_state[key] = value
                session["last_updated"] = datetime.now()

            # 执行图
            logger.info(f"执行图处理 - 输入: {user_input[:50]}...")
            final_state = self.graph.invoke(initial_state)

            # 更新会话状态
            self.sessions[session_id]["current_state"] = final_state

            # 记录执行时间
            execution_time = time.time() - start_time
            logger.info(f"工作流执行完成 - 耗时: {execution_time:.2f}秒")

            return final_state

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            # 返回错误状态
            error_state = create_initial_state(session_id, user_input)
            error_state["error_info"] = {
                "error": str(e),
                "timestamp": time.time(),
            }
            error_state["is_complete"] = True
            error_state["final_answer"] = f"抱歉，系统遇到了问题：{str(e)}"
            return error_state

    def continue_workflow(
        self,
        session_id: str,
        user_choice: str,
    ) -> AstroAgentState:
        """
        继续执行工作流（用于处理用户选择）
        
        Args:
            session_id: 会话ID
            user_choice: 用户选择（"是"或"否"）
            
        Returns:
            最终状态对象
        """
        start_time = time.time()
        logger.info(f"继续执行工作流 - 会话: {session_id}, 用户选择: {user_choice}")
        
        try:
            # 获取现有会话
            if session_id not in self.sessions:
                raise ValueError(f"会话不存在: {session_id}")
                
            session = self.sessions[session_id]
            current_state = session["current_state"].copy()
            
            # 设置用户选择
            current_state["user_choice"] = user_choice
            current_state["awaiting_user_choice"] = False
            session["last_updated"] = datetime.now()
            
            # 继续执行图
            logger.info(f"继续执行图处理，用户选择: {user_choice}")
            final_state = self.graph.invoke(current_state)
            
            # 更新会话状态
            self.sessions[session_id]["current_state"] = final_state
            
            # 记录执行时间
            execution_time = time.time() - start_time
            logger.info(f"工作流继续执行完成 - 耗时: {execution_time:.2f}秒")
            
            return final_state
            
        except Exception as e:
            logger.error(f"继续执行工作流失败: {e}")
            # 返回错误状态
            error_state = create_initial_state(session_id, user_choice)
            error_state["error_info"] = {
                "error": str(e),
                "timestamp": time.time(),
            }
            error_state["is_complete"] = True
            error_state["final_answer"] = f"抱歉，系统遇到了问题：{str(e)}"
            return error_state

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            return {
                "graph_initialized": self.graph is not None,
                "active_sessions": len(self.sessions),
                "session_ids": list(self.sessions.keys()),
                "config_loaded": self.config is not None,
                "use_memory": self.use_memory
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "graph_initialized": False,
                "active_sessions": 0,
                "session_ids": [],
                "config_loaded": False,
                "use_memory": self.use_memory,
                "error": str(e)
            }

    def list_sessions(self) -> List[str]:
        """列出所有活跃会话"""
        return list(self.sessions.keys())

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """获取会话信息"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            return {
                "session_id": session_id,
                "created_at": session["created_at"],
                "last_updated": session["last_updated"],
                "current_step": session["current_state"].get("current_step", "unknown"),
                "is_complete": session["current_state"].get("is_complete", False)
            }
        else:
            return {"error": "会话不存在"}

    def clear_session(self, session_id: str) -> bool:
        """清除指定会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"会话已清除: {session_id}")
            return True
        return False

    def clear_all_sessions(self) -> int:
        """清除所有会话"""
        count = len(self.sessions)
        self.sessions.clear()
        logger.info(f"已清除所有会话，共 {count} 个")
        return count


def execute_improved_astro_workflow(session_id: str, user_input: str, user_context: Optional[Dict[str, Any]] = None) -> AstroAgentState:
    """
    执行改进的天文科研工作流（便捷函数）
    
    Args:
        session_id: 会话ID
        user_input: 用户输入
        user_context: 用户上下文信息（可选）
        
    Returns:
        最终状态对象
    """
    workflow = ImprovedAstroWorkflow()
    return workflow.execute_workflow(session_id, user_input, user_context)
