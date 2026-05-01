<template>
  <div class="dashboard">
    <!-- 系统状态卡片 -->
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>运行模型</span>
            </div>
          </template>
          <div class="stat-value">{{ runningServices }}</div>
          <div class="stat-label">当前加载模型数量</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>GPU 使用率</span>
            </div>
          </template>
          <div class="stat-value">{{ gpuInfo.utilization }}%</div>
          <div class="stat-label">显存占用 {{ gpuInfo.memoryUsed.toFixed(1) }}GB / {{ gpuInfo.memoryTotal.toFixed(1) }}GB</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>今日请求</span>
            </div>
          </template>
          <div class="stat-value">{{ todayRequests }}</div>
          <div class="stat-label">API 调用次数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>平均延迟</span>
            </div>
          </template>
          <div class="stat-value">{{ avgLatency }}ms</div>
          <div class="stat-label">首字生成时间</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 多 GPU 详情展示 -->
    <el-row :gutter="20" style="margin-top: 20px;" v-if="gpuList.length > 0">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>GPU 状态详情 ({{ gpuList.length }} 张显卡)</span>
          </template>
          <el-row :gutter="15">
            <el-col :span="Math.min(24 / gpuList.length, 8)" v-for="gpu in gpuList" :key="gpu.index">
              <div class="gpu-card">
                <div class="gpu-header">
                  <span class="gpu-index">GPU {{ gpu.index }}</span>
                  <span class="gpu-name">{{ gpu.name }}</span>
                </div>
                <div class="gpu-stats">
                  <div class="gpu-stat-item">
                    <span class="gpu-stat-label">负载</span>
                    <el-progress :percentage="gpu.utilization" :color="getGpuColor(gpu.utilization)" :stroke-width="8" />
                  </div>
                  <div class="gpu-stat-item">
                    <span class="gpu-stat-label">显存</span>
                    <el-progress :percentage="gpu.memoryUtilization" :color="getMemColor(gpu.memoryUtilization)" :stroke-width="8" />
                    <span class="gpu-mem-text">{{ gpu.memoryUsed.toFixed(1) }} / {{ gpu.memoryTotal.toFixed(1) }} GB</span>
                  </div>
                  <div class="gpu-stat-row">
                    <span class="gpu-stat-label">温度</span>
                    <span class="gpu-temp" :class="{ 'high-temp': gpu.temperature > 80 }">{{ gpu.temperature }}°C</span>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>快捷操作</span>
          </template>
          <el-row :gutter="20">
            <el-col :span="6">
              <el-button type="primary" size="large" class="action-btn" @click="$router.push('/models')">
                <el-icon><Plus /></el-icon>
                添加模型
              </el-button>
            </el-col>
            <el-col :span="6">
              <el-button type="success" size="large" class="action-btn" @click="$router.push('/services')">
                <el-icon><Cpu /></el-icon>
                服务管理
              </el-button>
            </el-col>
            <el-col :span="6">
              <el-button type="warning" size="large" class="action-btn" @click="$router.push('/benchmark')">
                <el-icon><TrendCharts /></el-icon>
                性能测试
              </el-button>
            </el-col>
            <el-col :span="6">
              <el-button type="info" size="large" class="action-btn" @click="$router.push('/monitor')">
                <el-icon><Monitor /></el-icon>
                日志监控
              </el-button>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近活动 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>运行中的服务</span>
          </template>
          <el-table :data="runningModelsList" style="width: 100%" v-if="runningModelsList.length > 0" size="small">
            <el-table-column prop="name" label="服务名称" />
            <el-table-column prop="engine" label="引擎" width="100" />
            <el-table-column prop="port" label="端口" width="80" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.status === 'running' ? 'success' : 'info'" size="small">
                  {{ scope.row.status === 'running' ? '运行中' : '已停止' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty description="暂无运行中的服务" v-else :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>最近请求日志</span>
          </template>
          <div class="log-list" v-if="recentLogs.length > 0">
            <div v-for="(log, index) in recentLogs" :key="index" class="log-item">
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              <el-tag :type="log.status === 'success' ? 'success' : 'danger'" size="small">
                {{ log.status }}
              </el-tag>
              <span class="log-message">{{ log.model || 'N/A' }}</span>
            </div>
          </div>
          <el-empty description="暂无请求记录" v-else :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Plus, Cpu, TrendCharts, Monitor } from '@element-plus/icons-vue'
import { serviceApi, logApi, systemApi } from '../api'

const runningServices = ref(0)
const todayRequests = ref(0)
const avgLatency = ref(0)
const gpuInfo = ref({
  utilization: 0,
  memoryUsed: 0,
  memoryTotal: 0
})
const gpuList = ref([])
const runningModelsList = ref([])
const recentLogs = ref([])

let refreshInterval = null

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const getGpuColor = (util) => {
  if (util > 90) return '#F56C6C'
  if (util > 70) return '#E6A23C'
  return '#67C23A'
}

const getMemColor = (util) => {
  if (util > 90) return '#F56C6C'
  if (util > 80) return '#E6A23C'
  return '#409EFF'
}

const fetchDashboardData = async () => {
  try {
    // 获取服务列表
    const servicesRes = await serviceApi.list()
    const services = servicesRes.services || []
    runningModelsList.value = services.filter(s => s.status === 'running')
    runningServices.value = runningModelsList.value.length

    // 获取今日请求统计
    const today = new Date()
    const startTime = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()

    try {
      const statsRes = await logApi.stats({ start_time: startTime })
      if (statsRes.stats) {
        todayRequests.value = statsRes.stats.total_requests || 0
        avgLatency.value = Math.round(statsRes.stats.avg_ttft || 0)
      }
    } catch (e) {
      // 日志统计可能为空
    }

    // 获取最近请求日志
    try {
      const logsRes = await logApi.requests({ limit: 5 })
      recentLogs.value = logsRes.logs || []
    } catch (e) {
      recentLogs.value = []
    }

    // 获取 GPU 信息
    try {
      const gpuRes = await systemApi.gpu()
      if (gpuRes.gpus) {
        gpuList.value = gpuRes.gpus
        gpuInfo.value = {
          utilization: gpuRes.summary?.avgUtilization || 0,
          memoryUsed: gpuRes.summary?.totalMemoryUsed || 0,
          memoryTotal: gpuRes.summary?.totalMemoryTotal || 0
        }
      }
    } catch (e) {
      console.error('Failed to fetch GPU info:', e)
    }
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  }
}

onMounted(() => {
  fetchDashboardData()
  // 每 10 秒刷新一次
  refreshInterval = setInterval(fetchDashboardData, 10000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.dashboard {
  width: 100%;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
}

.stat-label {
  color: #999;
  font-size: 12px;
  margin-top: 8px;
}

.gpu-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}

.gpu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.gpu-index {
  font-weight: bold;
  color: #409EFF;
}

.gpu-name {
  font-size: 12px;
  color: #606266;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gpu-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gpu-stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gpu-stat-label {
  width: 40px;
  font-size: 12px;
  color: #909399;
}

.gpu-mem-text {
  font-size: 11px;
  color: #606266;
  margin-left: 8px;
}

.gpu-stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gpu-temp {
  font-size: 14px;
  font-weight: bold;
  color: #67C23A;
}

.gpu-temp.high-temp {
  color: #F56C6C;
}

.action-btn {
  width: 100%;
  height: 60px;
  font-size: 14px;
}

.action-btn .el-icon {
  margin-right: 8px;
}

.log-list {
  max-height: 200px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.log-time {
  color: #999;
  font-size: 12px;
}

.log-message {
  flex: 1;
  font-size: 13px;
}
</style>