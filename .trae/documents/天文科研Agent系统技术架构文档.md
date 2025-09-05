# 天文科研Agent系统技术架构文档 (LangGraph版本)

## 1. LangGraph系统架构设计

### 1.1 整体架构图

```mermaid
graph TD
    A[用户输入] --> B[LangGraph StateGraph]
    B --> C[identity_check_node]
    C -->|爱好者| D[qa_agent_node]
    C -->|专业用户| E[task_selector_node]
    E --> F[classification_config_node]
    F --> G[code_generator_node]
    G --> H[code_executor_node]
    H --> I[review_loop_node]
    I -->|满意| J[END]
    I -->|修改| F
    I -->|问题| D
    
    subgraph "LangGraph核心"
        B
        K[StateGraph]
        L[CompiledGraph]
        M[Checkpointer]
    end
    
    subgraph "数据层"
        N[PostgreSQL - 天文数据集]
        O[PostgreSQL - 系统数据]
        P[Redis - 会话缓存]
    end
    
    B <--> K
    K <--> L
    L <--> M
    F <--> N
    B <--> O
    B <--> P
```

### 1.2 LangGraph节点流程图

```mermaid
stateDiagram-v2
    [*] --> START
    START --> identity_check_node
    
    identity_check_node --> qa_agent_node : 爱好者
    identity_check_node --> task_selector_node : 专业用户
    
    qa_agent_node --> END : 问答结束
    
    task_selector_node --> classification_config_node : 选择分类任务
    task_selector_node --> data_retrieval_node : 选择数据检索
    task_selector_node --> literature_review_node : 选择文献综述
    
    classification_config_node --> code_generator_node : 配置完成
    code_generator_node --> code_executor_node : 代码生成完成
    code_executor_node --> review_loop_node : 执行完成
    
    review_loop_node --> END : 满意结束
    review_loop_node --> classification_config_node : 需要修改
    review_loop_node --> qa_agent_node : 有疑问
    
    data_retrieval_node --> END : 检索完成
    literature_review_node --> END : 综述完成
```

## 2. LangGraph Agent详细设计

### 2.1 LangGraph状态定义

采用LangGraph的TypedDict状态管理机制，确保状态传输的类型安全和一致性。

#### 2.1.1 状态结构定义

```python
from typing import TypedDict, Optional, List, Dict, Any, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode
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
    generated_code: Optional[str]
    execution_result: Optional[Dict[str, Any]]
    
    # 错误处理
    error_info: Optional[Dict[str, Any]]
    retry_count: int
    
    # 历史记录
    execution_history: List[Dict[str, Any]]
    timestamp: float

# 状态验证函数
def validate_state(state: AstroAgentState) -> bool:
    """验证状态完整性"""
    required_fields = ['session_id', 'user_input', 'current_step', 'timestamp']
    return all(field in state for field in required_fields)

# 初始化状态函数
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
        generated_code=None,
        execution_result=None,
        error_info=None,
        retry_count=0,
        execution_history=[],
        timestamp=time.time()
    )
```

#### 2.1.2 LangGraph节点实现

**1. 身份识别节点**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
import asyncio

# LLM服务初始化
llm: BaseChatModel = None  # 在实际使用时初始化

def identity_check_node(state: AstroAgentState) -> AstroAgentState:
    """身份识别节点 - 判断用户类型"""
    try:
        user_input = state["user_input"]
        
        # 身份识别提示词
        identity_prompt = ChatPromptTemplate.from_template(
            """请根据用户的问题判断其身份类型：
            
            1. 如果用户询问基础天文知识、观测建议、天体介绍等，判断为"amateur"（爱好者）
            2. 如果用户需要进行数据分析、编程处理、科研计算、论文相关工作，判断为"professional"（专业用户）
            
            用户问题：{user_input}
            
            请只回答"amateur"或"professional"，不要其他解释。
            """
        )
        
        # 调用LLM进行身份识别
        chain = identity_prompt | llm
        response = chain.invoke({"user_input": user_input})
        
        # 解析响应
        user_type = response.content.strip().lower()
        if user_type not in ["amateur", "professional"]:
            user_type = "amateur"  # 默认为爱好者
        
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
```

**2. QA问答节点**

```python
def qa_agent_node(state: AstroAgentState) -> AstroAgentState:
    """QA问答节点 - 处理爱好者的天文问答"""
    try:
        user_input = state["user_input"]
        
        # 构建QA提示词
        qa_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的天文学科普助手，请用通俗易懂的语言回答用户的天文问题。
            
            回答要求：
            1. 语言简洁明了，避免过于专业的术语
            2. 如果涉及观测，提供实用的观测建议
            3. 可以适当添加有趣的天文知识
            4. 如果问题超出天文范围，礼貌地引导回天文话题
            
            用户问题：{user_input}
            """
        )
        
        # 生成回答
        chain = qa_prompt | llm
        response = chain.invoke({"user_input": user_input})
        
        # 更新状态
        state["qa_response"] = response.content
        state["current_step"] = "qa_completed"
        state["is_complete"] = True
        
        # 添加助手消息
        state["messages"].append({
            "role": "assistant",
            "content": response.content
        })
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "qa_agent_node",
            "action": "generate_qa_response",
            "input": user_input,
            "output": response.content,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "qa_agent_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state
```

**3. 任务选择节点**

```python
def task_selector_node(state: AstroAgentState) -> AstroAgentState:
    """任务选择节点 - 为专业用户选择合适的任务类型"""
    try:
        user_input = state["user_input"]
        
        # 任务类型模板
        task_templates = {
            "classification": "天体分类任务",
            "retrieval": "数据检索任务", 
            "literature": "文献综述任务"
        }
        
        # 任务分类提示词
        task_prompt = ChatPromptTemplate.from_template(
            """请根据用户的需求，从以下任务类型中选择最合适的一个：
            
            可选任务类型：
            - classification: 天体分类任务（如星系分类、恒星分类等）
            - retrieval: 数据检索任务（如星表查询、观测数据获取等）
            - literature: 文献综述任务（如论文检索、研究综述等）
            
            用户需求：{user_input}
            
            请只返回任务类型的key（如：classification），不要其他解释。
            """
        )
        
        # 调用LLM进行任务分类
        chain = task_prompt | llm
        response = chain.invoke({"user_input": user_input})
        
        # 解析响应
        selected_task = response.content.strip()
        if selected_task not in task_templates:
            selected_task = "classification"  # 默认任务类型
        
        # 更新状态
        state["task_type"] = selected_task
        state["current_step"] = "task_selected"
        state["config_data"]["selected_task"] = selected_task
        state["config_data"]["task_description"] = task_templates[selected_task]
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "task_selector_node",
            "action": "task_selection",
            "input": user_input,
            "output": selected_task,
            "timestamp": time.time()
        })
        
        return state
        
    except Exception as e:
        state["error_info"] = {
            "node": "task_selector_node",
            "error": str(e),
            "timestamp": time.time()
        }
        state["retry_count"] += 1
        return state
```

**4. 分类配置节点**

```python
def classification_config_node(state: AstroAgentState) -> AstroAgentState:
    """分类配置节点 - 配置天体分类任务参数"""
    try:
        user_input = state["user_input"]
        task_type = state.get("task_type", "classification")
        
        # 配置模板
        config_templates = {
            "stellar_classification": {
                "data_source": "Gaia DR3",
                "features": ["bp_rp", "g_mag", "parallax", "pmra", "pmdec"],
                "algorithm": "Random Forest",
                "target_classes": ["Main Sequence", "Giant", "White Dwarf"]
            },
            "galaxy_classification": {
                "data_source": "SDSS DR17",
                "features": ["u-g", "g-r", "r-i", "i-z", "redshift"],
                "algorithm": "SVM",
                "target_classes": ["Elliptical", "Spiral", "Irregular"]
            },
            "exoplanet_classification": {
                "data_source": "Kepler/TESS",
                "features": ["period", "transit_depth", "duration", "stellar_mass"],
                "algorithm": "Neural Network",
                "target_classes": ["Hot Jupiter", "Super Earth", "Neptune-like"]
            }
        }
        
        # 配置生成提示词
        config_prompt = ChatPromptTemplate.from_template(
            """请根据用户需求生成天体分类任务的配置。
            
            用户需求：{user_input}
            任务类型：{task_type}
            
            请从以下配置模板中选择最合适的，或基于用户需求自定义配置：
            
            可选配置类型：
            1. stellar_classification - 恒星分类（基于Gaia数据）
            2. galaxy_classification - 星系分类（基于SDSS数据）
            3. exoplanet_classification - 系外行星分类（基于Kepler/TESS数据）
            
            请返回JSON格式的配置，包含：
            - data_source: 数据源
            - features: 特征参数列表
            - algorithm: 分类算法
            - target_classes: 目标分类类别
            - sample_size: 样本大小（可选）
            - validation_split: 验证集比例（可选）
            """
        )
        
        # 生成配置
        chain = config_prompt | llm
        response = chain.invoke({
            "user_input": user_input,
            "task_type": task_type
        })
        
        # 解析配置
        try:
            import json
            config = json.loads(response.content)
        except (json.JSONDecodeError, AttributeError):
            # 如果解析失败，使用默认配置
            config = config_templates.get("stellar_classification", {})
        
        # 更新状态
        state["task_config"] = config
        state["current_step"] = "config_generated"
        state["config_data"]["task_config"] = config
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "classification_config_node",
            "action": "generate_config",
            "input": {"user_input": user_input, "task_type": task_type},
            "output": config,
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
```

**5. 代码生成节点**

```python
def code_generator_node(state: AstroAgentState) -> AstroAgentState:
    """代码生成节点 - 根据配置生成执行代码"""
    try:
        task_config = state.get("task_config", {})
        user_input = state["user_input"]
        
        # 代码生成提示词
        code_prompt = ChatPromptTemplate.from_template(
            """请根据以下配置生成完整的Python代码来执行天文数据分析任务。
            
            用户需求：{user_input}
            任务配置：{task_config}
            
            代码要求：
            1. 包含必要的导入语句
            2. 数据获取和预处理
            3. 特征工程和模型训练
            4. 结果可视化和保存
            5. 添加适当的注释和错误处理
            6. 使用常见的天文学Python库（如astropy, pandas, sklearn等）
            
            请返回完整可执行的Python代码。
            """
        )
        
        # 生成代码
        chain = code_prompt | llm
        response = chain.invoke({
            "user_input": user_input,
            "task_config": str(task_config)
        })
        
        generated_code = response.content
        
        # 更新状态
        state["generated_code"] = generated_code
        state["current_step"] = "code_generated"
        state["config_data"]["generated_code"] = generated_code
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "code_generator_node",
            "action": "generate_code",
            "input": {"user_input": user_input, "task_config": task_config},
            "output": generated_code[:500] + "..." if len(generated_code) > 500 else generated_code,
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
```

**6. 代码执行节点**

```python
def code_executor_node(state: AstroAgentState) -> AstroAgentState:
    """代码执行节点 - 在安全环境中执行生成的代码"""
    try:
        generated_code = state.get("generated_code", "")
        
        if not generated_code:
            raise ValueError("No code to execute")
        
        # 代码安全检查
        dangerous_patterns = [
            "import os", "import subprocess", "import sys",
            "exec(", "eval(", "__import__",
            "open(", "file(", "input("
        ]
        
        for pattern in dangerous_patterns:
            if pattern in generated_code:
                raise ValueError(f"Potentially dangerous code detected: {pattern}")
        
        # 模拟代码执行（实际实现中应使用安全的沙箱环境）
        execution_result = {
            "status": "success",
            "output": "Code executed successfully",
            "plots": [],  # 生成的图表路径
            "data_files": [],  # 生成的数据文件
            "metrics": {}  # 性能指标
        }
        
        # 更新状态
        state["execution_result"] = execution_result
        state["current_step"] = "code_executed"
        state["config_data"]["execution_result"] = execution_result
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "code_executor_node",
            "action": "execute_code",
            "input": generated_code[:200] + "..." if len(generated_code) > 200 else generated_code,
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
```

**7. 审查循环节点**

```python
def review_loop_node(state: AstroAgentState) -> AstroAgentState:
    """审查循环节点 - 检查结果质量并决定是否需要重新生成"""
    try:
        execution_result = state.get("execution_result", {})
        user_input = state["user_input"]
        
        # 结果质量评估提示词
        review_prompt = ChatPromptTemplate.from_template(
            """请评估以下代码执行结果的质量，并判断是否满足用户需求。
            
            用户原始需求：{user_input}
            执行结果：{execution_result}
            
            评估标准：
            1. 是否正确回答了用户问题
            2. 结果是否合理和准确
            3. 是否包含必要的可视化
            4. 代码是否成功执行
            
            请返回JSON格式的评估结果：
            {{
                "quality_score": 0-100的分数,
                "is_satisfactory": true/false,
                "feedback": "具体的改进建议",
                "needs_revision": true/false
            }}
            """
        )
        
        # 生成评估
        chain = review_prompt | llm
        response = chain.invoke({
            "user_input": user_input,
            "execution_result": str(execution_result)
        })
        
        # 解析评估结果
        try:
            import json
            review_result = json.loads(response.content)
        except (json.JSONDecodeError, AttributeError):
            # 默认评估结果
            review_result = {
                "quality_score": 75,
                "is_satisfactory": True,
                "feedback": "结果基本满足要求",
                "needs_revision": False
            }
        
        # 更新状态
        state["review_result"] = review_result
        state["quality_score"] = review_result.get("quality_score", 75)
        
        # 判断是否需要重新生成
        if review_result.get("needs_revision", False) and state["retry_count"] < 3:
            state["current_step"] = "needs_revision"
            state["config_data"]["revision_feedback"] = review_result.get("feedback", "")
        else:
            state["current_step"] = "completed"
            state["is_complete"] = True
        
        # 记录执行历史
        state["execution_history"].append({
            "node": "review_loop_node",
            "action": "quality_review",
            "input": {"user_input": user_input, "execution_result": execution_result},
            "output": review_result,
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
```

## 3. LangGraph状态管理优化

### 3.1 状态持久化和检查点

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
import asyncpg
import json

class AstroAgentCheckpointer:
    """天文科研Agent的状态检查点管理器"""
    
    def __init__(self, postgres_url: str = None):
        if postgres_url:
            # 使用PostgreSQL作为持久化存储
            self.checkpointer = PostgresSaver.from_conn_string(postgres_url)
        else:
            # 使用内存存储（开发环境）
            self.checkpointer = MemorySaver()
    
    async def save_checkpoint(self, config: dict, checkpoint: dict, metadata: dict = None):
        """保存检查点"""
        await self.checkpointer.aput(config, checkpoint, metadata or {})
    
    async def load_checkpoint(self, config: dict):
        """加载检查点"""
        return await self.checkpointer.aget(config)
    
    async def list_checkpoints(self, config: dict, limit: int = 10):
        """列出历史检查点"""
        checkpoints = []
        async for checkpoint in self.checkpointer.alist(config, limit=limit):
            checkpoints.append(checkpoint)
        return checkpoints

# 状态验证和类型检查
def validate_state(state: AstroAgentState) -> bool:
    """验证状态数据的完整性和类型正确性"""
    try:
        # 检查必需字段
        required_fields = [
            "session_id", "user_input", "user_type", 
            "current_step", "messages", "config_data", 
            "execution_history", "retry_count"
        ]
        
        for field in required_fields:
            if field not in state:
                return False
        
        # 类型检查
        if not isinstance(state["session_id"], str):
            return False
        if not isinstance(state["messages"], list):
            return False
        if not isinstance(state["config_data"], dict):
            return False
        if not isinstance(state["execution_history"], list):
            return False
        if not isinstance(state["retry_count"], int):
            return False
        
        # 业务逻辑验证
        if state["user_type"] not in ["amateur", "professional"]:
            return False
        
        return True
        
    except Exception:
        return False

# 状态快照和恢复
class StateSnapshot:
    """状态快照管理"""
    
    @staticmethod
    def create_snapshot(state: AstroAgentState) -> dict:
        """创建状态快照"""
        return {
            "timestamp": time.time(),
            "session_id": state["session_id"],
            "current_step": state["current_step"],
            "user_type": state["user_type"],
            "retry_count": state["retry_count"],
            "is_complete": state.get("is_complete", False),
            "error_info": state.get("error_info"),
            "execution_summary": {
                "total_steps": len(state["execution_history"]),
                "last_action": state["execution_history"][-1] if state["execution_history"] else None
            }
        }
    
    @staticmethod
    def restore_from_snapshot(snapshot: dict, full_state: AstroAgentState) -> AstroAgentState:
        """从快照恢复状态"""
        # 恢复关键字段
        full_state["current_step"] = snapshot["current_step"]
        full_state["retry_count"] = snapshot["retry_count"]
        full_state["is_complete"] = snapshot.get("is_complete", False)
        
        if snapshot.get("error_info"):
            full_state["error_info"] = snapshot["error_info"]
        
        return full_state
```

### 3.2 LangGraph错误处理和恢复

```python
from typing import Optional, Dict, Any
import traceback
import logging

class LangGraphErrorHandler:
    """LangGraph风格的错误处理和恢复机制"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
    
    def handle_node_error(self, state: AstroAgentState, error: Exception, node_name: str) -> AstroAgentState:
        """处理节点执行错误"""
        self.logger.error(f"Error in node {node_name}: {str(error)}")
        
        # 更新错误信息
        state["error_info"] = {
            "node": node_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": time.time(),
            "retry_count": state.get("retry_count", 0)
        }
        
        # 增加重试计数
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        # 记录错误历史
        state["execution_history"].append({
            "node": node_name,
            "action": "error_occurred",
            "error": str(error),
            "timestamp": time.time()
        })
        
        return state
    
    def should_retry(self, state: AstroAgentState, error: Exception) -> bool:
        """判断是否应该重试"""
        retry_count = state.get("retry_count", 0)
        
        # 超过最大重试次数
        if retry_count >= self.max_retries:
            return False
        
        # 某些错误类型不应重试
        non_retryable_errors = [
            "ValidationError",
            "AuthenticationError",
            "PermissionError"
        ]
        
        if type(error).__name__ in non_retryable_errors:
            return False
        
        return True
    
    def get_recovery_strategy(self, state: AstroAgentState, error: Exception) -> str:
        """获取错误恢复策略"""
        error_type = type(error).__name__
        current_step = state.get("current_step", "unknown")
        user_type = state.get("user_type", "amateur")
        
        # 基于错误类型和当前状态的恢复策略
        if error_type in ["LLMError", "APIError", "TimeoutError"]:
            if self.should_retry(state, error):
                return "retry_current_node"
            else:
                return "fallback_to_qa" if user_type == "amateur" else "fallback_to_manual"
        
        elif error_type in ["ValidationError", "DataError"]:
            return "fallback_to_qa"
        
        elif error_type in ["ConfigurationError"]:
            return "restart_configuration"
        
        else:
            return "graceful_exit"

# 错误恢复装饰器
def with_error_recovery(error_handler: LangGraphErrorHandler):
    """为节点函数添加错误恢复能力的装饰器"""
    def decorator(node_func):
        def wrapper(state: AstroAgentState) -> AstroAgentState:
            try:
                return node_func(state)
            except Exception as e:
                # 处理错误
                state = error_handler.handle_node_error(state, e, node_func.__name__)
                
                # 获取恢复策略
                recovery_strategy = error_handler.get_recovery_strategy(state, e)
                
                # 执行恢复策略
                if recovery_strategy == "retry_current_node" and error_handler.should_retry(state, e):
                    # 重试当前节点
                    return wrapper(state)
                elif recovery_strategy == "fallback_to_qa":
                    # 降级到QA模式
                    state["current_step"] = "fallback_qa"
                    state["user_type"] = "amateur"
                elif recovery_strategy == "restart_configuration":
                    # 重新开始配置
                    state["current_step"] = "task_selected"
                elif recovery_strategy == "graceful_exit":
                    # 优雅退出
                    state["is_complete"] = True
                    state["current_step"] = "error_exit"
                
                return state
        
        return wrapper
    return decorator

# 状态恢复策略
class StateRecovery:
    """状态恢复策略实现"""
    
    @staticmethod
    def recover_from_checkpoint(checkpointer: AstroAgentCheckpointer, 
                              session_id: str, 
                              steps_back: int = 1) -> Optional[AstroAgentState]:
        """从检查点恢复状态"""
        try:
            config = {"configurable": {"thread_id": session_id}}
            checkpoints = checkpointer.list_checkpoints(config, limit=steps_back + 1)
            
            if len(checkpoints) > steps_back:
                # 恢复到指定步数之前的状态
                target_checkpoint = checkpoints[steps_back]
                return target_checkpoint.get("state")
            
            return None
            
        except Exception as e:
            logging.error(f"Failed to recover from checkpoint: {e}")
            return None
    
    @staticmethod
    def create_fallback_state(original_state: AstroAgentState, 
                            fallback_type: str = "qa") -> AstroAgentState:
        """创建降级状态"""
        fallback_state = original_state.copy()
        
        if fallback_type == "qa":
            fallback_state["user_type"] = "amateur"
            fallback_state["current_step"] = "identity_checked"
            fallback_state["retry_count"] = 0
            # 清除专业用户相关的配置
            fallback_state["config_data"] = {
                "user_input": fallback_state["user_input"]
            }
        
        return fallback_state
```

### 3.3 事件日志系统

```python
class EventLogger:
    """记录所有状态转换和事件，用于eval评估"""
    
    def __init__(self, postgres_client):
        self.postgres = postgres_client
    
    async def log_transition(self, session_id: str, from_agent: str, to_agent: str, 
                           old_status: AgentStatus, new_status: AgentStatus, timestamp: float):
        """记录Agent转换事件"""
        await self.postgres.execute(
            """
            INSERT INTO agent_transitions 
            (session_id, from_agent, to_agent, old_status, new_status, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            session_id, from_agent, to_agent, 
            old_status.value, new_status.value, timestamp
        )
    
    async def log_error(self, session_id: str, agent_name: str, error_info: Dict[str, Any]):
        """记录错误事件"""
        await self.postgres.execute(
            """
            INSERT INTO error_logs 
            (session_id, agent_name, error_type, error_message, timestamp)
            VALUES ($1, $2, $3, $4, $5)
            """,
            session_id, agent_name, 
            error_info.get("error_type", "Unknown"),
            error_info.get("error_message", ""),
            time.time()
        )
    
    async def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """获取会话的评估指标"""
        # 计算总耗时
        total_time = await self.postgres.fetchval(
            "SELECT MAX(timestamp) - MIN(timestamp) FROM agent_transitions WHERE session_id = $1",
            session_id
        )
        
        # 计算Agent转换次数
        transition_count = await self.postgres.fetchval(
            "SELECT COUNT(*) FROM agent_transitions WHERE session_id = $1",
            session_id
        )
        
        # 计算错误次数
        error_count = await self.postgres.fetchval(
            "SELECT COUNT(*) FROM error_logs WHERE session_id = $1",
            session_id
        )
        
        # 计算成功率
        success_rate = 1.0 - (error_count / max(transition_count, 1))
        
        return {
            "total_time": total_time,
            "transition_count": transition_count,
            "error_count": error_count,
            "success_rate": success_rate,
            "efficiency_score": self._calculate_efficiency(total_time, transition_count)
        }
```

## 4. 节点间接口统一设计

### 4.1 标准化节点接口协议

所有Agent节点都遵循统一的接口协议，确保可测试性和互操作性。

```python
class NodeInterface(Protocol):
    """节点接口协议"""
    
    async def process(self, state: AgentState) -> AgentState:
        """处理状态的标准接口"""
        ...
    
    def validate_input(self, state: AgentState) -> bool:
        """验证输入状态"""
        ...
    
    def get_expected_input_schema(self) -> Dict[str, Any]:
        """返回期望的输入状态结构"""
        ...
    
    def get_output_schema(self) -> Dict[str, Any]:
        """返回输出状态结构"""
        ...

class AgentRegistry:
    """Agent注册表，管理所有Agent的元信息"""
    
    _agents: Dict[str, Dict[str, Any]] = {
        "QA_Agent": {
            "class": QA_Agent,
            "input_schema": {
                "required": ["user_type", "config_data.user_input"],
                "user_type": "amateur"
            },
            "output_schema": {
                "adds": ["config_data.qa_response"],
                "next_agent": None
            },
            "dependencies": ["llm_service", "knowledge_base"]
        },
        "Task_Selector_Agent": {
            "class": Task_Selector_Agent,
            "input_schema": {
                "required": ["user_type"],
                "user_type": "professional"
            },
            "output_schema": {
                "adds": ["task_type", "config_data.available_tasks"],
                "next_agent": ["Classification_Configurator_Agent", "Data_Retrieval_Agent", "Literature_Review_Agent"]
            },
            "dependencies": []
        }
        # ... 其他Agent配置
    }
    
    @classmethod
    def validate_state_compatibility(cls, from_agent: str, to_agent: str, state: AgentState) -> bool:
        """验证两个Agent间的状态兼容性"""
        if to_agent not in cls._agents:
            return False
        
        target_schema = cls._agents[to_agent]["input_schema"]
        
        # 检查必需字段
        for required_field in target_schema.get("required", []):
            if "." in required_field:
                # 嵌套字段检查
                parts = required_field.split(".")
                current = state
                for part in parts:
                    if not hasattr(current, part):
                        return False
                    current = getattr(current, part)
            else:
                if not hasattr(state, required_field):
                    return False
        
        return True
```

### 4.2 节点测试框架

```python
class NodeTester:
    """节点测试框架，用于测试任意两个节点间的传输"""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.test_results = []
    
    async def test_node_transition(self, from_agent: str, to_agent: str, 
                                 test_state: AgentState) -> TestResult:
        """测试两个节点间的状态传输"""
        test_id = f"{from_agent}_to_{to_agent}_{int(time.time())}"
        
        try:
            # 1. 验证输入状态
            if not AgentRegistry.validate_state_compatibility(from_agent, to_agent, test_state):
                return TestResult(
                    test_id=test_id,
                    success=False,
                    error="State compatibility validation failed",
                    from_agent=from_agent,
                    to_agent=to_agent
                )
            
            # 2. 执行from_agent
            test_state.current_agent = from_agent
            intermediate_state = await self.state_manager.process_state(test_state)
            
            # 3. 检查中间状态
            if intermediate_state.status == AgentStatus.FAILED:
                return TestResult(
                    test_id=test_id,
                    success=False,
                    error=f"From agent {from_agent} failed",
                    intermediate_state=intermediate_state
                )
            
            # 4. 执行to_agent
            intermediate_state.current_agent = to_agent
            final_state = await self.state_manager.process_state(intermediate_state)
            
            # 5. 验证最终状态
            success = final_state.status != AgentStatus.FAILED
            
            result = TestResult(
                test_id=test_id,
                success=success,
                from_agent=from_agent,
                to_agent=to_agent,
                intermediate_state=intermediate_state,
                final_state=final_state,
                execution_time=final_state.timestamp - test_state.timestamp
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            return TestResult(
                test_id=test_id,
                success=False,
                error=str(e),
                from_agent=from_agent,
                to_agent=to_agent
            )
    
    async def run_full_pipeline_test(self) -> Dict[str, Any]:
        """运行完整的流水线测试"""
        test_cases = [
            ("Identity_Check", "QA_Agent", self._create_amateur_state()),
            ("Identity_Check", "Task_Selector_Agent", self._create_professional_state()),
            ("Task_Selector_Agent", "Classification_Configurator_Agent", self._create_classification_state()),
            ("Classification_Configurator_Agent", "Code_Generator_Agent", self._create_configured_state()),
            ("Code_Generator_Agent", "Code_Executor_Agent", self._create_code_ready_state()),
            ("Code_Executor_Agent", "Review_Loop_Agent", self._create_execution_complete_state())
        ]
        
        results = []
        for from_agent, to_agent, test_state in test_cases:
            result = await self.test_node_transition(from_agent, to_agent, test_state)
            results.append(result)
        
        # 生成测试报告
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        return {
            "total_tests": total_count,
            "successful_tests": success_count,
            "success_rate": success_count / total_count,
            "failed_tests": [r for r in results if not r.success],
            "average_execution_time": sum(r.execution_time or 0 for r in results) / total_count
        }

@dataclass
class TestResult:
    test_id: str
    success: bool
    from_agent: str
    to_agent: str
    error: Optional[str] = None
    intermediate_state: Optional[AgentState] = None
    final_state: Optional[AgentState] = None
    execution_time: Optional[float] = None
```

**对话交互**

```
POST /api/chat/message
```

请求:

| 参数名         | 参数类型   | 是否必需  | 描述     |
| ----------- | ------ | ----- | ------ |
| session\_id | string | true  | 会话ID   |
| message     | string | true  | 用户消息内容 |
| context     | object | false | 上下文信息  |

响应:

| 参数名          | 参数类型   | 描述        |
| ------------ | ------ | --------- |
| response     | string | Agent回复内容 |
| next\_action | string | 下一步操作类型   |
| options      | array  | 可选操作列表    |

**任务配置**

```
POST /api/tasks/configure
```

请求:

| 参数名        | 参数类型   | 是否必需 | 描述                                        |
| ---------- | ------ | ---- | ----------------------------------------- |
| task\_type | string | true | 任务类型（classification/retrieval/literature） |
| config     | object | true | 配置参数                                      |

响应:

| 参数名        | 参数类型   | 描述     |
| ---------- | ------ | ------ |
| config\_id | string | 配置唯一标识 |
| blueprint  | object | 配置蓝图   |

**代码生成与执行**

```
POST /api/code/generate
```

请求:

| 参数名        | 参数类型   | 是否必需 | 描述   |
| ---------- | ------ | ---- | ---- |
| config\_id | string | true | 配置ID |

响应:

| 参数名           | 参数类型   | 描述          |
| ------------- | ------ | ----------- |
| code          | string | 生成的Python代码 |
| execution\_id | string | 执行任务ID      |

```
POST /api/code/execute
```

请求:

| 参数名           | 参数类型   | 是否必需 | 描述     |
| ------------- | ------ | ---- | ------ |
| execution\_id | string | true | 执行任务ID |
| code          | string | true | 要执行的代码 |

响应:

| 参数名         | 参数类型   | 描述                             |
| ----------- | ------ | ------------------------------ |
| status      | string | 执行状态（running/completed/failed） |
| output      | string | 执行输出                           |
| result\_url | string | 结果文件下载链接                       |

## 5. 数据集管理方案

### 5.1 天文数据集下载与存储

```python
class AstronomyDataManager:
    """天文数据集管理器"""
    
    def __init__(self, pg_connection: str, docker_config: Optional[Dict] = None):
        self.pg_connection = pg_connection
        self.docker_config = docker_config or {}
        self.supported_datasets = {
            "gaia_dr3": {
                "url": "https://gea.esac.esa.int/archive/",
                "tables": ["gaia_source", "gaia_source_lite"],
                "size_gb": 1200,
                "update_frequency": "yearly"
            },
            "sdss_dr17": {
                "url": "https://www.sdss.org/dr17/",
                "tables": ["photoobj", "specobj", "galspec"],
                "size_gb": 800,
                "update_frequency": "yearly"
            },
            "2mass": {
                "url": "https://irsa.ipac.caltech.edu/2MASS/",
                "tables": ["fp_psc", "fp_xsc"],
                "size_gb": 150,
                "update_frequency": "static"
            },
            "wise_allwise": {
                "url": "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-scan",
                "tables": ["allwise_p3as_psd"],
                "size_gb": 200,
                "update_frequency": "static"
            }
        }
    
    async def download_dataset(self, dataset_name: str, 
                             tables: Optional[List[str]] = None,
                             chunk_size: int = 10000) -> bool:
        """下载指定数据集到PostgreSQL"""
        if dataset_name not in self.supported_datasets:
            raise ValueError(f"Unsupported dataset: {dataset_name}")
        
        dataset_info = self.supported_datasets[dataset_name]
        tables_to_download = tables or dataset_info["tables"]
        
        try:
            for table_name in tables_to_download:
                await self._download_table(dataset_name, table_name, chunk_size)
            
            # 创建索引以优化查询性能
            await self._create_indexes(dataset_name, tables_to_download)
            
            # 更新数据集元信息
            await self._update_dataset_metadata(dataset_name, tables_to_download)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download dataset {dataset_name}: {e}")
            return False
    
    async def _download_table(self, dataset_name: str, table_name: str, chunk_size: int):
        """下载单个数据表"""
        # 实现具体的数据下载逻辑
        # 支持断点续传和增量更新
        pass
    
    async def _create_indexes(self, dataset_name: str, tables: List[str]):
        """为数据表创建必要的索引"""
        index_configs = {
            "gaia_source": [
                "CREATE INDEX IF NOT EXISTS idx_gaia_ra_dec ON gaia_source (ra, dec);",
                "CREATE INDEX IF NOT EXISTS idx_gaia_parallax ON gaia_source (parallax);",
                "CREATE INDEX IF NOT EXISTS idx_gaia_pmra_pmdec ON gaia_source (pmra, pmdec);"
            ],
            "photoobj": [
                "CREATE INDEX IF NOT EXISTS idx_sdss_ra_dec ON photoobj (ra, dec);",
                "CREATE INDEX IF NOT EXISTS idx_sdss_type ON photoobj (type);",
                "CREATE INDEX IF NOT EXISTS idx_sdss_clean ON photoobj (clean);"
            ]
        }
        
        async with asyncpg.connect(self.pg_connection) as conn:
            for table in tables:
                if table in index_configs:
                    for index_sql in index_configs[table]:
                        await conn.execute(index_sql)

class DatasetAPI:
    """数据集访问API"""
    
    def __init__(self, data_manager: AstronomyDataManager):
        self.data_manager = data_manager
    
    async def query_objects_by_coordinates(self, ra: float, dec: float, 
                                         radius: float, dataset: str = "gaia_dr3") -> List[Dict]:
        """根据坐标查询天体"""
        query = f"""
        SELECT * FROM {dataset}_source 
        WHERE q3c_radial_query(ra, dec, {ra}, {dec}, {radius})
        LIMIT 1000
        """
        
        async with asyncpg.connect(self.data_manager.pg_connection) as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    async def cross_match_catalogs(self, catalog1: str, catalog2: str, 
                                 match_radius: float = 1.0) -> List[Dict]:
        """交叉匹配不同星表"""
        query = f"""
        SELECT c1.*, c2.*
        FROM {catalog1} c1
        JOIN {catalog2} c2 ON q3c_join(c1.ra, c1.dec, c2.ra, c2.dec, {match_radius}/3600.0)
        LIMIT 10000
        """
        
        async with asyncpg.connect(self.data_manager.pg_connection) as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
```

### 5.2 Docker部署配置

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: astronomy_data
      POSTGRES_USER: astro_user
      POSTGRES_PASSWORD: astro_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init_scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    command: |
      postgres 
      -c shared_preload_libraries=q3c 
      -c max_connections=200 
      -c shared_buffers=2GB 
      -c effective_cache_size=6GB
  
  data_downloader:
    build: .
    environment:
      DATABASE_URL: postgresql://astro_user:astro_password@postgres:5432/astronomy_data
    depends_on:
      - postgres
    volumes:
      - ./data_cache:/app/cache
    command: python -m astronomy_data.downloader

volumes:
  postgres_data:
```

```sql
-- init_scripts/01_extensions.sql
CREATE EXTENSION IF NOT EXISTS q3c;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- init_scripts/02_schemas.sql
CREATE SCHEMA IF NOT EXISTS gaia;
CREATE SCHEMA IF NOT EXISTS sdss;
CREATE SCHEMA IF NOT EXISTS twomass;
CREATE SCHEMA IF NOT EXISTS wise;
```

## 6. 服务架构图

```mermaid
graph TD
    A[客户端/前端] --> B[API网关层]
    B --> C[业务逻辑层]
    C --> D[数据访问层]
    D --> E[(数据库)]
    
    subgraph "业务逻辑层"
        C1[会话管理服务]
        C2[对话处理服务]
        C3[任务配置服务]
        C4[代码生成服务]
        C5[代码执行服务]
    end
    
    subgraph "外部服务集成层"
        F1[LLM API服务]
        F2[天文数据API]
        F3[文献检索API]
    end
    
    C --> F1
    C --> F2
    C --> F3
```

## 6. 简化身份识别机制

### 6.1 身份识别流程优化

移除复杂的用户身份库，采用基于LLM的智能身份识别：

```python
class SimplifiedIdentityChecker:
    """简化的身份识别器"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.identity_prompt = """
        请根据用户的问题判断其身份类型：
        
        1. 如果用户询问基础天文知识、观测建议、天体介绍等，判断为"amateur"（爱好者）
        2. 如果用户需要进行数据分析、编程处理、科研计算、论文相关工作，判断为"professional"（专业用户）
        
        用户问题：{user_input}
        
        请只回答"amateur"或"professional"，不要其他解释。
        """
    
    async def identify_user_type(self, user_input: str) -> str:
        """基于用户输入识别身份类型"""
        try:
            prompt = self.identity_prompt.format(user_input=user_input)
            response = await self.llm_service.generate(prompt)
            
            # 清理响应并验证
            user_type = response.strip().lower()
            if user_type in ["amateur", "professional"]:
                return user_type
            else:
                # 默认为爱好者，使用简单问答
                return "amateur"
                
        except Exception as e:
            logger.warning(f"Identity check failed: {e}, defaulting to amateur")
            return "amateur"

class OptimizedQAAgent(BaseAgent):
    """优化的问答Agent，专门处理爱好者问题"""
    
    def __init__(self, llm_service, knowledge_base):
        super().__init__()
        self.llm_service = llm_service
        self.knowledge_base = knowledge_base
        self.qa_prompt = """
        你是一个专业的天文学科普助手，请用通俗易懂的语言回答用户的天文问题。
        
        回答要求：
        1. 语言简洁明了，避免过于专业的术语
        2. 如果涉及观测，提供实用的观测建议
        3. 可以适当添加有趣的天文知识
        4. 如果问题超出天文范围，礼貌地引导回天文话题
        
        用户问题：{user_input}
        
        相关知识：{context}
        """
    
    async def process(self, state: AgentState) -> AgentState:
        """处理爱好者的天文问答"""
        try:
            user_input = state.config_data.get("user_input", "")
            
            # 从知识库检索相关信息
            context = await self.knowledge_base.search(user_input, limit=3)
            context_text = "\n".join([item["content"] for item in context])
            
            # 生成回答
            prompt = self.qa_prompt.format(
                user_input=user_input,
                context=context_text
            )
            
            response = await self.llm_service.generate(prompt)
            
            # 更新状态
            state.config_data["qa_response"] = response
            state.config_data["response_type"] = "amateur_qa"
            state.status = AgentStatus.COMPLETED
            state.next_agent = None  # 爱好者问答结束流程
            
            return state
            
        except Exception as e:
            state.status = AgentStatus.FAILED
            state.error_message = f"QA processing failed: {str(e)}"
            return state
    
    def validate_input(self, state: AgentState) -> bool:
        """验证输入状态"""
        return (
            hasattr(state, 'user_type') and 
            state.user_type == "amateur" and
            hasattr(state, 'config_data') and
            "user_input" in state.config_data
        )

class IdentityCheckAgent(BaseAgent):
    """身份检查Agent"""
    
    def __init__(self, identity_checker: SimplifiedIdentityChecker):
        super().__init__()
        self.identity_checker = identity_checker
    
    async def process(self, state: AgentState) -> AgentState:
        """处理身份识别"""
        try:
            user_input = state.config_data.get("user_input", "")
            
            # 使用LLM进行身份识别
            user_type = await self.identity_checker.identify_user_type(user_input)
            
            # 更新状态
            state.user_type = user_type
            state.config_data["identified_user_type"] = user_type
            
            # 根据身份类型决定下一步
            if user_type == "amateur":
                state.next_agent = "QA_Agent"
                state.config_data["flow_type"] = "simple_qa"
            else:
                state.next_agent = "Task_Selector_Agent"
                state.config_data["flow_type"] = "professional_workflow"
            
            state.status = AgentStatus.COMPLETED
            
            return state
            
        except Exception as e:
            state.status = AgentStatus.FAILED
            state.error_message = f"Identity check failed: {str(e)}"
            return state
    
    def validate_input(self, state: AgentState) -> bool:
        """验证输入状态"""
        return (
            hasattr(state, 'config_data') and
            "user_input" in state.config_data and
            len(state.config_data["user_input"].strip()) > 0
        )
```

### 6.2 优化后的流程图

```mermaid
graph TD
    A[用户输入] --> B[Identity_Check_Agent]
    B --> C{用户类型判断}
    
    C -->|amateur| D[QA_Agent]
    D --> E[返回科普回答]
    E --> F[结束]
    
    C -->|professional| G[Task_Selector_Agent]
    G --> H[Classification_Configurator_Agent]
    H --> I[Data_Retrieval_Agent]
    I --> J[Code_Generator_Agent]
    J --> K[Code_Executor_Agent]
    K --> L[Review_Loop_Agent]
    L --> M{需要优化?}
    M -->|是| N[Optimization_Agent]
    N --> J
    M -->|否| O[结果输出]
    O --> F
    
    style D fill:#e1f5fe
    style G fill:#f3e5f5
    style F fill:#e8f5e8
```

## 4. LangGraph图构建和路由

### 4.1 完整的图构建实现

```python
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from typing import Literal
import asyncio

class AstroAgentGraph:
    """天文科研Agent系统的LangGraph实现"""
    
    def __init__(self, checkpointer_type: str = "memory"):
        self.error_handler = LangGraphErrorHandler(max_retries=3)
        self.checkpointer = self._create_checkpointer(checkpointer_type)
        self.graph = self._build_graph()
    
    def _create_checkpointer(self, checkpointer_type: str):
        """创建检查点保存器"""
        if checkpointer_type == "postgres":
            return PostgresSaver.from_conn_string(
                "postgresql://user:password@localhost:5432/astro_agent"
            )
        else:
            return MemorySaver()
    
    def _build_graph(self) -> StateGraph:
        """构建完整的状态图"""
        # 创建状态图
        workflow = StateGraph(AstroAgentState)
        
        # 添加所有节点（使用错误恢复装饰器）
        workflow.add_node(
            "identity_check", 
            with_error_recovery(self.error_handler)(identity_check_node)
        )
        workflow.add_node(
            "qa_agent", 
            with_error_recovery(self.error_handler)(qa_agent_node)
        )
        workflow.add_node(
            "task_selector", 
            with_error_recovery(self.error_handler)(task_selector_node)
        )
        workflow.add_node(
            "classification_config", 
            with_error_recovery(self.error_handler)(classification_config_node)
        )
        workflow.add_node(
            "code_generator", 
            with_error_recovery(self.error_handler)(code_generator_node)
        )
        workflow.add_node(
            "code_executor", 
            with_error_recovery(self.error_handler)(code_executor_node)
        )
        workflow.add_node(
            "review_loop", 
            with_error_recovery(self.error_handler)(review_loop_node)
        )
        
        # 设置入口点
        workflow.set_entry_point("identity_check")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "identity_check",
            self.route_after_identity_check,
            {
                "amateur": "qa_agent",
                "professional": "task_selector",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "qa_agent",
            self.route_after_qa,
            {
                "complete": END,
                "continue": "qa_agent",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "task_selector",
            self.route_after_task_selection,
            {
                "classification": "classification_config",
                "data_retrieval": "code_generator",
                "literature_review": "code_generator",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "classification_config",
            self.route_after_configuration,
            {
                "configured": "code_generator",
                "reconfigure": "classification_config",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "code_generator",
            self.route_after_generation,
            {
                "generated": "code_executor",
                "regenerate": "code_generator",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "code_executor",
            self.route_after_execution,
            {
                "success": END,
                "needs_review": "review_loop",
                "regenerate": "code_generator",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "review_loop",
            self.route_after_review,
            {
                "approved": END,
                "needs_improvement": "code_generator",
                "error": END
            }
        )
        
        return workflow
    
    # 路由函数实现
    def route_after_identity_check(self, state: AstroAgentState) -> Literal["amateur", "professional", "error"]:
        """身份检查后的路由"""
        if state.get("error_info"):
            return "error"
        
        user_type = state.get("user_type")
        if user_type == "amateur":
            return "amateur"
        elif user_type == "professional":
            return "professional"
        else:
            return "error"
    
    def route_after_qa(self, state: AstroAgentState) -> Literal["complete", "continue", "error"]:
        """QA问答后的路由"""
        if state.get("error_info"):
            return "error"
        
        if state.get("is_complete", False):
            return "complete"
        elif state.get("needs_followup", False):
            return "continue"
        else:
            return "complete"
    
    def route_after_task_selection(self, state: AstroAgentState) -> Literal["classification", "data_retrieval", "literature_review", "error"]:
        """任务选择后的路由"""
        if state.get("error_info"):
            return "error"
        
        task_type = state.get("task_type")
        if task_type in ["classification", "data_retrieval", "literature_review"]:
            return task_type
        else:
            return "error"
    
    def route_after_configuration(self, state: AstroAgentState) -> Literal["configured", "reconfigure", "error"]:
        """配置完成后的路由"""
        if state.get("error_info"):
            return "error"
        
        config_status = state.get("config_status")
        if config_status == "complete":
            return "configured"
        elif config_status == "needs_revision":
            return "reconfigure"
        else:
            return "error"
    
    def route_after_generation(self, state: AstroAgentState) -> Literal["generated", "regenerate", "error"]:
        """代码生成后的路由"""
        if state.get("error_info"):
            return "error"
        
        generation_status = state.get("generation_status")
        if generation_status == "success":
            return "generated"
        elif generation_status == "retry":
            return "regenerate"
        else:
            return "error"
    
    def route_after_execution(self, state: AstroAgentState) -> Literal["success", "needs_review", "regenerate", "error"]:
        """代码执行后的路由"""
        if state.get("error_info"):
            return "error"
        
        execution_status = state.get("execution_status")
        if execution_status == "success":
            quality_score = state.get("quality_score", 0)
            if quality_score >= 0.8:
                return "success"
            else:
                return "needs_review"
        elif execution_status == "failed":
            retry_count = state.get("retry_count", 0)
            if retry_count < 3:
                return "regenerate"
            else:
                return "error"
        else:
            return "error"
    
    def route_after_review(self, state: AstroAgentState) -> Literal["approved", "needs_improvement", "error"]:
        """审查后的路由"""
        if state.get("error_info"):
            return "error"
        
        review_result = state.get("review_result")
        if review_result == "approved":
            return "approved"
        elif review_result == "needs_improvement":
            return "needs_improvement"
        else:
            return "error"
    
    def compile(self):
        """编译图"""
        return self.graph.compile(checkpointer=self.checkpointer)

# 创建图实例
astro_graph = AstroAgentGraph(checkpointer_type="memory")
app = astro_graph.compile()
```

### 4.2 图执行和调用示例

```python
import asyncio
from typing import Dict, Any

class AstroAgentExecutor:
    """天文科研Agent执行器"""
    
    def __init__(self, app):
        self.app = app
    
    async def run_conversation(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """运行完整的对话流程"""
        # 创建初始状态
        initial_state = create_initial_state(
            user_input=user_input,
            session_id=session_id
        )
        
        # 配置
        config = {
            "configurable": {
                "thread_id": session_id or initial_state["session_id"]
            }
        }
        
        try:
            # 执行图
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            return {
                "success": True,
                "result": final_state,
                "session_id": final_state["session_id"],
                "user_type": final_state.get("user_type"),
                "response": self._extract_response(final_state)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "session_id": initial_state["session_id"]
            }
    
    async def stream_conversation(self, user_input: str, session_id: str = None):
        """流式执行对话"""
        initial_state = create_initial_state(
            user_input=user_input,
            session_id=session_id
        )
        
        config = {
            "configurable": {
                "thread_id": session_id or initial_state["session_id"]
            }
        }
        
        async for event in self.app.astream(initial_state, config=config):
            yield event
    
    def _extract_response(self, state: AstroAgentState) -> str:
        """从最终状态中提取响应"""
        if state.get("user_type") == "amateur":
            return state.get("config_data", {}).get("qa_response", "")
        else:
            # 专业用户的响应可能包含代码执行结果
            execution_result = state.get("execution_result")
            if execution_result:
                return f"任务执行完成。结果：{execution_result.get('summary', '')}"
            else:
                return "任务配置完成，等待执行。"

# 使用示例
executor = AstroAgentExecutor(app)

# 爱好者问答示例
async def amateur_example():
    result = await executor.run_conversation(
        user_input="什么是黑洞？它是如何形成的？",
        session_id="amateur_session_1"
    )
    print(f"爱好者回答: {result['response']}")

# 专业用户工作流示例
async def professional_example():
    result = await executor.run_conversation(
        user_input="我需要对SDSS数据中的星系进行分类，使用机器学习方法分析它们的形态特征",
        session_id="professional_session_1"
    )
    print(f"专业用户结果: {result['response']}")

# 流式执行示例
async def streaming_example():
    async for event in executor.stream_conversation(
        user_input="帮我分析一下仙女座星系的基本特征",
        session_id="stream_session_1"
    ):
        print(f"流式事件: {event}")
```

### 4.3 检查点和状态恢复

```python
class StateManager:
    """状态管理器，支持检查点和恢复"""
    
    def __init__(self, checkpointer):
        self.checkpointer = checkpointer
    
    async def save_checkpoint(self, state: AstroAgentState, config: Dict[str, Any]):
        """保存检查点"""
        await self.checkpointer.aput(config, state)
    
    async def load_checkpoint(self, config: Dict[str, Any]) -> Optional[AstroAgentState]:
        """加载检查点"""
        checkpoint = await self.checkpointer.aget(config)
        return checkpoint.get("state") if checkpoint else None
    
    async def list_checkpoints(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """列出检查点历史"""
        config = {"configurable": {"thread_id": thread_id}}
        checkpoints = []
        
        async for checkpoint in self.checkpointer.alist(config, limit=limit):
            checkpoints.append({
                "checkpoint_id": checkpoint.get("id"),
                "timestamp": checkpoint.get("ts"),
                "state": checkpoint.get("state")
            })
        
        return checkpoints
    
    async def rollback_to_checkpoint(self, thread_id: str, steps_back: int = 1) -> Optional[AstroAgentState]:
        """回滚到指定检查点"""
        checkpoints = await self.list_checkpoints(thread_id, limit=steps_back + 1)
        
        if len(checkpoints) > steps_back:
            target_checkpoint = checkpoints[steps_back]
            return target_checkpoint["state"]
        
        return None
```

## 5. LangGraph测试框架

### 5.1 节点单元测试

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

class NodeTestFramework:
    """LangGraph节点测试框架"""
    
    def __init__(self):
        self.mock_llm = AsyncMock()
        self.mock_knowledge_base = AsyncMock()
        self.test_results = []
    
    async def test_identity_check_node(self):
        """测试身份识别节点"""
        # 测试爱好者识别
        amateur_state = {
            "user_input": "什么是黑洞？",
            "config_data": {"user_input": "什么是黑洞？"},
            "execution_history": []
        }
        
        self.mock_llm.generate.return_value = "amateur"
        result = await identity_check_node(amateur_state)
        
        assert result["user_type"] == "amateur"
        assert result["current_step"] == "identity_checked"
        
        # 测试专业用户识别
        professional_state = {
            "user_input": "我需要对SDSS数据进行星系分类分析",
            "config_data": {"user_input": "我需要对SDSS数据进行星系分类分析"},
            "execution_history": []
        }
        
        self.mock_llm.generate.return_value = "professional"
        result = await identity_check_node(professional_state)
        
        assert result["user_type"] == "professional"
        assert result["current_step"] == "identity_checked"
        
        return True
    
    async def test_qa_agent_node(self):
        """测试QA问答节点"""
        test_state = {
            "user_type": "amateur",
            "user_input": "什么是黑洞？",
            "config_data": {"user_input": "什么是黑洞？"},
            "execution_history": []
        }
        
        self.mock_llm.generate.return_value = "黑洞是一种极其致密的天体..."
        self.mock_knowledge_base.search.return_value = [
            {"content": "黑洞相关知识"}
        ]
        
        result = await qa_agent_node(test_state)
        
        assert "qa_response" in result["config_data"]
        assert result["current_step"] == "qa_completed"
        assert result["is_complete"] == True
        
        return True
    
    async def test_task_selector_node(self):
        """测试任务选择节点"""
        test_state = {
            "user_type": "professional",
            "user_input": "我需要对星系进行分类",
            "config_data": {"user_input": "我需要对星系进行分类"},
            "execution_history": []
        }
        
        self.mock_llm.generate.return_value = "classification"
        
        result = await task_selector_node(test_state)
        
        assert result["task_type"] == "classification"
        assert result["current_step"] == "task_selected"
        
        return True
    
    async def test_code_generator_node(self):
        """测试代码生成节点"""
        test_state = {
            "task_type": "classification",
            "config_data": {
                "data_source": "SDSS",
                "features": ["u-g", "g-r", "r-i"],
                "algorithm": "random_forest"
            },
            "execution_history": []
        }
        
        mock_code = """
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# 加载SDSS数据
data = pd.read_csv('sdss_data.csv')
# 特征工程和模型训练代码...
"""
        
        self.mock_llm.generate.return_value = mock_code
        
        result = await code_generator_node(test_state)
        
        assert "generated_code" in result
        assert result["generation_status"] == "success"
        assert result["current_step"] == "code_generated"
        
        return True
    
    async def run_all_node_tests(self) -> Dict[str, Any]:
        """运行所有节点测试"""
        test_methods = [
            self.test_identity_check_node,
            self.test_qa_agent_node,
            self.test_task_selector_node,
            self.test_code_generator_node
        ]
        
        results = {}
        for test_method in test_methods:
            try:
                result = await test_method()
                results[test_method.__name__] = {
                    "success": result,
                    "error": None
                }
            except Exception as e:
                results[test_method.__name__] = {
                    "success": False,
                    "error": str(e)
                }
        
        success_count = sum(1 for r in results.values() if r["success"])
        total_count = len(results)
        
        return {
            "total_tests": total_count,
            "successful_tests": success_count,
            "success_rate": success_count / total_count,
            "detailed_results": results
        }

# pytest测试用例
@pytest.mark.asyncio
async def test_identity_check_node_amateur():
    """测试身份识别节点 - 爱好者"""
    framework = NodeTestFramework()
    result = await framework.test_identity_check_node()
    assert result == True

@pytest.mark.asyncio
async def test_qa_agent_node_response():
    """测试QA节点响应"""
    framework = NodeTestFramework()
    result = await framework.test_qa_agent_node()
    assert result == True
```

### 5.2 图执行测试

```python
class GraphIntegrationTest:
    """图集成测试"""
    
    def __init__(self, app):
        self.app = app
        self.test_scenarios = []
    
    async def test_amateur_workflow(self):
        """测试爱好者工作流"""
        initial_state = create_initial_state(
            user_input="什么是超新星？它们是如何爆炸的？",
            session_id="test_amateur_session"
        )
        
        config = {
            "configurable": {
                "thread_id": "test_amateur_session"
            }
        }
        
        try:
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            # 验证爱好者工作流
            assert final_state["user_type"] == "amateur"
            assert "qa_response" in final_state["config_data"]
            assert final_state["is_complete"] == True
            
            return {
                "success": True,
                "workflow": "amateur",
                "final_state": final_state
            }
            
        except Exception as e:
            return {
                "success": False,
                "workflow": "amateur",
                "error": str(e)
            }
    
    async def test_professional_workflow(self):
        """测试专业用户工作流"""
        initial_state = create_initial_state(
            user_input="我需要使用机器学习对Gaia DR3数据中的恒星进行光谱分类",
            session_id="test_professional_session"
        )
        
        config = {
            "configurable": {
                "thread_id": "test_professional_session"
            }
        }
        
        try:
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            # 验证专业用户工作流
            assert final_state["user_type"] == "professional"
            assert final_state["task_type"] in ["classification", "data_retrieval", "literature_review"]
            
            # 检查是否生成了代码
            if "generated_code" in final_state:
                assert len(final_state["generated_code"]) > 0
            
            return {
                "success": True,
                "workflow": "professional",
                "final_state": final_state
            }
            
        except Exception as e:
            return {
                "success": False,
                "workflow": "professional",
                "error": str(e)
            }
    
    async def test_error_recovery(self):
        """测试错误恢复机制"""
        # 创建一个会导致错误的状态
        initial_state = {
            "user_input": "",  # 空输入应该触发错误
            "config_data": {},
            "execution_history": [],
            "session_id": "test_error_session"
        }
        
        config = {
            "configurable": {
                "thread_id": "test_error_session"
            }
        }
        
        try:
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            # 验证错误处理
            if "error_info" in final_state:
                assert "error_type" in final_state["error_info"]
                assert "error_message" in final_state["error_info"]
            
            return {
                "success": True,
                "test_type": "error_recovery",
                "error_handled": "error_info" in final_state
            }
            
        except Exception as e:
            return {
                "success": False,
                "test_type": "error_recovery",
                "error": str(e)
            }
    
    async def run_integration_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        test_methods = [
            self.test_amateur_workflow,
            self.test_professional_workflow,
            self.test_error_recovery
        ]
        
        results = []
        for test_method in test_methods:
            result = await test_method()
            results.append(result)
        
        success_count = sum(1 for r in results if r["success"])
        total_count = len(results)
        
        return {
            "total_tests": total_count,
            "successful_tests": success_count,
            "success_rate": success_count / total_count,
            "detailed_results": results
        }
```

### 5.3 性能评估指标

```python
import time
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    execution_time: float
    node_count: int
    memory_usage: float
    success_rate: float
    error_count: int
    throughput: float  # 每秒处理的请求数

class PerformanceEvaluator:
    """性能评估器"""
    
    def __init__(self, app):
        self.app = app
        self.metrics_history = []
    
    async def measure_single_execution(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """测量单次执行的性能"""
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        initial_state = create_initial_state(
            user_input=user_input,
            session_id=session_id or f"perf_test_{int(time.time())}"
        )
        
        config = {
            "configurable": {
                "thread_id": initial_state["session_id"]
            }
        }
        
        try:
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            end_time = time.time()
            end_memory = self._get_memory_usage()
            
            execution_time = end_time - start_time
            memory_delta = end_memory - start_memory
            node_count = len(final_state.get("execution_history", []))
            
            return {
                "success": True,
                "execution_time": execution_time,
                "memory_delta": memory_delta,
                "node_count": node_count,
                "final_state": final_state
            }
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            
            return {
                "success": False,
                "execution_time": execution_time,
                "error": str(e)
            }
    
    async def measure_concurrent_execution(self, test_cases: List[str], concurrency: int = 5) -> PerformanceMetrics:
        """测量并发执行性能"""
        start_time = time.time()
        
        # 创建并发任务
        tasks = []
        for i, user_input in enumerate(test_cases):
            task = self.measure_single_execution(user_input, f"concurrent_test_{i}")
            tasks.append(task)
        
        # 分批执行以控制并发数
        results = []
        for i in range(0, len(tasks), concurrency):
            batch = tasks[i:i + concurrency]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 计算指标
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success", False)]
        error_count = len(results) - len(successful_results)
        
        if successful_results:
            avg_execution_time = sum(r["execution_time"] for r in successful_results) / len(successful_results)
            avg_node_count = sum(r["node_count"] for r in successful_results) / len(successful_results)
            avg_memory_usage = sum(r.get("memory_delta", 0) for r in successful_results) / len(successful_results)
        else:
            avg_execution_time = 0
            avg_node_count = 0
            avg_memory_usage = 0
        
        success_rate = len(successful_results) / len(results)
        throughput = len(results) / total_time
        
        metrics = PerformanceMetrics(
            execution_time=avg_execution_time,
            node_count=avg_node_count,
            memory_usage=avg_memory_usage,
            success_rate=success_rate,
            error_count=error_count,
            throughput=throughput
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # 转换为MB
    
    async def run_performance_benchmark(self) -> Dict[str, Any]:
        """运行性能基准测试"""
        test_cases = [
            "什么是黑洞？",  # 爱好者问答
            "我需要对SDSS数据进行星系分类",  # 专业用户分类
            "帮我检索关于系外行星的最新文献",  # 文献检索
            "分析Gaia DR3中的恒星运动学数据",  # 数据分析
            "超新星爆炸的物理机制是什么？"  # 科普问答
        ]
        
        # 单次执行测试
        single_results = []
        for test_case in test_cases:
            result = await self.measure_single_execution(test_case)
            single_results.append(result)
        
        # 并发执行测试
        concurrent_metrics = await self.measure_concurrent_execution(test_cases * 4, concurrency=3)
        
        # 生成报告
        successful_single = [r for r in single_results if r["success"]]
        
        return {
            "single_execution": {
                "total_tests": len(single_results),
                "successful_tests": len(successful_single),
                "average_execution_time": sum(r["execution_time"] for r in successful_single) / len(successful_single) if successful_single else 0,
                "detailed_results": single_results
            },
            "concurrent_execution": {
                "metrics": concurrent_metrics,
                "throughput_per_second": concurrent_metrics.throughput,
                "success_rate": concurrent_metrics.success_rate
            },
            "recommendations": self._generate_performance_recommendations(concurrent_metrics)
        }
    
    def _generate_performance_recommendations(self, metrics: PerformanceMetrics) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        if metrics.execution_time > 10.0:
            recommendations.append("考虑优化LLM调用次数或使用更快的模型")
        
        if metrics.memory_usage > 500:  # 500MB
            recommendations.append("考虑实现状态压缩或清理机制")
        
        if metrics.success_rate < 0.9:
            recommendations.append("需要改进错误处理和恢复机制")
        
        if metrics.throughput < 0.5:  # 每秒少于0.5个请求
            recommendations.append("考虑增加并发处理能力或优化图执行路径")
        
        if not recommendations:
            recommendations.append("性能表现良好，无需特别优化")
        
        return recommendations

# 使用示例
async def run_performance_tests():
    evaluator = PerformanceEvaluator(app)
    benchmark_results = await evaluator.run_performance_benchmark()
    
    print("性能基准测试结果:")
    print(f"单次执行平均时间: {benchmark_results['single_execution']['average_execution_time']:.2f}秒")
    print(f"并发吞吐量: {benchmark_results['concurrent_execution']['throughput_per_second']:.2f}请求/秒")
    print(f"成功率: {benchmark_results['concurrent_execution']['success_rate']:.2%}")
    print("优化建议:")
    for rec in benchmark_results['recommendations']:
        print(f"- {rec}")
```

## 7. 数据模型

### 7.1 数据模型定义

```mermaid
erDiagram
    USER ||--o{ SESSION : creates
    SESSION ||--o{ MESSAGE : contains
    SESSION ||--o{ TASK_CONFIG : has
    TASK_CONFIG ||--o{ CODE_EXECUTION : generates
    CODE_EXECUTION ||--o{ RESULT : produces
    
    USER {
        uuid id PK
        string email
        string user_type
        timestamp created_at
        timestamp updated_at
    }
    
    SESSION {
        uuid id PK
        uuid user_id FK
        string status
        json context
        timestamp created_at
        timestamp updated_at
    }
    
    MESSAGE {
        uuid id PK
        uuid session_id FK
        string role
        text content
        json metadata
        timestamp created_at
    }
    
    TASK_CONFIG {
        uuid id PK
        uuid session_id FK
        string task_type
        json config_data
        string status
        timestamp created_at
    }
    
    CODE_EXECUTION {
        uuid id PK
        uuid config_id FK
        text generated_code
        string status
        text output
        text error_log
        timestamp started_at
        timestamp completed_at
    }
    
    RESULT {
        uuid id PK
        uuid execution_id FK
        string result_type
        string file_path
        json metadata
        timestamp created_at
    }
```

### 6.2 数据定义语言

**用户表 (users)**

```sql
-- 创建用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    user_type VARCHAR(20) CHECK (user_type IN ('professional', 'amateur')),
    preferences JSON DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_type ON users(user_type);
```

**会话表 (sessions)**

```sql
-- 创建会话表
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired')),
    context JSON DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);
```

**消息表 (messages)**

```sql
-- 创建消息表
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
```

**任务配置表 (task\_configs)**

```sql
-- 创建任务配置表
CREATE TABLE task_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    task_type VARCHAR(50) CHECK (task_type IN ('classification', 'data_retrieval', 'literature_review')),
    config_data JSON NOT NULL,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed', 'executed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_task_configs_session_id ON task_configs(session_id);
CREATE INDEX idx_task_configs_type ON task_configs(task_type);
```

**代码执行表 (code\_executions)**

```sql
-- 创建代码执行表
CREATE TABLE code_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID REFERENCES task_configs(id) ON DELETE CASCADE,
    generated_code TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    output TEXT,
    error_log TEXT,
    version INTEGER DEFAULT 1,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_code_executions_config_id ON code_executions(config_id);
CREATE INDEX idx_code_executions_status ON code_executions(status);
CREATE INDEX idx_code_executions_version ON code_executions(config_id, version DESC);
```

**结果表 (results)**

```sql
-- 创建结果表
CREATE TABLE results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID REFERENCES code_executions(id) ON DELETE CASCADE,
    result_type VARCHAR(50) CHECK (result_type IN ('csv', 'json', 'image', 'report')),
    file_path VARCHAR(500),
    file_size BIGINT,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_results_execution_id ON results(execution_id);
CREATE INDEX idx_results_type ON results(result_type);
```

**初始化数据**

```sql
-- 插入示例用户
INSERT INTO users (email, user_type) VALUES 
('researcher@example.com', 'professional'),
('student@example.com', 'amateur');

-- 插入系统配置
INSERT INTO task_configs (session_id, task_type, config_data, status) VALUES 
(gen_random_uuid(), 'classification', '{"default_data_source": "SDSS", "supported_objects": ["galaxy", "star", "quasar"]}', 'confirmed');
```

