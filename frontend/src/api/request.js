import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/',
  timeout: 30000,
})

// 请求拦截器 — 自动注入 token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 — 统一错误处理
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const msg = data?.message || data?.detail || error.message || '请求失败'

    if (status === 401) {
      // Token 过期，尝试刷新
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken && !error.config._retry) {
        error.config._retry = true
        return axios
          .post(
            '/auth/refresh',
            {},
            { headers: { 'X-Refresh-Token': refreshToken } }
          )
          .then((res) => {
            const newToken = res.data.access_token
            localStorage.setItem('access_token', newToken)
            localStorage.setItem('refresh_token', res.data.refresh_token)
            error.config.headers.Authorization = `Bearer ${newToken}`
            return request(error.config)
          })
          .catch(() => {
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user_info')
            window.location.href = '/login'
            return Promise.reject(error)
          })
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }

    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request