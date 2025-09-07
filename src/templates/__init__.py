#!/usr/bin/env python3
"""
模板模块
提供天体分类模板和分类引擎功能
"""

import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class ConfidenceLevel(Enum):
    """置信度级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ClassificationRequest:
    """分类请求数据结构"""
    query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: str = "auto"
    include_metadata: bool = True
    confidence_threshold: float = 0.5
    max_results: int = 10
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


@dataclass
class ClassificationResult:
    """分类结果数据结构"""
    object_name: str
    object_type: str
    confidence: float
    coordinates: Optional[Dict[str, float]] = None
    magnitude: Optional[float] = None
    distance: Optional[float] = None
    spectral_class: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    source: str = "classification_engine"
    confidence_level: Optional[ConfidenceLevel] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        
        # 根据置信度设置置信度级别
        if self.confidence_level is None:
            if self.confidence >= 0.9:
                self.confidence_level = ConfidenceLevel.VERY_HIGH
            elif self.confidence >= 0.7:
                self.confidence_level = ConfidenceLevel.HIGH
            elif self.confidence >= 0.5:
                self.confidence_level = ConfidenceLevel.MEDIUM
            else:
                self.confidence_level = ConfidenceLevel.LOW
        
        if self.metadata is None:
            self.metadata = {}


class EnhancedClassificationEngine:
    """增强分类引擎"""
    
    def __init__(self):
        self.classification_templates = self._load_classification_templates()
        self.celestial_objects_db = self._load_celestial_objects_db()
    
    def _load_classification_templates(self) -> Dict[str, Any]:
        """加载分类模板"""
        return {
            "star": {
                "keywords": ["star", "恒星", "stellar", "sun", "太阳"],
                "patterns": [r"\b\w+\s+star\b", r"\b恒星\w*\b"],
                "confidence_boost": 0.1
            },
            "galaxy": {
                "keywords": ["galaxy", "星系", "galactic", "spiral", "elliptical"],
                "patterns": [r"\b\w+\s+galaxy\b", r"\b星系\w*\b"],
                "confidence_boost": 0.1
            },
            "nebula": {
                "keywords": ["nebula", "星云", "emission", "reflection", "planetary"],
                "patterns": [r"\b\w+\s+nebula\b", r"\b星云\w*\b"],
                "confidence_boost": 0.1
            },
            "planet": {
                "keywords": ["planet", "行星", "planetary", "exoplanet", "系外行星"],
                "patterns": [r"\b\w+\s+planet\b", r"\b行星\w*\b"],
                "confidence_boost": 0.1
            },
            "supernova": {
                "keywords": ["supernova", "超新星", "explosion", "爆炸"],
                "patterns": [r"\bsupernova\b", r"\b超新星\b"],
                "confidence_boost": 0.15
            }
        }
    
    def _load_celestial_objects_db(self) -> Dict[str, Dict[str, Any]]:
        """加载天体对象数据库"""
        return {
            "M31": {
                "name": "M31",
                "type": "galaxy",
                "common_name": "Andromeda Galaxy",
                "coordinates": {"ra": 10.6847, "dec": 41.2687},
                "magnitude": 3.4,
                "distance": 2537000,
                "description": "The Andromeda Galaxy is a spiral galaxy"
            },
            "M42": {
                "name": "M42",
                "type": "nebula",
                "common_name": "Orion Nebula",
                "coordinates": {"ra": 83.8221, "dec": -5.3911},
                "magnitude": 4.0,
                "distance": 1344,
                "description": "The Orion Nebula is an emission nebula"
            },
            "Sirius": {
                "name": "Sirius",
                "type": "star",
                "common_name": "Dog Star",
                "coordinates": {"ra": 101.2871, "dec": -16.7161},
                "magnitude": -1.46,
                "spectral_class": "A1V",
                "distance": 8.6,
                "description": "Sirius is the brightest star in the night sky"
            }
        }
    
    def classify_query(self, request: ClassificationRequest) -> List[ClassificationResult]:
        """分类查询"""
        query = request.query.lower()
        results = []
        
        # 直接匹配已知天体对象
        for obj_name, obj_data in self.celestial_objects_db.items():
            if obj_name.lower() in query or obj_data.get("common_name", "").lower() in query:
                confidence = 0.9  # 直接匹配的高置信度
                result = ClassificationResult(
                    object_name=obj_data["name"],
                    object_type=obj_data["type"],
                    confidence=confidence,
                    coordinates=obj_data.get("coordinates"),
                    magnitude=obj_data.get("magnitude"),
                    distance=obj_data.get("distance"),
                    spectral_class=obj_data.get("spectral_class"),
                    description=obj_data.get("description"),
                    metadata={
                        "common_name": obj_data.get("common_name"),
                        "match_type": "direct_match",
                        "query": request.query
                    }
                )
                results.append(result)
        
        # 基于模板的分类
        for obj_type, template in self.classification_templates.items():
            base_confidence = 0.3
            
            # 关键词匹配
            for keyword in template["keywords"]:
                if keyword.lower() in query:
                    base_confidence += 0.2
            
            # 模式匹配
            import re
            for pattern in template["patterns"]:
                if re.search(pattern, query, re.IGNORECASE):
                    base_confidence += 0.3
            
            # 置信度提升
            base_confidence += template.get("confidence_boost", 0)
            
            if base_confidence >= request.confidence_threshold:
                result = ClassificationResult(
                    object_name=f"Unknown {obj_type}",
                    object_type=obj_type,
                    confidence=min(base_confidence, 1.0),
                    description=f"Classified as {obj_type} based on query patterns",
                    metadata={
                        "match_type": "template_match",
                        "query": request.query,
                        "matched_keywords": [kw for kw in template["keywords"] if kw.lower() in query]
                    }
                )
                results.append(result)
        
        # 按置信度排序并限制结果数量
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:request.max_results]
    
    def batch_classify(self, requests: List[ClassificationRequest]) -> List[List[ClassificationResult]]:
        """批量分类"""
        return [self.classify_query(request) for request in requests]


# 全局分类引擎实例
_classification_engine = None


def get_classification_engine() -> EnhancedClassificationEngine:
    """获取分类引擎实例"""
    global _classification_engine
    if _classification_engine is None:
        _classification_engine = EnhancedClassificationEngine()
    return _classification_engine


def classify_celestial_query(query: str, **kwargs) -> List[ClassificationResult]:
    """分类天体查询 - 便捷函数"""
    request = ClassificationRequest(query=query, **kwargs)
    engine = get_classification_engine()
    return engine.classify_query(request)


def batch_classify_queries(queries: List[str], **kwargs) -> List[List[ClassificationResult]]:
    """批量分类查询 - 便捷函数"""
    requests = [ClassificationRequest(query=query, **kwargs) for query in queries]
    engine = get_classification_engine()
    return engine.batch_classify(requests)


def create_classification_template(object_type: str, keywords: List[str], patterns: List[str] = None, confidence_boost: float = 0.0) -> Dict[str, Any]:
    """创建分类模板"""
    return {
        "keywords": keywords,
        "patterns": patterns or [],
        "confidence_boost": confidence_boost
    }


# 导出所有公共接口
__all__ = [
    "ConfidenceLevel",
    "ClassificationRequest",
    "ClassificationResult",
    "EnhancedClassificationEngine",
    "get_classification_engine",
    "classify_celestial_query",
    "batch_classify_queries",
    "create_classification_template",
]