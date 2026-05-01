import axios from 'axios'

const API_BASE = 'http://192.168.31.24:8606'

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: 60000
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 模型管理 API
export const modelApi = {
  list: () => api.get('/models'),
  get: (id) => api.get(`/models/${id}`),
  add: (data) => api.post('/models', data),
  scan: () => api.post('/models/scan'),
  delete: (id) => api.delete(`/models/${id}`)
}

// 服务管理 API
export const serviceApi = {
  list: () => api.get('/services'),
  get: (id) => api.get(`/services/${id}`),
  create: (data) => api.post('/services', data),
  start: (id) => api.post(`/services/${id}/start`),
  stop: (id) => api.post(`/services/${id}/stop`),
  restart: (id) => api.post(`/services/${id}/restart`),
  delete: (id) => api.delete(`/services/${id}`),
  logs: (id) => api.get(`/services/${id}/logs`),
  metrics: (id) => api.get(`/services/${id}/metrics`),
  getParams: (engine) => api.get(`/services/engines/${engine}/params`),
  getPort: (startPort, endPort) => api.get(`/services/port?start_port=${startPort}&end_port=${endPort}`)
}

// 性能测试 API
export const benchmarkApi = {
  run: (config) => api.post('/benchmark/single', config),
  compare: (config) => api.post('/benchmark/compare', config),
  status: (id) => api.get(`/benchmark/${id}/status`),
  result: (id) => api.get(`/benchmark/${id}/result`),
  history: (limit = 20) => api.get(`/benchmark/history?limit=${limit}`),
  delete: (id) => api.delete(`/benchmark/${id}`)
}

// 日志 API
export const logApi = {
  requests: (params) => api.get('/logs/requests', { params }),
  responses: (params) => api.get('/logs/responses', { params }),
  detail: (id) => api.get(`/logs/${id}`),
  stats: (params) => api.get('/logs/stats', { params }),
  export: (format, params) => api.get('/logs/export', { params: { format, ...params } }),
  models: () => api.get('/logs/models'),
  statuses: () => api.get('/logs/statuses')
}

// 系统监控 API
export const systemApi = {
  gpu: () => api.get('/system/gpu'),
  gpuById: (index) => api.get(`/system/gpu/${index}`),
  memory: () => api.get('/system/memory')
}

// 系统配置 API
export const configApi = {
  get: (key) => api.get(`/config/${key}`),
  set: (key, value) => api.put(`/config/${key}`, { value }),
  getScanPaths: () => api.get('/config/scan-paths'),
  addScanPath: (path, description) => api.post('/config/scan-paths', { path, description }),
  deleteScanPath: (id) => api.delete(`/config/scan-paths/${id}`),
  toggleScanPath: (id) => api.patch(`/config/scan-paths/${id}/toggle`),
  browseDirectory: (path) => api.get('/config/browse', { params: { path, show_files: true } })
}

export default api
