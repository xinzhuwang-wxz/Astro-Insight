#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天文科研Agent系统主程序入口

提供命令行交互界面，支持：
- 交互式问答模式
- 单次查询模式
- 系统状态查看
- 会话管理
"""

import sys
import os
import argparse
import json
from typing import Dict, Any, Optional
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.workflow import AstroWorkflow, execute_astro_workflow
from src.graph.types import AstroAgentState


def print_banner():
    """打印系统横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    天文科研Agent系统                          ║
║                  Astro Research Agent System                ║
║                                                              ║
║  支持爱好者问答和专业用户的数据检索、文献综述功能              ║
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
"""
    print(help_text)


def format_state_output(state: AstroAgentState) -> str:
    """格式化状态输出"""
    output = []
    output.append("=" * 60)
    
    # 基本信息
    user_type = state.get('user_type', '未识别')
    task_type = state.get('task_type', '未分类')
    current_step = state.get('current_step', '未知')
    is_complete = state.get('is_complete', False)
    
    output.append(f"用户类型: {user_type}")
    output.append(f"任务类型: {task_type}")
    output.append(f"当前步骤: {current_step}")
    output.append(f"处理状态: {'完成' if is_complete else '进行中'}")
    
    # QA响应
    if state.get('qa_response'):
        output.append("\n【QA回答】")
        output.append(state['qa_response'])
    
    # 数据检索配置
    if state.get('retrieval_config'):
        config = state['retrieval_config']
        output.append("\n【数据检索配置】")
        output.append(f"数据源: {config.get('data_source', '未配置')}")
        output.append(f"查询类型: {config.get('query_type', '未配置')}")
        output.append(f"输出格式: {config.get('output_format', '未配置')}")
    
    # 文献综述配置
    if state.get('literature_config'):
        config = state['literature_config']
        output.append("\n【文献综述配置】")
        databases = config.get('databases', [])
        output.append(f"数据库: {', '.join(databases) if databases else '未配置'}")
        output.append(f"时间范围: {config.get('time_range', '未配置')}")
        output.append(f"搜索策略: {config.get('search_strategy', '未配置')}")
    
    # 错误信息
    if state.get('error_info'):
        error = state['error_info']
        output.append("\n【错误信息】")
        output.append(f"错误类型: {error.get('error_type', '未知')}")
        output.append(f"错误详情: {error.get('error', '未知错误')}")
    
    # 执行历史
    history = state.get('execution_history', [])
    if history:
        output.append("\n【执行历史】")
        for i, step in enumerate(history, 1):
            node = step.get('node', '未知节点')
            action = step.get('action', '未知操作')
            output.append(f"  {i}. {node}: {action}")
    
    output.append("=" * 60)
    return "\n".join(output)


def interactive_mode(workflow: AstroWorkflow):
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
                session_counter += 1
                
            except Exception as e:
                print(f"\n❌ 处理过程中发生错误: {str(e)}")
                print("请检查您的输入或稍后重试")
        
        except KeyboardInterrupt:
            print("\n\n感谢使用天文科研Agent系统！")
            break
        except EOFError:
            print("\n\n感谢使用天文科研Agent系统！")
            break


def single_query_mode(workflow: AstroWorkflow, query: str, session_id: Optional[str] = None):
    """单次查询模式"""
    if not session_id:
        session_id = f"single_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n🤖 正在处理查询: {query}")
    
    try:
        result = workflow.execute_workflow(session_id, query)
        print(format_state_output(result))
        return result
    except Exception as e:
        print(f"\n❌ 处理过程中发生错误: {str(e)}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='天文科研Agent系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                           # 交互模式
  python main.py -q "什么是黑洞？"           # 单次查询
  python main.py --status                  # 查看系统状态
  python main.py --config custom.yaml     # 使用自定义配置
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
    
    args = parser.parse_args()
    
    # 配置日志级别
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 初始化工作流
        print("🚀 正在初始化天文科研Agent系统...")
        workflow = AstroWorkflow(args.config)
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
                    'retrieval_config': result.get('retrieval_config'),
                    'literature_config': result.get('literature_config'),
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