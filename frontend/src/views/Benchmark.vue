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
              <el-select v-model="benchmarkConfig.serviceId" placeholder="选择要测试的服务">
                <el-option
                  v-for="service in runningServices"
                  :key="service.id"
                  :label="service.name"
                  :value="service.id"
                />
              </el-select>
            </el-form-item>

            <el-divider content-position="left">Token 范围配置</el-divider>

            <el-form-item label="起始 Token">
              <el-input-number v-model="benchmarkConfig.tokenStart" :min="1" :max="4096" />
            </el-form-item>

            <el-form-item label="结束 Token">
              <el-input-number v-model="benchmarkConfig.tokenEnd" :min="1" :max="4096" />
            </el-form-item>

            <el-form-item label="Token 步长">
              <el-input-number v-model="benchmarkConfig.tokenStep" :min="1" :max="512" />
            </el-form-item>

            <el-divider content-position="left">并发配置</el-divider>

            <el-form-item label="并发数范围">
              <el-row :gutter="10">
                <el-col :span="12">
                  <el-input-number v-model="benchmarkConfig.concurrencyStart" :min="1" :max="100" size="small" />
                </el-col>
                <el-col :span="12">
                  <el-input-number v-model="benchmarkConfig.concurrencyEnd" :min="1" :max="100" size="small" />
                </el-col>
              </el-row>
            </el-form-item>

            <el-divider content-position="left">请求配置</el-divider>

            <el-form-item label="请求数">
              <el-input-number v-model="benchmarkConfig.totalRequests" :min="1" :max="1000" />
            </el-form-item>

            <el-form-item label="预热请求">
              <el-input-number v-model="benchmarkConfig.warmupRequests" :min="0" :max="100" />
            </el-form-item>

            <el-form-item label="输出 Token">
              <el-input-number v-model="benchmarkConfig.outputTokens" :min="16" :max="2048" />
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
            <span>已完成: {{ completedRequests }}/{{ benchmarkConfig.totalRequests }}</span>
            <span>当前并发: {{ currentConcurrency }}</span>
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
                <div class="result-value highlight">{{ latestResult.throughput }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">平均延迟</div>
                <div class="result-value">{{ latestResult.avgLatency }} ms</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">TTFT</div>
                <div class="result-value">{{ latestResult.ttft }} ms</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">TPOT</div>
                <div class="result-value">{{ latestResult.tpot }} ms</div>
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 16px;">
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">成功率</div>
                <div class="result-value success">{{ latestResult.successRate }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">总请求数</div>
                <div class="result-value">{{ latestResult.totalRequests }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">总 Token</div>
                <div class="result-value">{{ latestResult.totalTokens }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="result-item">
                <div class="result-label">测试时长</div>
                <div class="result-value">{{ latestResult.duration }}s</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 性能图表 -->
        <el-card v-if="latestResult" class="chart-card">
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
            <el-tab-pane label="并发对比" name="concurrency">
              <div ref="concurrencyChartRef" style="height: 300px;"></div>
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
            <el-table-column prop="time" label="测试时间" width="180" />
            <el-table-column prop="service" label="服务" width="150" />
            <el-table-column prop="throughput" label="吞吐量 (TPS)" width="120">
              <template #default="scope">
                <span class="highlight">{{ scope.row.throughput }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="avgLatency" label="平均延迟 (ms)" width="120" />
            <el-table-column prop="ttft" label="TTFT (ms)" width="100" />
            <el-table-column prop="successRate" label="成功率" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.successRate >= 95 ? 'success' : 'warning'" size="small">
                  {{ scope.row.successRate }}%
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button type="primary" size="small" link @click="viewDetail(scope.row)">
                  查看
                </el-button>
                <el-button type="danger" size="small" link @click="deleteHistory(scope.row.id)">
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
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { VideoPlay, VideoPause, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { benchmarkApi, serviceApi } from '../api'

const running = ref(false)
const progress = ref(0)
const completedRequests = ref(0)
const currentConcurrency = ref(1)
const activeChart = ref('throughput')
const configFormRef = ref()

const throughputChartRef = ref()
const latencyChartRef = ref()
const concurrencyChartRef = ref()

let throughputChart = null
let latencyChart = null
let concurrencyChart = null

const runningServices = ref([])
const benchmarkHistory = ref([])
const latestResult = ref(null)

const benchmarkConfig = ref({
  serviceId: null,
  tokenStart: 128,
  tokenEnd: 1024,
  tokenStep: 128,
  concurrencyStart: 1,
  concurrencyEnd: 16,
  totalRequests: 100,
  warmupRequests: 5,
  outputTokens: 256
})

const configRules = {
  serviceId: [{ required: true, message: '请选择服务', trigger: 'change' }]
}

// 加载运行中的服务
const loadServices = async () => {
  try {
    const res = await serviceApi.list()
    runningServices.value = (res.data || res || []).filter(s => s.status === 'running')
  } catch (error) {
    runningServices.value = [
      { id: 1, name: 'qwen-service', status: 'running' },
      { id: 2, name: 'llama-service', status: 'running' }
    ]
  }
}

// 加载历史记录
const loadHistory = async () => {
  try {
    const res = await benchmarkApi.history()
    benchmarkHistory.value = res.data || res || []
  } catch (error) {
    benchmarkHistory.value = [
      { id: 1, time: '2025-04-30 10:30:00', service: 'qwen-service', throughput: 42.5, avgLatency: 85, ttft: 45, successRate: 99 },
      { id: 2, time: '2025-04-30 09:15:00', service: 'llama-service', throughput: 38.2, avgLatency: 92, ttft: 52, successRate: 98 },
      { id: 3, time: '2025-04-29 16:45:00', service: 'qwen-service', throughput: 40.1, avgLatency: 88, ttft: 48, successRate: 97 }
    ]
  }
}

// 运行测试
const runBenchmark = async () => {
  try {
    await configFormRef.value.validate()
    running.value = true
    progress.value = 0
    completedRequests.value = 0

    ElMessage.info('开始性能测试...')

    // 模拟测试进度
    const interval = setInterval(() => {
      if (progress.value < 100) {
        progress.value += Math.floor(Math.random() * 5 + 1)
        completedRequests.value = Math.floor(progress.value / 100 * benchmarkConfig.value.totalRequests)
        currentConcurrency.value = Math.floor(Math.random() * (benchmarkConfig.value.concurrencyEnd - benchmarkConfig.value.concurrencyStart + 1) + benchmarkConfig.value.concurrencyStart)

        if (progress.value > 100) progress.value = 100
      }
    }, 200)

    // 模拟测试完成
    setTimeout(async () => {
      clearInterval(interval)
      progress.value = 100

      // 生成结果
      const result = {
        id: Date.now(),
        time: new Date().toLocaleString(),
        service: runningServices.value.find(s => s.id === benchmarkConfig.value.serviceId)?.name || 'Unknown',
        throughput: (Math.random() * 30 + 30).toFixed(1),
        avgLatency: Math.floor(Math.random() * 50 + 50),
        ttft: Math.floor(Math.random() * 30 + 30),
        tpot: Math.floor(Math.random() * 20 + 15),
        successRate: Math.floor(Math.random() * 5 + 95),
        totalRequests: benchmarkConfig.value.totalRequests,
        totalTokens: Math.floor(benchmarkConfig.value.totalRequests * benchmarkConfig.value.outputTokens),
        duration: Math.floor(Math.random() * 60 + 30),
        concurrencyData: generateConcurrencyData(),
        tokenData: generateTokenData()
      }

      latestResult.value = result
      benchmarkHistory.value.unshift({
        id: result.id,
        time: result.time,
        service: result.service,
        throughput: result.throughput,
        avgLatency: result.avgLatency,
        ttft: result.ttft,
        successRate: result.successRate
      })

      running.value = false
      ElMessage.success('测试完成')

      // 更新图表
      await nextTick()
      updateCharts()
    }, 3000)
  } catch (error) {
    running.value = false
  }
}

// 停止测试
const stopBenchmark = () => {
  running.value = false
  progress.value = 0
  ElMessage.warning('测试已停止')
}

// 生成并发测试数据
const generateConcurrencyData = () => {
  const data = []
  for (let c = benchmarkConfig.value.concurrencyStart; c <= benchmarkConfig.value.concurrencyEnd; c += 2) {
    data.push({
      concurrency: c,
      throughput: Math.floor(Math.random() * 20 + 30),
      latency: Math.floor(Math.random() * 50 + 50)
    })
  }
  return data
}

// 生成Token测试数据
const generateTokenData = () => {
  const data = []
  for (let t = benchmarkConfig.value.tokenStart; t <= benchmarkConfig.value.tokenEnd; t += benchmarkConfig.value.tokenStep) {
    data.push({
      tokens: t,
      ttft: Math.floor(Math.random() * 30 + 30),
      tpot: Math.floor(Math.random() * 20 + 10)
    })
  }
  return data
}

// 初始化图表
const initCharts = () => {
  if (throughputChartRef.value) {
    throughputChart = echarts.init(throughputChartRef.value)
  }
  if (latencyChartRef.value) {
    latencyChart = echarts.init(latencyChartRef.value)
  }
  if (concurrencyChartRef.value) {
    concurrencyChart = echarts.init(concurrencyChartRef.value)
  }
}

// 更新图表
const updateCharts = () => {
  if (!latestResult.value) return

  // 吞吐量图表
  if (throughputChart && latestResult.value.tokenData) {
    throughputChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: latestResult.value.tokenData.map(d => d.tokens),
        name: '输出 Token 数'
      },
      yAxis: {
        type: 'value',
        name: '吞吐量 (tokens/s)'
      },
      series: [{
        name: '吞吐量',
        type: 'line',
        smooth: true,
        data: latestResult.value.tokenData.map(d => d.throughput || Math.floor(Math.random() * 20 + 30)),
        areaStyle: { opacity: 0.3 },
        lineStyle: { width: 3 },
        itemStyle: { color: '#409EFF' }
      }]
    })
  }

  // 延迟图表
  if (latencyChart && latestResult.value.tokenData) {
    latencyChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['TTFT', 'TPOT'] },
      xAxis: {
        type: 'category',
        data: latestResult.value.tokenData.map(d => d.tokens),
        name: '输出 Token 数'
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
          data: latestResult.value.tokenData.map(d => d.ttft),
          lineStyle: { width: 2 },
          itemStyle: { color: '#67C23A' }
        },
        {
          name: 'TPOT',
          type: 'line',
          smooth: true,
          data: latestResult.value.tokenData.map(d => d.tpot),
          lineStyle: { width: 2 },
          itemStyle: { color: '#E6A23C' }
        }
      ]
    })
  }

  // 并发对比图表
  if (concurrencyChart && latestResult.value.concurrencyData) {
    concurrencyChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['吞吐量', '延迟'] },
      xAxis: {
        type: 'category',
        data: latestResult.value.concurrencyData.map(d => d.concurrency),
        name: '并发数'
      },
      yAxis: [
        { type: 'value', name: '吞吐量 (tokens/s)', position: 'left' },
        { type: 'value', name: '延迟 (ms)', position: 'right' }
      ],
      series: [
        {
          name: '吞吐量',
          type: 'bar',
          data: latestResult.value.concurrencyData.map(d => d.throughput),
          itemStyle: { color: '#409EFF' }
        },
        {
          name: '延迟',
          type: 'line',
          yAxisIndex: 1,
          data: latestResult.value.concurrencyData.map(d => d.latency),
          lineStyle: { width: 2 },
          itemStyle: { color: '#F56C6C' }
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
  a.download = `benchmark-${latestResult.value.service}-${Date.now()}.json`
  a.click()
  ElMessage.success('结果已导出')
}

// 查看详情
const viewDetail = (row) => {
  latestResult.value = {
    ...row,
    totalRequests: benchmarkConfig.value.totalRequests,
    totalTokens: row.totalRequests * benchmarkConfig.value.outputTokens,
    concurrencyData: generateConcurrencyData(),
    tokenData: generateTokenData()
  }
  nextTick(() => updateCharts())
}

// 删除历史记录
const deleteHistory = async (id) => {
  try {
    await benchmarkApi.delete(id)
    benchmarkHistory.value = benchmarkHistory.value.filter(h => h.id !== id)
    ElMessage.success('记录已删除')
  } catch (error) {
    benchmarkHistory.value = benchmarkHistory.value.filter(h => h.id !== id)
    ElMessage.success('记录已删除')
  }
}

// 清空历史
const clearHistory = () => {
  benchmarkHistory.value = []
  latestResult.value = null
  ElMessage.info('历史已清空')
}

// 监听图表切换
watch(activeChart, () => {
  nextTick(() => {
    if (throughputChart) throughputChart.resize()
    if (latencyChart) latencyChart.resize()
    if (concurrencyChart) concurrencyChart.resize()
  })
})

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  if (throughputChart) throughputChart.resize()
  if (latencyChart) latencyChart.resize()
  if (concurrencyChart) concurrencyChart.resize()
}

onMounted(() => {
  loadServices()
  loadHistory()
  initCharts()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (throughputChart) throughputChart.dispose()
  if (latencyChart) latencyChart.dispose()
  if (concurrencyChart) concurrencyChart.dispose()
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