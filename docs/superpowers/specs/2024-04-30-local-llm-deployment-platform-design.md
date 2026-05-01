# 本地大模型部署平台设计文档

## 项目概述

### 项目名称
本地大模型部署平台（Local LLM Deployment Platform）

### 目标
开发一个统一的Web应用，用于部署、管理和监控本地大语言模型，支持多种推理引擎（vLLM、LMDeploy、Llama.cpp），提供完整的参数可视化配置、API转发、性能测试和日志管理功能。

### 目标用户
个人开发者或小团队（几人规模），主要用于测试和开发场景。

---

## 目标服务器环境

| 项目 | 配置 |
|------|------|
| **GPU** | 2× Tesla V100-SXM2-32GB (32GB) + 1× RTX 3060 (12GB) |
| **系统** | Ubuntu 24.04.4 LTS |
| **内存** | 62GB |
| **磁盘** | 937GB NVMe (剩余289GB) |
| **Python** | 3.12.3 |
| **Docker** | 29.4.1 |
| **已安装引擎** | vLLM 0.16.0、LMDeploy 0.12.2、Llama.cpp |

---

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| **前端** | Vue.js 3 + Element Plus + ECharts |
| **后端** | Python FastAPI |
| **数据库** | SQLite |
| **进程管理** | Python subprocess |
| **图表库** | ECharts |

### 选型理由
- **Vue.js**：国内生态好、中文文档多、上手快，Element Plus提供丰富的表单组件
- **FastAPI**：异步高性能、自动API文档、Python原生调用推理引擎
- **SQLite**：轻量级、无需额外部署、适合小团队使用

---

## 系统架构

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Browser                            │
│                    (局域网访问)                              │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                    FastAPI 服务                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                     API Layer                          │ │
│  │  /api/models  /api/services  /api/proxy  /api/benchmark│ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Core Services                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │模型管理   │ │服务管理   │ │API转发   │ │性能测试   │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │              日志系统                              │  │ │
│  │  │     请求日志  │  响应日志  │  性能指标日志        │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Engine Adapters                       │ │
│  │      VLLMAdapter  │  LMDeployAdapter  │  LlamaCppAdapter│ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │ subprocess / Python API
┌─────────────────────────▼───────────────────────────────────┐
│              Inference Engines (本地进程)                    │
│         vLLM    │    LMDeploy    │    Llama.cpp             │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 职责 |
|------|------|
| **模型管理** | 模型下载、本地模型列表、模型文件管理 |
| **服务管理** | 推理服务启停、参数配置、多实例管理 |
| **API转发** | OpenAI/Claude/原生API格式转换与转发 |
| **性能测试** | 并发测试、Token范围测试、模型/引擎对比测试 |
| **日志系统** | 请求日志、响应日志、性能指标日志 |

---

## 功能模块详细设计

### 1. 模型管理模块

#### 功能列表
- 从 HuggingFace / ModelScope 下载模型
- 管理本地模型列表（扫描指定目录）
- 模型信息展示（名称、大小、格式、支持的引擎）
- 模型文件管理（删除、移动、重命名）

#### 数据结构

```python
class ModelInfo:
    id: str              # 模型唯一ID（如 Qwen/Qwen2.5-32B）
    name: str            # 显示名称
    path: str            # 本地存储路径
    size: int            # 文件大小（GB）
    format: str          # 格式：safetensors / gguf / pytorch
    supported_engines: list  # 支持的引擎：vllm, lmdeploy, llama.cpp
    metadata: dict       # 其他元数据
```

#### API接口

```
GET    /api/models                    # 获取模型列表
GET    /api/models/{id}               # 获取模型详情
POST   /api/models/download           # 下载模型
DELETE /api/models/{id}               # 删除模型
POST   /api/models/scan               # 扫描模型目录
```

---

### 2. 服务管理模块

#### 功能列表
- 创建推理服务实例（选择模型 + 引擎 + 参数）
- 启动/停止/重启服务
- 参数配置（分组展示 + 配置文件导入导出）
- 服务状态监控（运行状态、端口、PID）
- 多实例管理（同时运行多个服务）

#### 参数分组策略

| 分组 | 参数示例 |
|------|---------|
| **基础配置** | model_path, tokenizer, dtype |
| **GPU/硬件** | tensor_parallel_size, gpu_memory_utilization, max_model_len |
| **推理配置** | max_tokens, temperature, top_p, top_k, repetition_penalty |
| **性能优化** | kv_cache_dtype, enable_prefix_caching, speculative_decoding |
| **API配置** | host, port, api_key, max_concurrent_requests |
| **高级参数** | 其他引擎特定参数（折叠展示） |

#### 数据结构

```python
class ServiceInstance:
    id: str              # 服务实例ID
    name: str            # 服务名称
    model_id: str        # 使用的模型ID
    engine: str          # 推理引擎：vllm / lmdeploy / llama.cpp
    config: dict         # 参数配置（JSON）
    status: str          # 状态：running / stopped / error
    port: int            # 服务端口
    pid: int             # 进程ID
    created_at: datetime # 创建时间
```

#### API接口

```
GET    /api/services                  # 获取服务列表
GET    /api/services/{id}             # 获取服务详情
POST   /api/services                  # 创建服务
POST   /api/services/{id}/start       # 启动服务
POST   /api/services/{id}/stop        # 停止服务
POST   /api/services/{id}/restart     # 重启服务
DELETE /api/services/{id}             # 删除服务
GET    /api/services/{id}/logs        # 获取服务日志
GET    /api/services/{id}/metrics     # 获取服务指标
```

---

### 3. API转发模块

#### 功能列表
- 统一入口，接收客户端请求
- 三种转发模式：
  - **OpenAI格式**（默认）— 转换为标准OpenAI API格式
  - **Claude格式** — 支持Claude Code协议
  - **透传模式** — 直接转发到引擎原生API
- 请求路由（根据模型名或服务ID路由到对应推理服务）
- 流式响应支持（SSE）

#### 路由配置

```python
class RouteConfig:
    model_prefix: str    # 模型名前缀匹配（如 qwen-*）
    target_service: str  # 目标服务ID
    api_format: str     # API格式：openai / claude / passthrough
```

#### API接口

```
POST /v1/chat/completions   # OpenAI格式
POST /v1/messages           # Claude格式
GET  /v1/models             # 获取可用模型列表
POST /api/proxy/config      # 设置转发模式
GET  /api/proxy/routes      # 获取路由规则
POST /api/proxy/routes      # 添加路由规则
DELETE /api/proxy/routes/{id}  # 删除路由规则
```

---

### 4. 性能测试模块

#### 功能列表
- 并发压力测试（可配置并发数、请求数）
- Token长度范围测试（指定范围和步长）
- 模型对比测试（相同参数对比不同模型）
- 引擎对比测试（相同模型对比不同引擎）
- 测试报告生成（图表展示）
- 历史测试记录查看

#### 测试配置

```python
class BenchmarkConfig:
    # 目标配置
    target_url: str
    model: str
    
    # Token范围配置
    prompt_tokens_start: int = 1024
    prompt_tokens_end: int = 16384
    prompt_tokens_step: int = 1024  # 步长（1024整数倍）
    
    # 并发配置
    concurrent: int = 4
    requests_per_point: int = 10
    
    # 输出配置
    max_tokens: int = 128
    stream: bool = True

class CompareConfig:
    compare_type: str  # model / engine
    targets: List[str]  # 对比目标列表
    config: BenchmarkConfig
```

#### 性能指标

| 指标类别 | 具体指标 |
|---------|---------|
| **Prefill阶段** | Prefill时间、Prefill Token数、Prefill吞吐量 |
| **Decode阶段** | Decode时间、Decode Token数、Decode吞吐量、TPOT |
| **整体性能** | TTFT(首Token延迟)、总Token数、整体TPS |
| **资源监控** | GPU利用率、显存占用、KV Cache占用、系统内存 |

#### 结果展示图表

| 图表 | X轴 | Y轴 |
|------|-----|-----|
| 吞吐量曲线 | 输入Token长度 | Token/秒 |
| 延迟曲线 | 输入Token长度 | TTFT、TPOT |
| Prefill/Decode对比 | 输入Token长度 | 时间 |
| 资源利用率 | 输入Token长度 | 百分比 |
| 汇总对比表格 | 各模型/引擎关键指标汇总 | - |

#### API接口

```
POST /api/benchmark/single     # 单模型/单引擎测试
POST /api/benchmark/compare    # 对比测试
GET  /api/benchmark/{id}/status # 获取测试进度
GET  /api/benchmark/{id}/result # 获取测试结果
GET  /api/benchmark/history    # 历史测试记录
DELETE /api/benchmark/{id}     # 删除测试记录
```

---

### 5. 日志系统模块

#### 功能列表
- 请求日志记录（完整请求内容）
- 响应日志记录（完整响应内容 + 性能指标）
- 日志查询与筛选
- 日志导出（JSON/CSV格式）
- 日志统计分析

#### 日志字段

| 字段 | 请求日志 | 响应日志 |
|------|---------|---------|
| timestamp | ✅ | ✅ |
| request_id | ✅ | ✅ |
| api_type | ✅ | ✅ |
| model | ✅ | ✅ |
| prompt_length | ✅ | - |
| prompt_content | ✅ | - |
| parameters | ✅ | - |
| status | - | ✅ |
| output_length | - | ✅ |
| output_content | - | ✅ |
| total_time | - | ✅ |
| prefill_time | - | ✅ |
| prefill_tokens | - | ✅ |
| decode_time | - | ✅ |
| decode_tokens | - | ✅ |
| ttft | - | ✅ |
| tpot | - | ✅ |
| gpu_util | - | ✅ |
| memory_used | - | ✅ |

#### 日志存储配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 日志保留天数 | 30天 | 超过天数自动清理 |
| 单文件大小上限 | 100MB | 超过后自动分片 |
| 内容脱敏 | 关闭 | 可选择脱敏prompt/output内容 |

#### API接口

```
GET  /api/logs/requests         # 查询请求日志
GET  /api/logs/responses        # 查询响应日志
GET  /api/logs/{request_id}     # 获取完整日志详情
GET  /api/logs/stats            # 日志统计
GET  /api/logs/export           # 导出日志（支持JSON/CSV格式）
DELETE /api/logs                # 清理日志（按时间范围）
```

---

## 引擎适配层设计

### 参数分层架构

```
第一层：通用参数（所有引擎共有）
  - model_path, max_tokens, temperature, top_p, top_k, stream, host, port

第二层：引擎通用参数（同类引擎共有）
  - vLLM: max_model_len, gpu_memory_utilization, tensor_parallel_size
  - LMDeploy: session_len, cache_max_entry_count
  - Llama.cpp: ctx_size, n_gpu_layers

第三层：引擎独有参数（各引擎特有）
  - vLLM独有: speculative_model, enable_chunked_prefill, swap_space, quantization...
  - LMDeploy独有: turbomind, max_prefill_token_num...
  - Llama.cpp独有: rope_scaling, rope_freq_base, flash_attn...
```

### 参数配置文件结构

```
/config/engines/
├── vllm/
│   ├── v0.16.0_params.yaml
│   ├── v0.8.0_params.yaml
│   └── versions.yaml
├── lmdeploy/
│   ├── v0.12.2_params.yaml
│   └── versions.yaml
└── llamacpp/
    ├── b4500_params.yaml
    └── versions.yaml
```

### 参数配置文件示例

```yaml
engine: vllm
version: "0.16.0"

common_params:
  - name: model
    type: string
    required: true
    group: basic
    description: "模型路径"

unique_params:
  - name: gpu_memory_utilization
    type: float
    default: 0.9
    range: [0.1, 1.0]
    group: performance
    description: "GPU显存利用率"

groups:
  basic: "基础配置"
  performance: "性能优化"
  advanced: "高级参数"
```

### 版本适配机制

```yaml
# versions.yaml
engine: vllm

version_detection:
  method: "command"
  command: "vllm --version"
  parse_pattern: "(\d+\.\d+\.\d+)"

compatibility:
  ">=0.16.0": "v0.16.0_params.yaml"
  ">=0.8.0,<0.16.0": "v0.8.0_params.yaml"

changes:
  "0.16.0":
    added: ["enable_chunked_prefill", "kv_cache_dtype"]
    removed: ["old_param_name"]
    renamed:
      - { from: "block_size", to: "max_num_seqs" }
```

### 适配器接口

```python
class BaseEngineAdapter(ABC):
    def get_supported_params(self) -> dict: pass
    def get_param_groups(self) -> dict: pass
    def start_service(self, config: dict) -> ProcessInfo: pass
    def stop_service(self, process_id: int) -> bool: pass
    def get_service_status(self, process_id: int) -> ServiceStatus: pass
    def get_metrics(self, process_id: int) -> dict: pass
    def transform_request(self, request: dict, api_type: str) -> dict: pass
    def transform_response(self, response: dict, api_type: str) -> dict: pass
```

---

## 数据存储设计

### 存储方案

| 数据类型 | 存储方式 |
|---------|---------|
| 模型信息 | SQLite + 文件扫描 |
| 服务实例 | SQLite |
| 配置文件 | YAML文件 |
| 日志数据 | 文件 + SQLite |
| 测试结果 | SQLite + JSON文件 |
| 引擎参数定义 | YAML文件 |

### 数据库表

```sql
-- 模型信息表
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER,
    format TEXT,
    supported_engines TEXT,
    metadata TEXT,
    created_at DATETIME
);

-- 服务实例表
CREATE TABLE services (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    model_id TEXT,
    engine TEXT NOT NULL,
    config TEXT NOT NULL,
    status TEXT,
    port INTEGER,
    pid INTEGER,
    created_at DATETIME
);

-- 测试结果表
CREATE TABLE benchmark_results (
    id TEXT PRIMARY KEY,
    test_type TEXT,
    config TEXT NOT NULL,
    summary TEXT,
    status TEXT,
    created_at DATETIME
);

-- 请求日志表
CREATE TABLE request_logs (
    id TEXT PRIMARY KEY,
    request_id TEXT UNIQUE,
    timestamp DATETIME,
    api_type TEXT,
    model TEXT,
    prompt_length INTEGER,
    parameters TEXT,
    status TEXT
);

-- 响应日志表
CREATE TABLE response_logs (
    id TEXT PRIMARY KEY,
    request_id TEXT,
    timestamp DATETIME,
    status TEXT,
    output_length INTEGER,
    total_time REAL,
    prefill_time REAL,
    decode_time REAL,
    ttft REAL,
    tpot REAL,
    gpu_util REAL
);
```

### 文件存储结构

```
/data/
├── models/                      # 模型文件目录
├── configs/                     # 配置文件
│   ├── services/               # 服务配置模板
│   └── engines/                # 引擎参数定义
├── logs/                        # 日志文件
│   ├── requests/
│   ├── responses/
│   └── services/
├── benchmark/                   # 性能测试数据
│   ├── results/
│   └── exports/
└── database/
    └── portal.db
```

---

## 前端页面设计

### 页面结构

| 页面 | 功能 |
|------|------|
| 模型管理 | 模型列表、下载、删除 |
| 服务管理 | 服务列表、创建/启停、参数配置 |
| API转发 | 转发配置、路由规则、统计信息 |
| 性能测试 | 新建测试、进度查看、结果图表 |
| 日志查询 | 日志筛选、详情查看、导出 |
| 系统设置 | 基础配置、GPU监控 |

---

## 技术实现要点

### 1. 进程管理

```python
class ProcessManager:
    def start(self, engine: str, config: dict) -> ProcessInfo:
        cmd = self.build_command(engine, config)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        self.wait_for_ready(process, config['port'])
        return ProcessInfo(pid=process.pid, port=config['port'])
    
    def stop(self, pid: int) -> bool:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
```

### 2. 流式响应

```python
async def stream_response(request: dict, service: ServiceInstance):
    engine_request = adapter.transform_request(request)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:{service.port}/generate",
            json=engine_request
        )
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:])
                yield adapter.transform_stream_chunk(data)
```

### 3. 指标采集

```python
class MetricsCollector:
    async def collect_from_vllm(self, port: int) -> EngineMetrics:
        response = await client.get(f"http://localhost:{port}/metrics")
        return self.parse_prometheus(response.text)
```

### 4. GPU监控

```python
class GPUMonitor:
    def get_status(self) -> List[GPUStatus]:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu", 
             "index,name,utilization.gpu,memory.used,memory.total",
             "--format", "csv,noheader"],
            capture_output=True
        )
        return self.parse_output(result.stdout)
```

---

## 部署说明

### 部署位置
目标服务器（与模型同机）：Ubuntu 24.04, 192.168.31.24

### 部署方式
- FastAPI 服务使用 systemd 或 supervisor 管理
- 前端静态文件由 FastAPI 或 Nginx 托管
- 数据库使用 SQLite，无需额外部署

### 访问方式
局域网内直接访问，无需认证

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2024-04-30 | 初始设计文档 |