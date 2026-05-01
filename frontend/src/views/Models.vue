<template>
  <div class="models-page">
    <!-- 模型扫描路径配置 -->
    <el-card class="scan-path-card">
      <template #header>
        <div class="card-header">
          <span>模型扫描路径</span>
          <div class="header-actions">
            <el-button type="primary" size="small" @click="showPathDialog = true">
              <el-icon><Plus /></el-icon>
              添加路径
            </el-button>
            <el-button type="success" size="small" @click="handleScanModels" :loading="scanning">
              <el-icon><Search /></el-icon>
              扫描模型
            </el-button>
          </div>
        </div>
      </template>

      <div class="scan-path-list" v-if="scanPaths.length > 0">
        <el-row :gutter="12">
          <el-col :span="8" v-for="path in scanPaths" :key="path.id">
            <div class="scan-path-item" :class="{ disabled: !path.enabled }">
              <div class="path-info">
                <el-icon size="16"><Folder /></el-icon>
                <span class="path-text">{{ path.path }}</span>
              </div>
              <div class="path-actions">
                <el-switch v-model="path.enabled" size="small" @change="togglePath(path)" />
                <el-button type="danger" size="small" text @click="deletePath(path)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
      <el-empty v-else description="尚未配置扫描路径，请添加模型目录" :image-size="60" />
    </el-card>

    <!-- 模型列表 -->
    <el-card style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>模型列表</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            手动添加
          </el-button>
        </div>
      </template>

      <el-table :data="modelList" style="width: 100%" v-loading="loading">
        <el-table-column prop="name" label="模型名称" min-width="200">
          <template #default="scope">
            <div class="model-name">
              <el-icon size="18"><Document /></el-icon>
              <span>{{ scope.row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="文件路径" min-width="250" show-overflow-tooltip />
        <el-table-column prop="size" label="文件大小" width="120">
          <template #default="scope">
            {{ formatSize(scope.row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="format" label="格式" width="100">
          <template #default="scope">
            <el-tag size="small">{{ scope.row.format || 'GGUF' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="supported_engines" label="支持引擎" width="180">
          <template #default="scope">
            <div class="engine-tags">
              <el-tag v-for="engine in scope.row.supported_engines" :key="engine" size="small" type="info" class="engine-tag">
                {{ engine }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button
              type="danger"
              size="small"
              @click="confirmDelete(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加扫描路径对话框 -->
    <el-dialog v-model="showPathDialog" title="添加模型扫描路径" width="600px" destroy-on-close>
      <div class="path-browser">
        <!-- 当前路径显示 -->
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

        <!-- 目录浏览区域 -->
        <div class="directory-list" v-loading="browsing">
          <div
            v-for="item in browseData.items"
            :key="item.path"
            class="directory-item"
            :class="{
              is_model: item.is_model,
              is_dir: item.is_dir,
              selected: selectedPath === item.path
            }"
            @click="handleItemClick(item)"
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

        <!-- 选中的路径 -->
        <div class="selected-path" v-if="selectedPath">
          <span class="path-label">选中路径：</span>
          <el-input v-model="selectedPath" readonly />
          <el-input
            v-model="pathDescription"
            placeholder="添加描述（可选）"
            style="margin-top: 8px;"
          />
        </div>

        <!-- 快捷操作 -->
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

    <!-- 手动添加模型对话框 -->
    <el-dialog v-model="showAddDialog" title="手动添加模型" width="600px">
      <el-form :model="addModelForm" label-width="100px" :rules="addModelRules" ref="addModelFormRef">
        <el-form-item label="模型名称" prop="name">
          <el-input v-model="addModelForm.name" placeholder="输入模型名称" />
        </el-form-item>
        <el-form-item label="文件路径" prop="path">
          <el-input v-model="addModelForm.path" placeholder="输入模型文件的完整路径" />
        </el-form-item>
        <el-form-item label="模型格式">
          <el-select v-model="addModelForm.format" placeholder="自动检测">
            <el-option label="自动检测" value="unknown" />
            <el-option label="GGUF" value="gguf" />
            <el-option label="SafeTensors" value="safetensors" />
            <el-option label="PyTorch" value="pytorch" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddModel" :loading="adding">添加</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认对话框 -->
    <el-dialog v-model="showDeleteDialog" title="确认删除" width="400px">
      <div class="delete-warning">
        <el-icon size="48" color="#F56C6C"><WarningFilled /></el-icon>
        <p>确定要删除模型 <strong>{{ modelToDelete?.name }}</strong> 吗？</p>
        <p class="warning-text">此操作仅删除数据库记录，不会删除实际文件。</p>
      </div>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" @click="handleDeleteModel" :loading="deleting">确认删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus, Search, Document, Folder, Delete, ArrowUp, WarningFilled, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { modelApi } from '../api'
import axios from 'axios'

const API_BASE = 'http://192.168.31.24:8606'

const loading = ref(false)
const scanning = ref(false)
const adding = ref(false)
const deleting = ref(false)
const browsing = ref(false)
const addingPath = ref(false)
const showPathDialog = ref(false)
const showAddDialog = ref(false)
const showDeleteDialog = ref(false)
const modelToDelete = ref(null)
const addModelFormRef = ref()

const modelList = ref([])
const scanPaths = ref([])
const browseData = ref({ current_path: '/', parent_path: null, items: [] })
const currentBrowsePath = ref('/')
const selectedPath = ref('')
const pathDescription = ref('')

const addModelForm = reactive({
  name: '',
  path: '',
  format: 'unknown'
})

const addModelRules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  path: [{ required: true, message: '请输入模型路径', trigger: 'blur' }]
}

// 加载扫描路径列表
const loadScanPaths = async () => {
  try {
    const res = await axios.get(`${API_BASE}/api/config/scan-paths`)
    scanPaths.value = res.data || []
  } catch (error) {
    console.error('加载扫描路径失败:', error)
    scanPaths.value = []
  }
}

// 加载模型列表
const loadModels = async () => {
  loading.value = true
  try {
    const res = await modelApi.list()
    modelList.value = res || []
  } catch (error) {
    console.error('加载模型列表失败:', error)
    modelList.value = []
  } finally {
    loading.value = false
  }
}

// 浏览目录
const browseDirectory = async (path) => {
  browsing.value = true
  try {
    const res = await axios.get(`${API_BASE}/api/config/browse`, {
      params: { path }
    })
    browseData.value = res.data
    currentBrowsePath.value = res.data.current_path
  } catch (error) {
    ElMessage.error(`无法浏览目录: ${error.response?.data?.detail || error.message}`)
  } finally {
    browsing.value = false
  }
}

// 点击目录项 - 选中
const handleItemClick = (item) => {
  // 单击选中该路径
  selectedPath.value = item.path
}

// 双击目录项 - 进入目录
const handleItemDblClick = (item) => {
  if (item.is_dir) {
    browseDirectory(item.path)
    selectedPath.value = '' // 清除选中，等待新选择
  }
}

// 返回上级目录
const goToParent = () => {
  if (browseData.value.parent_path) {
    browseDirectory(browseData.value.parent_path)
  }
}

// 选中当前目录作为扫描路径
const selectCurrentPath = () => {
  selectedPath.value = currentBrowsePath.value
}

// 确认添加扫描路径
const confirmAddPath = async () => {
  if (!selectedPath.value) return

  addingPath.value = true
  try {
    await axios.post(`${API_BASE}/api/config/scan-paths`, {
      path: selectedPath.value,
      description: pathDescription.value
    })
    ElMessage.success('扫描路径添加成功')
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

// 切换路径启用状态
const togglePath = async (path) => {
  try {
    await axios.patch(`${API_BASE}/api/config/scan-paths/${path.id}/toggle`)
    ElMessage.success(path.enabled ? '路径已启用' : '路径已禁用')
  } catch (error) {
    ElMessage.error('操作失败')
    path.enabled = !path.enabled // 恢复原状态
  }
}

// 删除扫描路径
const deletePath = async (path) => {
  try {
    await axios.delete(`${API_BASE}/api/config/scan-paths/${path.id}`)
    ElMessage.success('路径已删除')
    await loadScanPaths()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 扫描模型
const handleScanModels = async () => {
  scanning.value = true
  try {
    const res = await modelApi.scan()
    const discovered = res || []
    if (discovered.length > 0) {
      ElMessage.success(`发现 ${discovered.length} 个模型`)
      // 自动添加发现的模型
      for (const model of discovered) {
        try {
          await modelApi.add({
            name: model.name,
            path: model.path,
            format: model.format,
            size: model.size
          })
        } catch (e) {
          // 可能已存在，忽略
        }
      }
      await loadModels()
    } else {
      ElMessage.info('未发现新模型')
    }
  } catch (error) {
    ElMessage.error('扫描失败')
  } finally {
    scanning.value = false
  }
}

// 手动添加模型
const handleAddModel = async () => {
  try {
    await addModelFormRef.value.validate()
    adding.value = true
    await modelApi.add(addModelForm)
    ElMessage.success('模型添加成功')
    showAddDialog.value = false
    resetAddForm()
    await loadModels()
  } catch (error) {
    if (error !== false) {
      ElMessage.error(`添加失败: ${error.response?.data?.detail || error.message}`)
    }
  } finally {
    adding.value = false
  }
}

// 确认删除模型
const confirmDelete = (model) => {
  modelToDelete.value = model
  showDeleteDialog.value = true
}

// 执行删除
const handleDeleteModel = async () => {
  if (!modelToDelete.value) return
  deleting.value = true
  try {
    await modelApi.delete(modelToDelete.value.id)
    ElMessage.success('模型已删除')
    await loadModels()
  } catch (error) {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = false
    showDeleteDialog.value = false
    modelToDelete.value = null
  }
}

// 重置添加表单
const resetAddForm = () => {
  addModelForm.name = ''
  addModelForm.path = ''
  addModelForm.format = 'unknown'
}

// 格式化文件大小
const formatSize = (bytes) => {
  if (!bytes) return 'Unknown'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) {
    return `${gb.toFixed(2)} GB`
  }
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(2)} MB`
}

// 打开路径对话框时初始化浏览
const initBrowse = () => {
  browseDirectory('/')
}

onMounted(() => {
  loadScanPaths()
  loadModels()
})

// 监听对话框打开
watch(showPathDialog, (val) => {
  if (val) {
    initBrowse()
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.scan-path-card {
  margin-bottom: 16px;
}

.scan-path-list {
  padding: 8px 0;
}

.scan-path-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #f5f7fa;
}

.scan-path-item.disabled {
  opacity: 0.6;
  background: #fafafa;
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

.model-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.engine-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.engine-tag {
  margin: 2px;
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

.item-name {
  flex: 1;
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

.directory-item.selected {
  background: #ecf5ff;
  border: 1px solid #409eff;
}

.check-icon {
  color: #409eff;
  margin-left: auto;
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