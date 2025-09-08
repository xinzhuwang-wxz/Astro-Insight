#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase客户端工具
用于连接和查询Supabase数据库
"""

import os
import sys
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from supabase import create_client, Client
    from supabase_config import get_supabase_config
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: Supabase not available, using mock client")

class SupabaseClient:
    """Supabase数据库客户端"""
    
    def __init__(self):
        self.client = None
        self.config = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Supabase客户端"""
        if not SUPABASE_AVAILABLE:
            print("Supabase not available, using mock client")
            return
        
        try:
            self.config = get_supabase_config()
            self.client = create_client(
                self.config["url"], 
                self.config["service_role_key"]
            )
            print("✅ Supabase客户端初始化成功")
        except Exception as e:
            print(f"❌ Supabase客户端初始化失败: {e}")
            self.client = None
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        if not self.client:
            return False
        
        try:
            # 尝试查询系统表来测试连接
            result = self.client.table("information_schema.tables").select("table_name").limit(1).execute()
            print("✅ Supabase连接测试成功")
            return True
        except Exception as e:
            # 如果系统表查询失败，尝试简单的连接测试
            try:
                # 尝试获取项目信息
                result = self.client.auth.get_user()
                print("✅ Supabase连接测试成功（通过认证）")
                return True
            except Exception as e2:
                print(f"❌ Supabase连接测试失败: {e}")
                return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表结构信息"""
        if not self.client:
            return {"error": "Supabase客户端未初始化"}
        
        try:
            # 获取表的前几条记录来了解结构
            result = self.client.table(table_name).select("*").limit(5).execute()
            
            if result.data:
                # 分析数据结构
                sample_data = result.data[0]
                columns = list(sample_data.keys())
                data_types = {col: type(val).__name__ for col, val in sample_data.items()}
                
                return {
                    "table_name": table_name,
                    "columns": columns,
                    "data_types": data_types,
                    "sample_data": sample_data,
                    "total_columns": len(columns)
                }
            else:
                return {"error": f"表 {table_name} 为空或不存在"}
                
        except Exception as e:
            return {"error": f"获取表信息失败: {str(e)}"}
    
    def query_data(self, table_name: str, filters: Dict[str, Any] = None, limit: int = 100) -> Dict[str, Any]:
        """查询数据"""
        if not self.client:
            return {"error": "Supabase客户端未初始化"}
        
        try:
            query = self.client.table(table_name).select("*")
            
            # 应用过滤条件
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        # 处理范围查询
                        if "gte" in value:
                            query = query.gte(key, value["gte"])
                        if "lte" in value:
                            query = query.lte(key, value["lte"])
                        if "gt" in value:
                            query = query.gt(key, value["gt"])
                        if "lt" in value:
                            query = query.lt(key, value["lt"])
                    else:
                        # 精确匹配
                        query = query.eq(key, value)
            
            # 应用限制
            query = query.limit(limit)
            
            # 执行查询
            result = query.execute()
            
            return {
                "success": True,
                "data": result.data,
                "count": len(result.data),
                "table_name": table_name,
                "filters": filters,
                "query_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "table_name": table_name
            }
    
    def get_available_tables(self) -> List[str]:
        """获取可用表列表（模拟）"""
        # 由于Supabase Python客户端没有直接获取表列表的方法
        # 这里返回一些常见的表名，实际使用时需要根据您的数据库调整
        common_tables = [
            "celestial_objects",
            "stars", 
            "galaxies",
            "nebulae",
            "planets",
            "asteroids",
            "comets"
        ]
        
        # 尝试测试每个表是否存在
        available_tables = []
        for table in common_tables:
            try:
                result = self.client.table(table).select("*").limit(1).execute()
                available_tables.append(table)
            except:
                continue
        
        return available_tables
    
    def save_query_result(self, data: List[Dict], filename: str, format: str = "csv") -> Dict[str, Any]:
        """保存查询结果到文件"""
        try:
            # 确保数据存储目录存在
            os.makedirs("./data/analysis_results", exist_ok=True)
            
            # 生成文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"./data/analysis_results/{filename}_{timestamp}.{format}"
            
            # 根据格式保存数据
            if format.lower() == "csv":
                df = pd.DataFrame(data)
                df.to_csv(filepath, index=False, encoding='utf-8')
            elif format.lower() == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            elif format.lower() == "xlsx":
                df = pd.DataFrame(data)
                df.to_excel(filepath, index=False)
            else:
                return {"success": False, "error": f"不支持的格式: {format}"}
            
            return {
                "success": True,
                "filepath": filepath,
                "format": format,
                "record_count": len(data),
                "file_size": os.path.getsize(filepath)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局客户端实例
supabase_client = SupabaseClient()

def get_supabase_client() -> SupabaseClient:
    """获取Supabase客户端实例"""
    return supabase_client
