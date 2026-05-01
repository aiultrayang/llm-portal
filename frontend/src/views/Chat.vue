<template>
  <div class="chat-page">
    <el-row :gutter="20" class="chat-container">
      <!-- 左侧会话列表 -->
      <el-col :span="6">
        <el-card class="session-list">
          <template #header>
            <div class="card-header">
              <span>会话列表</span>
              <el-button type="primary" size="small" @click="newSession">
                <el-icon><Plus /></el-icon>
                新建
              </el-button>
            </div>
          </template>
          <div
            v-for="session in sessions"
            :key="session.id"
            class="session-item"
            :class="{ active: currentSession === session.id }"
            @click="selectSession(session.id)"
          >
            <div class="session-title">{{ session.title }}</div>
            <div class="session-time">{{ session.time }}</div>
          </div>
          <el-empty v-if="sessions.length === 0" description="暂无会话" :image-size="60" />
        </el-card>

        <!-- 模型选择 -->
        <el-card style="margin-top: 10px;">
          <template #header>
            <span>当前模型</span>
          </template>
          <el-select v-model="selectedModel" placeholder="选择模型" style="width: 100%;" :loading="loadingModels">
            <el-option
              v-for="service in runningServices"
              :key="service.id"
              :label="service.name"
              :value="service.id"
            />
          </el-select>
          <div class="model-hint" v-if="runningServices.length === 0">
            <el-text type="info" size="small">暂无运行中的服务，请先启动服务</el-text>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧对话区 -->
      <el-col :span="18">
        <el-card class="chat-area">
          <div class="messages" ref="messagesRef">
            <el-empty v-if="messages.length === 0" description="开始对话吧" :image-size="100" />
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="message"
              :class="msg.role"
            >
              <div class="message-avatar">
                <el-avatar v-if="msg.role === 'user'" icon="UserFilled" />
                <el-avatar v-else icon="Monitor" />
              </div>
              <div class="message-content">
                <div class="message-text">{{ msg.content }}</div>
                <div class="message-meta">
                  <span class="token-count" v-if="msg.tokens">{{ msg.tokens }} tokens</span>
                  <span class="time">{{ msg.time }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="input-area">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              placeholder="输入消息..."
              @keydown.enter.ctrl="sendMessage"
              :disabled="!selectedModel"
            />
            <div class="input-actions">
              <el-checkbox v-model="streamMode">流式输出</el-checkbox>
              <el-button type="primary" @click="sendMessage" :loading="sending" :disabled="!selectedModel">
                发送 (Ctrl+Enter)
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { serviceApi } from '../api'

const selectedModel = ref('')
const inputText = ref('')
const streamMode = ref(true)
const sending = ref(false)
const messagesRef = ref()
const loadingModels = ref(false)

const currentSession = ref(1)
const sessions = ref([])
const messages = ref([])
const runningServices = ref([])

// 加载运行中的服务列表
const loadRunningServices = async () => {
  loadingModels.value = true
  try {
    const res = await serviceApi.list()
    const services = res.services || []
    runningServices.value = services.filter(s => s.status === 'running')
    if (runningServices.value.length > 0 && !selectedModel.value) {
      selectedModel.value = runningServices.value[0].id
    }
  } catch (error) {
    console.error('Failed to load services:', error)
  } finally {
    loadingModels.value = false
  }
}

const newSession = () => {
  const id = sessions.value.length + 1
  sessions.value.unshift({ id, title: `新会话 ${id}`, time: '刚刚' })
  currentSession.value = id
  messages.value = []
  ElMessage.success('新建会话成功')
}

const selectSession = (id) => {
  currentSession.value = id
}

const sendMessage = async () => {
  if (!inputText.value.trim()) return
  if (!selectedModel.value) {
    ElMessage.warning('请先选择一个运行中的模型')
    return
  }

  sending.value = true

  // 添加用户消息
  const userMsg = {
    id: messages.value.length + 1,
    role: 'user',
    content: inputText.value,
    tokens: inputText.value.length,
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(userMsg)

  const prompt = inputText.value
  inputText.value = ''

  try {
    // 获取选中的服务信息
    const service = runningServices.value.find(s => s.id === selectedModel.value)
    if (!service) {
      throw new Error('服务不存在')
    }

    // 调用实际的推理服务
    const response = await fetch(`http://192.168.31.24:${service.port}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: service.model_id || 'default',
        messages: messages.value.filter(m => m.role !== 'system').map(m => ({
          role: m.role,
          content: m.content
        })),
        max_tokens: 512,
        temperature: 0.7,
        stream: false
      })
    })

    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`)
    }

    const data = await response.json()
    const aiContent = data.choices?.[0]?.message?.content || '无响应内容'

    // 添加AI回复
    const aiMsg = {
      id: messages.value.length + 1,
      role: 'assistant',
      content: aiContent,
      tokens: data.usage?.completion_tokens || aiContent.length,
      time: new Date().toLocaleTimeString()
    }
    messages.value.push(aiMsg)
  } catch (error) {
    console.error('Send message error:', error)
    ElMessage.error(`发送失败: ${error.message}`)

    // 添加错误提示
    const errorMsg = {
      id: messages.value.length + 1,
      role: 'assistant',
      content: `抱歉，请求失败: ${error.message}\n请确保服务正在运行。`,
      tokens: 0,
      time: new Date().toLocaleTimeString()
    }
    messages.value.push(errorMsg)
  } finally {
    sending.value = false
  }

  // 滚动到底部
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

onMounted(() => {
  loadRunningServices()
})
</script>

<style scoped>
.chat-container {
  height: calc(100vh - 180px);
}

.session-list {
  height: 100%;
  overflow-y: auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: background-color 0.2s;
}

.session-item:hover {
  background-color: #f5f7fa;
}

.session-item.active {
  background-color: #ecf5ff;
}

.session-title {
  font-size: 14px;
  color: #333;
}

.session-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.chat-area {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 8px;
  background-color: #f0f0f0;
}

.message.user .message-content {
  background-color: #409EFF;
  color: #fff;
}

.message-meta {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
  display: flex;
  gap: 12px;
}

.message.user .message-meta {
  color: rgba(255, 255, 255, 0.8);
}

.input-area {
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.model-hint {
  margin-top: 8px;
  text-align: center;
}
</style>