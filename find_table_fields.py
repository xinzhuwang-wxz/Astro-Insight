#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找 galaxy_classification 表的实际字段
"""

import sys
import os
sys.path.insert(0, 'src')

from tools.supabase_client import get_supabase_client

def find_table_fields():
    """查找表的实际字段"""
    print("🔍 查找 galaxy_classification 表的实际字段...")
    
    client = get_supabase_client()
    
    if not client.client:
        print("❌ Supabase客户端未初始化")
        return
    
    # 尝试一些非常基础的字段名
    basic_fields = [
        "galaxy_id", "galaxy_name", "galaxy_type", "galaxy_class",
        "object_id", "object_name", "object_type", "object_class",
        "name", "type", "class", "category", "group",
        "ra", "dec", "right_ascension", "declination",
        "magnitude", "mag", "brightness",
        "distance", "redshift", "size", "mass",
        "spiral_type", "elliptical_type", "irregular_type",
        "barred", "unbarred", "lenticular",
        "created_at", "updated_at", "timestamp"
    ]
    
    successful_fields = []
    
    for field in basic_fields:
        print(f"\n🔍 测试字段: {field}")
        
        try:
            # 尝试插入只有这一个字段的记录
            test_data = {field: "test_value"}
            insert_result = client.client.table("galaxy_classification").insert(test_data).execute()
            print(f"✅ 字段 '{field}' 存在")
            successful_fields.append(field)
            
            # 立即删除测试记录
            if insert_result.data and len(insert_result.data) > 0:
                # 尝试通过字段值删除
                delete_result = client.client.table("galaxy_classification").delete().eq(field, "test_value").execute()
                print(f"✅ 测试记录已删除")
            
        except Exception as e:
            error_msg = str(e)
            if "Could not find" in error_msg and "column" in error_msg:
                print(f"❌ 字段 '{field}' 不存在")
            else:
                print(f"❌ 其他错误: {error_msg}")
    
    print(f"\n📊 总结:")
    if successful_fields:
        print(f"✅ 找到的字段: {successful_fields}")
        
        # 尝试查询表结构
        try:
            print(f"\n🔍 尝试查询表结构...")
            result = client.client.table("galaxy_classification").select("*").limit(1).execute()
            if result.data:
                print(f"📋 实际表结构: {list(result.data[0].keys())}")
            else:
                print("❌ 表仍然为空")
        except Exception as e:
            print(f"❌ 查询失败: {e}")
    else:
        print("❌ 没有找到任何有效字段")
        print("💡 建议：请检查表名是否正确，或者表是否真的存在")

if __name__ == "__main__":
    find_table_fields()
