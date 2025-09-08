#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tavily 搜索 API 包装器
提供简化的 Tavily 搜索功能
"""

import os
from typing import List, Dict, Any, Optional
from tavily import TavilyClient
from src.config.env_manager import get_api_key


def tavily_search(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    执行 Tavily 搜索
    
    Args:
        query: 搜索查询
        max_results: 最大结果数量
        
    Returns:
        搜索结果列表
    """
    try:
        # 获取 API 密钥
        try:
            from src.config.env_manager import env_manager
            search_config = env_manager.get_search_config()
            api_key = search_config.get('api_key')
            if not api_key:
                print("警告: 未设置 TAVILY_API_KEY，将返回空结果")
                return []
        except Exception as e:
            print(f"警告: 获取API密钥失败: {e}，将返回空结果")
            return []
        
        # 初始化客户端
        client = TavilyClient(api_key=api_key)
        
        # 执行搜索
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_domains=[],
            exclude_domains=[]
        )
        
        # 格式化结果
        results = []
        for item in response.get('results', []):
            results.append({
                'title': item.get('title', '无标题'),
                'content': item.get('content', '无内容'),
                'url': item.get('url', ''),
                'score': item.get('score', 0.0)
            })
        
        return results
        
    except Exception as e:
        print(f"Tavily 搜索错误: {e}")
        return []


def tavily_search_with_images(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    执行带图片的 Tavily 搜索
    
    Args:
        query: 搜索查询
        max_results: 最大结果数量
        
    Returns:
        包含文本和图片的搜索结果
    """
    try:
        # 获取 API 密钥
        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            print("警告: 未设置 TAVILY_API_KEY 环境变量，将返回空结果")
            return {'results': [], 'images': []}
        
        # 初始化客户端
        client = TavilyClient(api_key=api_key)
        
        # 执行搜索
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_domains=[],
            exclude_domains=[],
            include_images=True
        )
        
        # 格式化结果
        results = []
        for item in response.get('results', []):
            results.append({
                'title': item.get('title', '无标题'),
                'content': item.get('content', '无内容'),
                'url': item.get('url', ''),
                'score': item.get('score', 0.0)
            })
        
        # 提取图片
        images = response.get('images', [])
        
        return {
            'results': results,
            'images': images
        }
        
    except Exception as e:
        print(f"Tavily 搜索错误: {e}")
        return {'results': [], 'images': []}


if __name__ == "__main__":
    # 测试搜索功能
    test_query = "黑洞 天文学"
    print(f"测试搜索: {test_query}")
    
    results = tavily_search(test_query, max_results=2)
    print(f"搜索结果数量: {len(results)}")
    
    for i, result in enumerate(results, 1):
        print(f"\n结果 {i}:")
        print(f"标题: {result['title']}")
        print(f"内容: {result['content'][:100]}...")
        print(f"URL: {result['url']}")
        print(f"评分: {result['score']}")
