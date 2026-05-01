"""LMDeploy 推理引擎适配器"""

from typing import Dict, Any, List, Optional
import re

from .base import BaseEngineAdapter


class LMDeployAdapter(BaseEngineAdapter):
    """LMDeploy 推理引擎适配器"""

    _version = "0.12.2"  # 默认版本

    @property
    def name(self) -> str:
        """引擎名称"""
        return "lmdeploy"

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
            "model_path": {
                "type": "string",
                "default": None,
                "required": True,
                "description": "模型路径或名称",
                "group": "basic"
            },
            "dtype": {
                "type": "string",
                "default": "auto",
                "choices": ["auto", "float16", "bfloat16", "float32"],
                "description": "数据类型",
                "group": "basic"
            },
            "tp": {
                "type": "int",
                "default": 1,
                "min": 1,
                "max": 8,
                "description": "张量并行大小",
                "group": "gpu"
            },
            "cache_max_entry_count": {
                "type": "float",
                "default": 0.8,
                "min": 0.1,
                "max": 1.0,
                "description": "KV Cache 显存占用比例",
                "group": "gpu"
            },
            "session_len": {
                "type": "int",
                "default": None,
                "min": 1,
                "description": "会话最大长度",
                "group": "gpu"
            },
            "server_name": {
                "type": "string",
                "default": "0.0.0.0",
                "description": "服务监听地址",
                "group": "api"
            },
            "server_port": {
                "type": "int",
                "default": 8001,
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
        """构建 lmdeploy serve 命令"""
        # 获取必需参数
        model_path = config.get("model_path")
        if not model_path:
            raise ValueError("model_path 参数是必需的")

        # 构建基础命令
        cmd_parts = ["lmdeploy serve api_server", model_path]

        # 参数映射：配置名 -> 命令行参数名
        param_mapping = {
            "server_name": "--server-name",
            "server_port": "--server-port",
            "dtype": "--dtype",
            "tp": "--tp",
            "cache_max_entry_count": "--cache-max-entry-count",
            "session_len": "--session-len",
            "tokenizer_path": "--tokenizer-path",
            "max_prefill_token_num": "--max-prefill-token-num",
            "quantization": "--quantization",
            "model_format": "--model-format",
            "api_key": "--api-key",
            "trust_remote_code": "--trust-remote-code",
        }

        # 获取参数定义（用于检查默认值）
        params_def = self.get_supported_params()

        # 添加参数到命令
        for config_name, cli_name in param_mapping.items():
            value = config.get(config_name)
            if value is None:
                continue

            # 获取默认值
            default = params_def.get(config_name, {}).get('default')

            # 检查是否需要添加（非默认值或必需参数）
            if value == default and config_name not in ['server_name', 'server_port']:
                continue

            # 布尔类型特殊处理
            param_type = params_def.get(config_name, {}).get('type', 'string')
            if param_type == 'boolean':
                if value:
                    cmd_parts.append(cli_name)
            else:
                cmd_parts.append(f"{cli_name} {value}")

        # 特殊处理：turbomind 默认启用，如果禁用则使用 pytorch backend
        turbomind = config.get("turbomind", True)
        if not turbomind:
            cmd_parts.append("--backend pytorch")

        return " ".join(cmd_parts)

    def get_default_port(self) -> int:
        """获取默认端口"""
        return 8001

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
            "time_to_first_token_seconds": None,
            "generation_tokens_total": None,
            "avg_latency_seconds": None,
            "raw_metrics": {}
        }

        patterns = {
            "num_requests_running": r'lmdeploy:num_requests_running\{[^}]*\}\s+([\d.]+)',
            "num_requests_waiting": r'lmdeploy:num_requests_waiting\{[^}]*\}\s+([\d.]+)',
            "time_to_first_token_seconds": r'lmdeploy:time_to_first_token_seconds\{[^}]*\}\s+([\d.]+)',
            "generation_tokens_total": r'lmdeploy:generation_tokens_total\{[^}]*\}\s+([\d.]+)',
            "avg_latency_seconds": r'lmdeploy:avg_latency_seconds\{[^}]*\}\s+([\d.]+)'
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
        return f"http://localhost:{port}/v1/models"
