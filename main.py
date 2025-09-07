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
    """
    格式化状态输出
    
    Args:
        state: 状态字典
        
    Returns:
        格式化的状态字符串
    """
    output = []
    output.append("=" * 60)
    
    # 调试输出：显示状态中的所有字段
    print("\n=== DEBUG: 状态中的所有字段 ===")
    for key, value in state.items():
        print(f"{key}: {type(value)} = {value}")
    print("=== DEBUG END ===\n")
    
    # 基本信息
    user_type = state.get('user_type', '未识别')
    task_type = state.get('task_type', '未分类')
    current_step = state.get('current_step', '未知')
    is_complete = state.get('is_complete', False)
    
    output.append(f"用户类型: {user_type}")
    output.append(f"任务类型: {task_type}")
    output.append(f"当前步骤: {current_step}")
    output.append(f"处理状态: {'完成' if is_complete else '进行中'}")
    
    # QA响应 - 优化显示逻辑
    # 根据文档要求：
    # 1. 用户选择'否'后直接退出，不重复显示QA内容
    # 2. 用户选择'是'后直接进入专业模式，不重复显示QA内容
    # 3. 只在初次QA回答且等待用户选择时显示
    user_choice = state.get('user_choice')
    current_step = state.get('current_step', '')
    awaiting_choice = state.get('awaiting_user_choice', False)
    
    should_show_qa = False
    if state.get('qa_response'):
        # 只在以下情况显示QA回答：
        # 1. 等待有效选择输入（waiting_for_valid_choice）且正在等待选择
        if current_step == 'waiting_for_valid_choice' and awaiting_choice:
            should_show_qa = True
        # 用户已做出选择后不再显示QA内容
        elif user_choice in ['end', 'more_info'] or current_step in ['user_chose_end', 'user_chose_more_info']:
            should_show_qa = False
        # 已进入后续流程不显示QA内容
        elif current_step in ['classification_completed', 'task_completed', 'task_selected']:
            should_show_qa = False
        # 专业用户跳过QA显示
        elif user_type == 'professional':
            should_show_qa = False
        # 来自user_choice_handler的流程不显示QA内容
        elif state.get('from_user_choice'):
            should_show_qa = False
        # final_answer被清空时不显示QA内容
        elif not state.get('final_answer'):
            should_show_qa = False
    
    if should_show_qa:
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
    
    # 分类结果 - 检查多个可能的位置
    classification_result = None
    
    # 1. 检查final_answer中的classification_result
    final_answer = state.get('final_answer')
    if final_answer and isinstance(final_answer, dict) and final_answer.get('classification_result'):
        classification_result = final_answer['classification_result']
    
    # 2. 检查state中的classification_result
    elif state.get('classification_result'):
        classification_result = state['classification_result']
    
    # 3. 检查execution_history中的分类结果
    else:
        history = state.get('execution_history', [])
        for step in history:
            if (step.get('node') == 'classification_config_command_node' and 
                step.get('action') == 'celestial_classification' and 
                isinstance(step.get('output'), dict)):
                classification_result = step['output']
                break
    
    if classification_result:
        output.append("\n【天体分类结果】")
        
        # 获取分类结果的详细信息
        if 'classification_result' in classification_result:
            result = classification_result['classification_result']
            output.append(f"天体名称: {result.get('object_name', '未知')}")
            output.append(f"主要分类: {result.get('primary_category', '未分类')}")
            output.append(f"子分类: {result.get('subcategory', '未知')}")
            output.append(f"详细分类: {result.get('detailed_classification', '未知')}")
            output.append(f"置信度: {result.get('confidence_level', '未知')}")
            
            # 关键特征
            key_features = result.get('key_features', [])
            if key_features:
                output.append(f"关键特征: {', '.join(key_features)}")
            
            # 坐标信息
            coordinates = result.get('coordinates', {})
            if coordinates and coordinates.get('ra') != '未知':
                output.append(f"坐标: RA={coordinates.get('ra', '未知')}, DEC={coordinates.get('dec', '未知')}")
            
            # 附加信息
            additional_info = result.get('additional_info', {})
            if additional_info:
                info_parts = []
                for key, value in additional_info.items():
                    if value != '未知':
                        info_parts.append(f"{key}={value}")
                if info_parts:
                    output.append(f"附加信息: {', '.join(info_parts)}")
        
        # 解释说明
        if classification_result.get('explanation'):
            output.append(f"解释: {classification_result['explanation']}")
        
        # 建议
        suggestions = classification_result.get('suggestions', [])
        if suggestions:
            output.append(f"建议: {', '.join(suggestions)}")
    
    # 生成的代码
    if state.get('generated_code'):
        code = state['generated_code']
        metadata = state.get('code_metadata', {})
        
        output.append("\n【生成的代码】")
        output.append(f"代码长度: {len(code)} 字符")
        output.append(f"代码行数: {len(code.splitlines())} 行")
        
        # 显示代码元数据
        if metadata:
            output.append(f"任务类型: {metadata.get('task_type', '未知')}")
            output.append(f"优化级别: {metadata.get('optimization_level', '未知')}")
            output.append(f"语法验证: {'通过' if metadata.get('syntax_valid') else '未通过'}")
            
            # 天体信息
            celestial_info = metadata.get('celestial_info', {})
            if celestial_info:
                output.append(f"天体类型: {celestial_info.get('object_type', '未知')}")
                output.append(f"观测方法: {celestial_info.get('observation_method', '未知')}")
        
        # 执行结果
        execution_result = state.get('execution_result', {})
        if execution_result:
            output.append("\n【执行结果】")
            output.append(f"执行状态: {execution_result.get('status', '未知')}")
            if execution_result.get('output'):
                output.append(f"输出信息: {execution_result['output']}")
            if execution_result.get('error_message'):
                output.append(f"错误信息: {execution_result['error_message']}")
            if execution_result.get('execution_time'):
                import datetime
                exec_time = datetime.datetime.fromtimestamp(execution_result['execution_time'])
                output.append(f"执行时间: {exec_time.strftime('%H:%M:%S')}")
        
        # 显示实际的代码内容
        output.append("\n【代码内容】")
        output.append("```python")
        output.append(code)
        output.append("```")
    
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
            # 优先显示task_type，然后是action，最后是未知操作
            if 'task_type' in step:
                action = step['task_type']
            elif 'action' in step:
                action = step['action']
            else:
                action = '未知操作'
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
                    # 不传递choice_input作为新的user_input，让workflow内部处理用户选择
                    result = workflow.continue_workflow(session_id, choice_input)
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
            # 不传递choice_input作为新的user_input，让workflow内部处理用户选择
            result = workflow.continue_workflow(session_id, choice_input)
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