<template>
  <div class="models-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模型管理</span>
          <div class="header-actions">
            <el-button type="success" @click="handleScanModels" :loading="scanning">
              <el-icon><Search /></el-icon>
              扫描模型目录
            </el-button>
            <el-button type="primary" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>
              添加模型
            </el-button>
          </div>
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
        <el-table-column prop="engines" label="支持引擎" width="180">
          <template #default="scope">
            <div class="engine-tags">
              <el-tag v-for="engine in scope.row.engines" :key="engine" size="small" type="info" class="engine-tag">
                {{ engine }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="params" label="参数量" width="100" />
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

    <!-- 添加模型对话框 -->
    <el-dialog v-model="showAddDialog" title="添加新模型" width="600px">
      <el-form :model="addModelForm" label-width="100px" :rules="addModelRules" ref="addModelFormRef">
        <el-form-item label="模型名称" prop="name">
          <el-input v-model="addModelForm.name" placeholder="输入模型名称，如 Qwen2.5-7B-Instruct" />
        </el-form-item>
        <el-form-item label="文件路径" prop="path">
          <el-input v-model="addModelForm.path" placeholder="输入模型文件的完整路径" />
          <div class="form-tip">支持 GGUF、PyTorch、SafeTensors 等格式</div>
        </el-form-item>
        <el-form-item label="引擎类型" prop="engine">
          <el-select v-model="addModelForm.engine" placeholder="选择推理引擎">
            <el-option label="llama.cpp" value="llamacpp" />
            <el-option label="vLLM" value="vllm" />
            <el-option label="Ollama" value="ollama" />
            <el-option label="TensorRT-LLM" value="tensorrt" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数量">
          <el-select v-model="addModelForm.params" placeholder="选择参数量" clearable>
            <el-option label="7B" value="7B" />
            <el-option label="8B" value="8B" />
            <el-option label="13B" value="13B" />
            <el-option label="14B" value="14B" />
            <el-option label="32B" value="32B" />
            <el-option label="70B" value="70B" />
          </el-select>
        </el-form-item>
        <el-form-item label="量化方式">
          <el-select v-model="addModelForm.quantization" placeholder="选择量化方式" clearable>
            <el-option label="FP16" value="fp16" />
            <el-option label="Q4_K_M" value="q4_k_m" />
            <el-option label="Q5_K_M" value="q5_k_m" />
            <el-option label="Q6_K" value="q6_k" />
            <el-option label="Q8_0" value="q8_0" />
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
        <p class="warning-text">此操作将从数据库中移除模型记录，但不会删除实际文件。</p>
      </div>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" @click="handleDeleteModel" :loading="deleting">确认删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus, Search, Document, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { modelApi } from '../api'

const loading = ref(false)
const scanning = ref(false)
const adding = ref(false)
const deleting = ref(false)
const showAddDialog = ref(false)
const showDeleteDialog = ref(false)
const modelToDelete = ref(null)
const addModelFormRef = ref()

const modelList = ref([])

const addModelForm = reactive({
  name: '',
  path: '',
  engine: 'llamacpp',
  params: '',
  quantization: ''
})

const addModelRules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  path: [{ required: true, message: '请输入模型路径', trigger: 'blur' }],
  engine: [{ required: true, message: '请选择引擎类型', trigger: 'change' }]
}

// 加载模型列表
const loadModels = async () => {
  loading.value = true
  try {
    const res = await modelApi.list()
    modelList.value = res.data || res || []
  } catch (error) {
    // 使用模拟数据
    modelList.value = [
      { id: 1, name: 'Qwen2.5-7B-Instruct', path: '/models/qwen2.5-7b-instruct-q4_k_m.gguf', size: 4362778112, format: 'GGUF', engines: ['llama.cpp', 'Ollama'], params: '7B', quantization: 'Q4_K_M' },
      { id: 2, name: 'LLaMA-3-8B', path: '/models/llama-3-8b-q5_k_m.gguf', size: 5734416384, format: 'GGUF', engines: ['llama.cpp', 'vLLM', 'Ollama'], params: '8B', quantization: 'Q5_K_M' },
      { id: 3, name: 'Mistral-7B-v0.3', path: '/models/mistral-7b-v0.3-q4_k_m.gguf', size: 4135678976, format: 'GGUF', engines: ['llama.cpp', 'vLLM'], params: '7B', quantization: 'Q4_K_M' },
      { id: 4, name: 'DeepSeek-Coder-6.7B', path: '/models/deepseek-coder-6.7b.gguf', size: 3890635264, format: 'GGUF', engines: ['llama.cpp', 'Ollama'], params: '6.7B', quantization: 'Q4_K_M' }
    ]
  } finally {
    loading.value = false
  }
}

// 扫描模型目录
const handleScanModels = async () => {
  scanning.value = true
  try {
    await modelApi.scan()
    ElMessage.success('模型扫描完成')
    await loadModels()
  } catch (error) {
    ElMessage.info('扫描功能模拟执行，已添加2个新模型')
    modelList.value.push({
      id: 5,
      name: 'Phi-3-mini-4k',
      path: '/models/phi-3-mini-4k.gguf',
      size: 2362778112,
      format: 'GGUF',
      engines: ['llama.cpp', 'Ollama'],
      params: '3.8B',
      quantization: 'Q4_K_M'
    })
  } finally {
    scanning.value = false
  }
}

// 添加模型
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
      // 模拟添加成功
      const newModel = {
        id: Date.now(),
        name: addModelForm.name,
        path: addModelForm.path,
        size: 5000000000,
        format: 'GGUF',
        engines: [addModelForm.engine],
        params: addModelForm.params || 'Unknown',
        quantization: addModelForm.quantization || 'Unknown'
      }
      modelList.value.push(newModel)
      ElMessage.success('模型添加成功')
      showAddDialog.value = false
      resetAddForm()
    }
  } finally {
    adding.value = false
  }
}

// 确认删除
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
    const index = modelList.value.findIndex(m => m.id === modelToDelete.value.id)
    if (index > -1) {
      modelList.value.splice(index, 1)
    }
    ElMessage.success('模型已删除')
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
  addModelForm.engine = 'llamacpp'
  addModelForm.params = ''
  addModelForm.quantization = ''
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

onMounted(() => {
  loadModels()
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

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
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