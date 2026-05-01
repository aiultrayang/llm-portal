"""引擎参数配置加载器"""

import os
import yaml
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache


class EngineConfigLoader:
    """引擎参数配置加载器"""

    def __init__(self, config_dir: str = None):
        """
        初始化配置加载器

        Args:
            config_dir: 配置文件目录，默认为 backend/config/engines
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # 默认配置目录
            self.config_dir = Path(__file__).parent.parent.parent / "config" / "engines"

    @lru_cache(maxsize=10)
    def load_params_config(self, engine: str, version: str = None) -> Dict[str, Any]:
        """
        加载引擎参数配置

        Args:
            engine: 引擎名称 (vllm, lmdeploy, llamacpp)
            version: 版本号，如果不指定则自动检测

        Returns:
            参数配置字典
        """
        engine_dir = self.config_dir / engine
        if not engine_dir.exists():
            return {}

        # 如果未指定版本，尝试自动检测
        if not version:
            version = self._detect_version(engine)

        # 根据版本兼容性找到合适的配置文件
        config_file = self._find_config_file(engine, version)
        if not config_file:
            # 尝试使用默认配置
            config_file = self._get_default_config_file(engine)

        if not config_file or not config_file.exists():
            return {}

        # 加载 YAML 配置
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except Exception as e:
            print(f"Error loading config {config_file}: {e}")
            return {}

    def _detect_version(self, engine: str) -> Optional[str]:
        """
        检测引擎版本

        Args:
            engine: 引擎名称

        Returns:
            版本号字符串
        """
        # 加载版本检测配置
        versions_file = self.config_dir / engine / "versions.yaml"
        if not versions_file.exists():
            return None

        try:
            with open(versions_file, 'r', encoding='utf-8') as f:
                versions_config = yaml.safe_load(f)
        except Exception:
            return None

        detection = versions_config.get('version_detection', {})
        method = detection.get('method', 'command')

        if method == 'command':
            command = detection.get('command', '')
            pattern = detection.get('parse_pattern', r'(\d+\.\d+\.\d+)')

            if not command:
                return None

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    match = re.search(pattern, result.stdout + result.stderr)
                    if match:
                        return match.group(1)
            except Exception as e:
                print(f"Error detecting version for {engine}: {e}")

        return None

    def _find_config_file(self, engine: str, version: str) -> Optional[Path]:
        """
        根据版本兼容性找到合适的配置文件

        Args:
            engine: 引擎名称
            version: 版本号

        Returns:
            配置文件路径
        """
        engine_dir = self.config_dir / engine
        versions_file = engine_dir / "versions.yaml"

        if not versions_file.exists():
            # 尝试直接使用版本对应的文件
            direct_file = engine_dir / f"v{version}_params.yaml"
            if direct_file.exists():
                return direct_file
            return None

        try:
            with open(versions_file, 'r', encoding='utf-8') as f:
                versions_config = yaml.safe_load(f)
        except Exception:
            return None

        # 解析版本号
        try:
            from packaging.version import Version
        except ImportError:
            # 简单版本比较
            def parse_ver(v):
                return tuple(map(int, v.split('.')))
        else:
            def parse_ver(v):
                return Version(v)

        compatibility = versions_config.get('compatibility', {})

        # 按优先级匹配（从高到低）
        for version_spec, config_name in sorted(
            compatibility.items(),
            key=lambda x: parse_ver(x[0].split(',')[0].replace('>=', '').replace('>', '').strip()),
            reverse=True
        ):
            if self._version_matches(version, version_spec):
                config_file = engine_dir / config_name
                if config_file.exists():
                    return config_file

        return None

    def _version_matches(self, version: str, spec: str) -> bool:
        """
        检查版本是否匹配规范

        Args:
            version: 实际版本号
            spec: 版本规范（如 ">=0.16.0" 或 ">=0.8.0,<0.16.0"）

        Returns:
            是否匹配
        """
        # 预处理版本号：处理特殊格式如 "b4500" -> "4500"
        def normalize_version(v):
            # 处理 "b4500" 格式（llamacpp 的 build number）
            if v.startswith('b') and v[1:].isdigit():
                return v[1:]
            return v

        version = normalize_version(version)

        try:
            from packaging.version import Version
        except ImportError:
            # 简单版本解析
            parts = []
            for part in version.split('.'):
                match = re.match(r'(\d+)', part)
                parts.append(int(match.group(1)) if match else 0)
            ver_tuple = tuple(parts)

            def check_op(v1_tuple, op, v2_tuple):
                if op == '>=':
                    return v1_tuple >= v2_tuple
                elif op == '>':
                    return v1_tuple > v2_tuple
                elif op == '<':
                    return v1_tuple < v2_tuple
                elif op == '<=':
                    return v1_tuple <= v2_tuple
                return False

            def parse_spec(s):
                match = re.match(r'(>=|>|<=|<)(\d+(?:\.\d+)*)', s)
                if match:
                    op = match.group(1)
                    v_parts = []
                    for p in match.group(2).split('.'):
                        v_parts.append(int(p))
                    return op, tuple(v_parts)
                return None, None

            # 解析规范
            for part in spec.split(','):
                part = part.strip()
                op, ref_ver = parse_spec(part)
                if op and ref_ver:
                    if not check_op(ver_tuple, op, ref_ver):
                        return False

            return True
        else:
            ver = Version(version)

            for part in spec.split(','):
                part = part.strip()
                if part.startswith('>='):
                    if ver < Version(part[2:]):
                        return False
                elif part.startswith('>'):
                    if ver <= Version(part[1:]):
                        return False
                elif part.startswith('<='):
                    if ver > Version(part[2:]):
                        return False
                elif part.startswith('<'):
                    if ver >= Version(part[1:]):
                        return False

            return True

    def _get_default_config_file(self, engine: str) -> Optional[Path]:
        """获取默认配置文件"""
        engine_dir = self.config_dir / engine

        # 尝试常见的默认文件名
        default_names = [
            "v0.16.0_params.yaml",  # vllm
            "v0.12.2_params.yaml",  # lmdeploy
            "b4500_params.yaml",    # llamacpp
        ]

        for name in default_names:
            file = engine_dir / name
            if file.exists():
                return file

        # 列出所有配置文件，取第一个
        yaml_files = list(engine_dir.glob("*_params.yaml"))
        if yaml_files:
            return yaml_files[0]

        return None

    def get_all_params(self, engine: str, version: str = None) -> Dict[str, Any]:
        """
        获取所有参数定义（合并通用参数和独特参数）

        Args:
            engine: 引擎名称
            version: 版本号

        Returns:
            参数定义字典
        """
        config = self.load_params_config(engine, version)
        if not config:
            return {}

        params = {}

        # 添加通用参数
        for param in config.get('common_params', []):
            name = param.get('name')
            if name:
                params[name] = {
                    'type': param.get('type', 'string'),
                    'default': param.get('default'),
                    'required': param.get('required', False),
                    'description': param.get('description', ''),
                    'group': param.get('group', 'basic'),
                }
                # 可选属性
                if 'choices' in param:
                    params[name]['choices'] = param['choices']
                if 'min' in param:
                    params[name]['min'] = param['min']
                if 'max' in param:
                    params[name]['max'] = param['max']
                if 'range' in param:
                    params[name]['min'] = param['range'][0]
                    params[name]['max'] = param['range'][1]

        # 添加独特参数
        for param in config.get('unique_params', []):
            name = param.get('name')
            if name:
                params[name] = {
                    'type': param.get('type', 'string'),
                    'default': param.get('default'),
                    'required': param.get('required', False),
                    'description': param.get('description', ''),
                    'group': param.get('group', 'advanced'),
                }
                if 'choices' in param:
                    params[name]['choices'] = param['choices']
                if 'min' in param:
                    params[name]['min'] = param['min']
                if 'max' in param:
                    params[name]['max'] = param['max']
                if 'range' in param:
                    params[name]['min'] = param['range'][0]
                    params[name]['max'] = param['range'][1]

        return params

    def get_param_groups(self, engine: str, version: str = None) -> Dict[str, str]:
        """
        获取参数分组映射

        Args:
            engine: 引擎名称
            version: 版本号

        Returns:
            分组名称映射
        """
        config = self.load_params_config(engine, version)
        return config.get('groups', {
            'basic': '基础参数',
            'gpu': 'GPU 参数',
            'inference': '推理参数',
            'performance': '性能参数',
            'api': 'API 参数',
            'advanced': '高级参数'
        })


# 全局配置加载器实例
config_loader = EngineConfigLoader()
