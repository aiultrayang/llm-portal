import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
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
  getParams: (engine) => api.get(`/services/engines/${engine}/params`)
}

// 性能测试 API
export const benchmarkApi = {
  run: (config) => api.post('/benchmark/single', config),
  compare: (config) => api.post('/benchmark/compare', config),
  status: (id) => api.get(`/benchmark/${id}/status`),
  result: (id) => api.get(`/benchmark/${id}/result`),
  history: () => api.get('/benchmark/history'),
  delete: (id) => api.delete(`/benchmark/${id}`)
}

// 日志 API
export const logApi = {
  requests: (params) => api.get('/logs/requests', { params }),
  responses: (params) => api.get('/logs/responses', { params }),
  detail: (id) => api.get(`/logs/${id}`),
  stats: (params) => api.get('/logs/stats', { params }),
  export: (format, params) => api.get('/logs/export', { params: { format, ...params } })
}

// 系统监控 API
export const systemApi = {
  gpu: () => api.get('/system/gpu'),
  gpuById: (index) => api.get(`/system/gpu/${index}`),
  memory: () => api.get('/system/memory')
}

export default api
