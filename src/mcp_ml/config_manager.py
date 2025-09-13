"""
配置管理器
负责动态修改配置文件、为每个进程生成独立配置、处理模型保存路径冲突
"""
import yaml
import os
import shutil
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, base_config_dir: str = "config", output_manager=None):
        self.base_config_dir = base_config_dir
        self.output_manager = output_manager
        self.temp_config_dir = "temp_configs"
        self._ensure_temp_dir()
    
    def _ensure_temp_dir(self):
        """确保临时配置目录存在"""
        if not os.path.exists(self.temp_config_dir):
            os.makedirs(self.temp_config_dir)
            logger.info(f"创建临时配置目录: {self.temp_config_dir}")
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_path}: {e}")
            raise
    
    def create_process_config(self, base_config_path: str, process_id: int, 
                            gpu_allocation: Dict, batch_size_scale: float = 1.0) -> str:
        """为特定进程创建独立的配置文件"""
        try:
            # 加载基础配置
            config = self.load_config(base_config_path)
            
            # 生成时间戳和进程标识
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            process_suffix = f"_process_{process_id}_{timestamp}"
            
            # 修改配置以适应并行运行
            modified_config = self._modify_config_for_process(
                config, process_id, gpu_allocation, batch_size_scale, process_suffix
            )
            
            # 生成新的配置文件路径
            base_name = os.path.basename(base_config_path).replace('.yaml', '')
            new_config_path = os.path.join(
                self.temp_config_dir, 
                f"{base_name}{process_suffix}.yaml"
            )
            
            # 保存修改后的配置
            with open(new_config_path, 'w', encoding='utf-8') as file:
                yaml.dump(modified_config, file, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            
            logger.info(f"为进程 {process_id} 创建配置文件: {new_config_path}")
            return new_config_path
            
        except Exception as e:
            logger.error(f"创建进程配置失败: {e}")
            raise
    
    def _modify_config_for_process(self, config: Dict, process_id: int, 
                                 gpu_allocation: Dict, batch_size_scale: float, 
                                 process_suffix: str) -> Dict:
        """修改配置以适应并行运行"""
        modified_config = config.copy()
        
        # 1. 修改模型保存路径，避免冲突
        if 'model_training' in modified_config and 'checkpoint' in modified_config['model_training']:
            original_path = modified_config['model_training']['checkpoint']['filepath']
            base_name = os.path.basename(original_path).replace('.keras', '')
            
            # 如果有输出管理器，使用输出目录
            if self.output_manager:
                new_path = self.output_manager.get_path('temp', f"{base_name}{process_suffix}.keras")
            else:
                new_path = f"{base_name}{process_suffix}.keras"
            
            modified_config['model_training']['checkpoint']['filepath'] = new_path
        
        # 2. 修改结果分析配置中的模型路径
        if 'result_analysis' in modified_config:
            if 'model_path' in modified_config['result_analysis']:
                original_path = modified_config['result_analysis']['model_path']
                base_name = os.path.basename(original_path).replace('.keras', '')
                
                # 如果有输出管理器，使用输出目录
                if self.output_manager:
                    new_path = self.output_manager.get_path('temp', f"{base_name}{process_suffix}.keras")
                else:
                    new_path = f"{base_name}{process_suffix}.keras"
                
                modified_config['result_analysis']['model_path'] = new_path
        
        # 3. 调整batch_size以适应显存限制
        if 'data_preprocessing' in modified_config:
            original_batch_size = modified_config['data_preprocessing'].get('batch_size', 32)
            new_batch_size = max(1, int(original_batch_size * batch_size_scale))
            modified_config['data_preprocessing']['batch_size'] = new_batch_size
            logger.info(f"进程 {process_id} batch_size 调整为: {new_batch_size}")
        
        # 4. 设置不同的随机种子，避免数据冲突
        if 'data_preprocessing' in modified_config:
            modified_config['data_preprocessing']['random_state'] = 42 + process_id * 100
        
        # 5. 添加进程特定的日志配置
        modified_config['process_info'] = {
            'process_id': process_id,
            'gpu_allocation': gpu_allocation,
            'timestamp': datetime.now().isoformat(),
            'batch_size_scale': batch_size_scale
        }
        
        # 6. 添加输出管理器信息
        if self.output_manager:
            modified_config['process_info']['output_manager'] = {
                'session_dir': self.output_manager.session_dir,
                'subdirs': self.output_manager.subdirs
            }
        
        return modified_config
    
    def create_parallel_configs(self, config_paths: List[str], 
                              gpu_allocations: List[Dict]) -> List[str]:
        """为多个进程创建并行配置文件"""
        process_configs = []
        
        for i, (config_path, gpu_allocation) in enumerate(zip(config_paths, gpu_allocations)):
            # 根据GPU显存限制调整batch_size
            memory_fraction = gpu_allocation.get('memory_fraction', 1.0)
            batch_size_scale = min(1.0, memory_fraction * 1.5)  # 保守的显存使用
            
            process_config = self.create_process_config(
                config_path, i, gpu_allocation, batch_size_scale
            )
            process_configs.append(process_config)
        
        logger.info(f"创建了 {len(process_configs)} 个并行配置文件")
        return process_configs
    
    def cleanup_temp_configs(self):
        """清理临时配置文件"""
        try:
            if os.path.exists(self.temp_config_dir):
                shutil.rmtree(self.temp_config_dir)
                logger.info("临时配置文件清理完成")
        except Exception as e:
            logger.error(f"清理临时配置文件失败: {e}")
    
    def get_config_summary(self, config_paths: List[str]) -> Dict:
        """获取配置文件摘要信息"""
        summary = {
            'total_configs': len(config_paths),
            'config_details': []
        }
        
        for i, config_path in enumerate(config_paths):
            try:
                config = self.load_config(config_path)
                detail = {
                    'index': i,
                    'path': config_path,
                    'batch_size': config.get('data_preprocessing', {}).get('batch_size', 'N/A'),
                    'epochs': config.get('model_training', {}).get('epochs', 'N/A'),
                    'model_path': config.get('model_training', {}).get('checkpoint', {}).get('filepath', 'N/A')
                }
                summary['config_details'].append(detail)
            except Exception as e:
                logger.error(f"获取配置摘要失败 {config_path}: {e}")
        
        return summary
