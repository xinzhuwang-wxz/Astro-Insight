#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 galaxy_classification 表
"""

import sys
import os
sys.path.insert(0, 'src')

from tools.supabase_client import get_supabase_client

def test_galaxy_table():
    """测试 galaxy_classification 表"""
    print("🔍 测试 galaxy_classification 表...")
    
    client = get_supabase_client()
    
    if not client.client:
        print("❌ Supabase客户端未初始化")
        return
    
    try:
        # 查询 galaxy_classification 表
        print("\n📊 查询 galaxy_classification 表...")
        result = client.client.table("galaxy_classification").select("*").limit(5).execute()
        
        print(f"✅ 成功查询到表: galaxy_classification")
        print(f"📈 记录数: {len(result.data)}")
        
        if result.data:
            # 分析表结构
            sample_record = result.data[0]
            print(f"\n🔍 表字段: {list(sample_record.keys())}")
            print(f"📋 字段类型分析:")
            
            for field, value in sample_record.items():
                print(f"  - {field}: {type(value).__name__} = {value}")
            
            print(f"\n📊 示例记录:")
            for i, record in enumerate(result.data[:3]):
                print(f"  记录 {i+1}: {record}")
                
            # 获取表的总记录数
            try:
                count_result = client.client.table("galaxy_classification").select("id", count="exact").execute()
                print(f"\n📈 总记录数: {count_result.count}")
            except Exception as e:
                print(f"⚠️ 无法获取总记录数: {e}")
                
        else:
            print("❌ 表为空，尝试获取表结构...")
            
            # 尝试获取表结构信息
            try:
                # 使用REST API获取表结构
                response = client.client.table("galaxy_classification").select("*").limit(0).execute()
                print("✅ 表存在但无数据")
                
                # 尝试插入一条测试记录来了解表结构
                print("\n🔍 尝试插入测试记录来了解表结构...")
                test_data = {
                    "id": 1,
                    "name": "test_galaxy",
                    "ra": 10.0,
                    "dec": 20.0,
                    "magnitude": 12.5,
                    "type": "spiral",
                    "classification": "test"
                }
                
                try:
                    insert_result = client.client.table("galaxy_classification").insert(test_data).execute()
                    print("✅ 测试记录插入成功")
                    print(f"📊 插入结果: {insert_result.data}")
                    
                    # 立即删除测试记录
                    delete_result = client.client.table("galaxy_classification").delete().eq("id", 1).execute()
                    print("✅ 测试记录已删除")
                    
                except Exception as e:
                    print(f"❌ 插入测试记录失败: {e}")
                    print("这可能是由于表结构限制或权限问题")
                    
            except Exception as e:
                print(f"❌ 获取表结构失败: {e}")
            
    except Exception as e:
        print(f"❌ 查询 galaxy_classification 表失败: {e}")
        
        # 尝试其他可能的表名
        print("\n🔍 尝试其他可能的表名...")
        possible_tables = [
            "galaxy_classification", "galaxy_classifications", 
            "galaxy_data", "galaxies", "classification"
        ]
        
        for table in possible_tables:
            try:
                result = client.client.table(table).select("*").limit(1).execute()
                print(f"✅ 找到表: {table}")
                break
            except Exception as e2:
                print(f"❌ 表 {table} 不存在: {e2}")

if __name__ == "__main__":
    test_galaxy_table()
