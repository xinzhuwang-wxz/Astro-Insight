# 🌟 Astro-Insight: 天文数据智能分析系统

## 🚀 项目概述

Astro-Insight是一个基于LangGraph的智能天文数据分析系统，专门设计用于处理天文数据的智能查询、分析和代码生成。

## ✨ 核心功能

### 🤖 **代码生成Agent** (新增核心功能)
- **自然语言到代码**: 将用户的自然语言需求转换为可执行的Python代码
- **智能数据集选择**: 自动识别和选择最适合的数据集
- **安全代码执行**: 在受控沙箱环境中安全执行生成的代码
- **错误自动修复**: 智能检测和修复代码中的语法错误
- **可视化结果**: 自动生成图表和分析结果

### 📊 **支持的数据集**
1. **SDSS Galaxy Classification DR18** (100,000条记录)
   - 银河系分类数据，43个特征列
   - 适合特征分析、可视化、回归分析

2. **Star Type Prediction Dataset** (240条记录, 6类)
   - 恒星类型分类数据，平衡的多分类数据集
   - 适合机器学习分类任务

## 📁 项目结构

```
Astro-Insight/
├── src/coder/                    # 🆕 代码生成Agent核心模块
│   ├── agent.py                  # 核心Agent逻辑
│   ├── workflow.py               # LangGraph工作流
│   ├── dataset_selector.py       # 数据集选择器
│   ├── executor.py               # 代码执行器
│   ├── prompts.py                # 提示模板
│   └── types.py                  # 数据类型定义
├── dataset/                      # 数据集目录
│   ├── dataset/                  # 实际数据文件
│   └── full_description/         # 数据集描述文件
├── output/                       # 🆕 代码执行输出目录
├── conf.yaml                     # 🔧 LLM API配置
├── CODER_ARCHITECTURE.md         # 🆕 架构文档
├── ENVIRONMENT_SETUP.md          # 🆕 环境配置文档
└── interactive_coder_demo.py     # 🆕 交互式演示程序
```

## 🔧 快速开始

### 1. 环境准备
```bash
# 使用Anaconda环境（推荐）
conda activate base

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API密钥
编辑 `conf.yaml` 文件，添加你的LLM API密钥：
```yaml
CODE_MODEL:
  base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
  model: "doubao-1-5-pro-32k-250115"
  api_key: "your_api_key_here"
```

### 3. 运行代码生成Agent
```python
from src.coder.workflow import CodeGenerationWorkflow

# 创建工作流
workflow = CodeGenerationWorkflow()

# 执行任务
result = workflow.run("使用星类型数据集训练一个分类模型")
```

### 4. 交互式使用
```bash
python interactive_coder_demo.py
```

## 🎯 使用示例

### **数据探索**
```python
# 查看数据基本信息
workflow.run("展示6_class_csv数据集的前5行和基本统计信息")

# 数据分布分析
workflow.run("分析星类型数据集中各类别的分布情况")
```

### **数据可视化**
```python
# 创建分布图
workflow.run("创建星类型分布饼图")

# 特征关系分析
workflow.run("绘制温度和光度的散点图，按星类型着色")
```

### **机器学习**
```python
# 训练分类模型
workflow.run("使用星类型数据训练随机森林分类器，评估性能")

# 模型比较
workflow.run("比较不同算法在星类型分类上的性能")
```

## 📊 新增文件详情

### **核心代码生成模块** (10个文件)
- `src/coder/__init__.py` - 模块导出接口
- `src/coder/types.py` - 数据类型和状态定义  
- `src/coder/agent.py` - 核心Agent业务逻辑
- `src/coder/workflow.py` - LangGraph工作流编排
- `src/coder/dataset_selector.py` - 智能数据集发现
- `src/coder/prompts.py` - LLM提示模板管理
- `src/coder/executor.py` - 安全代码执行沙箱
- `src/coder/test_coder.py` - 完整测试套件
- `src/coder/example_usage.py` - 使用示例代码
- `src/coder/README.md` - 组件详细文档

### **配置和文档** (4个文件)
- `CODER_ARCHITECTURE.md` - 系统架构和逻辑文档
- `ENVIRONMENT_SETUP.md` - 虚拟环境配置说明
- `CODER_SETUP.md` - 快速安装指南
- `interactive_coder_demo.py` - 交互式演示程序

### **数据集扩展** (2个新数据集)
- `dataset/dataset/6_class_csv.csv` - 星类型分类数据
- `dataset/full_description/Star-dataset to predict star type.txt` - 描述文件

### **配置更新**
- `conf.yaml` - 添加了CODE_MODEL配置
- `src/config/agents.py` - 添加了coder agent映射

## 🔗 相关链接

- [详细架构文档](CODER_ARCHITECTURE.md)
- [环境配置指南](ENVIRONMENT_SETUP.md)
- [快速开始指南](CODER_SETUP.md)
- [项目网站](https://xinzhuwang-wxz.github.io/Astro-Insight/)

---

## 📈 项目统计

- **核心模块**: 10个文件
- **文档文件**: 4个
- **配置文件**: 2个
- **数据集**: 2个 (SDSS + Star Types)
- **代码行数**: ~2000行
- **支持任务**: 简单→中等→复杂 (3个级别)

---

**最后更新**: 2025-01-09  
**版本**: v1.0.0 - 代码生成Agent正式版  
**状态**: ✅ 核心功能完成，支持多数据集智能代码生成  
**维护者**: AI Assistant