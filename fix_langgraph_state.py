#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph状态管理修复工具
系统性地修复所有state.copy()问题
"""

import re
import os
from typing import List, Tuple

def find_state_copy_issues(file_path: str) -> List[Tuple[int, str]]:
    """查找文件中的state.copy()问题"""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if 'state.copy()' in line:
                issues.append((i, line.strip()))
    
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
    
    return issues

def fix_state_copy_pattern(content: str) -> str:
    """修复state.copy()模式"""
    
    # 模式1: updated_state = state.copy()
    pattern1 = r'(\s+)updated_state = state\.copy\(\)'
    replacement1 = r'\1# 只更新必要的字段，避免复制整个状态\n\1updated_state = {'
    
    content = re.sub(pattern1, replacement1, content)
    
    # 模式2: error_state = state.copy()
    pattern2 = r'(\s+)error_state = state\.copy\(\)'
    replacement2 = r'\1# 只更新必要的字段，避免复制整个状态\n\1error_state = {'
    
    content = re.sub(pattern2, replacement2, content)
    
    return content

def fix_dictionary_assignments(content: str) -> str:
    """修复字典赋值问题"""
    
    # 查找并修复类似这样的模式：
    # updated_state = {
    # updated_state["field"] = value
    # updated_state["field2"] = value2
    
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # 检查是否是updated_state = {开始
        if re.match(r'\s*updated_state\s*=\s*\{', line):
            # 找到开始行
            start_line = i
            indent = len(line) - len(line.lstrip())
            
            # 查找后续的赋值行
            assignment_lines = []
            j = i + 1
            
            while j < len(lines) and lines[j].strip():
                next_line = lines[j]
                # 检查是否是赋值行
                if re.match(r'\s*updated_state\["[^"]+"\]\s*=', next_line):
                    assignment_lines.append(next_line)
                    j += 1
                else:
                    break
            
            if assignment_lines:
                # 重构这部分代码
                fixed_lines.append(line)  # 保留开始行
                
                # 添加所有赋值作为字典内容
                for assignment_line in assignment_lines:
                    # 提取字段名和值
                    match = re.match(r'\s*updated_state\["([^"]+)"\]\s*=\s*(.+)', assignment_line)
                    if match:
                        field_name = match.group(1)
                        field_value = match.group(2)
                        # 添加适当的缩进
                        fixed_lines.append(f'{" " * (indent + 4)}"{field_name}": {field_value},')
                
                # 添加结束括号
                fixed_lines.append(f'{" " * indent}' + '}')
                
                i = j  # 跳过已处理的行
            else:
                fixed_lines.append(line)
                i += 1
        else:
            fixed_lines.append(line)
            i += 1
    
    return '\n'.join(fixed_lines)

def fix_specific_patterns(content: str) -> str:
    """修复特定的问题模式"""
    
    # 修复这种模式：
    # updated_state = {
    # updated_state["field"] = value
    # updated_state["field2"] = value2
    # }
    
    # 使用更精确的正则表达式
    pattern = r'(\s+)updated_state\s*=\s*\{\s*\n(\s+)updated_state\["([^"]+)"\]\s*=\s*([^\n]+)\s*\n(\s+)updated_state\["([^"]+)"\]\s*=\s*([^\n]+)\s*\n(\s+)updated_state\["([^"]+)"\]\s*=\s*([^\n]+)\s*\n(\s+)\}'
    
    def replace_func(match):
        indent1 = match.group(1)
        indent2 = match.group(2)
        field1 = match.group(3)
        value1 = match.group(4)
        field2 = match.group(6)
        value2 = match.group(7)
        field3 = match.group(9)
        value3 = match.group(10)
        indent_end = match.group(11)
        
        return f'{indent1}updated_state = {{\n{indent2}"{field1}": {value1},\n{indent2}"{field2}": {value2},\n{indent2}"{field3}": {value3}\n{indent_end}}}'
    
    content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
    
    return content

def fix_file(file_path: str) -> bool:
    """修复单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 应用修复
        content = fix_state_copy_pattern(content)
        content = fix_dictionary_assignments(content)
        content = fix_specific_patterns(content)
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"修复文件失败 {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("🔧 LangGraph状态管理修复工具")
    print("=" * 50)
    
    # 要修复的文件
    target_files = [
        'src/graph/nodes.py'
    ]
    
    total_issues = 0
    fixed_files = 0
    
    for file_path in target_files:
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            continue
        
        print(f"\n🔍 检查文件: {file_path}")
        
        # 查找问题
        issues = find_state_copy_issues(file_path)
        if issues:
            print(f"   发现 {len(issues)} 个问题:")
            for line_num, line_content in issues:
                print(f"   行 {line_num}: {line_content}")
            total_issues += len(issues)
        
        # 修复文件
        if fix_file(file_path):
            print(f"   ✅ 文件已修复")
            fixed_files += 1
        else:
            print(f"   ℹ️  文件无需修复")
    
    print(f"\n📊 修复总结:")
    print(f"   发现问题: {total_issues} 个")
    print(f"   修复文件: {fixed_files} 个")
    
    if fixed_files > 0:
        print(f"\n✅ 修复完成！请测试修复后的系统。")
    else:
        print(f"\nℹ️  没有发现需要修复的问题。")

if __name__ == "__main__":
    main()

