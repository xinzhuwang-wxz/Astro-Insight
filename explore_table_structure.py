#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探索 galaxy_classification 表结构
"""

import sys
import os
sys.path.insert(0, 'src')

from tools.supabase_client import get_supabase_client

def explore_table_structure():
    """探索表结构"""
    print("🔍 探索 galaxy_classification 表结构...")
    
    client = get_supabase_client()
    
    if not client.client:
        print("❌ Supabase客户端未初始化")
        return
    
    # 尝试不同的字段组合
    test_combinations = [
        # 基础字段
        {"id": 1, "name": "test"},
        {"id": 1, "galaxy_name": "test"},
        {"id": 1, "object_name": "test"},
        
        # 坐标字段
        {"id": 1, "ra": 10.0, "dec": 20.0},
        {"id": 1, "right_ascension": 10.0, "declination": 20.0},
        {"id": 1, "longitude": 10.0, "latitude": 20.0},
        
        # 星等字段
        {"id": 1, "magnitude": 12.5},
        {"id": 1, "mag": 12.5},
        {"id": 1, "brightness": 12.5},
        
        # 类型字段
        {"id": 1, "type": "spiral"},
        {"id": 1, "galaxy_type": "spiral"},
        {"id": 1, "object_type": "spiral"},
        {"id": 1, "morphology": "spiral"},
        
        # 分类字段
        {"id": 1, "class": "spiral"},
        {"id": 1, "category": "spiral"},
        {"id": 1, "group": "spiral"},
        
        # 其他常见字段
        {"id": 1, "distance": 1000.0},
        {"id": 1, "redshift": 0.1},
        {"id": 1, "size": 50000.0},
        {"id": 1, "mass": 1e12},
    ]
    
    successful_fields = set()
    
    for i, test_data in enumerate(test_combinations):
        print(f"\n🔍 测试组合 {i+1}: {list(test_data.keys())}")
        
        try:
            # 尝试插入
            insert_result = client.client.table("galaxy_classification").insert(test_data).execute()
            print(f"✅ 成功插入: {list(test_data.keys())}")
            
            # 记录成功的字段
            for field in test_data.keys():
                successful_fields.add(field)
            
            # 立即删除测试记录
            if insert_result.data and len(insert_result.data) > 0:
                record_id = insert_result.data[0].get('id')
                if record_id:
                    delete_result = client.client.table("galaxy_classification").delete().eq("id", record_id).execute()
                    print(f"✅ 测试记录已删除")
            
        except Exception as e:
            error_msg = str(e)
            if "Could not find" in error_msg and "column" in error_msg:
                # 提取不存在的字段名
                import re
                match = re.search(r"Could not find the '([^']+)' column", error_msg)
                if match:
                    missing_field = match.group(1)
                    print(f"❌ 字段 '{missing_field}' 不存在")
                else:
                    print(f"❌ 插入失败: {error_msg}")
            else:
                print(f"❌ 其他错误: {error_msg}")
    
    print(f"\n📊 总结:")
    print(f"✅ 成功的字段: {sorted(successful_fields)}")
    
    if successful_fields:
        print(f"\n🎯 建议的表结构:")
        print(f"表名: galaxy_classification")
        print(f"字段: {', '.join(sorted(successful_fields))}")
        
        # 尝试查询一条记录来确认结构
        try:
            print(f"\n🔍 尝试查询表结构...")
            result = client.client.table("galaxy_classification").select("*").limit(1).execute()
            if result.data:
                print(f"📋 实际表结构: {list(result.data[0].keys())}")
            else:
                print("❌ 表仍然为空")
        except Exception as e:
            print(f"❌ 查询失败: {e}")

if __name__ == "__main__":
    explore_table_structure()
