"""
并行执行器
负责管理多个子进程、处理进程间通信、错误处理和恢复
"""
import os
import sys
import logging
import time
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

from gpu_manager import GPUMemoryManager
from config_manager import ConfigManager
from process_monitor import ProcessMonitor
from output_manager import OutputManager

logger = logging.getLogger(__name__)

class ParallelMLExecutor:
    """并行ML执行器"""
    
    def __init__(self, config_paths: List[str], working_dir: str = None, session_name: str = None):
        self.config_paths = config_paths
        self.working_dir = working_dir or os.getcwd()
        
        # 初始化输出管理器
        self.output_manager = OutputManager()
        self.session_dir = self.output_manager.create_session(session_name)
        
        # 初始化组件
        self.gpu_manager = GPUMemoryManager()
        self.config_manager = ConfigManager(output_manager=self.output_manager)
        self.process_monitor = ProcessMonitor()
        
        # 执行状态
        self.is_running = False
        self.results = {}
        self.start_time = None
        self.end_time = None
        
        logger.info(f"并行ML执行器初始化完成，配置文件: {config_paths}")
        logger.info(f"会话目录: {self.session_dir}")
    
    def run_parallel(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        """并行运行多个ML训练流程"""
        try:
            self.start_time = datetime.now()
            self.is_running = True
            
            logger.info("开始并行ML训练流程")
            
            # 1. 检查GPU状态
            gpu_status = self.gpu_manager.get_gpu_status()
            logger.info(f"GPU状态: {gpu_status}")
            
            # 2. 分配GPU资源
            gpu_allocations = self.gpu_manager.allocate_gpu_memory(len(self.config_paths))
            logger.info(f"GPU分配: {gpu_allocations}")
            
            # 如果没有GPU，创建CPU分配
            if not gpu_allocations:
                gpu_allocations = [
                    {'gpu_index': -1, 'memory_limit': None, 'memory_fraction': 1.0, 'process_id': i}
                    for i in range(len(self.config_paths))
                ]
                logger.info(f"使用CPU分配: {gpu_allocations}")
            
            # 3. 创建进程配置文件
            process_configs = self.config_manager.create_parallel_configs(
                self.config_paths, gpu_allocations
            )
            logger.info(f"创建进程配置: {process_configs}")
            
            # 4. 启动并行进程
            self._start_parallel_processes(process_configs, gpu_allocations)
            
            # 5. 监控进程执行
            self._monitor_execution(timeout)
            
            # 6. 收集结果
            results = self._collect_results()
            
            self.end_time = datetime.now()
            self.is_running = False
            
            logger.info("并行ML训练流程完成")
            return results
            
        except Exception as e:
            logger.error(f"并行执行失败: {e}")
            self._cleanup()
            raise
        finally:
            self._cleanup()
    
    def _start_parallel_processes(self, process_configs: List[str], 
                                gpu_allocations: List[Dict]):
        """启动并行进程"""
        for i, (config_path, gpu_allocation) in enumerate(zip(process_configs, gpu_allocations)):
            try:
                # 构建命令
                command = self._build_process_command(config_path, i)
                
                # 设置环境变量
                env_vars = self._build_environment_variables(gpu_allocation, i)
                
                # 启动进程
                process = self.process_monitor.start_process(
                    process_id=i,
                    command=command,
                    working_dir=self.working_dir,
                    env_vars=env_vars
                )
                
                # 设置状态回调
                self.process_monitor.set_status_callback(i, self._process_status_callback)
                
                logger.info(f"进程 {i} 启动成功，使用配置: {config_path}")
                
            except Exception as e:
                logger.error(f"启动进程 {i} 失败: {e}")
                raise
    
    def _build_process_command(self, config_path: str, process_id: int) -> List[str]:
        """构建进程命令"""
        # 创建独立的训练脚本
        script_path = self._create_process_script(config_path, process_id)
        
        return [sys.executable, script_path]
    
    def _create_process_script(self, config_path: str, process_id: int) -> str:
        """为每个进程创建独立的训练脚本"""
        script_content = f'''
import sys
import os
import logging
import yaml
import tensorflow as tf

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loading import download_data
from data_preprocessing import load_and_preprocess_data, create_dataset
from model_training import train_model
from result_analysis import evaluate_model
from gpu_manager import GPUMemoryManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - Process {process_id} - %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("进程 {process_id} 开始执行")
        
        # 加载配置
        with open('{config_path}', 'r') as file:
            config = yaml.safe_load(file)
        
        logger.info("进程 {process_id} 配置加载完成")
        
        # 设置GPU
        gpu_manager = GPUMemoryManager()
        gpu_allocation = config.get('process_info', dict()).get('gpu_allocation', dict())
        if gpu_allocation:
            gpu_manager.setup_gpu_for_process(gpu_allocation)
        
        # 执行训练流程
        logger.info("进程 {process_id} 开始数据预处理")
        train_df, val_df, test_df, label_encoder = load_and_preprocess_data(config)
        train_dataset = create_dataset(train_df, config, is_training=True)
        val_dataset = create_dataset(val_df, config, is_training=False)
        test_dataset = create_dataset(test_df, config, is_training=False)
        
        logger.info("进程 {process_id} 开始模型训练")
        model, history = train_model(config)
        
        logger.info("进程 {process_id} 开始模型评估")
        best_model = tf.keras.models.load_model(config['model_training']['checkpoint']['filepath'])
        
        # 获取输出管理器
        output_manager = None
        if 'output_manager' in config.get('process_info', dict()):
            from output_manager import OutputManager
            output_manager = OutputManager()
            output_manager.session_dir = config['process_info']['output_manager']['session_dir']
            output_manager.subdirs = config['process_info']['output_manager']['subdirs']
        
        evaluate_model(best_model, history, test_dataset, label_encoder, config, output_manager, {process_id})
        
        logger.info("进程 {process_id} 执行完成")
        
    except Exception as e:
        logger.error("进程 {process_id} 执行失败: " + str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        # 保存脚本文件
        script_path = f"temp_script_process_{process_id}.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return script_path
    
    def _build_environment_variables(self, gpu_allocation: Dict, process_id: int) -> Dict[str, str]:
        """构建环境变量"""
        env_vars = {
            'PROCESS_ID': str(process_id),
            'CUDA_VISIBLE_DEVICES': str(gpu_allocation.get('gpu_index', 0)),
            'TF_CPP_MIN_LOG_LEVEL': '1',  # 减少TensorFlow日志
        }
        
        # 设置GPU显存限制
        memory_limit = gpu_allocation.get('memory_limit')
        if memory_limit:
            env_vars['TF_GPU_MEMORY_LIMIT'] = str(memory_limit)
        
        return env_vars
    
    def _process_status_callback(self, log_entry: Dict):
        """进程状态回调函数"""
        process_id = log_entry['process_id']
        message = log_entry['message']
        
        # 检查关键信息
        if 'epoch' in message.lower() and 'loss' in message.lower():
            logger.info(f"进程 {process_id} 训练进度: {message}")
        elif 'error' in message.lower() or 'failed' in message.lower():
            logger.error(f"进程 {process_id} 错误: {message}")
        elif 'completed' in message.lower() or 'finished' in message.lower():
            logger.info(f"进程 {process_id} 完成: {message}")
    
    def _monitor_execution(self, timeout: Optional[int] = None):
        """监控执行过程"""
        logger.info("开始监控并行进程执行")
        
        try:
            # 等待所有进程完成
            results = self.process_monitor.wait_for_all_processes(timeout)
            
            # 检查结果
            for process_id, return_code in results.items():
                if return_code == 0:
                    logger.info(f"进程 {process_id} 成功完成")
                else:
                    logger.error(f"进程 {process_id} 失败，返回码: {return_code}")
            
            self.results = results
            
        except Exception as e:
            logger.error(f"监控执行过程失败: {e}")
            raise
    
    def _collect_results(self) -> Dict[str, Any]:
        """收集执行结果"""
        results = {
            'execution_summary': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration': str(self.end_time - self.start_time) if self.start_time and self.end_time else None,
                'total_processes': len(self.config_paths),
                'successful_processes': sum(1 for code in self.results.values() if code == 0),
                'failed_processes': sum(1 for code in self.results.values() if code != 0),
                'session_dir': self.session_dir
            },
            'process_results': self.results,
            'process_logs': self.process_monitor.get_all_logs(),
            'gpu_status': self.gpu_manager.get_gpu_status(),
            'session_info': self.output_manager.get_session_info()
        }
        
        # 保存详细日志到输出目录
        log_data = self.process_monitor.get_all_logs()
        log_file = self.output_manager.save_log(log_data, 'execution_log.json')
        results['log_file'] = log_file
        
        # 保存结果摘要
        results_file = self.output_manager.save_result(results, 'execution_results.json')
        results['results_file'] = results_file
        
        # 保存会话摘要报告
        summary_file = self.output_manager.create_summary_report()
        results['summary_file'] = summary_file
        
        return results
    
    def _cleanup(self):
        """清理资源"""
        try:
            logger.info("开始清理资源")
            
            # 终止所有进程
            self.process_monitor.terminate_all_processes()
            
            # 移动模型文件到输出目录
            self._move_models_to_output()
            
            # 清理临时文件
            self._cleanup_temp_files()
            
            # 清理配置文件
            self.config_manager.cleanup_temp_configs()
            
            # 清理GPU资源
            self.gpu_manager.cleanup()
            
            # 清理进程监控器
            self.process_monitor.cleanup()
            
            # 清理输出管理器的临时文件
            self.output_manager.cleanup_temp_files()
            
            logger.info("资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    def _move_models_to_output(self):
        """将模型文件移动到输出目录"""
        try:
            # 1. 查找当前目录中的模型文件
            for filename in os.listdir('.'):
                if filename.endswith('.keras') and 'process_' in filename:
                    # 提取进程ID
                    parts = filename.split('_')
                    process_id = None
                    for i, part in enumerate(parts):
                        if part == 'process' and i + 1 < len(parts):
                            try:
                                process_id = int(parts[i + 1])
                                break
                            except ValueError:
                                continue
                    
                    # 移动到输出目录
                    target_path = self.output_manager.save_model(filename, process_id)
                    logger.info(f"模型文件已移动到: {target_path}")
                    
                    # 删除原文件
                    os.remove(filename)
            
            # 2. 查找temp目录中的模型文件
            temp_dir = self.output_manager.get_path('temp')
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    if filename.endswith('.keras') and 'process_' in filename:
                        # 提取进程ID
                        parts = filename.split('_')
                        process_id = None
                        for i, part in enumerate(parts):
                            if part == 'process' and i + 1 < len(parts):
                                try:
                                    process_id = int(parts[i + 1])
                                    break
                                except ValueError:
                                    continue
                        
                        # 源文件路径
                        source_path = os.path.join(temp_dir, filename)
                        
                        # 移动到models目录
                        target_path = self.output_manager.save_model(source_path, process_id)
                        logger.info(f"临时模型文件已移动到: {target_path}")
                        
                        # 删除临时文件
                        os.remove(source_path)
                    
        except Exception as e:
            logger.error(f"移动模型文件失败: {e}")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            # 清理临时脚本文件
            for i in range(len(self.config_paths)):
                script_path = f"temp_script_process_{i}.py"
                if os.path.exists(script_path):
                    os.remove(script_path)
                    logger.info(f"删除临时脚本: {script_path}")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前执行状态"""
        return {
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'process_status': self.process_monitor.get_all_process_status(),
            'gpu_status': self.gpu_manager.get_gpu_status()
        }
    
    def stop_execution(self):
        """停止执行"""
        if self.is_running:
            logger.info("停止并行执行")
            self.process_monitor.terminate_all_processes()
            self.is_running = False
