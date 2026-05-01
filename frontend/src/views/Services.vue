<template>
  <div class="services-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>服务管理</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            创建服务
          </el-button>
        </div>
      </template>

      <!-- 服务列表 -->
      <div class="service-list" v-loading="loading">
        <el-row :gutter="20" v-if="serviceList.length > 0">
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
                  <span class="info-value">{{ service.model_name || '-' }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">引擎:</span>
                  <span class="info-value">{{ service.engine }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">端口:</span>
                  <span class="info-value">{{ service.port || '-' }}</span>
                </div>
                <div class="info-row" v-if="service.pid">
                  <span class="info-label">PID:</span>
                  <span class="info-value">{{ service.pid }}</span>
                </div>
              </div>

              <!-- 启动命令 -->
              <div class="command-section" v-if="service.command">
                <div class="command-header" @click="toggleCommand(service.id)">
                  <span class="command-label">启动命令</span>
                  <el-icon :class="{ 'is-expanded': expandedCommands[service.id] }">
                    <ArrowDown />
                  </el-icon>
                </div>
                <div class="command-content" v-show="expandedCommands[service.id]">
                  <code>{{ service.command }}</code>
                  <el-button size="small" text @click="copyCommand(service.command)">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
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
                </el-button>
                <el-button
                  v-if="service.status === 'running'"
                  type="warning"
                  size="small"
                  @click="handleStop(service)"
                  :loading="service.stopping"
                >
                  <el-icon><VideoPause /></el-icon>
                </el-button>
                <el-button
                  type="primary"
                  size="small"
                  @click="handleRestart(service)"
                  :loading="service.restarting"
                  :disabled="service.status !== 'running'"
                >
                  <el-icon><RefreshRight /></el-icon>
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="confirmDelete(service)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else description="暂无服务，请创建新服务" :image-size="100" />
      </div>
    </el-card>

    <!-- 创建服务对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建推理服务" width="800px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createFormRef" label-position="left">
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="服务名称" prop="name">
              <el-input v-model="createForm.name" placeholder="输入服务名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="推理引擎" prop="engine">
              <el-select v-model="createForm.engine" placeholder="选择引擎" style="width: 100%" @change="handleEngineChange">
                <el-option label="llama.cpp" value="llamacpp" />
                <el-option label="vLLM" value="vllm" />
                <el-option label="LMDeploy" value="lmdeploy" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="选择模型" prop="model_id">
              <el-select v-model="createForm.model_id" placeholder="选择模型" style="width: 100%" @change="handleModelChange">
                <el-option
                  v-for="model in filteredModels"
                  :key="model.id"
                  :label="model.name"
                  :value="model.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="createForm.port" :min="1024" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 引擎参数配置 -->
        <el-divider content-position="left">引擎参数</el-divider>

        <div v-if="engineParamsLoading" class="loading-params">
          <el-icon class="is-loading" size="24"><Loading /></el-icon>
          <span>加载参数...</span>
        </div>

        <el-tabs v-else-if="engineParamGroups.length > 0" v-model="activeParamGroup" type="border-card">
          <el-tab-pane
            v-for="group in engineParamGroups"
            :key="group.key"
            :label="group.label"
            :name="group.key"
          >
            <el-row :gutter="16">
              <el-col :span="12" v-for="param in getParamsByGroup(group.key)" :key="param.name">
                <el-form-item :prop="`config.${param.name}`">
                  <template #label>
                    <span class="param-label">{{ getShortLabel(param) }}</span>
                    <el-tooltip v-if="param.description && param.description.length > 10" :content="param.description" placement="top">
                      <el-icon class="param-tip"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                  <!-- 整数滑块 -->
                  <el-slider
                    v-if="param.type === 'int' && isSliderParam(param)"
                    v-model="engineParams[param.name]"
                    :min="param.min ?? 0"
                    :max="param.max ?? 100"
                    show-input
                    :disabled="param.required"
                    size="small"
                  />
                  <!-- 整数输入 -->
                  <el-input-number
                    v-else-if="param.type === 'int'"
                    v-model="engineParams[param.name]"
                    :min="param.min"
                    :max="param.max"
                    controls-position="right"
                    style="width: 100%"
                    size="small"
                  />
                  <!-- 浮点数 -->
                  <el-input-number
                    v-else-if="param.type === 'float'"
                    v-model="engineParams[param.name]"
                    :min="param.min"
                    :max="param.max"
                    :precision="2"
                    controls-position="right"
                    style="width: 100%"
                    size="small"
                  />
                  <!-- 布尔值 -->
                  <el-switch
                    v-else-if="param.type === 'boolean'"
                    v-model="engineParams[param.name]"
                  />
                  <!-- 选择列表 -->
                  <el-select
                    v-else-if="param.choices && param.choices.length > 0"
                    v-model="engineParams[param.name]"
                    style="width: 100%"
                    size="small"
                  >
                    <el-option v-for="c in param.choices" :key="c" :label="c" :value="c" />
                  </el-select>
                  <!-- 字符串 -->
                  <el-input
                    v-else
                    v-model="engineParams[param.name]"
                    :placeholder="param.default?.toString()"
                    :disabled="param.required"
                    size="small"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>
        </el-tabs>

        <!-- 默认参数（无参数定义时） -->
        <div v-else class="default-params">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="上下文">
                <el-input-number v-model="engineParams.n_ctx" :min="512" :max="131072" :step="512" style="width: 100%" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="GPU层">
                <el-input-number v-model="engineParams.n_gpu_layers" :min="-1" :max="999" style="width: 100%" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- 启动命令预览 -->
        <el-divider content-position="left">启动命令</el-divider>
        <div class="command-preview">
          <pre>{{ previewCommand }}</pre>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateService" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认 -->
    <el-dialog v-model="showDeleteDialog" title="确认删除" width="400px">
      <div class="delete-warning">
        <el-icon size="48" color="#F56C6C"><WarningFilled /></el-icon>
        <p>确定要删除服务 <strong>{{ serviceToDelete?.name }}</strong> 吗？</p>
      </div>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" @click="handleDeleteService" :loading="deleting">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { Plus, Cpu, VideoPlay, VideoPause, RefreshRight, Delete, WarningFilled, Loading, ArrowDown, CopyDocument, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { serviceApi, modelApi } from '../api'
import axios from 'axios'

const API_BASE = 'http://192.168.31.24:8606'

const loading = ref(false)
const creating = ref(false)
const deleting = ref(false)
const engineParamsLoading = ref(false)
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const serviceToDelete = ref(null)
const createFormRef = ref()
const expandedCommands = ref({})
const activeParamGroup = ref('basic')

const serviceList = ref([])
const availableModels = ref([])
const serviceMetrics = ref({})
const engineParamDefs = ref({})
const engineParamGroups = ref([])

const createForm = reactive({
  name: '',
  model_id: null,
  engine: 'llamacpp',
  port: 8080
})

const engineParams = reactive({})

const createRules = {
  name: [{ required: true, message: '请输入服务名称', trigger: 'blur' }],
  model_id: [{ required: true, message: '请选择模型', trigger: 'change' }],
  engine: [{ required: true, message: '请选择引擎', trigger: 'change' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }]
}

// 根据引擎过滤模型
const filteredModels = computed(() => {
  const engine = createForm.engine
  return availableModels.value.filter(model => {
    if (!model.supported_engines || model.supported_engines.length === 0) return true
    return model.supported_engines.includes(engine)
  })
})

// 预览命令
const previewCommand = computed(() => {
  if (!createForm.model_id) return '请先选择模型'
  const model = availableModels.value.find(m => m.id === createForm.model_id)
  if (!model) return '请先选择模型'

  const config = { ...engineParams, port: createForm.port }
  const engine = createForm.engine

  const parts = []
  if (engine === 'vllm') {
    parts.push('vllm serve', model.path)
    if (config.port) parts.push(`--port ${config.port}`)
    if (config.host) parts.push(`--host ${config.host}`)
    if (config.dtype && config.dtype !== 'auto') parts.push(`--dtype ${config.dtype}`)
    if (config.tensor_parallel_size > 1) parts.push(`--tensor-parallel-size ${config.tensor_parallel_size}`)
    if (config.gpu_memory_utilization) parts.push(`--gpu-memory-utilization ${config.gpu_memory_utilization}`)
    if (config.max_model_len) parts.push(`--max-model-len ${config.max_model_len}`)
  } else if (engine === 'lmdeploy') {
    parts.push('lmdeploy serve api_server', model.path)
    parts.push(`--server-port ${config.port || 8001}`)
    if (config.server_name) parts.push(`--server-name ${config.server_name}`)
    if (config.tp > 1) parts.push(`--tp ${config.tp}`)
    if (config.cache_max_entry_count) parts.push(`--cache-max-entry-count ${config.cache_max_entry_count}`)
  } else {
    parts.push('llama-server', `-m ${model.path}`)
    parts.push(`--port ${config.port || 8080}`)
    parts.push(`--host ${config.host || '0.0.0.0'}`)
    if (config.n_ctx) parts.push(`-c ${config.n_ctx}`)
    if (config.n_gpu_layers !== undefined && config.n_gpu_layers !== -1) parts.push(`-ngl ${config.n_gpu_layers}`)
  }
  return parts.join(' \\\n  ')
})

// 获取简短标签
const getShortLabel = (param) => {
  const labels = {
    'model': '模型',
    'model_path': '模型路径',
    'model_alias': '别名',
    'n_ctx': '上下文',
    'n_gpu_layers': 'GPU层',
    'n_batch': '批处理',
    'n_predict': '最大输出',
    'temp': '温度',
    'top_k': 'Top-K',
    'top_p': 'Top-P',
    'repeat_penalty': '重复惩罚',
    'host': '监听地址',
    'port': '端口',
    'threads': '线程',
    'mlock': '内存锁定',
    'flash_attn': 'Flash Attn',
    'dtype': '精度',
    'tensor_parallel_size': 'TP大小',
    'gpu_memory_utilization': '显存利用率',
    'max_model_len': '最大长度',
    'server_name': '监听地址',
    'server_port': '端口',
    'tp': 'TP大小',
    'cache_max_entry_count': '缓存比例',
    'session_len': '会话长度',
    'quantization': '量化'
  }
  return labels[param.name] || param.name
}

// 判断是否适合滑块
const isSliderParam = (param) => {
  const range = (param.max ?? 100) - (param.min ?? 0)
  return range <= 100 && range > 1 && param.max > 1
}

const toggleCommand = (id) => { expandedCommands.value[id] = !expandedCommands.value[id] }
const copyCommand = async (cmd) => {
  try { await navigator.clipboard.writeText(cmd); ElMessage.success('已复制') } catch (e) { ElMessage.error('复制失败') }
}

const loadServices = async () => {
  loading.value = true
  try {
    const res = await serviceApi.list()
    serviceList.value = (res.services || []).map(s => ({ ...s, starting: false, stopping: false, restarting: false }))
  } catch (e) {
    console.error(e)
    serviceList.value = []
  } finally { loading.value = false }
}

const loadModels = async () => {
  try { availableModels.value = await modelApi.list() || [] } catch (e) { availableModels.value = [] }
}

const openCreateDialog = async () => {
  try {
    const res = await axios.get(`${API_BASE}/api/services/port?start_port=8000&end_port=9000`)
    createForm.port = res.data.port
  } catch (e) { createForm.port = 8080 }
  await handleEngineChange(createForm.engine)
  showCreateDialog.value = true
}

const handleEngineChange = async (engine) => {
  engineParamsLoading.value = true
  engineParamDefs.value = {}
  engineParamGroups.value = []
  Object.keys(engineParams).forEach(k => delete engineParams[k])

  try {
    const res = await axios.get(`${API_BASE}/api/services/engines/${engine}/params`)
    const params = res.data.params || {}
    const groups = res.data.groups || {}

    engineParamDefs.value = params
    engineParamGroups.value = Object.entries(groups).map(([k, l]) => ({ key: k, label: l }))

    Object.entries(params).forEach(([name, def]) => {
      if (def.default !== undefined) engineParams[name] = def.default
    })
    activeParamGroup.value = engineParamGroups.value[0]?.key || 'basic'
  } catch (e) {
    console.error(e)
    engineParams.n_ctx = 4096
    engineParams.n_gpu_layers = -1
  } finally { engineParamsLoading.value = false }
}

const getParamsByGroup = (group) => Object.entries(engineParamDefs.value).filter(([, def]) => def.group === group).map(([name, def]) => ({ name, ...def }))

const handleModelChange = (id) => {
  const m = availableModels.value.find(x => x.id === id)
  if (m && !createForm.name) createForm.name = `${m.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-service`
}

const getStatusType = (s) => ({ running: 'success', stopped: 'info', starting: 'warning', stopping: 'warning', error: 'danger' }[s] || 'info')
const getStatusText = (s) => ({ running: '运行中', stopped: '已停止', starting: '启动中', stopping: '停止中', error: '错误' }[s] || s)

const handleStart = async (s) => {
  s.starting = true
  try { Object.assign(s, await serviceApi.start(s.id)); ElMessage.success(`服务 ${s.name} 已启动`) }
  catch (e) { ElMessage.error(`启动失败: ${parseError(e)}`) }
  finally { s.starting = false }
}

const handleStop = async (s) => {
  s.stopping = true
  try { Object.assign(s, await serviceApi.stop(s.id)); ElMessage.warning(`服务 ${s.name} 已停止`) }
  catch (e) { ElMessage.error(`停止失败: ${parseError(e)}`) }
  finally { s.stopping = false }
}

const handleRestart = async (s) => {
  s.restarting = true
  try { Object.assign(s, await serviceApi.restart(s.id)); ElMessage.success(`服务 ${s.name} 已重启`) }
  catch (e) { ElMessage.error(`重启失败: ${parseError(e)}`) }
  finally { s.restarting = false }
}

const confirmDelete = (s) => { serviceToDelete.value = s; showDeleteDialog.value = true }

const handleDeleteService = async () => {
  if (!serviceToDelete.value) return
  deleting.value = true
  try {
    await serviceApi.delete(serviceToDelete.value.id)
    serviceList.value = serviceList.value.filter(x => x.id !== serviceToDelete.value.id)
    ElMessage.success('服务已删除')
  } catch (e) { ElMessage.error(`删除失败: ${parseError(e)}`) }
  finally { deleting.value = false; showDeleteDialog.value = false; serviceToDelete.value = null }
}

// 解析错误消息
const parseError = (e) => {
  const detail = e.response?.data?.detail
  if (!detail) return e.message || '未知错误'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(d => d.msg || JSON.stringify(d)).join('; ')
  }
  return JSON.stringify(detail)
}

const handleCreateService = async () => {
  try {
    await createFormRef.value.validate()
    creating.value = true
    await serviceApi.create({
      name: createForm.name,
      model_id: createForm.model_id,
      engine: createForm.engine,
      port: createForm.port,
      config: { ...engineParams, port: createForm.port }
    })
    ElMessage.success('服务创建成功')
    showCreateDialog.value = false
    await loadServices()
  } catch (e) {
    if (e !== false) ElMessage.error(`创建失败: ${parseError(e)}`)
  } finally { creating.value = false }
}

let refreshInterval = null
onMounted(() => { loadServices(); loadModels(); refreshInterval = setInterval(() => serviceList.value.forEach(s => s.status === 'running' && loadServiceStatus(s.id)), 15000) })
onUnmounted(() => { if (refreshInterval) clearInterval(refreshInterval) })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.service-list { padding: 10px 0; }
.service-card { margin-bottom: 20px; }
.service-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.service-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 500; }
.service-info { margin-bottom: 16px; }
.info-row { display: flex; justify-content: space-between; margin-bottom: 8px; }
.info-label { color: #909399; }
.info-value { color: #303133; font-weight: 500; }

.command-section { background: #f5f7fa; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
.command-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; cursor: pointer; }
.command-header:hover { background: #e9ecef; }
.command-label { font-size: 13px; color: #606266; }
.command-header .el-icon { transition: transform 0.3s; }
.command-header .el-icon.is-expanded { transform: rotate(180deg); }
.command-content { padding: 12px; border-top: 1px solid #e4e7ed; display: flex; align-items: flex-start; gap: 8px; }
.command-content code { flex: 1; font-size: 12px; word-break: break-all; white-space: pre-wrap; color: #303133; }

.service-controls { display: flex; gap: 8px; justify-content: center; }

.loading-params { display: flex; align-items: center; gap: 8px; justify-content: center; padding: 20px; color: #909399; }
.default-params { padding: 12px; background: #f5f7fa; border-radius: 8px; }

.command-preview { background: #1e1e1e; border-radius: 8px; padding: 16px; overflow-x: auto; }
.command-preview pre { color: #d4d4d4; font-size: 13px; white-space: pre-wrap; word-break: break-all; margin: 0; font-family: Consolas, Monaco, monospace; }

.param-label { font-size: 13px; }
.param-tip { margin-left: 4px; color: #909399; cursor: help; }

.delete-warning { text-align: center; padding: 20px; }
.delete-warning p { margin: 12px 0; }

:deep(.el-form-item) { margin-bottom: 16px; }
:deep(.el-form-item__label) { font-size: 13px; color: #606266; }
:deep(.el-tabs__header) { margin-bottom: 12px; }
:deep(.el-tab-pane) { padding: 8px 0; }
</style>