import axios, { AxiosResponse } from 'axios'
import toast from 'react-hot-toast'

const API_BASE_URL = 'http://localhost:8000/api'  // 直接バックエンドに接続

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分のタイムアウト（Claude API overload対応）
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      // タイムアウトエラー
      toast.error('処理に時間がかかっています。しばらく待ってから再度お試しください。')
    } else if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      toast.error('セッションが期限切れです。再度ログインしてください。')
      window.location.href = '/login'
    } else if (error.response?.status === 403) {
      toast.error('権限がありません。')
    } else if (error.response?.status >= 500) {
      toast.error('サーバーエラーが発生しました。')
    } else if (error.response?.data?.detail) {
      toast.error(error.response.data.detail)
    } else if (!error.response) {
      // ネットワークエラー
      toast.error('ネットワークエラーが発生しました。接続を確認してください。')
    }
    return Promise.reject(error)
  }
)

export default api