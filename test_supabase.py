#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Supabase连接
"""

import sys
import os
sys.path.insert(0, 'src')

from tools.supabase_client import get_supabase_client

def test_supabase_connection():
    """测试Supabase连接"""
    print("🔗 测试Supabase连接...")
    
    client = get_supabase_client()
    
    # 测试连接
    if client.test_connection():
        print("✅ Supabase连接成功！")
        
        # 尝试直接查询一些常见的表名
        common_tables = ["celestial_objects", "stars", "galaxies", "nebulae", "objects", "data"]
        
        for table_name in common_tables:
            print(f"\n🔍 尝试查询表: {table_name}")
            try:
                # 获取表信息
                table_info = client.get_table_info(table_name)
                if "error" not in table_info:
                    print(f"✅ 找到表: {table_name}")
                    print(f"📊 表结构: {table_info}")
                    
                    # 查询数据
                    query_result = client.query_data(table_name, limit=3)
                    print(f"📈 查询结果: {query_result}")
                    break
                else:
                    print(f"❌ 表 {table_name} 不存在: {table_info.get('error')}")
            except Exception as e:
                print(f"❌ 查询表 {table_name} 时出错: {e}")
        
        # 如果所有表都不存在，尝试列出所有表
        print("\n🔍 尝试获取所有表...")
        try:
            # 使用Supabase的REST API直接查询
            response = client.client.table("information_schema.tables").select("table_name").eq("table_schema", "public").execute()
            if response.data:
                print(f"📋 数据库中的所有表: {[row['table_name'] for row in response.data]}")
            else:
                print("❌ 无法获取表列表")
        except Exception as e:
            print(f"❌ 获取表列表失败: {e}")
            
        return True
    else:
        print("❌ Supabase连接失败！")
        return False

if __name__ == "__main__":
    test_supabase_connection()
