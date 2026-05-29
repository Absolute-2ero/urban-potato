import axios from 'axios'
import { message } from 'antd'

const client = axios.create({
  baseURL: '/',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail || err.message

    if (status === 401) {
      // 未登录，不弹 toast（由各页面自行处理）
    } else if (status >= 500) {
      message.error(`Server error: ${detail}`)
    } else if (status === 422) {
      message.error(`Invalid request: ${detail}`)
    }

    return Promise.reject(err)
  }
)

export default client
