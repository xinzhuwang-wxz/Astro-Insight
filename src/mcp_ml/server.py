from mcp.server.fastmcp import FastMCP
import logging
import json
import argparse
import signal
import sys
from typing import Optional, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create the MCP server object
mcp = FastMCP()

# 全局执行器实例
_global_executor = None

import yaml
from data_loading import download_data
from data_preprocessing import load_and_preprocess_data, create_dataset
from model_training import train_model
from result_analysis import evaluate_model
import tensorflow as tf

@mcp.tool()
def run_pipeline():
    """
    Main pipeline script to run the full workflow.
    """
    # Define the path to the configuration file
    config_path = 'config/config.yaml'
    
    # Load configuration
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    # Step 1: Download data
    # The download path is managed by kagglehub, but we can ensure it's downloaded.
    # download_data()

    # Step 2: Load and preprocess data
    print("Loading and preprocessing data...")
    train_df, val_df, test_df, label_encoder = load_and_preprocess_data(config)
    train_dataset = create_dataset(train_df, config, is_training=True)
    val_dataset = create_dataset(val_df, config, is_training=False)
    test_dataset = create_dataset(test_df, config, is_training=False)
    print("Data ready for training.")

    # Step 3: Train the model
    print("Starting model training...")
    # Handle TPU initialization
    try:
        tpu = tf.distribute.cluster_resolver.TPUClusterResolver()
        tf.config.experimental_connect_to_cluster(tpu)
        tf.tpu.experimental.initialize_tpu_system(tpu)
        strategy = tf.distribute.TPUStrategy(tpu)
        print("TPU initialized successfully! Training with TPU.")
        with strategy.scope():
            model, history = train_model(config)
    except ValueError:
        print("TPU not found. Training on CPU/GPU.")
        model, history = train_model(config)
    
    # Step 4: Evaluate the model and analyze results
    print("Evaluating model and generating analysis...")
    # Load the best performing model saved by ModelCheckpoint
    best_model = tf.keras.models.load_model(config['model_training']['checkpoint']['filepath'])
    evaluate_model(best_model, history, test_dataset, label_encoder, config)
    
    print("Pipeline finished successfully.")


@mcp.tool()
def run_parallel_pipeline():
    """
    并行运行多个ML训练流程，使用不同的配置文件。
    支持GPU显存管理和进程监控。
    """
    global _global_executor
    
    try:
        # 导入并行执行器
        from parallel_executor import ParallelMLExecutor
        
        # 定义要并行运行的配置文件
        configs = ["config/config1.yaml", "config/config2.yaml"]
        
        logger.info(f"开始并行ML训练流程，配置文件: {configs}")
        
        # 创建并行执行器
        _global_executor = ParallelMLExecutor(configs)
        
        # 运行并行流程
        results = _global_executor.run_parallel()
        
        logger.info("并行ML训练流程完成")
        return {
            "status": "success",
            "message": "并行ML训练流程执行完成",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"并行ML训练流程失败: {e}")
        return {
            "status": "error",
            "message": f"并行ML训练流程失败: {str(e)}",
            "error": str(e)
        }


@mcp.tool()
def get_parallel_status():
    """
    获取并行ML训练流程的当前状态。
    """
    global _global_executor
    
    try:
        if _global_executor is None:
            return {
                "status": "info",
                "message": "没有正在运行的并行执行器",
                "note": "请先运行 run_parallel_pipeline 来启动并行流程"
            }
        
        # 获取执行器状态
        status = _global_executor.get_status()
        
        return {
            "status": "success",
            "message": "成功获取并行执行器状态",
            "executor_status": status
        }
        
    except Exception as e:
        logger.error(f"获取并行状态失败: {e}")
        return {
            "status": "error",
            "message": f"获取并行状态失败: {str(e)}",
            "error": str(e)
        }


@mcp.tool()
def stop_parallel_execution():
    """
    停止正在运行的并行ML训练流程。
    """
    global _global_executor
    
    try:
        if _global_executor is None:
            return {
                "status": "info",
                "message": "没有正在运行的并行执行器",
                "note": "请先运行 run_parallel_pipeline 来启动并行流程"
            }
        
        # 停止执行器
        _global_executor.stop_execution()
        
        return {
            "status": "success",
            "message": "并行执行器已停止"
        }
        
    except Exception as e:
        logger.error(f"停止并行执行失败: {e}")
        return {
            "status": "error",
            "message": f"停止并行执行失败: {str(e)}",
            "error": str(e)
        }


def main(argv: Optional[List[str]] = None):
    """Entry point for running the MCP server.

    Accepts a --mode argument (default 'stdio') for flexibility.
    Installs simple signal handlers to enable graceful shutdown.
    """
    parser = argparse.ArgumentParser(description="CNN MCP server")
    parser.add_argument(
        "--mode",
        default="stdio",
        help="MCP run mode (default: stdio).",
    )
    args = parser.parse_args(argv)

    logger.info("Starting CNN server (mode=%s)", args.mode)

    def _shutdown(signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        # allow Clean shutdown if MCP supports it; otherwise exit
        try:
            # If mcp has a stop/close method, call it here (best-effort)
            stop = getattr(mcp, "stop", None)
            if callable(stop):
                stop()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        mcp.run(args.mode)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception:
        logger.exception("MCP server exited with an error")
        raise

if __name__ == "__main__":
    main()
