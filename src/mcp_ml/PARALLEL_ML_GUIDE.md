# 并行ML训练流程使用指南

## 概述

本系统实现了并行ML训练流程功能，支持同时运行多个配置文件，自动管理GPU显存分配，并提供完整的进程监控和错误处理机制。

## 功能特性

### 🚀 核心功能
- **并行执行**: 同时运行多个ML训练流程
- **GPU显存管理**: 自动分配GPU显存，避免显存冲突
- **进程监控**: 实时监控训练进度和状态
- **错误处理**: 完善的异常处理和恢复机制
- **日志管理**: 详细的执行日志和结果分析

### 🔧 技术特性
- **显存隔离**: 每个进程使用独立的GPU显存空间
- **配置隔离**: 为每个进程生成独立的配置文件
- **资源清理**: 自动清理临时文件和GPU资源
- **状态查询**: 实时查询执行状态和进度

## 文件结构

```
src/mcp_ml/
├── server.py                 # 主服务器文件（已添加并行功能）
├── parallel_executor.py      # 并行执行器
├── gpu_manager.py           # GPU显存管理器
├── config_manager.py        # 配置管理器
├── process_monitor.py       # 进程监控器
├── test_parallel.py         # 测试脚本
├── PARALLEL_ML_GUIDE.md     # 使用指南
└── config/
    ├── config1.yaml         # 配置文件1
    ├── config2.yaml         # 配置文件2
    └── config.yaml          # 默认配置文件
```

## 使用方法

### 1. 通过MCP工具调用

#### 启动并行训练
```python
# 调用 run_parallel_pipeline 工具
result = run_parallel_pipeline()
```

#### 查询执行状态
```python
# 调用 get_parallel_status 工具
status = get_parallel_status()
```

#### 停止执行
```python
# 调用 stop_parallel_execution 工具
result = stop_parallel_execution()
```

### 2. 直接使用并行执行器

```python
from parallel_executor import ParallelMLExecutor

# 创建执行器
configs = ["config/config1.yaml", "config/config2.yaml"]
executor = ParallelMLExecutor(configs)

# 运行并行流程
results = executor.run_parallel()

# 获取状态
status = executor.get_status()

# 停止执行
executor.stop_execution()
```

## 配置说明

### 配置文件要求

每个配置文件需要包含以下基本结构：

```yaml
# 数据预处理配置
data_preprocessing:
  image_dir: 'sample_data/images'
  batch_size: 32  # 会根据GPU显存自动调整
  split_ratios:
    train: 0.8
    validation: 0.1
    test: 0.1
  random_state: 42

# 模型训练配置
model_training:
  epochs: 4
  checkpoint:
    filepath: 'best_model.keras'  # 会自动添加进程标识

# 结果分析配置
result_analysis:
  model_path: 'best_model.keras'  # 会自动添加进程标识
```

### 自动配置修改

系统会自动为每个进程修改以下配置：

1. **模型保存路径**: 添加进程标识和时间戳
2. **Batch Size**: 根据GPU显存限制自动调整
3. **随机种子**: 为每个进程设置不同的随机种子
4. **日志配置**: 添加进程特定的日志信息

## GPU显存管理

### 显存分配策略

- **单GPU环境**: 每个进程分配50%显存
- **多GPU环境**: 每个进程使用不同的GPU
- **显存监控**: 实时监控显存使用情况
- **自动调整**: 根据显存限制自动调整batch_size

### 显存配置示例

```python
# 显存分配示例
gpu_allocations = [
    {
        'gpu_index': 0,
        'memory_limit': 4000,  # 4GB显存限制
        'memory_fraction': 0.5,
        'process_id': 0
    },
    {
        'gpu_index': 0,
        'memory_limit': 4000,  # 4GB显存限制
        'memory_fraction': 0.5,
        'process_id': 1
    }
]
```

## 进程监控

### 监控功能

- **实时日志**: 收集每个进程的训练日志
- **状态跟踪**: 监控进程运行状态
- **错误检测**: 自动检测和处理异常
- **资源监控**: 监控GPU和内存使用情况

### 日志格式

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "process_id": 0,
  "pid": 12345,
  "message": "Epoch 1/4 - loss: 0.5 - accuracy: 0.8",
  "type": "stdout"
}
```

## 错误处理

### 常见错误及解决方案

1. **GPU显存不足**
   - 自动调整batch_size
   - 减少模型复杂度
   - 使用CPU训练

2. **配置文件错误**
   - 检查YAML格式
   - 验证配置参数
   - 查看错误日志

3. **进程启动失败**
   - 检查Python环境
   - 验证依赖包
   - 查看系统资源

### 错误恢复机制

- **进程隔离**: 一个进程失败不影响其他进程
- **资源清理**: 自动清理失败的进程资源
- **日志保存**: 保存详细的错误日志
- **状态恢复**: 支持从失败点重新开始

## 性能优化

### 建议配置

1. **Batch Size调整**
   ```yaml
   # 根据GPU显存调整
   batch_size: 16  # 4GB显存
   batch_size: 32  # 8GB显存
   batch_size: 64  # 16GB显存
   ```

2. **模型复杂度**
   - 使用较小的模型进行并行训练
   - 考虑使用模型蒸馏技术
   - 优化网络结构

3. **数据预处理**
   - 使用数据缓存
   - 优化数据加载流程
   - 减少数据预处理时间

## 测试和验证

### 运行测试

```bash
# 运行测试脚本
python test_parallel.py
```

### 测试内容

- GPU管理器功能测试
- 配置管理器功能测试
- 并行执行器功能测试
- 进程监控功能测试

## 注意事项

### 使用限制

1. **GPU要求**: 需要支持CUDA的GPU
2. **内存要求**: 建议至少16GB系统内存
3. **存储要求**: 需要足够的磁盘空间存储模型和日志

### 最佳实践

1. **配置文件**: 确保配置文件格式正确
2. **资源监控**: 定期检查GPU和内存使用情况
3. **日志管理**: 定期清理日志文件
4. **错误处理**: 及时处理训练错误

## 故障排除

### 常见问题

1. **Q: 进程启动失败**
   A: 检查Python环境和依赖包，查看错误日志

2. **Q: GPU显存不足**
   A: 减少batch_size或使用更小的模型

3. **Q: 配置文件错误**
   A: 检查YAML格式和配置参数

4. **Q: 进程卡死**
   A: 使用stop_parallel_execution停止执行

### 获取帮助

- 查看日志文件获取详细错误信息
- 运行测试脚本验证系统功能
- 检查GPU和系统资源使用情况

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 支持基本的并行ML训练功能
- 实现GPU显存管理
- 添加进程监控和错误处理

---

**注意**: 本系统仍在开发中，如有问题请及时反馈。
