"""推理引擎适配器基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    port: int
    command: str


@dataclass
class ServiceStatus:
    """服务状态"""
    running: bool
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: Optional[float] = None


class BaseEngineAdapter(ABC):
    """推理引擎适配器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass

    @abstractmethod
    def get_supported_params(self) -> Dict[str, Any]:
        """获取支持的参数定义"""
        pass

    @abstractmethod
    def get_param_groups(self) -> Dict[str, str]:
        """获取参数分组"""
        pass

    @abstractmethod
    def build_command(self, config: Dict[str, Any]) -> str:
        """构建启动命令"""
        pass

    @abstractmethod
    def get_default_port(self) -> int:
        """获取默认端口"""
        pass

    @abstractmethod
    def transform_request(self, request: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """转换请求格式 (OpenAI/Claude/passthrough)"""
        pass

    @abstractmethod
    def transform_response(self, response: Dict[str, Any], api_type: str) -> Dict[str, Any]:
        """转换响应格式"""
        pass

    @abstractmethod
    def parse_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """解析性能指标"""
        pass

    @abstractmethod
    def health_check_url(self, port: int) -> str:
        """健康检查URL"""
        pass
