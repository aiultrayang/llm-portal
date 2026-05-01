<template>
  <div class="monitor-page">
    <el-row :gutter="20">
      <!-- 左侧：日志筛选和统计 -->
      <el-col :span="6">
        <!-- 筛选面板 -->
        <el-card class="filter-card">
          <template #header>
            <div class="card-header">
              <span>日志筛选</span>
              <el-button size="small" @click="resetFilters">
                <el-icon><Refresh /></el-icon>
                重置
              </el-button>
            </div>
          </template>

          <el-form label-width="80px" size="small">
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="filters.timeRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                value-format="YYYY-MM-DD HH:mm:ss"
                :shortcuts="timeShortcuts"
              />
            </el-form-item>

            <el-form-item label="模型">
              <el-select v-model="filters.model" placeholder="全部模型" clearable>
                <el-option
                  v-for="model in modelList"
                  :key="model"
                  :label="model"
                  :value="model"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="状态">
              <el-select v-model="filters.status" placeholder="全部状态" clearable>
                <el-option label="成功" value="success" />
                <el-option label="失败" value="error" />
                <el-option label="超时" value="timeout" />
              </el-select>
            </el-form-item>

            <el-form-item label="请求ID">
              <el-input v-model="filters.requestId" placeholder="输入请求ID" clearable />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="applyFilters">
                <el-icon><Search /></el-icon>
                查询
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 统计面板 -->
        <el-card class="stats-card">
          <template #header>
            <span>请求统计</span>
          </template>

          <div class="stat-item">
            <div class="stat-label">总请求数</div>
            <div class="stat-value">{{ stats.totalRequests }}</div>
          </div>

          <div class="stat-item">
            <div class="stat-label">成功率</div>
            <div class="stat-value success">{{ stats.successRate }}%</div>
          </div>

          <div class="stat-item">
            <div class="stat-label">平均延迟</div>
            <div class="stat-value">{{ stats.avgLatency }} ms</div>
          </div>

          <div class="stat-item">
            <div class="stat-label">平均吞吐</div>
            <div class="stat-value highlight">{{ stats.avgThroughput }} t/s</div>
          </div>

          <div class="stat-item">
            <div class="stat-label">总 Token</div>
            <div class="stat-value">{{ formatNumber(stats.totalTokens) }}</div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：日志列表和详情 -->
      <el-col :span="18">
        <!-- 日志统计图表 -->
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>请求趋势</span>
              <el-radio-group v-model="chartType" size="small">
                <el-radio-button label="count">请求数</el-radio-button>
                <el-radio-button label="latency">延迟</el-radio-button>
                <el-radio-button label="throughput">吞吐量</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="chartRef" style="height: 250px;"></div>
        </el-card>

        <!-- 请求日志列表 -->
        <el-card class="log-list-card">
          <template #header>
            <div class="card-header">
              <span>请求日志</span>
              <div class="header-actions">
                <el-button size="small" @click="refreshLogs" :loading="loading">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
                <el-dropdown @command="handleExport">
                  <el-button size="small">
                    <el-icon><Download /></el-icon>
                    导出
                    <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="json">JSON 格式</el-dropdown-item>
                      <el-dropdown-item command="csv">CSV 格式</el-dropdown-item>
                      <el-dropdown-item command="txt">纯文本</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>

          <el-table :data="logList" style="width: 100%" v-loading="loading" @row-click="viewDetail">
            <el-table-column prop="timestamp" label="时间" width="180">
              <template #default="scope">
                {{ formatTime(scope.row.timestamp) }}
              </template>
            </el-table-column>
            <el-table-column prop="requestId" label="请求ID" width="200">
              <template #default="scope">
                <el-tooltip :content="scope.row.requestId" placement="top">
                  <span class="request-id">{{ scope.row.requestId?.substring(0, 12) }}...</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="model" label="模型" width="150" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)" size="small">
                  {{ getStatusText(scope.row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="latency" label="延迟 (ms)" width="100">
              <template #default="scope">
                <span :class="{ 'high-latency': scope.row.latency > 500 }">
                  {{ scope.row.latency }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="tokens" label="Token 数" width="100" />
            <el-table-column prop="throughput" label="吞吐量" width="100">
              <template #default="scope">
                {{ scope.row.throughput }} t/s
              </template>
            </el-table-column>
            <el-table-column prop="prompt" label="Prompt" min-width="200" show-overflow-tooltip />
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="pagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handlePageChange"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 日志详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="请求详情" width="800px" destroy-on-close>
      <el-descriptions :column="2" border v-if="selectedLog">
        <el-descriptions-item label="请求ID">{{ selectedLog.requestId }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(selectedLog.timestamp) }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ selectedLog.model }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedLog.status)">
            {{ getStatusText(selectedLog.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="延迟">{{ selectedLog.latency }} ms</el-descriptions-item>
        <el-descriptions-item label="TTFT">{{ selectedLog.ttft || 'N/A' }} ms</el-descriptions-item>
        <el-descriptions-item label="输入 Token">{{ selectedLog.inputTokens }}</el-descriptions-item>
        <el-descriptions-item label="输出 Token">{{ selectedLog.outputTokens }}</el-descriptions-item>
        <el-descriptions-item label="吞吐量">{{ selectedLog.throughput }} t/s</el-descriptions-item>
        <el-descriptions-item label="总 Token">{{ selectedLog.tokens }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">请求内容</el-divider>
      <div class="content-box">
        <pre>{{ selectedLog?.prompt }}</pre>
      </div>

      <el-divider content-position="left">响应内容</el-divider>
      <div class="content-box response">
        <pre>{{ selectedLog?.response || '无响应内容' }}</pre>
      </div>

      <el-divider content-position="left" v-if="selectedLog?.error">错误信息</el-divider>
      <div class="error-box" v-if="selectedLog?.error">
        <pre>{{ selectedLog.error }}</pre>
      </div>

      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="copyLogDetail">
          <el-icon><CopyDocument /></el-icon>
          复制详情
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Refresh, Search, Download, ArrowDown, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { logApi } from '../api'

const loading = ref(false)
const showDetailDialog = ref(false)
const selectedLog = ref(null)
const chartRef = ref()
const chartType = ref('count')
const chart = ref()

const modelList = ref(['Qwen2.5-7B-Instruct', 'LLaMA-3-8B', 'Mistral-7B-v0.3', 'DeepSeek-Coder-6.7B'])

const filters = reactive({
  timeRange: [],
  model: '',
  status: '',
  requestId: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const stats = reactive({
  totalRequests: 15420,
  successRate: 98.5,
  avgLatency: 125,
  avgThroughput: 38.5,
  totalTokens: 1250000
})

const logList = ref([])

const timeShortcuts = [
  {
    text: '最近1小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000)
      return [start, end]
    }
  },
  {
    text: '最近24小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24)
      return [start, end]
    }
  },
  {
    text: '最近7天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    }
  }
]

// 加载日志列表
const loadLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      pageSize: pagination.pageSize,
      ...filters
    }
    const res = await logApi.requests(params)
    logList.value = res.data?.list || res || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    // 模拟数据
    logList.value = generateMockLogs()
    pagination.total = 154
  } finally {
    loading.value = false
  }
}

// 生成模拟日志数据
const generateMockLogs = () => {
  const models = ['Qwen2.5-7B-Instruct', 'LLaMA-3-8B', 'Mistral-7B-v0.3']
  const statuses = ['success', 'success', 'success', 'success', 'success', 'success', 'error', 'timeout']
  const prompts = [
    '请解释什么是机器学习？',
    '用简单的语言说明量子计算的基本原理。',
    '帮我写一个 Python 快速排序算法。',
    '分析一下当前人工智能发展的趋势。',
    '解释神经网络中的反向传播算法。'
  ]
  const responses = [
    '机器学习是人工智能的一个分支...',
    '量子计算利用量子力学原理...',
    'def quicksort(arr): ...',
    '当前人工智能发展呈现以下趋势...',
    '反向传播是神经网络训练的核心算法...'
  ]

  return Array.from({ length: pagination.pageSize }, (_, i) => {
    const idx = Math.floor(Math.random() * models.length)
    const statusIdx = Math.floor(Math.random() * statuses.length)
    const latency = Math.floor(Math.random() * 400 + 50)
    const inputTokens = Math.floor(Math.random() * 100 + 20)
    const outputTokens = Math.floor(Math.random() * 200 + 50)

    return {
      id: Date.now() - i * 60000,
      requestId: `req-${Date.now()}-${i}`,
      timestamp: new Date(Date.now() - i * 60000),
      model: models[idx],
      status: statuses[statusIdx],
      latency,
      ttft: Math.floor(latency * 0.3),
      tokens: inputTokens + outputTokens,
      inputTokens,
      outputTokens,
      throughput: (outputTokens / (latency / 1000)).toFixed(1),
      prompt: prompts[Math.floor(Math.random() * prompts.length)],
      response: responses[Math.floor(Math.random() * responses.length)],
      error: statuses[statusIdx] === 'error' ? '连接超时' : null
    }
  })
}

// 应用筛选
const applyFilters = () => {
  pagination.page = 1
  loadLogs()
}

// 重置筛选
const resetFilters = () => {
  filters.timeRange = []
  filters.model = ''
  filters.status = ''
  filters.requestId = ''
  pagination.page = 1
  loadLogs()
}

// 刷新日志
const refreshLogs = () => {
  loadLogs()
  ElMessage.success('日志已刷新')
}

// 查看详情
const viewDetail = (row) => {
  selectedLog.value = row
  showDetailDialog.value = true
}

// 复制详情
const copyLogDetail = () => {
  const detail = JSON.stringify(selectedLog.value, null, 2)
  navigator.clipboard.writeText(detail)
  ElMessage.success('详情已复制到剪贴板')
}

// 导出日志
const handleExport = async (format) => {
  try {
    await logApi.export(format, filters)
    ElMessage.success(`正在导出 ${format.toUpperCase()} 格式`)
  } catch (error) {
    ElMessage.success(`已模拟导出 ${format.toUpperCase()} 格式日志`)
  }
}

// 状态样式
const getStatusType = (status) => {
  const types = { success: 'success', error: 'danger', timeout: 'warning' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { success: '成功', error: '失败', timeout: '超时' }
  return texts[status] || status
}

// 格式化
const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString()
}

const formatNumber = (num) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num
}

// 分页
const handleSizeChange = (size) => {
  pagination.pageSize = size
  loadLogs()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadLogs()
}

// 初始化图表
const initChart = () => {
  if (chartRef.value) {
    chart.value = echarts.init(chartRef.value)
    updateChart()
  }
}

// 更新图表
const updateChart = () => {
  if (!chart.value) return

  const hours = Array.from({ length: 24 }, (_, i) => `${23 - i}:00`)
  let seriesData = []

  switch (chartType.value) {
    case 'count':
      seriesData = {
        name: '请求数',
        data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 500 + 200))
      }
      break
    case 'latency':
      seriesData = {
        name: '平均延迟',
        data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 100 + 80))
      }
      break
    case 'throughput':
      seriesData = {
        name: '平均吞吐量',
        data: Array.from({ length: 24 }, () => (Math.random() * 20 + 30).toFixed(1))
      }
      break
  }

  chart.value.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: hours.reverse(),
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: seriesData.name,
      type: 'line',
      smooth: true,
      data: seriesData.data,
      areaStyle: { opacity: 0.3 },
      lineStyle: { width: 2 },
      itemStyle: { color: '#409EFF' }
    }]
  })
}

// 监听图表类型变化
watch(chartType, () => {
  updateChart()
})

// 窗口大小变化
const handleResize = () => {
  if (chart.value) chart.value.resize()
}

onMounted(() => {
  loadLogs()
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chart.value) chart.value.dispose()
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
  gap: 8px;
}

.filter-card {
  margin-bottom: 20px;
}

.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-value.success {
  color: #67C23A;
}

.stat-value.highlight {
  color: #409EFF;
}

.chart-card {
  margin-bottom: 20px;
}

.log-list-card {
  margin-bottom: 20px;
}

.request-id {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #606266;
}

.high-latency {
  color: #E6A23C;
  font-weight: bold;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.content-box {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.content-box pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.content-box.response {
  background: #ecf5ff;
}

.error-box {
  background: #fef0f0;
  padding: 16px;
  border-radius: 8px;
  color: #F56C6C;
}

.error-box pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}
</style>