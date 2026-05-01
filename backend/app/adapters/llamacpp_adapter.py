"""Llama.cpp 推理引擎适配器"""

from typing import Dict, Any, List, Optional
import re

from .base import BaseEngineAdapter


class LlamaCppAdapter(BaseEngineAdapter):
    """Llama.cpp 推理引擎适配器"""

    _version = "b4500"  # 默认版本（llama.cpp 使用 commit hash 或版本号）

    @property
    def name(self) -> str:
        """引擎名称"""
        return "llamacpp"

    def get_supported_params(self) -> Dict[str, Any]:
        """获取支持的参数定义（从配置文件动态加载）"""
        # 尝试从配置文件加载
        params = self.load_params_from_config()
        if params:
            return params

        # 如果配置文件不存在，返回基础参数定义
        return self._get_fallback_params()

    def _get_fallback_params(self) -> Dict[str, Any]:
        """配置文件不存在时的备用参数"""
        return {
            "model": {
                "type": "string",
                "default": None,
                "required": True,
                "description": "GGUF 模型文件路径",
                "group": "basic"
            },
            "model_alias": {
                "type": "string",
                "default": None,
                "description": "模型别名",
                "group": "basic"
            },
            "n_gpu_layers": {
                "type": "int",
                "default": -1,
                "min": -1,
                "max": 999,
                "description": "GPU 层数，-1 表示全部载入 GPU",
                "group": "gpu"
            },
            "n_ctx": {
                "type": "int",
                "default": 4096,
                "min": 512,
                "max": 131072,
                "description": "上下文长度",
                "group": "gpu"
            },
            "n_batch": {
                "type": "int",
                "default": 512,
                "min": 1,
                "max": 16384,
                "description": "批处理大小",
                "group": "gpu"
            },
            "host": {
                "type": "string",
                "default": "0.0.0.0",
                "description": "服务监听地址",
                "group": "api"
            },
            "port": {
                "type": "int",
                "default": 8080,
                "min": 1,
                "max": 65535,
                "description": "服务监听端口",
                "group": "api"
            },
        }

    def get_param_groups(self) -> Dict[str, str]:
        """获取参数分组"""
        groups = self.load_groups_from_config()
        if groups:
            return groups
        return {
            "basic": "基础参数",
            "gpu": "GPU 参数",
            "inference": "推理参数",
            "performance": "性能参数",
            "api": "API 参数",
            "advanced": "高级参数"
        }

    def build_command(self, config: Dict[str, Any]) -> str:
        """构建 llama-server 命令"""
        # 获取必需参数
        model = config.get("model")
        if not model:
            raise ValueError("model 参数是必需的")

        # 构建基础命令
        cmd_parts = ["llama-server", f"-m {model}"]

        # 参数映射：配置名 -> 命令行参数名
        # 注意：llama.cpp 使用短参数名和长参数名混合
        param_mapping = {
            "host": "--host",
            "port": "--port",
            "n_ctx": "-c",
            "n_gpu_layers": "-ngl",
            "n_batch": "--batch-size",
            "model_alias": "--alias",
            "n_predict": "-n",
            "temp": "--temp",
            "top_k": "--top-k",
            "top_p": "--top-p",
            "repeat_penalty": "--repeat-penalty",
            "mlock": "--mlock",
            "no_mmap": "--no-mmap",
            "flash_attn": "--flash-attn",
            "rope_scaling": "--rope-scaling",
            "rope_freq_base": "--rope-freq-base",
            "threads": "--threads",
            "tensor_split": "--tensor-split",
            "timeout": "--timeout",
        }

        # 获取参数定义（用于检查默认值）
        params_def = self.get_supported_params()

        # 特殊参数单独处理
        # host 和 port 始终添加
        host = config.get("host", "0.0.0.0")
        port = config.get("port", 8080)
        cmd_parts.append(f"--host {host}")
        cmd_parts.append(f"--port {port}")

        # n_ctx 上下文长度始终添加
        n_ctx = config.get("n_ctx", 4096)
        cmd_parts.append(f"-c {n_ctx}")

        # 添加其他参数到命令
        for config_name, cli_name in param_mapping.items():
            # 跳过已处理的参数
            if config_name in ['host', 'port', 'n_ctx']:
                continue

            value = config.get(config_name)
            if value is None:
                continue

            # 获取默认值
            default = params_def.get(config_name, {}).get('default')

            # n_gpu_layers 特殊处理：-1 是默认值，不添加参数
            if config_name == 'n_gpu_layers' and value == -1:
                continue

            # 检查是否需要添加（非默认值）
            if value == default:
                continue

            # 布尔类型特殊处理
            param_type = params_def.get(config_name, {}).get('type', 'string')
            if param_type == 'boolean':
                if value:
                    cmd_parts.append(cli_name)
            else:
                cmd_parts.append(f"{cli_name} {value}")

        return " ".join(cmd_parts)

    def get_default_port(self) -> int:
        """获取默认端口"""
        return 8080

    def transform_request(self, request: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """转换请求格式"""
        if api_type == "passthrough":
            return request

        if api_type == "openai":
            return request

        if api_type == "claude":
            transformed = {}
            if "messages" in request:
                transformed["messages"] = self._convert_claude_messages(request["messages"])
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
            if "system" in request:
                system_msg = {"role": "system", "content": request["system"]}
                if "messages" in transformed:
                    transformed["messages"].insert(0, system_msg)
                else:
                    transformed["messages"] = [system_msg]
            return transformed

        return request

    def _convert_claude_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换 Claude 消息格式"""
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")
            if isinstance(content, list):
                converted_msg = {"role": role, "content": content}
            else:
                converted_msg = {"role": role, "content": content}
            converted.append(converted_msg)
        return converted

    def transform_response(self, response: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """转换响应格式"""
        if api_type == "passthrough":
            return response

        if api_type == "openai":
            return response

        if api_type == "claude":
            return self._convert_to_claude_response(response)

        return response

    def _convert_to_claude_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """将 OpenAI 格式响应转换为 Claude 格式"""
        converted = {}

        if "id" in response:
            converted["id"] = response["id"]
        if "model" in response:
            converted["model"] = response["model"]

        if "choices" in response and response["choices"]:
            choice = response["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")

            converted["content"] = [{"type": "text", "text": content}]
            converted["role"] = message.get("role", "assistant")

            if "finish_reason" in choice:
                converted["stop_reason"] = self._convert_finish_reason(choice["finish_reason"])

        if "usage" in response:
            usage = response["usage"]
            converted["usage"] = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0)
            }

        return converted

    def _convert_finish_reason(self, reason: str) -> str:
        """转换 finish_reason"""
        mapping = {"stop": "end_turn", "length": "max_tokens", "content_filter": "stop_sequence"}
        return mapping.get(reason, reason)

    def parse_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """解析 Prometheus 格式指标"""
        metrics = {
            "num_requests_running": None,
            "num_requests_waiting": None,
            "tokens_generated_total": None,
            "prompt_tokens_processed_total": None,
            "time_to_first_token_seconds": None,
            "avg_generation_tokens_per_second": None,
            "raw_metrics": {}
        }

        patterns = {
            "num_requests_running": r'llama:num_requests_running\{[^}]*\}\s+([\d.]+)',
            "num_requests_waiting": r'llama:num_requests_waiting\{[^}]*\}\s+([\d.]+)',
            "tokens_generated_total": r'llama:tokens_generated_total\{[^}]*\}\s+([\d.]+)',
            "prompt_tokens_processed_total": r'llama:prompt_tokens_processed_total\{[^}]*\}\s+([\d.]+)',
            "time_to_first_token_seconds": r'llama:time_to_first_token_seconds\{[^}]*\}\s+([\d.]+)',
            "avg_generation_tokens_per_second": r'llama:avg_generation_tokens_per_second\{[^}]*\}\s+([\d.]+)'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, metrics_text)
            if match:
                value = match.group(1)
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
        """健康检查 URL"""
        return f"http://localhost:{port}/health"
