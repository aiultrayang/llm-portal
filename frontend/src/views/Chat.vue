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
          <div class="session-scroll">
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
                <el-avatar v-if="msg.role === 'user'" :size="36" style="background-color: #409EFF;">
                  <el-icon :size="20"><UserFilled /></el-icon>
                </el-avatar>
                <el-avatar v-else :size="36" style="background-color: #67C23A;">
                  <el-icon :size="20"><Monitor /></el-icon>
                </el-avatar>
              </div>
              <div class="message-content">
                <div class="message-text" v-html="formatContent(msg.content)"></div>
                <!-- 用户消息的图片 -->
                <div class="message-images" v-if="msg.images && msg.images.length > 0">
                  <img v-for="(img, idx) in msg.images" :key="idx" :src="img" class="message-image" @click="previewImage(img)" />
                </div>
                <div class="message-meta">
                  <template v-if="msg.role === 'assistant' && msg.tokens">
                    <span class="meta-item">{{ msg.tokens }} tokens</span>
                    <span class="meta-item" v-if="msg.tokensPerSecond">{{ msg.tokensPerSecond.toFixed(1) }} tokens/s</span>
                    <span class="meta-item" v-if="msg.duration">{{ msg.duration.toFixed(2) }}s</span>
                  </template>
                  <span class="meta-item">{{ msg.time }}</span>
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
              placeholder="输入消息... (Ctrl+Enter 发送)"
              @keydown.enter.ctrl="sendMessage"
              :disabled="!selectedModel"
            />
            <!-- 已选图片预览 -->
            <div class="selected-images" v-if="selectedImages.length > 0">
              <div class="image-preview" v-for="(img, idx) in selectedImages" :key="idx">
                <img :src="img.url" />
                <el-icon class="remove-btn" @click="removeImage(idx)"><Close /></el-icon>
              </div>
            </div>
            <div class="input-actions">
              <div class="left-actions">
                <el-checkbox v-model="streamMode">流式输出</el-checkbox>
                <el-upload
                  ref="uploadRef"
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="handleImageSelect"
                  multiple
                >
                  <el-button :disabled="!selectedModel">
                    <el-icon><Picture /></el-icon>
                    图片
                  </el-button>
                </el-upload>
              </div>
              <div class="right-actions">
                <el-select v-model="selectedModel" placeholder="选择模型" style="width: 180px;" :loading="loadingModels">
                  <el-option
                    v-for="service in runningServices"
                    :key="service.id"
                    :label="service.model_name || service.name"
                    :value="service.id"
                  />
                </el-select>
                <el-button type="primary" @click="sendMessage" :loading="sending" :disabled="!selectedModel">
                  发送
                </el-button>
              </div>
            </div>
            <div class="model-hint" v-if="runningServices.length === 0">
              <el-text type="warning" size="small">暂无运行中的服务，请先启动服务</el-text>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图片预览对话框 -->
    <el-dialog v-model="showImagePreview" title="图片预览" width="fit-content">
      <img :src="previewImageUrl" style="max-width: 80vw; max-height: 80vh;" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { Plus, UserFilled, Monitor, Picture, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { serviceApi } from '../api'

const selectedModel = ref('')
const inputText = ref('')
const streamMode = ref(true)
const sending = ref(false)
const messagesRef = ref()
const loadingModels = ref(false)
const uploadRef = ref()

const currentSession = ref(1)
const sessions = ref([])
const messages = ref([])
const runningServices = ref([])
const selectedImages = ref([])

const showImagePreview = ref(false)
const previewImageUrl = ref('')

// 格式化内容（支持换行）
const formatContent = (content) => {
  if (!content) return ''
  return content.replace(/\n/g, '<br>')
}

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
  selectedImages.value = []
  ElMessage.success('新建会话成功')
}

const selectSession = (id) => {
  currentSession.value = id
}

// 图片选择处理
const handleImageSelect = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    selectedImages.value.push({
      file: file.raw,
      url: e.target.result,
      name: file.name
    })
  }
  reader.readAsDataURL(file.raw)
}

const removeImage = (idx) => {
  selectedImages.value.splice(idx, 1)
}

const previewImage = (url) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

// 将图片转为base64
const imageToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const sendMessage = async () => {
  if (!inputText.value.trim() && selectedImages.value.length === 0) return
  if (!selectedModel.value) {
    ElMessage.warning('请先选择一个运行中的模型')
    return
  }

  sending.value = true
  const startTime = Date.now()

  // 构建用户消息
  const userMsg = {
    id: Date.now(),
    role: 'user',
    content: inputText.value || '(图片)',
    tokens: inputText.value.length,
    time: new Date().toLocaleTimeString(),
    images: selectedImages.value.map(img => img.url)
  }
  messages.value.push(userMsg)

  // 准备消息内容
  const prompt = inputText.value
  const images = [...selectedImages.value]
  inputText.value = ''
  selectedImages.value = []

  // 添加AI消息占位
  const aiMsgId = Date.now() + 1
  const aiMsg = {
    id: aiMsgId,
    role: 'assistant',
    content: '',
    tokens: 0,
    tokensPerSecond: 0,
    duration: 0,
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(aiMsg)

  try {
    const service = runningServices.value.find(s => s.id === selectedModel.value)
    if (!service) {
      throw new Error('服务不存在')
    }

    // 构建消息内容（支持多模态）
    const messageContent = []

    // 添加图片
    for (const img of images) {
      const base64 = await imageToBase64(img.file)
      messageContent.push({
        type: 'image_url',
        image_url: { url: base64 }
      })
    }

    // 添加文本
    if (prompt) {
      messageContent.push({
        type: 'text',
        text: prompt
      })
    }

    const requestBody = {
      model: service.model_id || 'default',
      messages: [
        ...messages.value
          .filter(m => m.role !== 'system' && m.id !== aiMsgId)
          .map(m => {
            if (m.images && m.images.length > 0) {
              return {
                role: m.role,
                content: [
                  ...m.images.map(imgUrl => ({
                    type: 'image_url',
                    image_url: { url: imgUrl }
                  })),
                  { type: 'text', text: m.content === '(图片)' ? '请描述这张图片' : m.content }
                ]
              }
            }
            return { role: m.role, content: m.content }
          }),
        { role: 'user', content: messageContent.length > 0 ? messageContent : prompt }
      ],
      max_tokens: 2048,
      temperature: 0.7,
      stream: streamMode.value
    }

    if (streamMode.value) {
      // 流式输出
      const response = await fetch(`http://192.168.31.24:${service.port}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let tokenCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)
              const delta = parsed.choices?.[0]?.delta?.content || ''
              if (delta) {
                fullContent += delta
                // 直接更新数组中的消息对象
                const msgIndex = messages.value.findIndex(m => m.id === aiMsgId)
                if (msgIndex !== -1) {
                  messages.value[msgIndex].content = fullContent
                }
                await nextTick()
                if (messagesRef.value) {
                  messagesRef.value.scrollTop = messagesRef.value.scrollHeight
                }
              }
              // 尝试获取token统计
              if (parsed.usage?.completion_tokens) {
                tokenCount = parsed.usage.completion_tokens
              }
            } catch (e) {
              // 忽略解析错误，继续处理
            }
          }
        }
      }

      const endTime = Date.now()
      const duration = (endTime - startTime) / 1000
      const msgIndex = messages.value.findIndex(m => m.id === aiMsgId)
      if (msgIndex !== -1) {
        messages.value[msgIndex].tokens = tokenCount || fullContent.length
        messages.value[msgIndex].duration = duration
        messages.value[msgIndex].tokensPerSecond = duration > 0 ? (messages.value[msgIndex].tokens / duration) : 0
      }
    } else {
      // 非流式输出
      const response = await fetch(`http://192.168.31.24:${service.port}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }

      const data = await response.json()
      const endTime = Date.now()
      const duration = (endTime - startTime) / 1000
      const tokenCount = data.usage?.completion_tokens || data.choices?.[0]?.message?.content?.length || 0

      const msgIndex = messages.value.findIndex(m => m.id === aiMsgId)
      if (msgIndex !== -1) {
        messages.value[msgIndex].content = data.choices?.[0]?.message?.content || '无响应内容'
        messages.value[msgIndex].tokens = tokenCount
        messages.value[msgIndex].duration = duration
        messages.value[msgIndex].tokensPerSecond = duration > 0 ? (tokenCount / duration) : 0
      }
    }
  } catch (error) {
    console.error('Send message error:', error)
    const msgIndex = messages.value.findIndex(m => m.id === aiMsgId)
    if (msgIndex !== -1) {
      messages.value[msgIndex].content = `抱歉，请求失败: ${error.message}\n请确保服务正在运行。`
    }
  } finally {
    sending.value = false
  }

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
  height: calc(100vh - 140px);
  max-height: calc(100vh - 140px);
  overflow: hidden;
}

.session-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.session-list :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.session-scroll {
  flex: 1;
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

.chat-area :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  min-height: 0;
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

.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.message-image {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.2s;
}

.message-image:hover {
  transform: scale(1.05);
}

.message-meta {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.message.user .message-meta {
  color: rgba(255, 255, 255, 0.8);
}

.meta-item {
  display: inline-flex;
  align-items: center;
}

.input-area {
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
  flex-shrink: 0;
}

.selected-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.image-preview {
  position: relative;
  width: 60px;
  height: 60px;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #dcdfe6;
}

.remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  background: #f56c6c;
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 12px;
  padding: 2px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.left-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.right-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-hint {
  margin-top: 8px;
}
</style>
