<template>
  <div class="benchmark-page">
    <el-row :gutter="20">
      <!-- 左侧：测试配置 -->
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>测试配置</span>
          </template>

          <el-form :model="benchmarkConfig" label-width="100px" :rules="configRules" ref="configFormRef">
            <el-form-item label="选择服务" prop="serviceId">
              <el-select v-model="benchmarkConfig.serviceId" placeholder="选择要测试的服务" style="width: 100%;">
                <el-option
                  v-for="service in runningServices"
                  :key="service.id"
                  :label="service.model_name || service.name"
                  :value="service.id"
                />
              </el-select>
            </el-form-item>

            <el-divider content-position="left">Token 范围配置</el-divider>

            <el-form-item label="起始 Token">
              <el-input-number v-model="benchmarkConfig.prompt_tokens_start" :min="128" :max="16384" :step="128" style="width: 100%;" />
            </el-form-item>

            <el-form-item label="结束 Token">
              <el-input-number v-model="benchmarkConfig.prompt_tokens_end" :min="128" :max="16384" :step="128" style="width: 100%;" />
            </el-form-item>

            <el-form-item label="Token 步长">
              <el-input-number v-model="benchmarkConfig.prompt_tokens_step" :min="128" :max="2048" :step="128" style="width: 100%;" />
            </el-form-item>

            <el-divider content-position="left">并发配置</el-divider>

            <el-form-item label="并发数">
              <el-input-number v-model="benchmarkConfig.concurrent" :min="1" :max="64" style="width: 100%;" />
            </el-form-item>

            <el-form-item label="每点请求数">
              <el-input-number v-model="benchmarkConfig.requests_per_point" :min="1" :max="100" style="width: 100%;" />
            </el-form-item>

            <el-divider content-position="left">输出配置</el-divider>

            <el-form-item label="输出 Token">
              <el-input-number v-model="benchmarkConfig.max_tokens" :min="16" :max="2048" style="width: 100%;" />
            </el-form-item>

            <el-form-item label="流式输出">
              <el-switch v-model="benchmarkConfig.stream" />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="runBenchmark"
                :loading="running"
                :disabled="!benchmarkConfig.serviceId"
              >
                <el-icon><VideoPlay /></el-icon>
                开始测试
              </el-button>
              <el-button @click="stopBenchmark" :disabled="!running">
                <el-icon><VideoPause /></el-icon>
                停止测试
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：测试结果 -->
      <el-col :span="16">
        <!-- 测试进度 -->
        <el-card v-if="running" class="progress-card">
          <template #header>
            <div class="card-header">
              <span>测试进度</span>
              <span class="progress-text">{{ progress }}%</span>
            </div>
          </template>
          <el-progress
            :percentage="progress"
            :status="progress >= 100 ? 'success' : ''"
            :stroke-width="20"
          />
          <div class="progress-info">
            <span>当前步骤: {{ currentStep }}</span>
          </div>
        </el-card>

        <!-- 测试结果摘要 -->
        <el-card v-if="latestResult" class="result-card">
          <template #header>
            <div class="card-header">
              <span>测试结果</span>
              <el-button size="small" @click="exportResult">
                <el-icon><Download /></el-icon>
                导出结果
              </el-button>
            </div>
          </template>

          <el-row :gutter="20">
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">吞吐量 (TPS)</div>
                <div class="result-value highlight">{{ latestResult.summary?.throughput?.toFixed(1) || '-' }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">平均延迟</div>
                <div class="result-value">{{ latestResult.summary?.avg_latency?.toFixed(0) || '-' }} ms</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">TTFT</div>
                <div class="result-value">{{ latestResult.summary?.avg_ttft?.toFixed(0) || '-' }} ms</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">TPOT</div>
                <div class="result-value">{{ latestResult.summary?.avg_tpot?.toFixed(1) || '-' }} ms</div>
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 16px;">
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">成功率</div>
                <div class="result-value success">{{ latestResult.summary?.success_rate?.toFixed(1) || 100 }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">总请求数</div>
                <div class="result-value">{{ latestResult.summary?.total_requests || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">总 Token</div>
                <div class="result-value">{{ latestResult.summary?.total_tokens || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">测试时长</div>
                <div class="result-value">{{ latestResult.summary?.duration?.toFixed(1) || 0 }}s</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 性能图表 -->
        <el-card v-if="latestResult && latestResult.results" class="chart-card">
          <template #header>
            <span>性能曲线</span>
          </template>
          <el-tabs v-model="activeChart">
            <el-tab-pane label="吞吐量曲线" name="throughput">
              <div ref="throughputChartRef" style="height: 300px;"></div>
            </el-tab-pane>
            <el-tab-pane label="TTFT/TPOT 曲线" name="latency">
              <div ref="latencyChartRef" style="height: 300px;"></div>
            </el-tab-pane>
            <el-tab-pane label="详细数据" name="data">
              <el-table :data="latestResult.results" style="width: 100%" max-height="300">
                <el-table-column prop="prompt_tokens" label="输入Token" width="100" />
                <el-table-column prop="throughput" label="吞吐量(t/s)" width="120">
                  <template #default="scope">
                    {{ scope.row.throughput?.toFixed(2) }}
                  </template>
                </el-table-column>
                <el-table-column prop="ttft" label="TTFT(ms)" width="100">
                  <template #default="scope">
                    {{ scope.row.ttft?.toFixed(0) }}
                  </template>
                </el-table-column>
                <el-table-column prop="tpot" label="TPOT(ms)" width="100">
                  <template #default="scope">
                    {{ scope.row.tpot?.toFixed(2) }}
                  </template>
                </el-table-column>
                <el-table-column prop="success_count" label="成功数" width="80" />
                <el-table-column prop="error_count" label="失败数" width="80" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <!-- 历史记录 -->
        <el-card class="history-card">
          <template #header>
            <div class="card-header">
              <span>历史测试记录</span>
              <el-button size="small" type="danger" @click="clearHistory" :disabled="benchmarkHistory.length === 0">
                <el-icon><Delete /></el-icon>
                清空历史
              </el-button>
            </div>
          </template>
          <el-table :data="benchmarkHistory" style="width: 100%">
            <el-table-column prop="created_at" label="测试时间" width="180">
              <template #default="scope">
                {{ formatTime(scope.row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="config" label="配置" width="200">
              <template #default="scope">
                {{ scope.row.config?.model || 'Unknown' }}
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="吞吐量 (TPS)" width="120">
              <template #default="scope">
                <span class="highlight">{{ scope.row.summary?.throughput?.toFixed(1) || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="平均延迟 (ms)" width="120">
              <template #default="scope">
                {{ scope.row.summary?.avg_latency?.toFixed(0) || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="成功率" width="100">
              <template #default="scope">
                <el-tag :type="(scope.row.summary?.success_rate || 100) >= 95 ? 'success' : 'warning'" size="small">
                  {{ scope.row.summary?.success_rate?.toFixed(0) || 100 }}%
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button type="primary" size="small" link @click="viewDetail(scope.row)">
                  查看
                </el-button>
                <el-button type="danger" size="small" link @click="deleteHistory(scope.row.benchmark_id)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { VideoPlay, VideoPause, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { benchmarkApi, serviceApi } from '../api'

const running = ref(false)
const progress = ref(0)
const currentStep = ref('')
const activeChart = ref('throughput')
const configFormRef = ref()
const currentBenchmarkId = ref(null)
let pollInterval = null

const throughputChartRef = ref()
const latencyChartRef = ref()

let throughputChart = null
let latencyChart = null

const runningServices = ref([])
const benchmarkHistory = ref([])
const latestResult = ref(null)

const benchmarkConfig = ref({
  serviceId: null,
  prompt_tokens_start: 512,
  prompt_tokens_end: 2048,
  prompt_tokens_step: 256,
  concurrent: 4,
  requests_per_point: 10,
  max_tokens: 128,
  stream: true
})

const configRules = {
  serviceId: [{ required: true, message: '请选择服务', trigger: 'change' }]
}

// 加载运行中的服务
const loadServices = async () => {
  try {
    const res = await serviceApi.list()
    const services = res.services || []
    runningServices.value = services.filter(s => s.status === 'running')
  } catch (error) {
    console.error('Failed to load services:', error)
    runningServices.value = []
  }
}

// 加载历史记录
const loadHistory = async () => {
  try {
    const res = await benchmarkApi.history(20)
    benchmarkHistory.value = res.history || []
  } catch (error) {
    console.error('Failed to load history:', error)
    benchmarkHistory.value = []
  }
}

// 运行测试
const runBenchmark = async () => {
  try {
    await configFormRef.value.validate()

    const service = runningServices.value.find(s => s.id === benchmarkConfig.value.serviceId)
    if (!service) {
      ElMessage.error('找不到选中的服务')
      return
    }

    running.value = true
    progress.value = 0
    currentStep.value = '正在启动测试...'

    // 构建请求配置
    const config = {
      target_url: `http://192.168.31.24:${service.port}`,
      model: service.model_name || 'default',
      prompt_tokens_start: benchmarkConfig.value.prompt_tokens_start,
      prompt_tokens_end: benchmarkConfig.value.prompt_tokens_end,
      prompt_tokens_step: benchmarkConfig.value.prompt_tokens_step,
      concurrent: benchmarkConfig.value.concurrent,
      requests_per_point: benchmarkConfig.value.requests_per_point,
      max_tokens: benchmarkConfig.value.max_tokens,
      stream: benchmarkConfig.value.stream
    }

    const res = await benchmarkApi.run(config)
    currentBenchmarkId.value = res.benchmark_id

    ElMessage.success('测试已启动，正在收集数据...')

    // 开始轮询状态
    pollInterval = setInterval(async () => {
      try {
        const status = await benchmarkApi.status(currentBenchmarkId.value)
        progress.value = Math.min(status.progress || 0, 100)
        currentStep.value = status.current_step || '处理中...'

        if (status.status === 'completed') {
          clearInterval(pollInterval)
          await fetchResult()
          running.value = false
          ElMessage.success('测试完成')
          await loadHistory()
        } else if (status.status === 'failed') {
          clearInterval(pollInterval)
          running.value = false
          ElMessage.error(`测试失败: ${status.error || '未知错误'}`)
        }
      } catch (error) {
        console.error('Failed to poll status:', error)
      }
    }, 2000)

  } catch (error) {
    running.value = false
    ElMessage.error(`启动失败: ${error.response?.data?.detail || error.message}`)
  }
}

// 获取测试结果
const fetchResult = async () => {
  if (!currentBenchmarkId.value) return

  try {
    const result = await benchmarkApi.result(currentBenchmarkId.value)
    latestResult.value = result

    await nextTick()
    updateCharts()
  } catch (error) {
    console.error('Failed to get result:', error)
  }
}

// 停止测试
const stopBenchmark = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  running.value = false
  progress.value = 0
  currentStep.value = ''
  ElMessage.warning('测试已停止')
}

// 初始化图表
const initCharts = () => {
  if (throughputChartRef.value) {
    throughputChart = echarts.init(throughputChartRef.value)
  }
  if (latencyChartRef.value) {
    latencyChart = echarts.init(latencyChartRef.value)
  }
}

// 更新图表
const updateCharts = () => {
  if (!latestResult.value || !latestResult.value.results) return

  const results = latestResult.value.results
  const xData = results.map(r => r.prompt_tokens)

  // 吞吐量图表
  if (throughputChart) {
    throughputChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: xData,
        name: '输入 Token 数'
      },
      yAxis: {
        type: 'value',
        name: '吞吐量 (tokens/s)'
      },
      series: [{
        name: '吞吐量',
        type: 'line',
        smooth: true,
        data: results.map(r => r.throughput?.toFixed(2) || 0),
        areaStyle: { opacity: 0.3 },
        lineStyle: { width: 3 },
        itemStyle: { color: '#409EFF' }
      }]
    })
  }

  // 延迟图表
  if (latencyChart) {
    latencyChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['TTFT', 'TPOT'] },
      xAxis: {
        type: 'category',
        data: xData,
        name: '输入 Token 数'
      },
      yAxis: {
        type: 'value',
        name: '延迟 (ms)'
      },
      series: [
        {
          name: 'TTFT',
          type: 'line',
          smooth: true,
          data: results.map(r => r.ttft?.toFixed(0) || 0),
          lineStyle: { width: 2 },
          itemStyle: { color: '#67C23A' }
        },
        {
          name: 'TPOT',
          type: 'line',
          smooth: true,
          data: results.map(r => r.tpot?.toFixed(2) || 0),
          lineStyle: { width: 2 },
          itemStyle: { color: '#E6A23C' }
        }
      ]
    })
  }
}

// 导出结果
const exportResult = () => {
  if (!latestResult.value) return
  const data = JSON.stringify(latestResult.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `benchmark-${Date.now()}.json`
  a.click()
  ElMessage.success('结果已导出')
}

// 查看详情
const viewDetail = async (row) => {
  try {
    const result = await benchmarkApi.result(row.benchmark_id)
    latestResult.value = result
    await nextTick()
    updateCharts()
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

// 删除历史记录
const deleteHistory = async (id) => {
  try {
    await benchmarkApi.delete(id)
    benchmarkHistory.value = benchmarkHistory.value.filter(h => h.benchmark_id !== id)
    ElMessage.success('记录已删除')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 清空历史
const clearHistory = async () => {
  for (const item of benchmarkHistory.value) {
    try {
      await benchmarkApi.delete(item.benchmark_id)
    } catch (e) {
      // ignore
    }
  }
  benchmarkHistory.value = []
  latestResult.value = null
  ElMessage.info('历史已清空')
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString()
}

// 监听图表切换
watch(activeChart, () => {
  nextTick(() => {
    if (throughputChart) throughputChart.resize()
    if (latencyChart) latencyChart.resize()
  })
})

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  if (throughputChart) throughputChart.resize()
  if (latencyChart) latencyChart.resize()
}

onMounted(() => {
  loadServices()
  loadHistory()
  initCharts()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pollInterval) clearInterval(pollInterval)
  if (throughputChart) throughputChart.dispose()
  if (latencyChart) latencyChart.dispose()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-card {
  margin-bottom: 20px;
}

.progress-text {
  font-size: 18px;
  font-weight: bold;
  color: #409EFF;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  color: #909399;
}

.result-card {
  margin-bottom: 20px;
}

.result-item {
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.result-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.result-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.result-value.highlight {
  color: #409EFF;
}

.result-value.success {
  color: #67C23A;
}

.chart-card {
  margin-bottom: 20px;
}

.history-card {
  margin-bottom: 20px;
}

.highlight {
  color: #409EFF;
  font-weight: bold;
}
</style>
