<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <!-- 基础设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>基础设置</span>
          </template>
          <el-form :model="basicSettings" label-width="120px">
            <el-form-item label="服务端口">
              <el-input-number v-model="basicSettings.port" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="日志级别">
              <el-select v-model="basicSettings.logLevel">
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARN" value="warn" />
                <el-option label="ERROR" value="error" />
              </el-select>
            </el-form-item>
            <el-form-item label="最大连接数">
              <el-input-number v-model="basicSettings.maxConnections" :min="1" :max="1000" />
            </el-form-item>
            <el-form-item label="请求超时">
              <el-input-number v-model="basicSettings.timeout" :min="10" :max="600" />
              <span style="margin-left: 8px; color: #999;">秒</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- GPU 设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>GPU 设置</span>
          </template>
          <el-form :model="gpuSettings" label-width="120px">
            <el-form-item label="GPU 设备">
              <el-select v-model="gpuSettings.device" multiple>
                <el-option label="GPU 0 (RTX 4080)" value="0" />
                <el-option label="GPU 1 (RTX 3080)" value="1" />
              </el-select>
            </el-form-item>
            <el-form-item label="默认GPU层">
              <el-slider v-model="gpuSettings.defaultLayers" :min="0" :max="100" show-input />
            </el-form-item>
            <el-form-item label="显存阈值">
              <el-input-number v-model="gpuSettings.vramThreshold" :min="50" :max="100" />
              <span style="margin-left: 8px; color: #999;">%</span>
            </el-form-item>
            <el-form-item label="自动卸载">
              <el-switch v-model="gpuSettings.autoUnload" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模型设置 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>默认模型参数</span>
          </template>
          <el-form :model="modelDefaults" label-width="120px">
            <el-form-item label="默认上下文">
              <el-input-number v-model="modelDefaults.contextLength" :min="512" :max="32768" :step="512" />
            </el-form-item>
            <el-form-item label="默认温度">
              <el-slider v-model="modelDefaults.temperature" :min="0" :max="2" :step="0.1" show-input />
            </el-form-item>
            <el-form-item label="Top P">
              <el-slider v-model="modelDefaults.topP" :min="0" :max="1" :step="0.05" show-input />
            </el-form-item>
            <el-form-item label="最大生成长度">
              <el-input-number v-model="modelDefaults.maxTokens" :min="32" :max="4096" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 存储设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>存储设置</span>
          </template>
          <el-form :model="storageSettings" label-width="120px">
            <el-form-item label="模型目录">
              <el-input v-model="storageSettings.modelPath">
                <template #append>
                  <el-button>浏览</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="日志目录">
              <el-input v-model="storageSettings.logPath">
                <template #append>
                  <el-button>浏览</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="数据目录">
              <el-input v-model="storageSettings.dataPath">
                <template #append>
                  <el-button>浏览</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="保留日志">
              <el-input-number v-model="storageSettings.logRetention" :min="1" :max="90" />
              <span style="margin-left: 8px; color: #999;">天</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 保存按钮 -->
    <div class="action-bar">
      <el-button type="primary" size="large" @click="saveSettings">
        保存设置
      </el-button>
      <el-button size="large" @click="resetSettings">
        重置默认
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const basicSettings = reactive({
  port: 9000,
  logLevel: 'info',
  maxConnections: 100,
  timeout: 120
})

const gpuSettings = reactive({
  device: ['0'],
  defaultLayers: 35,
  vramThreshold: 80,
  autoUnload: true
})

const modelDefaults = reactive({
  contextLength: 4096,
  temperature: 0.7,
  topP: 0.9,
  maxTokens: 2048
})

const storageSettings = reactive({
  modelPath: '/Users/app/ai/claude-projects/models',
  logPath: '/Users/app/ai/claude-projects/logs',
  dataPath: '/Users/app/ai/claude-projects/data',
  logRetention: 7
})

const saveSettings = async () => {
  await ElMessageBox.confirm('确定要保存设置吗？部分设置需要重启服务才能生效。', '确认保存')
  ElMessage.success('设置已保存')
}

const resetSettings = async () => {
  await ElMessageBox.confirm('确定要重置为默认设置吗？', '确认重置')
  ElMessage.info('设置已重置')
}
</script>

<style scoped>
.action-bar {
  margin-top: 20px;
  text-align: center;
  padding: 20px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>
