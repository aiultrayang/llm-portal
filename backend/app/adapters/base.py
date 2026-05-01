"""推理引擎适配器基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
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

    # 引擎版本，子类应该覆盖
    _version: str = None

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass

    @property
    def version(self) -> str:
        """引擎版本"""
        return self._version or "unknown"

    def set_version(self, version: str):
        """设置引擎版本"""
        self._version = version

    @abstractmethod
    def get_supported_params(self) -> Dict[str, Any]:
        """获取支持的参数定义（从配置文件动态加载）"""
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

    # 新增方法：从配置文件获取参数
    def load_params_from_config(self, version: str = None) -> Dict[str, Any]:
        """
        从 YAML 配置文件加载参数定义

        Args:
            version: 版本号，如果不指定则使用当前版本

        Returns:
            参数定义字典
        """
        from .config_loader import config_loader
        return config_loader.get_all_params(self.name, version or self.version)

    def load_groups_from_config(self, version: str = None) -> Dict[str, str]:
        """
        从 YAML 配置文件加载参数分组

        Args:
            version: 版本号

        Returns:
            分组名称映射
        """
        from .config_loader import config_loader
        return config_loader.get_param_groups(self.name, version or self.version)

    # 新增方法：启动服务（子类可选实现）
    def start_service(self, config: Dict[str, Any]) -> ProcessInfo:
        """
        启动服务（使用进程管理器）

        Args:
            config: 服务配置

        Returns:
            进程信息
        """
        # 默认实现：构建命令并返回
        command = self.build_command(config)
        port = config.get('port', self.get_default_port())
        # 实际启动由 ProcessManager 完成
        return ProcessInfo(pid=0, port=port, command=command)

    # 新增方法：停止服务（子类可选实现）
    def stop_service(self, pid: int) -> bool:
        """停止服务"""
        # 由 ProcessManager 完成
        return True

    # 新增方法：获取服务状态
    def get_service_status(self, pid: int) -> ServiceStatus:
        """获取服务状态"""
        # 由 ProcessManager 完成
        return ServiceStatus(running=False, pid=pid)

    # 新增方法：获取指标
    def get_metrics(self, port: int) -> Dict[str, Any]:
        """
        从服务获取性能指标

        Args:
            port: 服务端口

        Returns:
            指标字典
        """
        import requests
        try:
            metrics_url = f"http://localhost:{port}/metrics"
            response = requests.get(metrics_url, timeout=5)
            if response.status_code == 200:
                return self.parse_metrics(response.text)
        except Exception:
            pass
        return {}

    # 辅助方法：验证参数值
    def validate_param(self, name: str, value: Any, param_def: Dict[str, Any]) -> bool:
        """
        验证参数值是否符合定义

        Args:
            name: 参数名
            value: 参数值
            param_def: 参数定义

        Returns:
            是否有效
        """
        param_type = param_def.get('type', 'string')

        # 类型检查
        if param_type == 'int':
            if not isinstance(value, (int, float)) or value != int(value):
                return False
            value = int(value)
        elif param_type == 'float':
            if not isinstance(value, (int, float)):
                return False
        elif param_type == 'boolean':
            if not isinstance(value, bool):
                return False
        elif param_type == 'string':
            if not isinstance(value, str):
                return False

        # 范围检查
        if param_type in ('int', 'float'):
            min_val = param_def.get('min')
            max_val = param_def.get('max')
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False

        # 选择检查
        choices = param_def.get('choices')
        if choices and value not in choices:
            return False

        return True

    # 辅助方法：获取参数默认值
    def get_param_defaults(self) -> Dict[str, Any]:
        """
        获取所有参数的默认值

        Returns:
            默认值字典
        """
        params = self.get_supported_params()
        defaults = {}
        for name, defn in params.items():
            if defn.get('default') is not None:
                defaults[name] = defn['default']
        return defaults

    # 辅助方法：过滤有效参数
    def filter_valid_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        过滤出有效的参数

        Args:
            config: 配置字典

        Returns:
            有效参数字典
        """
        params = self.get_supported_params()
        valid = {}

        for name, value in config.items():
            if name in params:
                if self.validate_param(name, value, params[name]):
                    valid[name] = value

        return valid