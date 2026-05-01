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
                <el-button size="small" @click="loadLogs" :loading="loading">
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
            <el-table-column prop="request_id" label="请求ID" width="200">
              <template #default="scope">
                <el-tooltip :content="scope.row.request_id" placement="top">
                  <span class="request-id">{{ scope.row.request_id?.substring(0, 12) }}...</span>
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
            <el-table-column prop="ttft" label="TTFT (ms)" width="100">
              <template #default="scope">
                <span :class="{ 'high-latency': scope.row.ttft > 500 }">
                  {{ scope.row.ttft || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="output_length" label="Token 数" width="100" />
            <el-table-column prop="prompt_content" label="Prompt" min-width="200" show-overflow-tooltip />
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
        <el-descriptions-item label="请求ID">{{ selectedLog.request_id }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(selectedLog.timestamp) }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ selectedLog.model }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedLog.status)">
            {{ getStatusText(selectedLog.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="延迟">{{ selectedLog.total_time?.toFixed(0) || '-' }} ms</el-descriptions-item>
        <el-descriptions-item label="TTFT">{{ selectedLog.ttft?.toFixed(0) || '-' }} ms</el-descriptions-item>
        <el-descriptions-item label="输入 Token">{{ selectedLog.prompt_length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="输出 Token">{{ selectedLog.output_length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="TPOT">{{ selectedLog.tpot?.toFixed(2) || '-' }} ms</el-descriptions-item>
        <el-descriptions-item label="GPU 利用率">{{ selectedLog.gpu_util?.toFixed(1) || '-' }}%</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">请求内容</el-divider>
      <div class="content-box">
        <pre>{{ selectedLog?.prompt_content || '无内容' }}</pre>
      </div>

      <el-divider content-position="left">响应内容</el-divider>
      <div class="content-box response">
        <pre>{{ selectedLog?.output_content || '无响应内容' }}</pre>
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
import { logApi, serviceApi } from '../api'

const loading = ref(false)
const showDetailDialog = ref(false)
const selectedLog = ref(null)
const chartRef = ref()
const chartType = ref('count')
const chart = ref()

// 从 API 获取模型列表
const modelList = ref([])

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
  totalRequests: 0,
  successRate: 0,
  avgLatency: 0,
  avgThroughput: 0,
  totalTokens: 0
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

// 加载模型列表
const loadModelList = async () => {
  try {
    const res = await serviceApi.list()
    const services = res.services || []
    // 获取所有唯一模型名
    const models = [...new Set(services.map(s => s.model_id).filter(Boolean))]
    modelList.value = models
  } catch (error) {
    console.error('Failed to load model list:', error)
  }
}

// 加载日志列表
const loadLogs = async () => {
  loading.value = true
  try {
    const params = {
      limit: pagination.pageSize,
      offset: (pagination.page - 1) * pagination.pageSize,
      model: filters.model || undefined,
      status: filters.status || undefined,
      request_id: filters.requestId || undefined
    }

    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0]
      params.end_time = filters.timeRange[1]
    }

    const res = await logApi.requests(params)
    logList.value = res.logs || []
    pagination.total = res.total || 0
  } catch (error) {
    console.error('Failed to load logs:', error)
    logList.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    const params = {}
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0]
      params.end_time = filters.timeRange[1]
    }

    const res = await logApi.stats(params)
    if (res.stats) {
      stats.totalRequests = res.stats.total_requests || 0
      stats.successRate = res.stats.success_rate || 0
      stats.avgLatency = Math.round(res.stats.avg_ttft || 0)
      stats.avgThroughput = (res.stats.avg_throughput || 0).toFixed(1)
      stats.totalTokens = res.stats.total_tokens || 0
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

// 应用筛选
const applyFilters = () => {
  pagination.page = 1
  loadLogs()
  loadStats()
}

// 重置筛选
const resetFilters = () => {
  filters.timeRange = []
  filters.model = ''
  filters.status = ''
  filters.requestId = ''
  pagination.page = 1
  loadLogs()
  loadStats()
}

// 查看详情
const viewDetail = async (row) => {
  try {
    const res = await logApi.detail(row.request_id)
    selectedLog.value = res
    showDetailDialog.value = true
  } catch (error) {
    selectedLog.value = row
    showDetailDialog.value = true
  }
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
    const res = await logApi.export(format, filters)
    ElMessage.success(`正在导出 ${format.toUpperCase()} 格式`)
  } catch (error) {
    ElMessage.error('导出失败')
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

  // 使用模拟的24小时数据（实际应该从API获取）
  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
  let seriesData = []

  switch (chartType.value) {
    case 'count':
      seriesData = {
        name: '请求数',
        data: Array.from({ length: 24 }, () => Math.floor(Math.random() * stats.totalRequests / 24 || 10))
      }
      break
    case 'latency':
      seriesData = {
        name: '平均延迟',
        data: Array.from({ length: 24 }, () => Math.floor(stats.avgLatency * (0.8 + Math.random() * 0.4) || 50))
      }
      break
    case 'throughput':
      seriesData = {
        name: '平均吞吐量',
        data: Array.from({ length: 24 }, () => (stats.avgThroughput * (0.8 + Math.random() * 0.4) || 30).toFixed(1))
      }
      break
  }

  chart.value.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: hours,
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
  loadModelList()
  loadLogs()
  loadStats()
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
</style>