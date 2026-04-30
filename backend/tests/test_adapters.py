"""适配器模块测试"""

import pytest
from abc import ABC
from dataclasses import fields
from typing import Dict, Any

from app.adapters.base import BaseEngineAdapter, ProcessInfo, ServiceStatus


class TestProcessInfo:
    """测试 ProcessInfo 数据类"""

    def test_process_info_creation(self):
        """测试创建 ProcessInfo 实例"""
        info = ProcessInfo(pid=12345, port=8080, command="llama-server --port 8080")
        assert info.pid == 12345
        assert info.port == 8080
        assert info.command == "llama-server --port 8080"

    def test_process_info_fields(self):
        """测试 ProcessInfo 字段定义"""
        field_names = {f.name for f in fields(ProcessInfo)}
        assert field_names == {"pid", "port", "command"}

    def test_process_info_equality(self):
        """测试 ProcessInfo 相等性比较"""
        info1 = ProcessInfo(pid=12345, port=8080, command="test")
        info2 = ProcessInfo(pid=12345, port=8080, command="test")
        assert info1 == info2


class TestServiceStatus:
    """测试 ServiceStatus 数据类"""

    def test_service_status_creation_full(self):
        """测试创建完整的 ServiceStatus 实例"""
        status = ServiceStatus(
            running=True,
            pid=12345,
            port=8080,
            uptime=3600.5
        )
        assert status.running is True
        assert status.pid == 12345
        assert status.port == 8080
        assert status.uptime == 3600.5

    def test_service_status_creation_minimal(self):
        """测试创建最小 ServiceStatus 实例"""
        status = ServiceStatus(running=False)
        assert status.running is False
        assert status.pid is None
        assert status.port is None
        assert status.uptime is None

    def test_service_status_fields(self):
        """测试 ServiceStatus 字段定义"""
        field_names = {f.name for f in fields(ServiceStatus)}
        assert field_names == {"running", "pid", "port", "uptime"}

    def test_service_status_equality(self):
        """测试 ServiceStatus 相等性比较"""
        status1 = ServiceStatus(running=True, pid=123, port=8080, uptime=100.0)
        status2 = ServiceStatus(running=True, pid=123, port=8080, uptime=100.0)
        assert status1 == status2


class TestBaseEngineAdapter:
    """测试 BaseEngineAdapter 抽象类"""

    def test_is_abstract_class(self):
        """测试是否为抽象类"""
        assert ABC in BaseEngineAdapter.__bases__
        assert not hasattr(BaseEngineAdapter, '__abstractmethods__') or len(BaseEngineAdapter.__abstractmethods__) > 0

    def test_abstract_methods_exist(self):
        """测试抽象方法存在"""
        # 检查所有抽象方法是否定义
        expected_methods = {
            'name',
            'get_supported_params',
            'get_param_groups',
            'build_command',
            'get_default_port',
            'transform_request',
            'transform_response',
            'parse_metrics',
            'health_check_url'
        }

        # 检查方法是否存在
        for method_name in expected_methods:
            assert hasattr(BaseEngineAdapter, method_name), f"Missing method: {method_name}"

    def test_cannot_instantiate_directly(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseEngineAdapter()


class MockEngineAdapter(BaseEngineAdapter):
    """模拟引擎适配器用于测试"""

    @property
    def name(self) -> str:
        return "mock-engine"

    def get_supported_params(self) -> Dict[str, Any]:
        return {"port": {"type": "int", "default": 8080}}

    def get_param_groups(self) -> Dict[str, str]:
        return {"port": "network"}

    def build_command(self, config: Dict[str, Any]) -> str:
        return f"mock-server --port {config.get('port', 8080)}"

    def get_default_port(self) -> int:
        return 8080

    def transform_request(self, request: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        return request

    def transform_response(self, response: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        return response

    def parse_metrics(self, metrics_text: str) -> Dict[str, Any]:
        return {"raw": metrics_text}

    def health_check_url(self, port: int) -> str:
        return f"http://localhost:{port}/health"


class TestMockEngineAdapter:
    """使用模拟适配器测试基类功能"""

    def test_mock_adapter_creation(self):
        """测试模拟适配器创建"""
        adapter = MockEngineAdapter()
        assert adapter.name == "mock-engine"

    def test_get_supported_params(self):
        """测试获取支持的参数"""
        adapter = MockEngineAdapter()
        params = adapter.get_supported_params()
        assert "port" in params
        assert params["port"]["type"] == "int"

    def test_get_param_groups(self):
        """测试获取参数分组"""
        adapter = MockEngineAdapter()
        groups = adapter.get_param_groups()
        assert groups["port"] == "network"

    def test_build_command(self):
        """测试构建命令"""
        adapter = MockEngineAdapter()
        cmd = adapter.build_command({"port": 9000})
        assert "9000" in cmd

    def test_get_default_port(self):
        """测试获取默认端口"""
        adapter = MockEngineAdapter()
        assert adapter.get_default_port() == 8080

    def test_transform_request(self):
        """测试请求转换"""
        adapter = MockEngineAdapter()
        request = {"prompt": "hello"}
        result = adapter.transform_request(request, "openai")
        assert result == request

    def test_transform_response(self):
        """测试响应转换"""
        adapter = MockEngineAdapter()
        response = {"text": "world"}
        result = adapter.transform_response(response, "openai")
        assert result == response

    def test_parse_metrics(self):
        """测试解析指标"""
        adapter = MockEngineAdapter()
        metrics = adapter.parse_metrics("cpu: 50%")
        assert metrics["raw"] == "cpu: 50%"

    def test_health_check_url(self):
        """测试健康检查URL"""
        adapter = MockEngineAdapter()
        url = adapter.health_check_url(8080)
        assert url == "http://localhost:8080/health"


class TestVLLMAdapter:
    """测试 VLLMAdapter"""

    @pytest.fixture
    def adapter(self):
        """创建 VLLMAdapter 实例"""
        from app.adapters.vllm_adapter import VLLMAdapter
        return VLLMAdapter()

    def test_adapter_name(self, adapter):
        """测试适配器名称"""
        assert adapter.name == "vllm"

    def test_get_default_port(self, adapter):
        """测试默认端口"""
        assert adapter.get_default_port() == 8000

    def test_health_check_url(self, adapter):
        """测试健康检查URL"""
        url = adapter.health_check_url(8000)
        assert url == "http://localhost:8000/health"

    def test_get_supported_params_structure(self, adapter):
        """测试支持的参数结构"""
        params = adapter.get_supported_params()

        # 检查基础参数
        assert "model" in params
        assert params["model"]["required"] is True
        assert params["model"]["group"] == "basic"

        # 检查 dtype 参数
        assert "dtype" in params
        assert params["dtype"]["default"] == "auto"
        assert "auto" in params["dtype"]["choices"]
        assert "float16" in params["dtype"]["choices"]
        assert "bfloat16" in params["dtype"]["choices"]

        # 检查 GPU 参数
        assert "tensor_parallel_size" in params
        assert params["tensor_parallel_size"]["default"] == 1
        assert params["tensor_parallel_size"]["min"] == 1

        assert "gpu_memory_utilization" in params
        assert params["gpu_memory_utilization"]["default"] == 0.9
        assert params["gpu_memory_utilization"]["min"] == 0.1
        assert params["gpu_memory_utilization"]["max"] == 1.0

        # 检查推理参数
        assert "max_tokens" in params
        assert "temperature" in params
        assert "top_p" in params
        assert "top_k" in params
        assert "repetition_penalty" in params

        # 检查性能参数
        assert "kv_cache_dtype" in params
        assert "enable_prefix_caching" in params
        assert "enable_chunked_prefill" in params

        # 检查 API 参数
        assert "host" in params
        assert "port" in params
        assert "api_key" in params

        # 检查高级参数
        assert "speculative_model" in params
        assert "quantization" in params
        assert "swap_space" in params

    def test_get_param_groups(self, adapter):
        """测试参数分组"""
        groups = adapter.get_param_groups()

        assert "basic" in groups
        assert "gpu" in groups
        assert "inference" in groups
        assert "performance" in groups
        assert "api" in groups
        assert "advanced" in groups

        assert groups["basic"] == "基础参数"
        assert groups["gpu"] == "GPU 参数"

    def test_build_command_basic(self, adapter):
        """测试构建基本命令"""
        config = {"model": "meta-llama/Llama-2-7b-hf"}
        cmd = adapter.build_command(config)

        assert "vllm serve meta-llama/Llama-2-7b-hf" in cmd
        assert "--host 0.0.0.0" in cmd
        assert "--port 8000" in cmd
        assert "--dtype auto" in cmd

    def test_build_command_with_port(self, adapter):
        """测试构建带端口的命令"""
        config = {"model": "meta-llama/Llama-2-7b-hf", "port": 9000}
        cmd = adapter.build_command(config)

        assert "--port 9000" in cmd

    def test_build_command_with_dtype(self, adapter):
        """测试构建带 dtype 的命令"""
        config = {"model": "meta-llama/Llama-2-7b-hf", "dtype": "float16"}
        cmd = adapter.build_command(config)

        assert "--dtype float16" in cmd

    def test_build_command_with_tensor_parallel(self, adapter):
        """测试构建带张量并行的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "tensor_parallel_size": 2
        }
        cmd = adapter.build_command(config)

        assert "--tensor-parallel-size 2" in cmd

    def test_build_command_with_gpu_memory(self, adapter):
        """测试构建带 GPU 显存利用率的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "gpu_memory_utilization": 0.8
        }
        cmd = adapter.build_command(config)

        assert "--gpu-memory-utilization 0.8" in cmd

    def test_build_command_with_max_model_len(self, adapter):
        """测试构建带最大模型长度的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "max_model_len": 4096
        }
        cmd = adapter.build_command(config)

        assert "--max-model-len 4096" in cmd

    def test_build_command_with_trust_remote_code(self, adapter):
        """测试构建带信任远程代码的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "trust_remote_code": True
        }
        cmd = adapter.build_command(config)

        assert "--trust-remote-code" in cmd

    def test_build_command_with_performance_options(self, adapter):
        """测试构建带性能选项的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "enable_prefix_caching": True,
            "enable_chunked_prefill": True,
            "kv_cache_dtype": "fp8"
        }
        cmd = adapter.build_command(config)

        assert "--enable-prefix-caching" in cmd
        assert "--enable-chunked-prefill" in cmd
        assert "--kv-cache-dtype fp8" in cmd

    def test_build_command_with_quantization(self, adapter):
        """测试构建带量化的命令"""
        config = {
            "model": "meta-llama/Llama-2-7b-hf",
            "quantization": "awq"
        }
        cmd = adapter.build_command(config)

        assert "--quantization awq" in cmd

    def test_build_command_without_model_raises(self, adapter):
        """测试缺少 model 参数时抛出异常"""
        config = {}
        with pytest.raises(ValueError, match="model"):
            adapter.build_command(config)

    def test_transform_request_openai_passthrough(self, adapter):
        """测试 OpenAI 请求直接传递"""
        request = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        result = adapter.transform_request(request, "openai")

        assert result == request

    def test_transform_request_passthrough(self, adapter):
        """测试原始传递模式"""
        request = {"some": "data"}
        result = adapter.transform_request(request, "passthrough")

        assert result == request

    def test_transform_request_claude_to_openai(self, adapter):
        """测试 Claude 请求转换为 OpenAI 格式"""
        request = {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        result = adapter.transform_request(request, "claude")

        assert result["model"] == "test-model"
        assert result["max_tokens"] == 100
        assert result["temperature"] == 0.7
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_transform_request_claude_with_system(self, adapter):
        """测试带系统消息的 Claude 请求转换"""
        request = {
            "model": "test-model",
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        result = adapter.transform_request(request, "claude")

        # 系统消息应该在 messages 开头
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are a helpful assistant."
        assert result["messages"][1]["role"] == "user"

    def test_transform_response_openai_passthrough(self, adapter):
        """测试 OpenAI 响应直接返回"""
        response = {
            "id": "test-id",
            "model": "test-model",
            "choices": [{"message": {"content": "Hello!"}}]
        }
        result = adapter.transform_response(response, "openai")

        assert result == response

    def test_transform_response_passthrough(self, adapter):
        """测试原始响应传递"""
        response = {"some": "data"}
        result = adapter.transform_response(response, "passthrough")

        assert result == response

    def test_transform_response_to_claude(self, adapter):
        """测试 OpenAI 响应转换为 Claude 格式"""
        response = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5
            }
        }
        result = adapter.transform_response(response, "claude")

        assert result["id"] == "test-id"
        assert result["model"] == "test-model"
        assert result["role"] == "assistant"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello!"
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_parse_metrics_basic(self, adapter):
        """测试解析基本指标"""
        metrics_text = """
# HELP vllm:num_requests_running Number of running requests
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running{} 5.0
# HELP vllm:num_requests_waiting Number of waiting requests
# TYPE vllm:num_requests_waiting gauge
vllm:num_requests_waiting{} 10.0
# HELP vllm:time_to_first_token_seconds Time to first token
# TYPE vllm:time_to_first_token_seconds histogram
vllm:time_to_first_token_seconds{} 0.5
# HELP vllm:generation_tokens_total Total generation tokens
# TYPE vllm:generation_tokens_total counter
vllm:generation_tokens_total{} 1000
"""
        result = adapter.parse_metrics(metrics_text)

        assert result["num_requests_running"] == 5.0
        assert result["num_requests_waiting"] == 10.0
        assert result["time_to_first_token_seconds"] == 0.5
        assert result["generation_tokens_total"] == 1000

    def test_parse_metrics_empty(self, adapter):
        """测试解析空指标"""
        result = adapter.parse_metrics("")

        assert result["num_requests_running"] is None
        assert result["num_requests_waiting"] is None
        assert result["time_to_first_token_seconds"] is None
        assert result["generation_tokens_total"] is None

    def test_parse_metrics_partial(self, adapter):
        """测试解析部分指标"""
        metrics_text = """
vllm:num_requests_running{} 3
vllm:num_requests_waiting{} 7
"""
        result = adapter.parse_metrics(metrics_text)

        assert result["num_requests_running"] == 3
        assert result["num_requests_waiting"] == 7
        assert result["time_to_first_token_seconds"] is None
        assert result["generation_tokens_total"] is None

    def test_finish_reason_conversion(self, adapter):
        """测试 finish_reason 转换"""
        # 测试 stop -> end_turn
        assert adapter._convert_finish_reason("stop") == "end_turn"

        # 测试 length -> max_tokens
        assert adapter._convert_finish_reason("length") == "max_tokens"

        # 测试 content_filter -> stop_sequence
        assert adapter._convert_finish_reason("content_filter") == "stop_sequence"

        # 测试未知值原样返回
        assert adapter._convert_finish_reason("unknown") == "unknown"
