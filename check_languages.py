#!/usr/bin/env python3

try:
    from deep_translator import GoogleTranslator
    
    # 获取支持的语言
    translator = GoogleTranslator(source='auto', target='en')
    supported_languages = translator.get_supported_languages()
    
    print("支持的语言代码:")
    for i, lang in enumerate(supported_languages[:20]):
        print(f"{lang}: {lang}")
    
    print("\n中文相关的语言代码:")
    chinese_langs = [lang for lang in supported_languages if 'zh' in lang or 'chinese' in lang.lower()]
    for lang in chinese_langs:
        print(f"{lang}: {lang}")
        
    print(f"\n总共支持 {len(supported_languages)} 种语言")
except Exception as e:
    print(f"错误: {e}")