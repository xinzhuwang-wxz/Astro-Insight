# Maxen Wong
# SPDX-License-Identifier: MIT

from typing import TypedDict, Optional, List, Dict, Any, Annotated, Literal
from langgraph.graph.message import add_messages
import time
import uuid


class AstroAgentState(TypedDict):
    """LangGraph状态定义 - 天文科研Agent系统"""
    # 基础会话信息
    session_id: str
    user_input: str
    messages: Annotated[List[Dict[str, Any]], add_messages]
    
    # 用户身份和任务信息
    user_type: Optional[Literal["amateur", "professional"]]
    task_type: Optional[Literal["classification", "retrieval", "literature"]]
    
    # 配置数据
    config_data: Dict[str, Any]
    
    # 执行状态
    current_step: str
    next_step: Optional[str]
    is_complete: bool
    
    # 结果数据
    qa_response: Optional[str]
    final_answer: Optional[str]
    generated_code: Optional[str]
    execution_result: Optional[Dict[str, Any]]
    
    # 错误处理
    error_info: Optional[Dict[str, Any]]
    retry_count: int
    
    # 历史记录
    execution_history: List[Dict[str, Any]]
    timestamp: float


def validate_state(state: AstroAgentState) -> tuple[bool, List[str]]:
    """验证状态完整性"""
    required_fields = ['session_id', 'user_input', 'current_step', 'timestamp']
    missing_fields = [field for field in required_fields if field not in state]
    is_valid = len(missing_fields) == 0
    return is_valid, missing_fields


def create_initial_state(session_id: str, user_input: str) -> AstroAgentState:
    """创建初始状态"""
    return AstroAgentState(
        session_id=session_id or str(uuid.uuid4()),
        user_input=user_input,
        messages=[{"role": "user", "content": user_input}],
        user_type=None,
        task_type=None,
        config_data={"user_input": user_input},
        current_step="identity_check",
        next_step=None,
        is_complete=False,
        qa_response=None,
        final_answer=None,
        generated_code=None,
        execution_result=None,
        error_info=None,
        retry_count=0,
        execution_history=[],
        timestamp=time.time()
    )
