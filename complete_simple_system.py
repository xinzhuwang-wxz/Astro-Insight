#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整功能的天文科研系统 - 简化版
包含所有原始功能，但绕过LangGraph的复杂状态管理
"""

import sys
import os
sys.path.insert(0, 'src')

from utils.error_handler import handle_error, create_error_context, AstroError, ErrorCode, ErrorSeverity
from utils.state_manager import format_state_output, validate_state, create_initial_state
from database.local_storage import LocalDatabase, CelestialObject, ClassificationResult
from tools.language_processor import language_processor
from llms.llm import get_llm_by_type
from prompts.template import get_prompt
from core.container import DIContainer, configure_default_services
from core.interfaces import UserType, TaskType
import time
import json
import uuid
from typing import Dict, Any, List, Optional

# 导入Tavily搜索
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    print("Warning: Tavily not available, using mock search")

# 导入配置加载
from config.loader import load_yaml_config

class CompleteSimpleAstroSystem:
    """完整功能的天文科研系统 - 简化版"""
    
    def __init__(self):
        # 加载配置文件
        try:
            self.config = load_yaml_config()
            print("✅ 配置文件加载成功")
        except Exception as e:
            print(f"Warning: 配置文件加载失败，使用默认配置: {e}")
            self.config = {
                "llm": {"api_key": "test_key", "model": "test_model"},
                "debug": True,
                "database": {"path": "astro_data.db"},
                "cache": {"max_size": 1000, "ttl": 3600}
            }
        
        # 初始化数据库
        self.db = LocalDatabase()
        
        # 初始化LLM
        try:
            self.llm = get_llm_by_type("basic")
            print("✅ LLM初始化成功")
        except Exception as e:
            print(f"Warning: Failed to initialize LLM: {e}")
            self.llm = None
        
        # 初始化Tavily搜索
        self.tavily_client = None
        if TAVILY_AVAILABLE and self.config.get("SEARCH_API", {}).get("api_key"):
            try:
                self.tavily_client = TavilyClient(
                    api_key=self.config["SEARCH_API"]["api_key"]
                )
                print("✅ Tavily搜索初始化成功")
            except Exception as e:
                print(f"Warning: Tavily搜索初始化失败: {e}")
        
        # 初始化依赖注入容器
        self.container = DIContainer()
        configure_default_services(self.container)
        
        # 初始化缓存
        self.cache = {}
        
        # 初始化对话历史存储
        self.conversation_history = {}  # {session_id: [{"role": "user/assistant", "content": "...", "timestamp": ...}]}
        
        print("✅ 完整功能系统初始化完成")
    
    def process_query(self, session_id: str, user_input: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """处理用户查询 - 支持多步对话"""
        try:
            # 初始化或获取对话历史
            if session_id not in self.conversation_history:
                self.conversation_history[session_id] = []
            
            # 添加用户输入到历史
            self.conversation_history[session_id].append({
                "role": "user",
                "content": user_input,
                "timestamp": time.time()
            })
            
            # 创建初始状态
            state = create_initial_state(session_id, user_input)
            
            # 1. 身份识别
            user_type = self._identify_user_type(user_input)
            state["user_type"] = user_type
            state["current_step"] = "identity_checked"
            state["identity_completed"] = True
            
            # 2. 任务分类 - 考虑对话上下文
            task_type = self._classify_task_with_context(user_input, user_type, session_id)
            state["task_type"] = task_type
            
            # 3. 根据任务类型处理
            if task_type == "qa":
                result = self._handle_qa_query_with_context(user_input, user_type, state, session_id)
                state.update(result)
                state["current_step"] = "qa_completed"
                
            elif task_type == "classification":
                result = self._handle_classification_query(user_input, user_type, state)
                state.update(result)
                state["current_step"] = "classification_completed"
                
            elif task_type == "data_retrieval":
                result = self._handle_data_retrieval_query(user_input, user_type, state)
                state.update(result)
                state["current_step"] = "data_retrieved"
                
            elif task_type == "literature_review":
                result = self._handle_literature_review_query(user_input, user_type, state)
                state.update(result)
                state["current_step"] = "literature_reviewed"
                
            elif task_type == "code_generation":
                result = self._handle_code_generation_query(user_input, user_type, state)
                state.update(result)
                state["current_step"] = "code_generated"
                
            else:
                result = self._handle_general_query(user_input, user_type, state)
                state.update(result)
                state["current_step"] = "general_completed"
            
            state["is_complete"] = True
            
            # 记录查询历史
            self._record_query_history(session_id, user_input, state)
            
            return state
            
        except Exception as e:
            error_context = create_error_context(session_id=session_id)
            error_info = handle_error(e, error_context, reraise=False)
            state["error_info"] = error_info
            state["current_step"] = "error"
            return state
    
    def _identify_user_type(self, user_input: str) -> str:
        """身份识别 - 完整版本"""
        # 使用依赖注入的用户服务
        try:
            from core.interfaces import IUserService
            user_service = self.container.get(IUserService)
            user_type = user_service.identify_user_type(user_input)
            return user_type.value if hasattr(user_type, 'value') else str(user_type)
        except Exception as e:
            print(f"User service failed, using fallback: {e}")
        
        # 规则识别
        professional_keywords = [
            "分析", "数据", "代码", "编程", "算法", "分类", 
            "处理", "计算", "研究", "生成代码", "写代码",
            "professional", "专业", "开发", "脚本", "SDSS",
            "天体", "星系", "恒星", "行星", "黑洞", "脉冲星",
            "检索", "查询", "数据库", "API", "接口"
        ]
        
        if any(kw in user_input.lower() for kw in professional_keywords):
            return "professional"
        else:
            return "amateur"
    
    def _classify_task(self, user_input: str, user_type: str) -> str:
        """任务分类 - 完整版本"""
        # 使用依赖注入的任务服务
        try:
            from core.interfaces import ITaskService
            task_service = self.container.get(ITaskService)
            task_type = task_service.classify_task(user_input, user_type)
            return task_type.value if hasattr(task_type, 'value') else str(task_type)
        except Exception as e:
            print(f"Task service failed, using fallback: {e}")
        
        # 规则分类 - 只检查明确指向分类任务的关键词
        classification_keywords = [
            "分类", "classify", "什么类型", "天体类型", "天体分类", "属于什么", "属于哪类"
        ]
        
        # 优先检查是否包含分类关键词
        if any(keyword in user_input for keyword in classification_keywords):
            return "classification"
        elif "数据" in user_input or "检索" in user_input or "data" in user_input.lower():
            return "data_retrieval"
        elif "文献" in user_input or "literature" in user_input.lower():
            return "literature_review"
        elif "代码" in user_input or "code" in user_input.lower():
            return "code_generation"
        else:
            return "qa"
    
    def _is_solar_system_object(self, celestial_name: str) -> bool:
        """判断是否为太阳系天体"""
        solar_system_objects = [
            "水星", "金星", "地球", "火星", "木星", "土星", "天王星", "海王星",
            "冥王星", "谷神星", "阋神星", "妊神星", "鸟神星",
            "mercury", "venus", "earth", "mars", "jupiter", "saturn", 
            "uranus", "neptune", "pluto", "ceres", "eris", "haumea", "makemake",
            "太阳", "月亮", "月球", "sun", "moon", "luna"
        ]
        
        name_lower = celestial_name.lower()
        return any(obj in name_lower for obj in solar_system_objects)
    
    def _handle_solar_system_classification(self, celestial_name: str, user_input: str) -> Dict[str, Any]:
        """处理太阳系天体分类"""
        # 太阳系天体分类信息
        solar_system_info = {
            "水星": {"type": "行星", "classification": "terrestrial_planet", "distance": "0.39 AU", "description": "最靠近太阳的行星，表面温度极高"},
            "金星": {"type": "行星", "classification": "terrestrial_planet", "distance": "0.72 AU", "description": "最亮的行星，有浓厚的大气层"},
            "地球": {"type": "行星", "classification": "terrestrial_planet", "distance": "1.00 AU", "description": "我们的家园，唯一已知有生命的行星"},
            "火星": {"type": "行星", "classification": "terrestrial_planet", "distance": "1.52 AU", "description": "红色行星，有极地冰冠和季节变化"},
            "木星": {"type": "行星", "classification": "gas_giant", "distance": "5.20 AU", "description": "太阳系最大的行星，有著名的大红斑"},
            "土星": {"type": "行星", "classification": "gas_giant", "distance": "9.58 AU", "description": "有美丽光环的气态巨行星"},
            "天王星": {"type": "行星", "classification": "ice_giant", "distance": "19.22 AU", "description": "侧躺着运行的行星，有微弱的光环"},
            "海王星": {"type": "行星", "classification": "ice_giant", "distance": "30.05 AU", "description": "太阳系最远的行星，有强烈的风暴"},
            "冥王星": {"type": "矮行星", "classification": "dwarf_planet", "distance": "39.48 AU", "description": "曾经的第九行星，现为矮行星"},
            "太阳": {"type": "恒星", "classification": "G-type_main_sequence", "distance": "0 AU", "description": "太阳系的中心，G型主序星"},
            "月亮": {"type": "卫星", "classification": "natural_satellite", "distance": "384,400 km", "description": "地球的天然卫星，影响潮汐"},
            "月球": {"type": "卫星", "classification": "natural_satellite", "distance": "384,400 km", "description": "地球的天然卫星，影响潮汐"}
        }
        
        # 查找天体信息
        info = None
        for name, data in solar_system_info.items():
            if name in celestial_name or celestial_name.lower() in data.get("english_name", "").lower():
                info = data
                break
        
        if not info:
            # 尝试英文名称匹配
            english_names = {
                "mercury": "水星", "venus": "金星", "earth": "地球", "mars": "火星",
                "jupiter": "木星", "saturn": "土星", "uranus": "天王星", "neptune": "海王星",
                "pluto": "冥王星", "sun": "太阳", "moon": "月亮"
            }
            
            for eng_name, chn_name in english_names.items():
                if eng_name in celestial_name.lower():
                    info = solar_system_info[chn_name]
                    break
        
        if info:
            # 构建简化的太阳系天体回答（不显示层级）
            answer_parts = [
                f"天体分类完成：{celestial_name}",
                f"天体类型：{info['type']} ({info['classification']})",
                f"特征：{info['description']}",
                f"距离：{info['distance']}"
            ]
            
            # 添加同类天体示例
            if info['classification'] == 'terrestrial_planet':
                answer_parts.append(f"同类天体：水星、金星、地球、火星")
            elif info['classification'] == 'gas_giant':
                answer_parts.append(f"同类天体：木星、土星")
            elif info['classification'] == 'ice_giant':
                answer_parts.append(f"同类天体：天王星、海王星")
            
            final_answer = "\n".join(answer_parts)
            final_answer += "\n\n[🌍 太阳系天体 - 专业分类]"
            
            return {
                "classification_result": {
                    "found": True,
                    "object_type": info['type'],
                    "classification": info['classification'],
                    "source": "Solar System Database"
                },
                "final_answer": final_answer,
                "response": final_answer
            }
        else:
            return {
                "classification_result": {"found": False, "error": "Unknown solar system object"},
                "final_answer": f"天体分类完成：{celestial_name} 被分类为 unknown\n\n[⚠️ 降级处理 - 规则分类]",
                "response": f"天体分类完成：{celestial_name} 被分类为 unknown"
            }
    
    def _extract_celestial_name(self, user_input: str) -> str:
        """从用户输入中提取天体名称"""
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
        # 对于简单的中文天体名称，直接返回清理后的输入
        result = clean_input.strip()
        return result if result else user_input
    
    def _translate_celestial_name(self, celestial_name: str) -> str:
        """使用大模型智能翻译天体名称"""
        try:
            # 检查是否为中文或需要转换的名称
            is_chinese = any('\u4e00' <= char <= '\u9fff' for char in celestial_name)
            
            # 如果已经是英文标准格式，直接返回
            if not is_chinese and self._is_standard_english_name(celestial_name):
                return celestial_name
            
            # 使用大模型进行智能转换
            if self.llm:
                prompt = f"""请将以下天体名称转换为Simbad数据库可以识别的标准英文名称。

输入名称: {celestial_name}

请只返回最可能的英文名称，不要解释。如果无法确定，请返回原名称。

示例:
- 太阳 -> Sun
- 天狼星 -> Sirius
- 仙女座星系 -> Andromeda Galaxy
- 蟹状星云 -> Crab Nebula
- 银河系中心黑洞 -> Sgr A*
- 猎户座大星云 -> Orion Nebula
- 昴宿星团 -> Pleiades
- 参宿四 -> Betelgeuse
- 心宿二 -> Antares
- 人马座A* -> Sgr A*
- 半人马座阿尔法星 -> Alpha Centauri

标准英文名称:"""
                
                response = self.llm.invoke(prompt)
                translated_name = response.content.strip()
                
                # 验证转换结果
                if translated_name and translated_name != celestial_name:
                    print(f"大模型转换: {celestial_name} -> {translated_name}")
                    return translated_name
            
            return celestial_name
            
        except Exception as e:
            print(f"天体名称转换失败: {e}")
            return celestial_name
    
    def _is_standard_english_name(self, name: str) -> bool:
        """检查是否为标准英文天体名称"""
        import re
        
        # 检查常见的天体命名模式
        patterns = [
            r'^M\d+$',  # 梅西耶天体
            r'^NGC\s*\d+$',  # NGC天体
            r'^IC\s*\d+$',  # IC天体
            r'^HD\s*\d+$',  # HD星表
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',  # 星座+天体名
            r'^[A-Z][a-z]+\s+Nebula$',  # 星云
            r'^[A-Z][a-z]+\s+Galaxy$',  # 星系
            r'^[A-Z][a-z]+\s+Cluster$',  # 星团
            r'^[A-Z][a-z]+$',  # 单一天体名
            r'^Sgr\s+A\*$',  # 人马座A*
            r'^Alpha\s+Centauri$',  # 半人马座阿尔法星
        ]
        
        for pattern in patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return True
        
        return False
    
    def _get_classification_explanation(self, object_type: str, classification: str) -> str:
        """获取天体分类的中文解释和同类天体 - 动态层级化显示"""
        explanations = {
            "Radio Galaxy": {
                "chinese": "射电星系",
                "description": "具有强烈射电辐射的星系，通常中心有超大质量黑洞",
                "examples": "M87、半人马座A、天鹅座A"
            },
            "Sy2": {
                "chinese": "赛弗特星系2型",
                "description": "活动星系核的一种，具有窄发射线，中心有活跃的超大质量黑洞",
                "examples": "NGC 1068、NGC 4151、NGC 4945"
            },
            "HII Region": {
                "chinese": "HII区（电离氢区）",
                "description": "由年轻恒星电离周围氢气形成的发光区域",
                "examples": "猎户座大星云、鹰状星云、三叶星云"
            },
            "SNR": {
                "chinese": "超新星遗迹",
                "description": "超新星爆发后留下的膨胀气体壳层",
                "examples": "蟹状星云、仙后座A、天鹅座环"
            },
            "Star": {
                "chinese": "恒星",
                "description": "通过核聚变产生能量的发光天体",
                "examples": "太阳、天狼星、织女星"
            },
            "SB*": {
                "chinese": "分光双星",
                "description": "通过光谱分析才能识别的双星系统",
                "examples": "天狼星、大陵五、角宿一"
            },
            "**": {
                "chinese": "双星系统",
                "description": "两颗恒星相互绕转的恒星系统",
                "examples": "半人马座α、天狼星、大陵五"
            },
            "X": {
                "chinese": "X射线源",
                "description": "发射强烈X射线的天体，通常是黑洞或中子星",
                "examples": "人马座A*、天鹅座X-1、V404天鹅座"
            }
        }
        
        # 查找匹配的解释
        info = None
        for key, data in explanations.items():
            if key in object_type or key == classification:
                info = data
                break
        
        if info:
            # 动态生成层级结构
            hierarchy = self._generate_hierarchy_structure(object_type, classification)
            hierarchy_text = "\n".join(hierarchy)
            return f"{hierarchy_text}\n\n天体类型：{object_type} ({info['chinese']})\n特征：{info['description']}\n同类天体：{info['examples']}"
        
        # 如果没有找到，返回通用解释
        hierarchy = self._generate_hierarchy_structure(object_type, classification)
        hierarchy_text = "\n".join(hierarchy)
        return f"{hierarchy_text}\n\n天体类型：{object_type}\n特征：{object_type}是天文观测中常见的天体类型"
    
    def _generate_hierarchy_structure(self, object_type: str, classification: str) -> List[str]:
        """动态生成层级结构"""
        hierarchy = ["分类层级："]
        
        # 根据分类动态构建层级
        if "galaxy" in classification.lower() or "galaxy" in object_type.lower():
            if "radio" in classification.lower() or "radio" in object_type.lower():
                hierarchy.extend([
                    "  └── 宇宙结构",
                    "      └── 星系团",
                    "          └── 星系",
                    "              └── 椭圆星系",
                    "                  └── 射电星系"
                ])
            elif "sy" in classification.lower() or "seyfert" in object_type.lower():
                hierarchy.extend([
                    "  └── 宇宙结构",
                    "      └── 星系团",
                    "          └── 星系",
                    "              └── 活动星系核",
                    "                  └── 赛弗特星系"
                ])
            else:
                hierarchy.extend([
                    "  └── 宇宙结构",
                    "      └── 星系团",
                    "          └── 星系"
                ])
        elif "star" in classification.lower() or "star" in object_type.lower() or "sb" in object_type.lower() or "**" in object_type:
            if "binary" in classification.lower() or "**" in object_type or "sb" in object_type.lower():
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 恒星",
                    "          └── 双星系统"
                ])
                if "sb" in object_type.lower():
                    hierarchy.append("              └── 分光双星")
            else:
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 恒星"
                ])
        elif "nebula" in classification.lower() or "nebula" in object_type.lower():
            if "snr" in object_type.lower() or "supernova" in classification.lower():
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 星云",
                    "          └── 超新星遗迹"
                ])
            elif "hii" in object_type.lower() or "ionized" in classification.lower():
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 星云",
                    "          └── 电离氢区"
                ])
            else:
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 星云"
                ])
        elif "cluster" in classification.lower() or "cluster" in object_type.lower():
            if "globular" in classification.lower() or "glc" in object_type.lower():
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 球状星团"
                ])
            elif "open" in classification.lower() or "opc" in object_type.lower():
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 疏散星团"
                ])
            else:
                hierarchy.extend([
                    "  └── 银河系",
                    "      └── 星团"
                ])
        elif "x" in object_type.lower() or "x-ray" in classification.lower():
            hierarchy.extend([
                "  └── 银河系",
                "      └── 致密天体",
                "          └── X射线源"
            ])
        else:
            # 默认层级
            hierarchy.extend([
                "  └── 宇宙结构",
                "      └── 天体"
            ])
        
        return hierarchy
    
    def _generate_solar_system_hierarchy(self, classification: str) -> List[str]:
        """动态生成太阳系层级结构"""
        hierarchy = ["分类层级："]
        
        if classification == 'terrestrial_planet':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 行星",
                "          └── 类地行星"
            ])
        elif classification == 'gas_giant':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 行星",
                "          └── 气态巨行星"
            ])
        elif classification == 'ice_giant':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 行星",
                "          └── 冰巨星"
            ])
        elif classification == 'dwarf_planet':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 矮行星"
            ])
        elif classification == 'G-type_main_sequence':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 恒星"
            ])
        elif classification == 'natural_satellite':
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 卫星",
                "          └── 天然卫星"
            ])
        else:
            hierarchy.extend([
                "  └── 太阳系",
                "      └── 天体"
            ])
        
        return hierarchy
    
    def _handle_qa_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理问答查询 - 完整版本"""
        # 使用LLM进行问答
        if self.llm:
            try:
                # 直接使用简单的prompt，确保Qwen模型能正确理解
                simple_prompt = f"""你是一个专业的天文科普助手。请根据用户类型回答以下天文问题：

用户类型：{user_type}
用户问题：{user_input}

请提供准确、简洁的天文知识回答。对于简单问候，请简短回应并引导到天文话题。"""
                
                response = self.llm.invoke(simple_prompt)
                qa_response = response.content
                # 标注为AI回答
                final_answer = f"{qa_response}\n\n[🤖 AI回答 - Qwen 2.5:7b (Ollama)]"
            except Exception as e:
                print(f"LLM QA failed, using template: {e}")
                qa_response = self._get_template_qa_response(user_input, user_type)
                final_answer = f"{qa_response}\n\n[⚠️ 模拟回答 - LLM服务不可用]"
        else:
            qa_response = self._get_template_qa_response(user_input, user_type)
            final_answer = f"{qa_response}\n\n[⚠️ 模拟回答 - LLM服务未配置]"
        
        return {
            "qa_response": qa_response,
            "final_answer": final_answer,
            "qa_completed": True
        }
    
    def _handle_classification_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理天体分类查询 - 完整版本"""
        try:
            # 使用Simbad进行真实分类
            from src.tools.simbad_client import SimbadClient
            simbad_client = SimbadClient()
            
            # 从用户输入中提取天体名称
            celestial_name = self._extract_celestial_name(user_input)
            
            # 检查是否为太阳系天体
            if self._is_solar_system_object(celestial_name):
                return self._handle_solar_system_classification(celestial_name, user_input)
            
            # 翻译天体名称为Simbad可识别的格式
            translated_name = self._translate_celestial_name(celestial_name)
            
            # 查询Simbad
            simbad_result = simbad_client.search_object(translated_name)
            
            if simbad_result.get("found"):
                # 构建分类结果
                classification_result = {
                    "object_name": celestial_name,
                    "object_type": simbad_result.get("object_type", "unknown"),
                    "classification": simbad_result.get("classification", "unknown"),
                    "coordinates": simbad_result.get("coordinates"),
                    "magnitude": simbad_result.get("magnitude"),
                    "source": "Simbad",
                    "confidence": 0.95  # Simbad数据可信度很高
                }
                
                # 保存到数据库（如果数据库支持）
                try:
                    if self.db and hasattr(self.db, 'save_celestial_object'):
                        self.db.save_celestial_object(classification_result)
                except Exception as e:
                    print(f"数据库保存失败: {e}")
                
                # 生成详细回答
                answer_parts = [
                    f"天体分类完成：{celestial_name}",
                    f"天体类型：{classification_result['object_type']}",
                    f"分类：{classification_result['classification']}"
                ]
                
                # 添加中文解释和同类天体
                explanation = self._get_classification_explanation(
                    classification_result['object_type'], 
                    classification_result['classification']
                )
                if explanation:
                    answer_parts.append(f"\n{explanation}")
                
                if classification_result.get("coordinates"):
                    answer_parts.append(f"\n坐标：{classification_result['coordinates']}")
                
                if classification_result.get("magnitude"):
                    answer_parts.append(f"星等：{classification_result['magnitude']}")
                
                final_answer = "\n".join(answer_parts) + "\n\n[🔍 真实分类 - Simbad数据库]"
                
                return {
                    "classification_result": classification_result,
                    "final_answer": final_answer
                }
            else:
                # Simbad未找到，使用降级处理
                print(f"Simbad未找到天体 {celestial_name}，使用降级处理")
                return self._fallback_classification(user_input, state)
            
        except Exception as e:
            print(f"Simbad分类失败，使用降级处理: {e}")
            return self._fallback_classification(user_input, state)
    
    def _handle_data_retrieval_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据检索查询 - 完整版本"""
        try:
            # 使用依赖注入的数据检索服务
            from core.interfaces import IDataRetrievalService
            retrieval_service = self.container.get(IDataRetrievalService)
            result = retrieval_service.search_astronomical_data(user_input)
            
            return {
                "retrieval_result": result,
                "final_answer": f"数据检索完成，找到{result.get('total_count', 0)}条相关数据。\n\n[⚙️ 服务实现 - 默认数据检索服务]"
            }
            
        except Exception as e:
            print(f"Data retrieval service failed, using fallback: {e}")
            return self._fallback_data_retrieval(user_input, state)
    
    def _handle_literature_review_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理文献综述查询 - 完整版本"""
        try:
            # 提取关键词
            try:
                keywords = language_processor.extract_keywords(user_input)
            except AttributeError:
                keywords = user_input.split()[:5]  # 简单分词
            
            literature_config = {
                "query": user_input,
                "keywords": keywords,
                "year_range": [2020, 2024],
                "sources": ["arXiv", "ADS", "NASA"]
            }
            
            # 使用真实搜索或模拟搜索
            if self.tavily_client:
                literature_result = self._real_literature_search(user_input, keywords)
            else:
                literature_result = self._mock_literature_search(user_input, keywords)
            
            # 根据搜索类型添加标注
            if self.tavily_client:
                final_answer = f"文献综述完成，共分析了{literature_result['papers_found']}篇相关论文。\n\n[🔍 真实搜索 - Tavily API]"
            else:
                final_answer = f"文献综述完成，共分析了{literature_result['papers_found']}篇相关论文。\n\n[⚠️ 模拟搜索 - Tavily服务不可用]"
            
            return {
                "literature_config": literature_config,
                "literature_result": literature_result,
                "final_answer": final_answer
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "final_answer": f"文献综述失败：{str(e)}"
            }
    
    def _real_literature_search(self, query: str, keywords: List[str]) -> Dict[str, Any]:
        """真实的文献搜索 - 使用Tavily API"""
        try:
            # 构建搜索查询
            search_query = f"{query} astronomy astrophysics"
            if keywords:
                search_query += " " + " ".join(keywords[:3])
            
            # 执行搜索
            search_results = self.tavily_client.search(
                query=search_query,
                search_depth="advanced",
                max_results=5,
                include_domains=["arxiv.org", "adsabs.harvard.edu", "nasa.gov", "esa.int"]
            )
            
            # 处理搜索结果
            papers = []
            for result in search_results.get("results", []):
                paper = {
                    "title": result.get("title", "无标题"),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "published_date": result.get("published_date", ""),
                    "source": self._extract_source_from_url(result.get("url", ""))
                }
                papers.append(paper)
            
            return {
                "papers_found": len(papers),
                "papers": papers,
                "summary": f"通过Tavily搜索找到{len(papers)}篇相关论文，主要来源：{', '.join(set([p['source'] for p in papers]))}。"
            }
            
        except Exception as e:
            print(f"Tavily搜索失败，使用模拟数据: {e}")
            return self._mock_literature_search(query, keywords)
    
    def _mock_literature_search(self, query: str, keywords: List[str]) -> Dict[str, Any]:
        """模拟文献搜索"""
        return {
            "papers_found": 25,
            "papers": [
                {
                    "title": "Recent Advances in Galaxy Classification",
                    "authors": ["Smith, J.", "Johnson, A."],
                    "year": 2023,
                    "source": "arXiv",
                    "abstract": "This paper presents new methods for galaxy classification..."
                },
                {
                    "title": "Machine Learning in Astronomy",
                    "authors": ["Brown, M.", "Wilson, K."],
                    "year": 2024,
                    "source": "ADS",
                    "abstract": "Application of ML techniques to astronomical data analysis..."
                }
            ],
            "summary": "找到25篇相关论文，主要涉及星系分类和机器学习在天文学中的应用。"
        }
    
    def _extract_source_from_url(self, url: str) -> str:
        """从URL提取来源"""
        if "arxiv.org" in url:
            return "arXiv"
        elif "adsabs.harvard.edu" in url:
            return "ADS"
        elif "nasa.gov" in url:
            return "NASA"
        elif "esa.int" in url:
            return "ESA"
        else:
            return "其他"
    
    def _handle_code_generation_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理代码生成查询 - 完整版本"""
        try:
            # 使用依赖注入的代码生成服务
            from core.interfaces import ICodeGenerationService
            code_service = self.container.get(ICodeGenerationService)
            code = code_service.generate_analysis_code({"query": user_input, "user_type": user_type})
            
            return {
                "generated_code": code,
                "code_metadata": {"query": user_input, "user_type": user_type},
                "final_answer": f"代码生成完成，生成了{len(code.split())}行代码。\n\n[⚙️ 服务实现 - 默认代码生成服务]"
            }
            
        except Exception as e:
            print(f"Code generation service failed, using fallback: {e}")
            return self._fallback_code_generation(user_input, state)
    
    def _handle_general_query(self, user_input: str, user_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理一般查询"""
        return {
            "final_answer": f"已处理您的查询：{user_input}。请提供更具体的要求以获得更好的帮助。"
        }
    
    def _get_template_qa_response(self, user_input: str, user_type: str) -> str:
        """获取模板问答响应"""
        if user_type == "amateur":
            return f"""您好！我是天文科研助手，很高兴为您解答天文问题。

您的问题：{user_input}

作为天文爱好者，我建议您：
1. 从基础概念开始了解
2. 使用简单的观测工具
3. 加入天文爱好者社区
4. 阅读科普书籍和文章

如果您需要更专业的数据分析或代码生成，请告诉我，我可以为您提供专业级别的服务。"""
        else:
            return f"""您好！我是天文科研助手，为您提供专业级服务。

您的问题：{user_input}

作为专业用户，我可以为您提供：
1. 天体分类和分析
2. 数据检索和处理
3. 代码生成和执行
4. 文献综述和研究建议

请告诉我您具体需要什么帮助。"""
    
    def _fallback_classification(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """备用分类功能"""
        try:
            # 提取天体信息
            try:
                celestial_info = language_processor.extract_celestial_info(user_input)
            except AttributeError:
                # 如果方法不存在，使用简单的提取
                celestial_info = {"name": user_input, "type": "unknown"}
            
            # 基于规则的分类
            name = celestial_info.get("name", "").lower()
            if "galaxy" in name or "星系" in name:
                object_type = "galaxy"
            elif "star" in name or "恒星" in name:
                object_type = "star"
            elif "planet" in name or "行星" in name:
                object_type = "planet"
            else:
                object_type = "unknown"
            
            classification_result = {
                "object_type": object_type,
                "confidence": 0.8,
                "celestial_info": celestial_info
            }
            
            return {
                "classification_result": classification_result,
                "final_answer": f"天体分类完成：{celestial_info.get('name', '未知天体')} 被分类为 {object_type}\n\n[⚠️ 降级处理 - 规则分类]"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "final_answer": f"天体分类失败：{str(e)}"
            }
    
    def _fallback_data_retrieval(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """备用数据检索功能"""
        try:
            # 模拟数据检索
            retrieval_config = {
                "query": user_input,
                "data_source": "SDSS",
                "filters": {},
                "limit": 100
            }
            
            # 模拟检索结果
            retrieval_result = {
                "data": {
                    "count": 50,
                    "objects": [
                        {"name": "Galaxy_001", "type": "galaxy", "magnitude": 12.5},
                        {"name": "Star_002", "type": "star", "magnitude": 8.3},
                        {"name": "Nebula_003", "type": "nebula", "magnitude": 15.2}
                    ]
                },
                "metadata": {
                    "source": "SDSS",
                    "query_time": time.time(),
                    "total_available": 1000
                }
            }
            
            return {
                "retrieval_config": retrieval_config,
                "retrieval_result": retrieval_result,
                "final_answer": f"数据检索完成，找到{retrieval_result['data']['count']}个相关天体。\n\n[⚠️ 降级处理 - 模拟数据]"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "final_answer": f"数据检索失败：{str(e)}"
            }
    
    def _fallback_code_generation(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """备用代码生成功能"""
        try:
            # 根据用户输入生成代码
            if "分析" in user_input or "analysis" in user_input.lower():
                code = self._generate_analysis_code(user_input)
            elif "可视化" in user_input or "plot" in user_input.lower():
                code = self._generate_visualization_code(user_input)
            elif "数据处理" in user_input or "data processing" in user_input.lower():
                code = self._generate_data_processing_code(user_input)
            else:
                code = self._generate_general_code(user_input)
            
            metadata = {
                "task_type": "code_generation",
                "language": "python",
                "dependencies": ["numpy", "matplotlib", "astropy"],
                "generated_at": time.time()
            }
            
            return {
                "code": code,
                "metadata": metadata,
                "final_answer": "代码生成完成，请查看生成的代码。\n\n[⚠️ 降级处理 - 模板生成]"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "final_answer": f"代码生成失败：{str(e)}"
            }
    
    def _generate_analysis_code(self, user_input: str) -> str:
        """生成分析代码"""
        return f'''# 天文数据分析代码
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

def analyze_astronomical_data():
    """分析天文数据"""
    # 用户需求: {user_input}
    
    # 1. 数据加载
    # data = fits.open('your_data.fits')[1].data
    
    # 2. 数据预处理
    # processed_data = preprocess_data(data)
    
    # 3. 分析
    # results = perform_analysis(processed_data)
    
    # 4. 可视化
    # plot_results(results)
    
    print("分析完成")
    return results

if __name__ == "__main__":
    analyze_astronomical_data()
'''
    
    def _generate_visualization_code(self, user_input: str) -> str:
        """生成可视化代码"""
        return f'''# 天文数据可视化代码
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

def visualize_astronomical_data():
    """可视化天文数据"""
    # 用户需求: {user_input}
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 示例数据
    x = np.random.normal(0, 1, 1000)
    y = np.random.normal(0, 1, 1000)
    
    # 散点图
    ax.scatter(x, y, alpha=0.6)
    ax.set_xlabel('X坐标')
    ax.set_ylabel('Y坐标')
    ax.set_title('天文数据可视化')
    
    plt.show()

if __name__ == "__main__":
    visualize_astronomical_data()
'''
    
    def _generate_data_processing_code(self, user_input: str) -> str:
        """生成数据处理代码"""
        return f'''# 天文数据处理代码
import numpy as np
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

def process_astronomical_data():
    """处理天文数据"""
    # 用户需求: {user_input}
    
    # 1. 数据加载
    # data = fits.open('your_data.fits')[1].data
    
    # 2. 数据清洗
    # cleaned_data = clean_data(data)
    
    # 3. 数据转换
    # converted_data = convert_coordinates(cleaned_data)
    
    # 4. 数据保存
    # save_processed_data(converted_data)
    
    print("数据处理完成")
    return converted_data

if __name__ == "__main__":
    process_astronomical_data()
'''
    
    def _generate_general_code(self, user_input: str) -> str:
        """生成通用代码"""
        return f'''# 天文科研代码
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

def astronomical_research():
    """天文研究代码"""
    # 用户需求: {user_input}
    
    # 在这里添加您的代码
    print("天文研究代码执行完成")
    
    return None

if __name__ == "__main__":
    astronomical_research()
'''
    
    def _record_query_history(self, session_id: str, user_input: str, state: Dict[str, Any]) -> None:
        """记录查询历史"""
        try:
            history_entry = {
                "session_id": session_id,
                "user_input": user_input,
                "user_type": state.get("user_type"),
                "task_type": state.get("task_type"),
                "timestamp": time.time(),
                "success": state.get("is_complete", False)
            }
            
            # 这里应该保存到数据库
            if session_id not in self.cache:
                self.cache[session_id] = []
            self.cache[session_id].append(history_entry)
            
        except Exception as e:
            print(f"Failed to record query history: {e}")
    
    def get_query_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取查询历史"""
        return self.cache.get(session_id, [])
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "system_initialized": True,
            "llm_available": self.llm is not None,
            "database_connected": True,
            "cache_size": len(self.cache),
            "active_sessions": len(self.cache),
            "services_configured": True
        }
    
    def _classify_task_with_context(self, user_input: str, user_type: str, session_id: str) -> str:
        """考虑对话上下文的任务分类"""
        # 优先使用规则分类
        rule_classification = self._classify_task(user_input, user_type)
        if rule_classification != "qa":
            return rule_classification
        
        # 如果规则分类返回QA，再使用LLM进行上下文分类
        try:
            # 获取最近的对话历史（最近3轮）
            recent_history = self.conversation_history.get(session_id, [])[-6:]  # 最近3轮对话
            
            # 构建上下文信息
            context_info = ""
            if recent_history:
                context_info = "最近的对话历史：\n"
                for msg in recent_history:
                    role = "用户" if msg["role"] == "user" else "助手"
                    context_info += f"{role}: {msg['content']}\n"
                context_info += "\n"
            
            # 使用LLM进行智能任务分类
            classification_prompt = f"""
{context_info}请分析以下用户输入，判断应该执行哪种任务类型：

用户输入: {user_input}
用户类型: {user_type}

可选任务类型：
1. qa - 一般问答，如"你好"、"什么是黑洞"、"如何观测流星雨"
2. classification - 天体分类查询，如"天狼星是什么类型"、"M87属于什么星系"
3. data_retrieval - 数据检索，如"获取太阳的数据"、"查询火星轨道参数"
4. literature_review - 文献综述，如"关于黑洞的最新研究"、"超新星爆发文献"
5. code_generation - 代码生成，如"生成天文计算代码"、"编写观测脚本"

请只返回任务类型名称（如：qa、classification、data_retrieval、literature_review、code_generation），不要其他内容。
"""

            # 使用简单的字符串调用
            response = self.llm.invoke(classification_prompt)
            # 处理LLM返回的响应
            if hasattr(response, 'content'):
                task_type = response.content.strip().lower()
            else:
                task_type = str(response).strip().lower()
            
            # 验证返回的任务类型
            valid_types = ["qa", "classification", "data_retrieval", "literature_review", "code_generation"]
            if task_type in valid_types:
                return task_type
            else:
                print(f"LLM返回无效任务类型: {task_type}，使用规则分类结果")
                return rule_classification
                
        except Exception as e:
            print(f"LLM任务分类失败: {e}，使用规则分类结果")
            return rule_classification
    
    def _handle_qa_query_with_context(self, user_input: str, user_type: str, state: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """处理问答查询 - 支持多步对话上下文"""
        try:
            # 获取对话历史
            history = self.conversation_history.get(session_id, [])
            
            # 构建上下文信息
            context_info = ""
            if len(history) > 1:  # 有历史对话
                context_info = "对话历史：\n"
                for msg in history[-4:]:  # 最近2轮对话
                    role = "用户" if msg["role"] == "user" else "助手"
                    context_info += f"{role}: {msg['content']}\n"
                context_info += "\n"
            
            # 构建提示词
            simple_prompt = f"""
{context_info}你是一个专业的天文科研助手。用户类型：{user_type}

请根据对话上下文回答用户的问题。如果用户的问题与之前的对话相关，请结合上下文给出连贯的回答。

用户问题：{user_input}

请提供准确、简洁的天文知识回答。如果是简单问候，请简洁回应并引导到天文话题。
"""

            # 生成回答
            if self.llm:
                llm_response = self.llm.invoke(simple_prompt)
                # 处理LLM返回的响应
                if hasattr(llm_response, 'content'):
                    response = llm_response.content
                else:
                    response = str(llm_response)
            else:
                response = f"抱歉，LLM服务不可用，无法回答您的问题：{user_input}"
            
            # 添加助手回答到历史
            self.conversation_history[session_id].append({
                "role": "assistant",
                "content": response,
                "timestamp": time.time()
            })
            
            return {
                "qa_response": response,
                "final_answer": f"[🤖 AI回答 - Qwen 2.5:7b (Ollama)]\n\n{response}",
                "response": response
            }
            
        except Exception as e:
            error_msg = f"问答处理失败: {str(e)}"
            print(f"Error in QA query: {e}")
            
            # 添加错误回答到历史
            self.conversation_history[session_id].append({
                "role": "assistant", 
                "content": error_msg,
                "timestamp": time.time()
            })
            
            return {
                "qa_response": error_msg,
                "final_answer": f"[❌ 错误] {error_msg}",
                "response": error_msg,
                "error": error_msg
            }

def main():
    """测试完整功能系统"""
    print("🌌 完整功能天文科研系统")
    print("=" * 50)
    
    system = CompleteSimpleAstroSystem()
    
    # 测试用例
    test_cases = [
        "你好",
        "什么是黑洞？",
        "我需要分析M87星系",
        "帮我检索SDSS数据",
        "生成分析代码",
        "帮我查找相关论文",
        "分类这个天体：M87"
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case}")
        print("-" * 40)
        
        result = system.process_query(f"test_{i}", test_case)
        
        print(f"会话ID: {result['session_id']}")
        print(f"用户类型: {result['user_type']}")
        print(f"任务类型: {result['task_type']}")
        print(f"处理状态: {'完成' if result['is_complete'] else '进行中'}")
        
        if result.get('final_answer'):
            print(f"回答: {result['final_answer']}")
        
        if result.get('error_info'):
            print(f"错误: {result['error_info']}")
        
        print("-" * 40)
    
    # 显示系统状态
    print(f"\n📊 系统状态:")
    status = system.get_system_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    

if __name__ == "__main__":
    main()
