# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import sys
import subprocess
import tempfile
import time
import traceback
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional, Dict, Any, List
from pathlib import Path

from .types import CodeExecutionResult, ExecutionStatus


class CodeExecutor:
    """代码执行器 - 安全执行生成的Python代码"""
    
    def __init__(self, timeout: int = 60, output_dir: str = "output"):
        self.timeout = timeout
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 安全的执行环境设置
        self.allowed_imports = {
            'pandas', 'numpy', 'matplotlib', 'seaborn', 'sklearn', 'scipy',
            'astropy', 'astroquery', 'plotly', 'warnings', 'os', 'sys',
            'pathlib', 'json', 'csv', 're', 'math', 'statistics', 'datetime',
            'collections', 'itertools', 'functools', 'operator'
        }
        
        # 禁止的操作
        self.forbidden_patterns = [
            'import subprocess', 'import os.system', '__import__',
            'exec(', 'eval(', 'open(', 'file(', 'input(',
            'raw_input(', 'execfile(', 'compile('
        ]
    
    def execute_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> CodeExecutionResult:
        """执行代码并返回结果"""
        start_time = time.time()
        
        # 预处理代码
        processed_code = self._preprocess_code(code)
        
        # 安全检查
        safety_check = self._safety_check(processed_code)
        if not safety_check["safe"]:
            return CodeExecutionResult(
                status=ExecutionStatus.ERROR,
                code=code,
                output=None,
                error=f"安全检查失败: {safety_check['reason']}",
                execution_time=time.time() - start_time,
                generated_files=[]
            )
        
        # 执行代码
        try:
            result = self._execute_in_sandbox(processed_code, context or {})
            execution_time = time.time() - start_time
            
            # 检查生成的文件
            generated_files = self._find_generated_files()
            
            return CodeExecutionResult(
                status=ExecutionStatus.SUCCESS if result["success"] else ExecutionStatus.ERROR,
                code=code,
                output=result["output"],
                error=result["error"],
                execution_time=execution_time,
                generated_files=generated_files
            )
            
        except Exception as e:
            return CodeExecutionResult(
                status=ExecutionStatus.ERROR,
                code=code,
                output=None,
                error=f"执行异常: {str(e)}",
                execution_time=time.time() - start_time,
                generated_files=[]
            )
    
    def _preprocess_code(self, code: str) -> str:
        """预处理代码"""
        lines = code.split('\n')
        processed_lines = []
        
        for line in lines:
            # 处理输出目录
            if 'plt.savefig' in line or '.savefig' in line:
                # 确保图片保存到output目录
                if 'output/' not in line:
                    line = line.replace('plt.savefig(', f'plt.savefig("{self.output_dir}/')
                    line = line.replace('.savefig(', f'.savefig("{self.output_dir}/')
            
            # 处理文件路径
            if 'pd.read_csv' in line or 'pd.read_' in line:
                # 确保使用正确的路径分隔符
                line = line.replace('\\', '/')
            
            processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _safety_check(self, code: str) -> Dict[str, Any]:
        """代码安全检查"""
        # 检查禁止的模式
        for pattern in self.forbidden_patterns:
            if pattern in code:
                return {"safe": False, "reason": f"禁止的操作: {pattern}"}
        
        # 检查导入的模块
        import ast
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in self.allowed_imports:
                            return {"safe": False, "reason": f"禁止导入模块: {module_name}"}
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        if module_name not in self.allowed_imports:
                            return {"safe": False, "reason": f"禁止导入模块: {module_name}"}
        except SyntaxError as e:
            return {"safe": False, "reason": f"语法错误: {str(e)}"}
        
        return {"safe": True, "reason": ""}
    
    def _execute_in_sandbox(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """在沙箱环境中执行代码"""
        output_buffer = StringIO()
        error_buffer = StringIO()
        
        try:
            # 准备执行环境
            import builtins
            globals_dict = {
                '__builtins__': {
                    'print': print,
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'list': list,
                    'dict': dict,
                    'tuple': tuple,
                    'set': set,
                    'range': range,
                    'enumerate': enumerate,
                    'zip': zip,
                    'sorted': sorted,
                    'sum': sum,
                    'max': max,
                    'min': min,
                    'abs': abs,
                    'round': round,
                    'type': type,
                    'isinstance': isinstance,
                    'hasattr': hasattr,
                    'getattr': getattr,
                    'setattr': setattr,
                    '__import__': __import__,  # 允许import
                    'locals': locals,         # 添加 locals
                    'globals': globals,       # 添加 globals
                },
                '__name__': '__main__',       # 添加 __name__
                '__file__': '<generated_code>',  # 添加 __file__
            }
            globals_dict.update(context)
            
            # 重定向输出
            with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                exec(code, globals_dict)
            
            return {
                "success": True,
                "output": output_buffer.getvalue(),
                "error": None
            }
            
        except Exception as e:
            error_info = error_buffer.getvalue()
            if not error_info:
                error_info = str(e)
            
            # 添加详细的错误信息
            error_details = f"{error_info}\n\n详细错误:\n{traceback.format_exc()}"
            
            return {
                "success": False,
                "output": output_buffer.getvalue(),
                "error": error_details
            }
    
    def _find_generated_files(self) -> List[str]:
        """查找执行过程中生成的文件"""
        generated_files = []
        
        if self.output_dir.exists():
            for file_path in self.output_dir.iterdir():
                if file_path.is_file():
                    generated_files.append(str(file_path))
        
        return generated_files
    
    def clean_output_dir(self) -> None:
        """清理输出目录"""
        if self.output_dir.exists():
            for file_path in self.output_dir.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"清理文件失败 {file_path}: {e}")
    
    def validate_code_syntax(self, code: str) -> Dict[str, Any]:
        """验证代码语法"""
        try:
            compile(code, '<string>', 'exec')
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": f"语法错误: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"编译错误: {str(e)}"}
