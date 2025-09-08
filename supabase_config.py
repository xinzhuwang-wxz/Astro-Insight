#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase数据库配置
"""

import os
from typing import Dict, Any

# Supabase配置
SUPABASE_CONFIG = {
    "url": "https://lciwqkzalvdhuxhlqcdw.supabase.co",
    "anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjaXdxa3phbHZkaHV4aGxxY2R3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzE2MDc0MiwiZXhwIjoyMDcyNzM2NzQyfQ.Df95x4K-ugcXPNS2b4AG-dEB31kUybk5szWTxl2Vrls",
    "service_role_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxjaXdxa3phbHZkaHV4aGxxY2R3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzE2MDc0MiwiZXhwIjoyMDcyNzM2NzQyfQ.Df95x4K-ugcXPNS2b4AG-dEB31kUybk5szWTxl2Vrls"
}

# 数据存储配置
DATA_STORAGE_CONFIG = {
    "base_path": "./data/analysis_results",
    "formats": ["csv", "json", "xlsx"],
    "default_format": "csv"
}

# 可视化配置
VISUALIZATION_CONFIG = {
    "default_style": "seaborn",
    "figure_size": (12, 8),
    "dpi": 300,
    "formats": ["png", "pdf", "svg"],
    "default_format": "png"
}

def get_supabase_config() -> Dict[str, str]:
    """获取Supabase配置"""
    return SUPABASE_CONFIG

def get_data_storage_config() -> Dict[str, Any]:
    """获取数据存储配置"""
    return DATA_STORAGE_CONFIG

def get_visualization_config() -> Dict[str, Any]:
    """获取可视化配置"""
    return VISUALIZATION_CONFIG
