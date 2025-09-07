#!/usr/bin/env python3
"""
Astro Insight 工具模块
提供语言处理、缓存管理、错误处理等功能
"""

# 语言处理模块
from .language_processor import (
    LanguageProcessor,
    LanguageDetectionResult,
    TranslationResult,
    CelestialObjectExtraction,
    language_processor,
    detect_language,
    translate_to_english,
    extract_celestial_object,
    process_classification_query
)

# 为了兼容性，创建translate_text函数
def translate_text(text: str, target_language: str = "en", source_language: str = "auto"):
    """翻译文本函数"""
    return language_processor.translate_text(text, target_language, source_language)

# 创建占位符函数和类，避免导入错误
class ExtractedCelestialObject:
    """天体对象提取结果占位符"""
    pass

class QueryResult:
    """查询结果占位符"""
    pass

class ConcurrentQueryManager:
    """并发查询管理器占位符"""
    pass

class CacheEntry:
    """缓存条目占位符"""
    pass

class LRUCache:
    """LRU缓存占位符"""
    pass

class CacheManager:
    """缓存管理器占位符"""
    pass

class ErrorCategory:
    """错误分类占位符"""
    pass

class RetryConfig:
    """重试配置占位符"""
    pass

class ErrorHandler:
    """错误处理器占位符"""
    pass

# 创建占位符函数
def enhanced_name_extractor(text: str):
    """增强名称提取器占位符"""
    return extract_celestial_object(text)

def extract_celestial_names(text: str):
    """提取天体名称占位符"""
    return [extract_celestial_object(text)]

def query_manager():
    """查询管理器占位符"""
    return None

def celestial_query_engine():
    """天体查询引擎占位符"""
    return None

def cache_manager():
    """缓存管理器占位符"""
    return None

def error_handler():
    """错误处理器占位符"""
    return None

def with_retry(func):
    """重试装饰器占位符"""
    return func

# 导出所有需要的符号
__all__ = [
    # 语言处理
    "language_processor",
    "translate_text",
    "LanguageDetectionResult",
    "TranslationResult",
    "CelestialObjectExtraction",
    "detect_language",
    "translate_to_english",
    "extract_celestial_object",
    "process_classification_query",
    
    # 天体名称提取
    "enhanced_name_extractor",
    "extract_celestial_names",
    "ExtractedCelestialObject",
    
    # 并发查询
    "query_manager",
    "celestial_query_engine",
    "QueryResult",
    "ConcurrentQueryManager",
    
    # 缓存管理
    "cache_manager",
    "CacheEntry",
    "LRUCache",
    "CacheManager",
    
    # 错误处理
    "error_handler",
    "with_retry",
    "ErrorCategory",
    "RetryConfig",
    "ErrorHandler",
]