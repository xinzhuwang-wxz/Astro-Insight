from enum import Enum
from dataclasses import dataclass
from typing import List

class AnalysisType(Enum):
    CLASSIFICATION = "classification"

class ObjectType(Enum):
    STAR = "star"
    GALAXY = "galaxy"
    NEBULA = "nebula"
    SUPERNOVA = "supernova"
    QUASAR = "quasar"
    ASTEROID = "asteroid"
    COMET = "comet"
    EXOPLANET = "exoplanet"

@dataclass
class CodeTemplate:
    name: str
    description: str
    analysis_type: AnalysisType
    object_types: List[ObjectType]
    required_libraries: List[str]
    template_code: str

# 测试最小版本
templates = {}
templates["simple_classification"] = CodeTemplate(
    name="天体分类检索",
    description="从天文数据库检索天体分类信息",
    analysis_type=AnalysisType.CLASSIFICATION,
    object_types=[
        ObjectType.STAR,
        ObjectType.GALAXY,
        ObjectType.NEBULA,
        ObjectType.SUPERNOVA,
        ObjectType.QUASAR,
        ObjectType.ASTEROID,
        ObjectType.COMET,
        ObjectType.EXOPLANET,
    ],
    required_libraries=["astropy", "astroquery", "pandas"],
    template_code="""#!/usr/bin/env python3
# 天体分类检索代码
print("Hello World")
"""
)

print("最小测试通过")