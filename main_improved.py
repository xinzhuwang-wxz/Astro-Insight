#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的天文科研Agent系统主程序入口
基于改进的工作流，提供更稳定的命令行交互界面
"""

import sys
import os
import argparse
import json
from typing import Dict, Any, Optional
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.workflow_improved import ImprovedAstroWorkflow, execute_improved_astro_workflow
from src.graph.types import AstroAgentState
from src.utils.error_handler import handle_error, create_error_context, AstroError, ErrorCode, ErrorSeverity
from src.utils.state_manager import format_state_output, validate_state


def print_banner():
    """打印系统横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    天文科研Agent系统                          ║
║                  Astro Research Agent System                ║
║                                                              ║
║  支持爱好者问答和专业用户的数据检索、文献综述功能              ║
║  (改进版 - 基于稳定的LangGraph架构)                          ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
可用命令：
  help, h          - 显示此帮助信息
  status, s        - 显示系统状态
  sessions         - 显示所有会话
  clear <id>       - 清除指定会话
  clear all        - 清除所有会话
  quit, q, exit    - 退出系统
  
直接输入问题开始对话，例如：
  什么是黑洞？
  我需要获取SDSS的星系数据
  请帮我查找关于引力波的最新文献
  分类这个天体：M87
  生成数据分析代码
"""
    print(help_text)


def interactive_mode(workflow: ImprovedAstroWorkflow):
    """交互式模式"""
    print("\n进入交互模式（输入 'help' 查看帮助，'quit' 退出）")
    session_counter = 1
    
    while True:
        try:
            user_input = input("\n🔭 请输入您的身份与问题: ").strip()
            
            if not user_input:
                continue
            
            # 处理命令
            if user_input.lower() in ['quit', 'q', 'exit']:
                print("感谢使用天文科研Agent系统！")
                break
            
            elif user_input.lower() in ['help', 'h']:
                print_help()
                continue
            
            elif user_input.lower() in ['status', 's']:
                status = workflow.get_system_status()
                print("\n系统状态:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
                continue
            
            elif user_input.lower() == 'sessions':
                sessions = workflow.list_sessions()
                print(f"\n活跃会话数: {len(sessions)}")
                for session_id in sessions:
                    session_info = workflow.get_session_info(session_id)
                    created_at = session_info['created_at'].strftime('%H:%M:%S')
                    print(f"  {session_id} (创建于 {created_at})")
                continue
            
            elif user_input.lower().startswith('clear '):
                parts = user_input.split()
                if len(parts) == 2:
                    if parts[1] == 'all':
                        workflow.clear_all_sessions()
                        print("所有会话已清除")
                    else:
                        session_id = parts[1]
                        if workflow.clear_session(session_id):
                            print(f"会话 {session_id} 已清除")
                        else:
                            print(f"会话 {session_id} 不存在")
                continue
            
            # 处理用户问题
            session_id = f"interactive_{session_counter}"
            print(f"\n🤖 正在处理您的问题...")
            
            try:
                result = workflow.execute_workflow(session_id, user_input)
                print(format_state_output(result))
                
                # 检查是否需要等待用户选择
                while result.get('awaiting_user_choice', False):
                    print("\n请选择 (是/否): ", end="")
                    user_choice = input().strip().lower()
                    
                    if user_choice in ['是', 'y', 'yes', '1']:
                        choice_input = "是"
                    elif user_choice in ['否', 'n', 'no', '0']:
                        choice_input = "否"
                    else:
                        print("请输入有效选择：是/否")
                        continue
                    
                    # 继续执行workflow处理用户选择
                    print(f"\n🤖 正在处理您的选择...")
                    result = workflow.continue_workflow(session_id, choice_input)
                    print(format_state_output(result))
                
                session_counter += 1
                
            except Exception as e:
                # 使用新的错误处理
                error_context = create_error_context(
                    session_id=session_id,
                    user_id="interactive_user"
                )
                error_info = handle_error(e, error_context, reraise=False)
                print(f"\n❌ 处理过程中发生错误: {error_info['message']}")
                print("请检查您的输入或稍后重试")
        
        except KeyboardInterrupt:
            print("\n\n感谢使用天文科研Agent系统！")
            break
        except EOFError:
            print("\n\n感谢使用天文科研Agent系统！")
            break


def single_query_mode(workflow: ImprovedAstroWorkflow, query: str, session_id: Optional[str] = None):
    """单次查询模式"""
    if not session_id:
        session_id = f"single_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n🤖 正在处理查询: {query}")
    
    try:
        result = workflow.execute_workflow(session_id, query)
        print(format_state_output(result))
        
        # 检查是否需要等待用户选择
        while result.get('awaiting_user_choice', False):
            print("\n请选择 (是/否): ", end="")
            user_choice = input().strip().lower()
            
            if user_choice in ['是', 'y', 'yes', '1']:
                choice_input = "是"
            elif user_choice in ['否', 'n', 'no', '0']:
                choice_input = "否"
            else:
                print("请输入有效选择：是/否")
                continue
            
            # 继续执行workflow处理用户选择
            print(f"\n🤖 正在处理您的选择...")
            result = workflow.continue_workflow(session_id, choice_input)
            print(format_state_output(result))
        
        return result
    except Exception as e:
        # 使用新的错误处理
        error_context = create_error_context(
            session_id=session_id,
            user_id="single_query_user"
        )
        error_info = handle_error(e, error_context, reraise=False)
        print(f"\n❌ 处理过程中发生错误: {error_info['message']}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='改进的天文科研Agent系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main_improved.py                           # 交互模式
  python main_improved.py -q "什么是黑洞？"           # 单次查询
  python main_improved.py --status                  # 查看系统状态
  python main_improved.py --config custom.yaml     # 使用自定义配置
"""
    )
    
    parser.add_argument(
        '-q', '--query',
        type=str,
        help='单次查询模式，直接处理指定问题'
    )
    
    parser.add_argument(
        '-s', '--session-id',
        type=str,
        help='指定会话ID（用于单次查询模式）'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='显示系统状态并退出'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='指定配置文件路径'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='以JSON格式输出结果（仅用于单次查询模式）'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志信息'
    )
    
    parser.add_argument(
        '--no-memory',
        action='store_true',
        help='不使用内存存储会话状态'
    )
    
    args = parser.parse_args()
    
    # 配置日志级别
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 初始化工作流
        print("🚀 正在初始化改进的天文科研Agent系统...")
        workflow = ImprovedAstroWorkflow(args.config, use_memory=not args.no_memory)
        print("✅ 系统初始化完成")
        
        # 处理不同模式
        if args.status:
            # 状态查看模式
            status = workflow.get_system_status()
            if args.json:
                print(json.dumps(status, indent=2, ensure_ascii=False))
            else:
                print("\n系统状态:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
        
        elif args.query:
            # 单次查询模式
            if not args.json:
                print_banner()
            
            result = single_query_mode(workflow, args.query, args.session_id)
            
            if args.json and result:
                # 输出JSON格式结果
                json_result = {
                    'session_id': result.get('session_id'),
                    'user_type': result.get('user_type'),
                    'task_type': result.get('task_type'),
                    'current_step': result.get('current_step'),
                    'is_complete': result.get('is_complete'),
                    'qa_response': result.get('qa_response'),
                    'final_answer': result.get('final_answer'),
                    'error_info': result.get('error_info')
                }
                print(json.dumps(json_result, indent=2, ensure_ascii=False))
        
        else:
            # 交互模式
            print_banner()
            interactive_mode(workflow)
    
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 系统启动失败: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
