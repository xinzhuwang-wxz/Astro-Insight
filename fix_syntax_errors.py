#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复nodes.py中的语法错误
"""

import re

def fix_syntax_errors():
    """修复语法错误"""
    
    with open('src/graph/nodes.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复模式：error_state = { error_state["field"] = value }
    pattern = r'(\s+)error_state = \{\s*\n(\s+)error_state\["([^"]+)"\] = \{\s*\n([^}]+)\s*\n(\s+)\}\s*\n(\s+)error_state\["([^"]+)"\] = ([^\n]+)\s*\n(\s+)\}'
    
    def replace_func(match):
        indent1 = match.group(1)
        indent2 = match.group(2)
        field1 = match.group(3)
        value1_content = match.group(4)
        indent3 = match.group(5)
        indent4 = match.group(6)
        field2 = match.group(7)
        value2 = match.group(8)
        indent5 = match.group(9)
        
        return f'{indent1}error_state = {{\n{indent2}"{field1}": {{\n{value1_content}\n{indent3}}},\n{indent4}"{field2}": {value2}\n{indent5}}}'
    
    # 应用修复
    content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
    
    # 修复简单的模式：error_state = { error_state["field"] = value }
    simple_pattern = r'(\s+)error_state = \{\s*\n(\s+)error_state\["([^"]+)"\] = ([^\n]+)\s*\n(\s+)\}'
    
    def simple_replace_func(match):
        indent1 = match.group(1)
        indent2 = match.group(2)
        field = match.group(3)
        value = match.group(4)
        indent3 = match.group(5)
        
        return f'{indent1}error_state = {{\n{indent2}"{field}": {value}\n{indent3}}}'
    
    content = re.sub(simple_pattern, simple_replace_func, content, flags=re.MULTILINE)
    
    # 写回文件
    with open('src/graph/nodes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 语法错误修复完成")

if __name__ == "__main__":
    fix_syntax_errors()