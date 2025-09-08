#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查Supabase数据库结构
"""

import sys
import os
sys.path.insert(0, 'src')

from tools.supabase_client import get_supabase_client

def check_database_structure():
    """检查数据库结构"""
    print("🔍 检查Supabase数据库结构...")
    
    client = get_supabase_client()
    
    if not client.client:
        print("❌ Supabase客户端未初始化")
        return
    
    try:
        # 尝试使用REST API直接查询
        print("\n📋 尝试获取数据库信息...")
        
        # 方法1: 尝试查询pg_tables
        try:
            result = client.client.rpc('get_tables').execute()
            print(f"✅ 通过RPC获取表列表: {result.data}")
        except Exception as e:
            print(f"❌ RPC方法失败: {e}")
        
        # 方法2: 尝试直接查询
        try:
            # 使用SQL查询
            result = client.client.rpc('exec_sql', {'sql': 'SELECT table_name FROM information_schema.tables WHERE table_schema = \'public\''}).execute()
            print(f"✅ 通过SQL获取表列表: {result.data}")
        except Exception as e:
            print(f"❌ SQL方法失败: {e}")
        
        # 方法3: 尝试列出所有可用的表
        print("\n🔍 尝试列出所有可访问的表...")
        try:
            # 尝试一些常见的表名
            test_tables = [
                "users", "profiles", "data", "objects", "celestial", 
                "astronomy", "stars", "galaxies", "planets", "moons"
            ]
            
            found_tables = []
            for table in test_tables:
                try:
                    result = client.client.table(table).select("*").limit(1).execute()
                    found_tables.append(table)
                    print(f"✅ 找到表: {table}")
                except:
                    pass
            
            if found_tables:
                print(f"📊 找到的表: {found_tables}")
            else:
                print("❌ 没有找到任何表")
                
        except Exception as e:
            print(f"❌ 列出表失败: {e}")
            
    except Exception as e:
        print(f"❌ 检查数据库结构失败: {e}")

if __name__ == "__main__":
    check_database_structure()
