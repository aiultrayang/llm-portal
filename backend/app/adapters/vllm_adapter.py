"""vLLM 推理引擎适配器"""

from typing import Dict, Any, List, Optional
import re

from .base import BaseEngineAdapter


class VLLMAdapter(BaseEngineAdapter):
    """vLLM 推理引擎适配器 (v0.16.0)"""

    @property
    def name(self) -> str:
        """引擎名称"""
        return "vllm"

    def get_supported_params(self) -> Dict[str, Any]:
        """获取 vLLM 0.16.0 支持的参数定义"""
        return {
            # 基础参数
            "model": {
                "type": "string",
                "default": None,
                "required": True,
                "description": "模型名称或路径",
                "group": "basic"
            },
            "tokenizer": {
                "type": "string",
                "default": None,
                "required": False,
                "description": "分词器名称或路径",
                "group": "basic"
            },
            "dtype": {
                "type": "string",
                "default": "auto",
                "required": False,
                "choices": ["auto", "float16", "bfloat16", "float32"],
                "description": "数据类型",
                "group": "basic"
            },
            "trust_remote_code": {
                "type": "boolean",
                "default": False,
                "required": False,
                "description": "是否信任远程代码",
                "group": "basic"
            },
            # GPU 参数
            "tensor_parallel_size": {
                "type": "int",
                "default": 1,
                "required": False,
                "min": 1,
                "max": 8,
                "description": "张量并行大小",
                "group": "gpu"
            },
            "gpu_memory_utilization": {
                "type": "float",
                "default": 0.9,
                "required": False,
                "min": 0.1,
                "max": 1.0,
                "description": "GPU 显存利用率",
                "group": "gpu"
            },
            "max_model_len": {
                "type": "int",
                "default": None,
                "required": False,
                "min": 1,
                "description": "模型最大上下文长度，默认自动检测",
                "group": "gpu"
            },
            # 推理参数
            "max_tokens": {
                "type": "int",
                "default": 16,
                "required": False,
                "min": 1,
                "description": "最大生成 token 数",
                "group": "inference"
            },
            "temperature": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.0,
                "max": 2.0,
                "description": "温度参数",
                "group": "inference"
            },
            "top_p": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 0.0,
                "max": 1.0,
                "description": "Top-p 采样参数",
                "group": "inference"
            },
            "top_k": {
                "type": "int",
                "default": -1,
                "required": False,
                "min": -1,
                "description": "Top-k 采样参数，-1 表示禁用",
                "group": "inference"
            },
            "repetition_penalty": {
                "type": "float",
                "default": 1.0,
                "required": False,
                "min": 1.0,
                "max": 2.0,
                "description": "重复惩罚系数",
                "group": "inference"
            },
            # 性能参数
            "kv_cache_dtype": {
                "type": "string",
                "default": "auto",
                "required": False,
                "choices": ["auto", "fp8", "fp8_e5m2", "fp8_e4m3"],
                "description": "KV 缓存数据类型",
                "group": "performance"
            },
            "enable_prefix_caching": {
                "type": "boolean",
                "default": False,
                "required": False,
                "description": "启用前缀缓存",
                "group": "performance"
            },
            "enable_chunked_prefill": {
                "type": "boolean",
                "default": False,
                "required": False,
                "description": "启用分块预填充",
                "group": "performance"
            },
            # API 参数
            "host": {
                "type": "string",
                "default": "0.0.0.0",
                "required": False,
                "description": "服务监听地址",
                "group": "api"
            },
            "port": {
                "type": "int",
                "default": 8000,
                "required": False,
                "min": 1,
                "max": 65535,
                "description": "服务监听端口",
                "group": "api"
            },
            "api_key": {
                "type": "string",
                "default": None,
                "required": False,
                "description": "API 密钥",
                "group": "api"
            },
            # 高级参数
            "speculative_model": {
                "type": "string",
                "default": None,
                "required": False,
                "description": "推测解码模型路径",
                "group": "advanced"
            },
            "quantization": {
                "type": "string",
                "default": None,
                "required": False,
                "choices": ["awq", "gptq", "fp8", "bitsandbytes"],
                "description": "量化方法",
                "group": "advanced"
            },
            "swap_space": {
                "type": "int",
                "default": 4,
                "required": False,
                "min": 1,
                "max": 64,
                "description": "CPU-GPU 交换空间大小 (GB)",
                "group": "advanced"
            }
        }

    def get_param_groups(self) -> Dict[str, str]:
        """获取参数分组名称映射"""
        return {
            "basic": "基础参数",
            "gpu": "GPU 参数",
            "inference": "推理参数",
            "performance": "性能参数",
            "api": "API 参数",
            "advanced": "高级参数"
        }

    def build_command(self, config: Dict[str, Any]) -> str:
        """构建 vllm serve 命令"""
        # 获取必需参数
        model = config.get("model")
        if not model:
            raise ValueError("model 参数是必需的")

        # 构建基础命令
        cmd_parts = ["vllm serve", model]

        # API 参数
        host = config.get("host", "0.0.0.0")
        port = config.get("port", 8000)
        cmd_parts.append(f"--host {host}")
        cmd_parts.append(f"--port {port}")

        # 数据类型
        dtype = config.get("dtype", "auto")
        cmd_parts.append(f"--dtype {dtype}")

        # GPU 参数
        tensor_parallel_size = config.get("tensor_parallel_size")
        if tensor_parallel_size and tensor_parallel_size > 1:
            cmd_parts.append(f"--tensor-parallel-size {tensor_parallel_size}")

        gpu_memory_utilization = config.get("gpu_memory_utilization")
        if gpu_memory_utilization and gpu_memory_utilization != 0.9:
            cmd_parts.append(f"--gpu-memory-utilization {gpu_memory_utilization}")

        max_model_len = config.get("max_model_len")
        if max_model_len:
            cmd_parts.append(f"--max-model-len {max_model_len}")

        # 分词器
        tokenizer = config.get("tokenizer")
        if tokenizer:
            cmd_parts.append(f"--tokenizer {tokenizer}")

        # 信任远程代码
        if config.get("trust_remote_code", False):
            cmd_parts.append("--trust-remote-code")

        # 性能参数
        kv_cache_dtype = config.get("kv_cache_dtype")
        if kv_cache_dtype and kv_cache_dtype != "auto":
            cmd_parts.append(f"--kv-cache-dtype {kv_cache_dtype}")

        if config.get("enable_prefix_caching", False):
            cmd_parts.append("--enable-prefix-caching")

        if config.get("enable_chunked_prefill", False):
            cmd_parts.append("--enable-chunked-prefill")

        # API 密钥
        api_key = config.get("api_key")
        if api_key:
            cmd_parts.append(f"--api-key {api_key}")

        # 高级参数
        speculative_model = config.get("speculative_model")
        if speculative_model:
            cmd_parts.append(f"--speculative-model {speculative_model}")

        quantization = config.get("quantization")
        if quantization:
            cmd_parts.append(f"--quantization {quantization}")

        swap_space = config.get("swap_space")
        if swap_space and swap_space != 4:
            cmd_parts.append(f"--swap-space {swap_space}")

        return " ".join(cmd_parts)

    def get_default_port(self) -> int:
        """获取默认端口"""
        return 8000

    def transform_request(self, request: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """
        转换请求格式

        Args:
            request: 原始请求
            api_type: API 类型 (openai, claude, passthrough)

        Returns:
            转换后的请求
        """
        if api_type == "passthrough":
            return request

        if api_type == "openai":
            # vLLM 原生支持 OpenAI 格式，直接返回
            return request

        if api_type == "claude":
            # Claude 格式转换为 OpenAI 格式
            transformed = {}

            # 转换 messages
            if "messages" in request:
                transformed["messages"] = self._convert_claude_messages(request["messages"])

            # 转换其他参数
            if "model" in request:
                transformed["model"] = request["model"]
            if "max_tokens" in request:
                transformed["max_tokens"] = request["max_tokens"]
            if "temperature" in request:
                transformed["temperature"] = request["temperature"]
            if "top_p" in request:
                transformed["top_p"] = request["top_p"]
            if "top_k" in request:
                transformed["top_k"] = request["top_k"]
            if "stream" in request:
                transformed["stream"] = request["stream"]
            if "stop" in request:
                transformed["stop"] = request["stop"]

            # Claude 特有参数转换
            if "system" in request:
                # 将系统消息添加到 messages 开头
                system_msg = {"role": "system", "content": request["system"]}
                if "messages" in transformed:
                    transformed["messages"].insert(0, system_msg)
                else:
                    transformed["messages"] = [system_msg]

            return transformed

        # 未知类型，原样返回
        return request

    def _convert_claude_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        转换 Claude 消息格式到 OpenAI 格式

        Claude 格式: {"role": "user", "content": "..."} 或
                     {"role": "user", "content": [{"type": "text", "text": "..."}]}
        OpenAI 格式: {"role": "user", "content": "..."} 或
                     {"role": "user", "content": [{"type": "text", "text": "..."}]}
        """
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")

            # 处理 content 为列表的情况
            if isinstance(content, list):
                # Claude 和 OpenAI 都支持多模态内容格式，基本兼容
                converted_msg = {"role": role, "content": content}
            else:
                # 字符串内容
                converted_msg = {"role": role, "content": content}

            converted.append(converted_msg)

        return converted

    def transform_response(self, response: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """
        转换响应格式

        Args:
            response: 原始响应
            api_type: API 类型 (openai, claude, passthrough)

        Returns:
            转换后的响应
        """
        if api_type == "passthrough":
            return response

        if api_type == "openai":
            # vLLM 返回的是 OpenAI 格式，直接返回
            return response

        if api_type == "claude":
            # 将 OpenAI 格式转换为 Claude 格式
            return self._convert_to_claude_response(response)

        # 未知类型，原样返回
        return response

    def _convert_to_claude_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """将 OpenAI 格式响应转换为 Claude 格式"""
        converted = {}

        # 转换 id
        if "id" in response:
            converted["id"] = response["id"]

        # 转换 model
        if "model" in response:
            converted["model"] = response["model"]

        # 转换 choices
        if "choices" in response and response["choices"]:
            choice = response["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")

            # Claude 格式的响应结构
            converted["content"] = [
                {
                    "type": "text",
                    "text": content
                }
            ]
            converted["role"] = message.get("role", "assistant")

            # 转换 finish_reason
            if "finish_reason" in choice:
                converted["stop_reason"] = self._convert_finish_reason(choice["finish_reason"])

        # 转换 usage
        if "usage" in response:
            usage = response["usage"]
            converted["usage"] = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0)
            }

        return converted

    def _convert_finish_reason(self, reason: str) -> str:
        """转换 finish_reason 到 Claude 格式"""
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "content_filter": "stop_sequence"
        }
        return mapping.get(reason, reason)

    def parse_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """
        解析 Prometheus 格式指标

        Args:
            metrics_text: Prometheus 格式的指标文本

        Returns:
            解析后的指标字典
        """
        metrics = {
            "num_requests_running": None,
            "num_requests_waiting": None,
            "time_to_first_token_seconds": None,
            "generation_tokens_total": None,
            "raw_metrics": {}
        }

        # 定义需要提取的指标模式
        patterns = {
            "num_requests_running": r'vllm:num_requests_running\{[^}]*\}\s+([\d.]+)',
            "num_requests_waiting": r'vllm:num_requests_waiting\{[^}]*\}\s+([\d.]+)',
            "time_to_first_token_seconds": r'vllm:time_to_first_token_seconds\{[^}]*\}\s+([\d.]+)',
            "generation_tokens_total": r'vllm:generation_tokens_total\{[^}]*\}\s+([\d.]+)'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, metrics_text)
            if match:
                value = match.group(1)
                # 尝试转换为数字
                try:
                    if '.' in value:
                        metrics[key] = float(value)
                        metrics["raw_metrics"][key] = float(value)
                    else:
                        metrics[key] = int(value)
                        metrics["raw_metrics"][key] = int(value)
                except ValueError:
                    metrics[key] = value
                    metrics["raw_metrics"][key] = value

        return metrics

    def health_check_url(self, port: int) -> str:
        """
        健康检查 URL

        Args:
            port: 服务端口

        Returns:
            健康检查 URL
        """
        return f"http://localhost:{port}/health"