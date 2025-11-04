/**
 * API 客户端封装
 * 负责所有与后端的通信
 * 支持基于 user_id 的持久化会话
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
    // 可以在这里添加认证token等
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
 * API 服务类
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
   * 删除会话
   * @param {string} sessionId - 会话ID
   */
  async deleteSession(sessionId) {
    return apiClient.delete(`/session/${sessionId}`);
  }

  /**
   * 发送查询（非流式）
   * @param {string} sessionId - 会话ID
   * @param {string} message - 用户消息
   * @returns {Promise<{response: string}>}
   */
  async query(sessionId, message) {
    const userId = getUserId();

    return apiClient.post('/query', {
      session_id: sessionId,
      message: message,
      user_id: userId  // 新增：携带 user_id
    });
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
    // 确保 message 是字符串，防止传递对象导致 [object Object]
    const messageStr = typeof message === 'string' ? message : String(message);
    const userId = getUserId();

    // 构建 SSE URL
    const url = new URL('/api/query/stream', window.location.origin);
    url.searchParams.append('session_id', sessionId || '');
    url.searchParams.append('message', messageStr);  // URLSearchParams 会自动进行 URL 编码
    url.searchParams.append('user_id', userId);  // 新增：携带 user_id

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
   * 清空用户上下文（新接口）
   * @returns {Promise<{success: boolean, new_session_id: string}>}
   */
  async clearContext() {
    const userId = getUserId();

    return apiClient.post('/clear_context', {
      user_id: userId
    });
  }

  /**
   * 上传文件
   * @param {FileList|File[]} files - 文件列表
   * @param {Function} onProgress - 上传进度回调
   * @returns {Promise<{files: Array}>}
   */
  async uploadFiles(files, onProgress) {
    const formData = new FormData();

    // 添加所有文件到 FormData
    Array.from(files).forEach(file => {
      formData.append('files', file);
    });

    return apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });
  }

  /**
   * 健康检查
   * @returns {Promise<{status: string}>}
   */
  async healthCheck() {
    return apiClient.get('/health');
  }

  /**
   * 获取系统信息
   * @returns {Promise<Object>}
   */
  async getSystemInfo() {
    return apiClient.get('/info');
  }
}

// 创建单例实例
const apiService = new APIService();

export default apiService;
