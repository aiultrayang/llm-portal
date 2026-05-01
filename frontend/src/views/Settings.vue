<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <!-- 基础设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>基础设置</span>
            </div>
          </template>
          <el-form :model="basicSettings" label-width="120px" v-loading="loading">
            <el-form-item label="日志级别">
              <el-select v-model="basicSettings.logLevel" @change="saveBasicSettings">
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARN" value="warn" />
                <el-option label="ERROR" value="error" />
              </el-select>
            </el-form-item>
            <el-form-item label="请求超时">
              <el-input-number v-model="basicSettings.timeout" :min="10" :max="600" @change="saveBasicSettings" />
              <span style="margin-left: 8px; color: #999;">秒</span>
            </el-form-item>
            <el-form-item label="日志保留天数">
              <el-input-number v-model="basicSettings.logRetention" :min="1" :max="90" @change="saveBasicSettings" />
              <span style="margin-left: 8px; color: #999;">天</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- GPU 设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>GPU 设置</span>
              <el-button size="small" @click="refreshGPU" :loading="gpuLoading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <el-form :model="gpuSettings" label-width="120px" v-loading="gpuLoading">
            <el-form-item label="默认GPU层">
              <el-slider v-model="gpuSettings.defaultLayers" :min="-1" :max="100" show-input @change="saveGpuSettings" />
              <div class="form-hint">-1 表示全部加载到 GPU</div>
            </el-form-item>
            <el-form-item label="显存阈值">
              <el-input-number v-model="gpuSettings.vramThreshold" :min="50" :max="100" @change="saveGpuSettings" />
              <span style="margin-left: 8px; color: #999;">%</span>
            </el-form-item>
            <el-form-item label="自动卸载">
              <el-switch v-model="gpuSettings.autoUnload" @change="saveGpuSettings" />
            </el-form-item>
          </el-form>

          <!-- GPU 状态显示 -->
          <el-divider content-position="left">当前GPU状态</el-divider>
          <div class="gpu-status" v-if="gpuInfo.length > 0">
            <div v-for="gpu in gpuInfo" :key="gpu.index" class="gpu-item">
              <div class="gpu-header">
                <span class="gpu-name">{{ gpu.name }}</span>
                <el-tag size="small" :type="gpu.temperature > 80 ? 'danger' : 'success'">
                  {{ gpu.temperature }}°C
                </el-tag>
              </div>
              <div class="gpu-metrics">
                <div class="metric">
                  <span class="label">利用率:</span>
                  <el-progress :percentage="gpu.utilization" :stroke-width="10" />
                </div>
                <div class="metric">
                  <span class="label">显存:</span>
                  <span>{{ gpu.memoryUsed.toFixed(1) }} / {{ gpu.memoryTotal }} GB</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else description="无法获取GPU信息" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 模型默认参数 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>默认模型参数</span>
          </template>
          <el-form :model="modelDefaults" label-width="120px">
            <el-form-item label="默认上下文">
              <el-input-number v-model="modelDefaults.contextLength" :min="512" :max="32768" :step="512" @change="saveModelDefaults" />
            </el-form-item>
            <el-form-item label="默认温度">
              <el-slider v-model="modelDefaults.temperature" :min="0" :max="2" :step="0.1" show-input @change="saveModelDefaults" />
            </el-form-item>
            <el-form-item label="Top P">
              <el-slider v-model="modelDefaults.topP" :min="0" :max="1" :step="0.05" show-input @change="saveModelDefaults" />
            </el-form-item>
            <el-form-item label="最大生成长度">
              <el-input-number v-model="modelDefaults.maxTokens" :min="32" :max="8192" @change="saveModelDefaults" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 模型扫描路径 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>模型扫描路径</span>
              <el-button type="primary" size="small" @click="showPathDialog = true">
                <el-icon><Plus /></el-icon>
                添加路径
              </el-button>
            </div>
          </template>
          <div class="scan-path-list" v-if="scanPaths.length > 0">
            <div v-for="path in scanPaths" :key="path.id" class="scan-path-item">
              <div class="path-info">
                <el-icon><Folder /></el-icon>
                <span class="path-text">{{ path.path }}</span>
                <el-tag v-if="path.description" size="small" type="info">{{ path.description }}</el-tag>
              </div>
              <div class="path-actions">
                <el-switch v-model="path.enabled" size="small" @change="togglePath(path)" />
                <el-button type="danger" size="small" text @click="deletePath(path)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="尚未配置扫描路径" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加路径对话框 -->
    <el-dialog v-model="showPathDialog" title="添加模型扫描路径" width="600px" destroy-on-close>
      <div class="path-browser">
        <div class="current-path">
          <span class="path-label">当前目录：</span>
          <el-input v-model="currentBrowsePath" readonly>
            <template #append>
              <el-button @click="goToParent" :disabled="!browseData.parent_path">
                <el-icon><ArrowUp /></el-icon>
              </el-button>
            </template>
          </el-input>
        </div>

        <div class="directory-list" v-loading="browsing">
          <div
            v-for="item in browseData.items"
            :key="item.path"
            class="directory-item"
            :class="{ is_model: item.is_model, is_dir: item.is_dir, selected: selectedPath === item.path }"
            @click="selectedPath = item.path"
            @dblclick="handleItemDblClick(item)"
          >
            <el-icon v-if="item.is_dir"><Folder /></el-icon>
            <el-icon v-else><Document /></el-icon>
            <span class="item-name">{{ item.name }}</span>
            <el-tag v-if="item.is_model" type="success" size="small">模型</el-tag>
            <el-icon v-if="selectedPath === item.path" class="check-icon"><Check /></el-icon>
          </div>
          <el-empty v-if="browseData.items.length === 0" description="空目录" :image-size="40" />
        </div>

        <div class="selected-path" v-if="selectedPath">
          <span class="path-label">选中路径：</span>
          <el-input v-model="selectedPath" readonly />
          <el-input v-model="pathDescription" placeholder="添加描述（可选）" style="margin-top: 8px;" />
        </div>

        <div class="quick-actions">
          <el-button size="small" @click="selectCurrentPath">
            <el-icon><Folder /></el-icon>
            选择当前目录
          </el-button>
          <span class="hint">单击选中，双击进入目录</span>
        </div>
      </div>

      <template #footer>
        <el-button @click="showPathDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmAddPath" :disabled="!selectedPath" :loading="addingPath">
          确认添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Refresh, Plus, Folder, Delete, ArrowUp, Document, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { systemApi, configApi } from '../api'

const loading = ref(false)
const gpuLoading = ref(false)
const browsing = ref(false)
const addingPath = ref(false)
const showPathDialog = ref(false)

const basicSettings = reactive({
  logLevel: 'info',
  timeout: 120,
  logRetention: 7
})

const gpuSettings = reactive({
  defaultLayers: -1,
  vramThreshold: 80,
  autoUnload: false
})

const modelDefaults = reactive({
  contextLength: 4096,
  temperature: 0.7,
  topP: 0.9,
  maxTokens: 2048
})

const gpuInfo = ref([])
const scanPaths = ref([])
const browseData = ref({ current_path: '/', parent_path: null, items: [] })
const currentBrowsePath = ref('/')
const selectedPath = ref('')
const pathDescription = ref('')

// 加载设置
const loadSettings = async () => {
  loading.value = true
  try {
    // 加载各项设置
    const keys = ['logLevel', 'timeout', 'logRetention', 'defaultLayers', 'vramThreshold', 'autoUnload', 'contextLength', 'temperature', 'topP', 'maxTokens']

    for (const key of keys) {
      try {
        const res = await configApi.get(key)
        if (res && res.value !== undefined) {
          if (['timeout', 'logRetention', 'defaultLayers', 'contextLength', 'maxTokens'].includes(key)) {
            basicSettings[key] = parseInt(res.value) || basicSettings[key]
            if (['defaultLayers', 'vramThreshold', 'autoUnload'].includes(key)) {
              gpuSettings[key] = key === 'autoUnload' ? res.value === 'true' : parseInt(res.value) || gpuSettings[key]
            }
            if (['contextLength', 'temperature', 'topP', 'maxTokens'].includes(key)) {
              modelDefaults[key] = key === 'temperature' || key === 'topP' ? parseFloat(res.value) : parseInt(res.value) || modelDefaults[key]
            }
          } else {
            basicSettings[key] = res.value
          }
        }
      } catch (e) {
        // 设置项不存在，使用默认值
      }
    }
  } finally {
    loading.value = false
  }
}

// 加载GPU信息
const refreshGPU = async () => {
  gpuLoading.value = true
  try {
    const res = await systemApi.gpu()
    gpuInfo.value = res.gpus || []
  } catch (error) {
    console.error('Failed to load GPU info:', error)
    gpuInfo.value = []
  } finally {
    gpuLoading.value = false
  }
}

// 加载扫描路径
const loadScanPaths = async () => {
  try {
    const res = await configApi.getScanPaths()
    scanPaths.value = res || []
  } catch (error) {
    console.error('Failed to load scan paths:', error)
    scanPaths.value = []
  }
}

// 保存设置
const saveBasicSettings = async () => {
  try {
    await configApi.set('logLevel', basicSettings.logLevel)
    await configApi.set('timeout', basicSettings.timeout.toString())
    await configApi.set('logRetention', basicSettings.logRetention.toString())
    ElMessage.success('基础设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const saveGpuSettings = async () => {
  try {
    await configApi.set('defaultLayers', gpuSettings.defaultLayers.toString())
    await configApi.set('vramThreshold', gpuSettings.vramThreshold.toString())
    await configApi.set('autoUnload', gpuSettings.autoUnload.toString())
    ElMessage.success('GPU设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const saveModelDefaults = async () => {
  try {
    await configApi.set('contextLength', modelDefaults.contextLength.toString())
    await configApi.set('temperature', modelDefaults.temperature.toString())
    await configApi.set('topP', modelDefaults.topP.toString())
    await configApi.set('maxTokens', modelDefaults.maxTokens.toString())
    ElMessage.success('模型默认参数已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 浏览目录
const browseDirectory = async (path) => {
  browsing.value = true
  try {
    const res = await configApi.browseDirectory(path)
    browseData.value = res
    currentBrowsePath.value = res.current_path
  } catch (error) {
    ElMessage.error(`无法浏览目录: ${error.response?.data?.detail || error.message}`)
  } finally {
    browsing.value = false
  }
}

const handleItemDblClick = (item) => {
  if (item.is_dir) {
    browseDirectory(item.path)
    selectedPath.value = ''
  }
}

const goToParent = () => {
  if (browseData.value.parent_path) {
    browseDirectory(browseData.value.parent_path)
  }
}

const selectCurrentPath = () => {
  selectedPath.value = currentBrowsePath.value
}

// 添加路径
const confirmAddPath = async () => {
  if (!selectedPath.value) return

  addingPath.value = true
  try {
    await configApi.addScanPath(selectedPath.value, pathDescription.value)
    ElMessage.success('路径添加成功')
    showPathDialog.value = false
    selectedPath.value = ''
    pathDescription.value = ''
    await loadScanPaths()
  } catch (error) {
    ElMessage.error(`添加失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    addingPath.value = false
  }
}

// 切换路径状态
const togglePath = async (path) => {
  try {
    await configApi.toggleScanPath(path.id)
    ElMessage.success(path.enabled ? '路径已禁用' : '路径已启用')
  } catch (error) {
    ElMessage.error('操作失败')
    path.enabled = !path.enabled // 恢复原状态
  }
}

// 删除路径
const deletePath = async (path) => {
  try {
    await configApi.deleteScanPath(path.id)
    ElMessage.success('路径已删除')
    await loadScanPaths()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 监听对话框打开
import { watch } from 'vue'
watch(showPathDialog, (val) => {
  if (val) {
    browseDirectory('/')
  }
})

onMounted(() => {
  loadSettings()
  loadScanPaths()
  refreshGPU()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.gpu-status {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gpu-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #f5f7fa;
}

.gpu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.gpu-name {
  font-weight: 500;
  color: #303133;
}

.gpu-metrics {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric .label {
  width: 60px;
  font-size: 13px;
  color: #606266;
}

.scan-path-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scan-path-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #f5f7fa;
}

.scan-path-item:has(.path-text:empty) {
  opacity: 0.6;
}

.path-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.path-text {
  font-size: 14px;
  color: #303133;
}

.path-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 路径浏览器样式 */
.path-browser {
  padding: 16px 0;
}

.current-path {
  margin-bottom: 16px;
}

.path-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  display: block;
}

.directory-list {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
}

.directory-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.directory-item:hover {
  background: #f0f2f5;
}

.directory-item.is_dir {
  color: #409eff;
}

.directory-item.is_model {
  background: #f0f9eb;
}

.directory-item.is_model:hover {
  background: #e1f3d8;
}

.directory-item.selected {
  background: #ecf5ff;
  border: 1px solid #409eff;
}

.item-name {
  flex: 1;
}

.check-icon {
  color: #409eff;
  margin-left: auto;
}

.selected-path {
  margin-top: 16px;
  padding: 12px;
  background: #ecf5ff;
  border-radius: 8px;
}

.quick-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  font-size: 12px;
  color: #909399;
}
</style>
