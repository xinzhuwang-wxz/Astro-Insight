#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天体名称翻译器
将中文天体名称转换为Simbad可识别的英文名称
"""

class CelestialNameTranslator:
    """天体名称翻译器"""
    
    def __init__(self):
        # 中文到英文的天体名称映射表
        self.name_mapping = {
            # 恒星
            "太阳": "Sun",
            "天狼星": "Sirius",
            "织女星": "Vega",
            "牛郎星": "Altair",
            "北极星": "Polaris",
            "参宿四": "Betelgeuse",
            "参宿七": "Rigel",
            "心宿二": "Antares",
            "角宿一": "Spica",
            "大角星": "Arcturus",
            "五车二": "Capella",
            "南门二": "Alpha Centauri",
            "半人马座阿尔法星": "Alpha Centauri",
            "比邻星": "Proxima Centauri",
            
            # 行星
            "水星": "Mercury",
            "金星": "Venus",
            "地球": "Earth",
            "火星": "Mars",
            "木星": "Jupiter",
            "土星": "Saturn",
            "天王星": "Uranus",
            "海王星": "Neptune",
            "冥王星": "Pluto",
            
            # 星系
            "仙女座星系": "Andromeda Galaxy",
            "银河系": "Milky Way",
            "银河系中心": "Galactic Center",
            "银河系中心黑洞": "Sgr A*",
            "人马座A*": "Sgr A*",
            "M31": "M31",
            "M87": "M87",
            "M104": "M104",
            "M51": "M51",
            "M101": "M101",
            
            # 星云
            "蟹状星云": "Crab Nebula",
            "猎户座大星云": "Orion Nebula",
            "马头星云": "Horsehead Nebula",
            "鹰状星云": "Eagle Nebula",
            "三叶星云": "Trifid Nebula",
            "猫眼星云": "Cat's Eye Nebula",
            "环状星云": "Ring Nebula",
            "螺旋星云": "Helix Nebula",
            "M1": "M1",
            "M42": "M42",
            "M57": "M57",
            "M27": "M27",
            
            # 星团
            "昴宿星团": "Pleiades",
            "七姐妹星团": "Pleiades",
            "昴星团": "Pleiades",
            "毕宿星团": "Hyades",
            "M45": "M45",
            "M13": "M13",
            "M3": "M3",
            "M5": "M5",
            
            # 星座
            "猎户座": "Orion",
            "大熊座": "Ursa Major",
            "小熊座": "Ursa Minor",
            "仙女座": "Andromeda",
            "天鹅座": "Cygnus",
            "天鹰座": "Aquila",
            "天琴座": "Lyra",
            "半人马座": "Centaurus",
            "人马座": "Sagittarius",
            "天蝎座": "Scorpius",
            "狮子座": "Leo",
            "处女座": "Virgo",
            
            # 特殊天体
            "黑洞": "Black Hole",
            "脉冲星": "Pulsar",
            "类星体": "Quasar",
            "超新星": "Supernova",
            "中子星": "Neutron Star",
            "白矮星": "White Dwarf",
            "红巨星": "Red Giant",
            "蓝巨星": "Blue Giant",
            "超巨星": "Supergiant",
            
            # 常见天体编号
            "M87": "M87",
            "M31": "M31",
            "M104": "M104",
            "M51": "M51",
            "M101": "M101",
            "M42": "M42",
            "M1": "M1",
            "M57": "M57",
            "M27": "M27",
            "M45": "M45",
            "M13": "M13",
            "M3": "M3",
            "M5": "M5",
        }
        
        # 反向映射（英文到中文）
        self.reverse_mapping = {v: k for k, v in self.name_mapping.items()}
    
    def translate_to_english(self, chinese_name: str) -> str:
        """
        将中文天体名称转换为英文
        
        Args:
            chinese_name: 中文天体名称
            
        Returns:
            英文天体名称
        """
        # 直接查找映射
        if chinese_name in self.name_mapping:
            return self.name_mapping[chinese_name]
        
        # 模糊匹配
        for chinese, english in self.name_mapping.items():
            if chinese in chinese_name or chinese_name in chinese:
                return english
        
        # 如果没找到，返回原名称
        return chinese_name
    
    def translate_to_chinese(self, english_name: str) -> str:
        """
        将英文天体名称转换为中文
        
        Args:
            english_name: 英文天体名称
            
        Returns:
            中文天体名称
        """
        # 直接查找映射
        if english_name in self.reverse_mapping:
            return self.reverse_mapping[english_name]
        
        # 模糊匹配
        for english, chinese in self.reverse_mapping.items():
            if english.lower() in english_name.lower() or english_name.lower() in english.lower():
                return chinese
        
        # 如果没找到，返回原名称
        return english_name
    
    def is_chinese_name(self, name: str) -> bool:
        """
        判断是否为中文名称
        
        Args:
            name: 天体名称
            
        Returns:
            是否为中文
        """
        # 检查是否包含中文字符
        return any('\u4e00' <= char <= '\u9fff' for char in name)
    
    def get_simbad_query_name(self, name: str) -> str:
        """
        获取适合Simbad查询的名称
        
        Args:
            name: 天体名称
            
        Returns:
            适合Simbad查询的名称
        """
        # 如果是中文，先转换为英文
        if self.is_chinese_name(name):
            english_name = self.translate_to_english(name)
            return english_name
        
        # 如果已经是英文，直接返回
        return name
    
    def get_display_name(self, name: str, language: str = "zh") -> str:
        """
        获取显示名称
        
        Args:
            name: 天体名称
            language: 显示语言 ("zh" 或 "en")
            
        Returns:
            显示名称
        """
        if language == "zh":
            return self.translate_to_chinese(name)
        else:
            return self.translate_to_english(name)

# 测试函数
def test_translator():
    """测试翻译器"""
    translator = CelestialNameTranslator()
    
    print("🔍 测试天体名称翻译器")
    print("=" * 50)
    
    test_cases = [
        "太阳", "天狼星", "织女星", "仙女座星系", "蟹状星云",
        "猎户座大星云", "银河系中心黑洞", "M87", "M31", "M42",
        "昴宿星团", "参宿四", "心宿二", "人马座A*", "Crab Nebula"
    ]
    
    for name in test_cases:
        print(f"\n原始名称: {name}")
        print(f"是否中文: {translator.is_chinese_name(name)}")
        print(f"Simbad查询名: {translator.get_simbad_query_name(name)}")
        print(f"中文显示: {translator.get_display_name(name, 'zh')}")
        print(f"英文显示: {translator.get_display_name(name, 'en')}")

if __name__ == "__main__":
    test_translator()
