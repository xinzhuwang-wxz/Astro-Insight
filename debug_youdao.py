#!/usr/bin/env python3
"""
调试有道翻译返回值
"""

import translators as ts

def debug_youdao():
    """调试有道翻译的返回值"""
    test_text = "Hello World"
    
    print(f"测试文本: {test_text}")
    
    try:
        result = ts.translate_text(test_text, translator='youdao', from_language='en', to_language='zh-CHS')
        print(f"返回值类型: {type(result)}")
        print(f"返回值内容: {result}")
        print(f"返回值repr: {repr(result)}")
        
        # 检查是否有特定属性
        if hasattr(result, 'translation'):
            print(f"translation属性: {result.translation}")
        if hasattr(result, 'text'):
            print(f"text属性: {result.text}")
        if hasattr(result, '__dict__'):
            print(f"所有属性: {result.__dict__}")
            
    except Exception as e:
        print(f"有道翻译失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_youdao()