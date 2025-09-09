# 🌟 Astro-Insight 天文科研Agent系统

一个基于 LangGraph 的天文科研助手与数据智能分析系统，支持爱好者问答与专业用户的数据检索、文献综述与代码生成。

## 🚀 项目概述

- 智能问答、天体分类、网络检索与文献综述
- 代码生成 Agent：将自然语言转为可执行 Python，支持安全执行与可视化

## ✨ 核心功能

- 🤖 智能问答：基于 LLM 的天文知识问答
- 🔍 天体分类：集成专业数据库（如 SIMBAD）的分类能力
- 📊 数据检索：支持多种天文数据源
- 🌐 网络搜索：集成 Tavily 搜索 API
- 📝 文献综述：自动检索并生成结构化综述
- 🧪 代码生成 Agent（新增）：
  - 自然语言到代码与图表
  - 智能数据集选择（内置 SDSS/Star Types）
  - 安全沙箱执行与错误自动修复

### 支持的数据集
1. SDSS Galaxy Classification DR18（约10万条，43特征）
2. Star Type Prediction Dataset（240条，6类）

## 快速开始

### 🚀 5分钟部署

1) 克隆与安装依赖
```bash
git clone https://github.com/xinzhuwang-wxz/Astro-Insight.git
cd Astro-Insight
pip install -r requirements.txt
```

2) 配置环境变量（必须，勿把密钥写入配置文件）
```bash
# 复制模板
copy env.template .env   # Windows
# cp env.template .env   # Linux/Mac

# 在 .env 填入真实密钥（示例）
TAVILY_API_KEY=tvly-dev-your_actual_api_key_here
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
```

3) 启动本地 LLM（可选：使用 Ollama）
```bash
ollama serve
ollama pull qwen2.5:7b
```

4) 运行与自检
```bash
python main.py          # 交互模式
python main.py -q "分类这个天体：M87"  # 单次查询
python main.py --status # 配置自检
```

### 代码生成 Agent 快速上手
```python
from src.coder.workflow import CodeGenerationWorkflow

workflow = CodeGenerationWorkflow()
result = workflow.run("使用星类型数据集训练一个分类模型并可视化结果")
```

常用指令示例：
```python
# 数据探索
workflow.run("展示6_class_csv数据集的前5行和基本统计信息")
workflow.run("分析星类型数据集中各类别的分布情况")

# 可视化
workflow.run("绘制温度-光度散点图，按星类型着色")

# 机器学习
workflow.run("使用星类型数据训练随机森林分类器并评估性能")
```

## 环境要求

- Python 3.8+
- 可选：Ollama（本地 LLM 服务）
- Tavily API Key（网络搜索）

## 环境变量管理与优先级

1. .env（最高）
2. 系统环境变量
3. conf.yaml（仅存放非敏感配置，不放密钥）

建议的 LLM 提供商配置：
- 本地：Ollama（`qwen2.5:7b` 推荐）
- 云端：OpenAI、DeepSeek、豆包、Claude、Gemini（在 .env 中设置对应 provider/model/base_url/api_key）

配置验证：
```bash
python main.py --status
```
正常：
```
✅ 环境变量配置正常
🚀 正在初始化天文科研Agent系统...
✅ 系统初始化完成
```

## 项目结构

```
Astro-Insight/
├── src/
│   ├── coder/                 # 代码生成 Agent 核心
│   │   ├── agent.py
│   │   ├── workflow.py
│   │   ├── dataset_selector.py
│   │   ├── executor.py
│   │   ├── prompts.py
│   │   └── types.py
│   ├── config/
│   ├── graph/
│   ├── llms/
│   ├── tools/
│   └── ...
├── dataset/
│   ├── dataset/
│   └── full_description/
├── output/
├── conf.yaml
├── env.template
├── main.py
└── requirements.txt
```

## 故障排除（节选）

- Tavily 未授权：检查 `.env` 中 `TAVILY_API_KEY`
- .env 未加载：确保根目录存在 `.env`
- API 密钥格式错误：确认提供商要求的格式

## 安全与合规

- `.env` 已加入 `.gitignore`，请勿提交真实密钥
- 推荐使用环境变量而非将密钥写入配置文件

## 许可证

MIT License

## 贡献

欢迎提交 Issue 与 Pull Request！
