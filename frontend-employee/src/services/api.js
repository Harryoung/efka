/**
 * API 客户端封装
 * 负责所有与后端的通信（Employee UI 简化版）
 */

import axios from 'axios';
import { getUserId } from '../utils/userManager';

// API 基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

/**
 * API 服务类（Employee UI 简化版）
 */
class APIService {
  /**
   * 创建会话
   * @returns {Promise<{session_id: string}>}
   */
  async createSession() {
    return apiClient.post('/session/create');
  }

  /**
   * 发送查询（SSE 流式）
   * @param {string} sessionId - 会话ID
   * @param {string} message - 用户消息
   * @param {Function} onMessage - 消息回调
   * @param {Function} onError - 错误回调
   * @param {Function} onComplete - 完成回调
   * @returns {EventSource} - EventSource 实例，可用于关闭连接
   */
  queryStream(sessionId, message, onMessage, onError, onComplete) {
    const messageStr = typeof message === 'string' ? message : String(message);
    const userId = getUserId();

    // 构建 SSE URL - 使用 Employee API
    const url = new URL('/api/employee/query', window.location.origin);
    url.searchParams.append('session_id', sessionId || '');
    url.searchParams.append('message', messageStr);
    url.searchParams.append('user_id', userId);

    const eventSource = new EventSource(url.toString());

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'done') {
          eventSource.close();
          if (onComplete) onComplete();
        } else {
          if (onMessage) onMessage(data);
        }
      } catch (error) {
        console.error('Failed to parse SSE message:', error);
        if (onError) onError(error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      eventSource.close();
      if (onError) onError(error);
    };

    return eventSource;
  }

  /**
   * 健康检查
   * @returns {Promise<{status: string}>}
   */
  async healthCheck() {
    return apiClient.get('/health');
  }
}

// 创建单例实例
const apiService = new APIService();

export default apiService;
