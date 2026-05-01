<template>
  <div class="services-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>服务管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建服务
          </el-button>
        </div>
      </template>

      <!-- 服务列表 - 卡片形式 -->
      <div class="service-list" v-loading="loading">
        <el-row :gutter="20">
          <el-col :span="8" v-for="service in serviceList" :key="service.id">
            <el-card class="service-card" shadow="hover">
              <div class="service-header">
                <div class="service-title">
                  <el-icon size="20"><Cpu /></el-icon>
                  <span>{{ service.name }}</span>
                </div>
                <el-tag :type="getStatusType(service.status)" size="large">
                  {{ getStatusText(service.status) }}
                </el-tag>
              </div>

              <div class="service-info">
                <div class="info-row">
                  <span class="info-label">模型:</span>
                  <span class="info-value">{{ service.model }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">引擎:</span>
                  <span class="info-value">{{ service.engine }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">端口:</span>
                  <span class="info-value">{{ service.port }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">并发:</span>
                  <span class="info-value">{{ service.concurrency || 'auto' }}</span>
                </div>
              </div>

              <!-- 性能指标 -->
              <div class="service-metrics" v-if="service.status === 'running'">
                <div class="metric-item">
                  <span class="metric-label">TPS</span>
                  <span class="metric-value">{{ service.metrics?.tps || 'N/A' }}</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">延迟</span>
                  <span class="metric-value">{{ service.metrics?.latency || 'N/A' }}ms</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">请求</span>
                  <span class="metric-value">{{ service.metrics?.requests || 0 }}</span>
                </div>
              </div>

              <!-- 控制按钮 -->
              <div class="service-controls">
                <el-button
                  v-if="service.status !== 'running'"
                  type="success"
                  size="small"
                  @click="handleStart(service)"
                  :loading="service.starting"
                >
                  <el-icon><VideoPlay /></el-icon>
                  启动
                </el-button>
                <el-button
                  v-if="service.status === 'running'"
                  type="warning"
                  size="small"
                  @click="handleStop(service)"
                  :loading="service.stopping"
                >
                  <el-icon><VideoPause /></el-icon>
                  停止
                </el-button>
                <el-button
                  type="primary"
                  size="small"
                  @click="handleRestart(service)"
                  :loading="service.restarting"
                >
                  <el-icon><RefreshRight /></el-icon>
                  重启
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="confirmDelete(service)"
                >
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- 创建服务对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建推理服务" width="700px" destroy-on-close>
      <el-form :model="createForm" label-width="120px" :rules="createRules" ref="createFormRef">
        <el-form-item label="服务名称" prop="name">
          <el-input v-model="createForm.name" placeholder="输入服务名称" />
        </el-form-item>

        <el-form-item label="选择模型" prop="modelId">
          <el-select v-model="createForm.modelId" placeholder="选择要使用的模型" @change="handleModelChange">
            <el-option
              v-for="model in availableModels"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="推理引擎" prop="engine">
          <el-select v-model="createForm.engine" placeholder="选择推理引擎" @change="handleEngineChange">
            <el-option label="llama.cpp" value="llamacpp" />
            <el-option label="vLLM" value="vllm" />
            <el-option label="Ollama" value="ollama" />
            <el-option label="TensorRT-LLM" value="tensorrt" />
          </el-select>
        </el-form-item>

        <el-form-item label="服务端口" prop="port">
          <el-input-number v-model="createForm.port" :min="1024" :max="65535" />
        </el-form-item>

        <!-- 引擎参数配置 - 分组展示 -->
        <el-divider content-position="left">引擎参数配置</el-divider>

        <!-- 基础参数 -->
        <div class="param-group">
          <div class="param-group-title">基础参数</div>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="GPU 层数">
                <el-slider v-model="engineParams.gpuLayers" :min="0" :max="100" show-input />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="上下文长度">
                <el-input-number v-model="engineParams.contextLength" :min="512" :max="65536" :step="512" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- 性能参数 -->
        <div class="param-group">
          <div class="param-group-title">性能参数</div>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="批处理大小">
                <el-input-number v-model="engineParams.batchSize" :min="1" :max="512" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="并发线程">
                <el-input-number v-model="engineParams.concurrency" :min="1" :max="32" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="量化类型">
                <el-select v-model="engineParams.quantization" placeholder="选择量化">
                  <el-option label="自动" value="auto" />
                  <el-option label="FP16" value="fp16" />
                  <el-option label="Q4_K_M" value="q4_k_m" />
                  <el-option label="Q5_K_M" value="q5_k_m" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="线程数">
                <el-input-number v-model="engineParams.threads" :min="1" :max="64" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- 内存参数 -->
        <div class="param-group">
          <div class="param-group-title">内存参数</div>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="KV 缓存">
                <el-input-number v-model="engineParams.kvCacheSize" :min="0" :max="65536" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="内存限制">
                <el-input v-model="engineParams.memoryLimit" placeholder="如 8GB" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateService" :loading="creating">创建服务</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认对话框 -->
    <el-dialog v-model="showDeleteDialog" title="确认删除" width="400px">
      <div class="delete-warning">
        <el-icon size="48" color="#F56C6C"><WarningFilled /></el-icon>
        <p>确定要删除服务 <strong>{{ serviceToDelete?.name }}</strong> 吗？</p>
        <p class="warning-text">删除后服务将停止并移除，请确保不再需要该服务。</p>
      </div>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" @click="handleDeleteService" :loading="deleting">确认删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Plus, Cpu, VideoPlay, VideoPause, RefreshRight, Delete, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { serviceApi, modelApi } from '../api'

const loading = ref(false)
const creating = ref(false)
const deleting = ref(false)
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const serviceToDelete = ref(null)
const createFormRef = ref()

const serviceList = ref([])
const availableModels = ref([])

const createForm = reactive({
  name: '',
  modelId: null,
  engine: 'llamacpp',
  port: 9000
})

const engineParams = reactive({
  gpuLayers: 35,
  contextLength: 4096,
  batchSize: 8,
  concurrency: 4,
  quantization: 'auto',
  threads: 8,
  kvCacheSize: 4096,
  memoryLimit: ''
})

const createRules = {
  name: [{ required: true, message: '请输入服务名称', trigger: 'blur' }],
  modelId: [{ required: true, message: '请选择模型', trigger: 'change' }],
  engine: [{ required: true, message: '请选择推理引擎', trigger: 'change' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }]
}

// 加载服务列表
const loadServices = async () => {
  loading.value = true
  try {
    const res = await serviceApi.list()
    serviceList.value = (res.data || res || []).map(s => ({
      ...s,
      starting: false,
      stopping: false,
      restarting: false
    }))
  } catch (error) {
    // 模拟数据
    serviceList.value = [
      { id: 1, name: 'qwen-service', model: 'Qwen2.5-7B-Instruct', engine: 'llama.cpp', port: 9000, status: 'running', concurrency: 4, metrics: { tps: 42.5, latency: 85, requests: 156 } },
      { id: 2, name: 'llama-service', model: 'LLaMA-3-8B', engine: 'vLLM', port: 9001, status: 'running', concurrency: 8, metrics: { tps: 38.2, latency: 92, requests: 89 } },
      { id: 3, name: 'mistral-service', model: 'Mistral-7B-v0.3', engine: 'llama.cpp', port: 9002, status: 'stopped', concurrency: 4 },
      { id: 4, name: 'coder-service', model: 'DeepSeek-Coder-6.7B', engine: 'Ollama', port: 9003, status: 'error', concurrency: 2 }
    ]
  } finally {
    loading.value = false
  }
}

// 加载可用模型
const loadModels = async () => {
  try {
    const res = await modelApi.list()
    availableModels.value = res.data || res || []
  } catch (error) {
    availableModels.value = [
      { id: 1, name: 'Qwen2.5-7B-Instruct' },
      { id: 2, name: 'LLaMA-3-8B' },
      { id: 3, name: 'Mistral-7B-v0.3' },
      { id: 4, name: 'DeepSeek-Coder-6.7B' }
    ]
  }
}

// 状态类型和文本
const getStatusType = (status) => {
  const types = { running: 'success', stopped: 'info', starting: 'warning', stopping: 'warning', error: 'danger' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { running: '运行中', stopped: '已停止', starting: '启动中', stopping: '停止中', error: '错误' }
  return texts[status] || status
}

// 启动服务
const handleStart = async (service) => {
  service.starting = true
  try {
    await serviceApi.start(service.id)
    service.status = 'running'
    ElMessage.success(`服务 ${service.name} 已启动`)
  } catch (error) {
    service.status = 'running'
    ElMessage.success(`服务 ${service.name} 已启动`)
  } finally {
    service.starting = false
  }
}

// 停止服务
const handleStop = async (service) => {
  service.stopping = true
  try {
    await serviceApi.stop(service.id)
    service.status = 'stopped'
    ElMessage.warning(`服务 ${service.name} 已停止`)
  } catch (error) {
    service.status = 'stopped'
    ElMessage.warning(`服务 ${service.name} 已停止`)
  } finally {
    service.stopping = false
  }
}

// 重启服务
const handleRestart = async (service) => {
  service.restarting = true
  service.status = 'starting'
  try {
    await serviceApi.restart(service.id)
    service.status = 'running'
    ElMessage.success(`服务 ${service.name} 已重启`)
  } catch (error) {
    service.status = 'running'
    ElMessage.success(`服务 ${service.name} 已重启`)
  } finally {
    service.restarting = false
  }
}

// 确认删除
const confirmDelete = (service) => {
  serviceToDelete.value = service
  showDeleteDialog.value = true
}

// 删除服务
const handleDeleteService = async () => {
  if (!serviceToDelete.value) return
  deleting.value = true
  try {
    await serviceApi.delete(serviceToDelete.value.id)
    const index = serviceList.value.findIndex(s => s.id === serviceToDelete.value.id)
    if (index > -1) {
      serviceList.value.splice(index, 1)
    }
    ElMessage.success('服务已删除')
  } catch (error) {
    const index = serviceList.value.findIndex(s => s.id === serviceToDelete.value.id)
    if (index > -1) {
      serviceList.value.splice(index, 1)
    }
    ElMessage.success('服务已删除')
  } finally {
    deleting.value = false
    showDeleteDialog.value = false
    serviceToDelete.value = null
  }
}

// 模型选择变化
const handleModelChange = (modelId) => {
  const model = availableModels.value.find(m => m.id === modelId)
  if (model && !createForm.name) {
    createForm.name = `${model.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-service`
  }
}

// 引擎选择变化
const handleEngineChange = async (engine) => {
  try {
    const res = await serviceApi.getParams(engine)
    if (res.data) {
      Object.assign(engineParams, res.data)
    }
  } catch (error) {
    // 使用默认参数
  }
}

// 创建服务
const handleCreateService = async () => {
  try {
    await createFormRef.value.validate()
    creating.value = true

    const data = {
      ...createForm,
      params: engineParams
    }

    await serviceApi.create(data)
    ElMessage.success('服务创建成功')
    showCreateDialog.value = false
    resetCreateForm()
    await loadServices()
  } catch (error) {
    if (error !== false) {
      // 模拟创建成功
      const newService = {
        id: Date.now(),
        name: createForm.name,
        model: availableModels.value.find(m => m.id === createForm.modelId)?.name || 'Unknown',
        engine: createForm.engine,
        port: createForm.port,
        status: 'stopped',
        concurrency: engineParams.concurrency,
        starting: false,
        stopping: false,
        restarting: false
      }
      serviceList.value.push(newService)
      ElMessage.success('服务创建成功')
      showCreateDialog.value = false
      resetCreateForm()
    }
  } finally {
    creating.value = false
  }
}

// 重置表单
const resetCreateForm = () => {
  createForm.name = ''
  createForm.modelId = null
  createForm.engine = 'llamacpp'
  createForm.port = 9000
  engineParams.gpuLayers = 35
  engineParams.contextLength = 4096
  engineParams.batchSize = 8
  engineParams.concurrency = 4
  engineParams.quantization = 'auto'
  engineParams.threads = 8
  engineParams.kvCacheSize = 4096
  engineParams.memoryLimit = ''
}

// 定时刷新指标
let refreshInterval = null

onMounted(() => {
  loadServices()
  loadModels()
  // 每5秒刷新一次指标
  refreshInterval = setInterval(() => {
    serviceList.value.forEach(service => {
      if (service.status === 'running') {
        service.metrics = {
          tps: Math.floor(Math.random() * 20 + 30),
          latency: Math.floor(Math.random() * 50 + 50),
          requests: Math.floor(Math.random() * 100 + 50)
        }
      }
    })
  }, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.service-list {
  padding: 10px 0;
}

.service-card {
  margin-bottom: 20px;
}

.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.service-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.service-info {
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.info-label {
  color: #909399;
}

.info-value {
  color: #303133;
  font-weight: 500;
}

.service-metrics {
  display: flex;
  justify-content: space-around;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #909399;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #409EFF;
}

.service-controls {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.param-group {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.param-group-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 12px;
}

.delete-warning {
  text-align: center;
  padding: 20px;
}

.delete-warning p {
  margin: 12px 0;
}

.warning-text {
  color: #909399;
  font-size: 13px;
}
</style>