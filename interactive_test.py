#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式测试程序
提供统一的程序接口来测试所有功能
"""

import sys
sys.path.insert(0, 'src')

from complete_simple_system import CompleteSimpleAstroSystem
import time

def main():
    """主程序"""
    print("🌌 天文科研系统 - 交互式测试")
    print("=" * 50)
    print("支持的功能:")
    print("1. 问答查询 (如: 什么是黑洞?)")
    print("2. 天体分类 (如: 分类这个天体：M87)")
    print("3. 数据检索 (如: 帮我检索SDSS数据)")
    print("4. 代码生成 (如: 生成分析代码)")
    print("5. 文献综述 (如: 帮我查找相关论文)")
    print("=" * 50)
    
    # 初始化系统
    try:
        system = CompleteSimpleAstroSystem()
        print("✅ 系统初始化成功")
    except Exception as e:
        print(f"❌ 系统初始化失败: {e}")
        return
    
    session_id = f"interactive_{int(time.time())}"
    
    while True:
        try:
            # 获取用户输入
            user_input = input("\n请输入您的查询 (输入 'quit' 退出): ").strip()
            
            if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
            
            print(f"\n🔍 处理查询: {user_input}")
            print("-" * 40)
            
            # 处理查询
            result = system.process_query(session_id, user_input)
            
            # 显示结果
            if result.get("final_answer"):
                print(f"📝 回答:")
                print(result["final_answer"])
            
            # 显示处理状态
            if result.get("current_step"):
                print(f"\n📊 处理状态: {result['current_step']}")
            
            # 显示用户类型和任务类型
            if result.get("user_type"):
                print(f"👤 用户类型: {result['user_type']}")
            if result.get("task_type"):
                print(f"🎯 任务类型: {result['task_type']}")
            
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 处理出错: {e}")

if __name__ == "__main__":
    main()
