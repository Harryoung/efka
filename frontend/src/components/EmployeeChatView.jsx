/**
 * EmployeeChatView - 员工端问答界面
 * 简化版 ChatView，只有问答功能，无文件上传
 */

import React, { useState, useEffect, useRef } from 'react';
import apiService from '../shared/api';
import Message from './Message';
import './ChatView.css';

const EmployeeChatView = () => {
  // 状态管理
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // refs
  const messagesEndRef = useRef(null);
  const eventSourceRef = useRef(null);
  const inputRef = useRef(null);
  const isInitializedRef = useRef(false);

  // 初始化：创建会话
  useEffect(() => {
    if (isInitializedRef.current) {
      return;
    }
    isInitializedRef.current = true;

    initializeSession();

    // 清理函数
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // 自动滚动到底部
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初始化会话
  const initializeSession = async () => {
    try {
      const result = await apiService.createSession();
      setSessionId(result.session_id);

      // 添加欢迎消息
      addSystemMessage('你好！我是智能知识库助手，有什么可以帮你的吗？');
    } catch (error) {
      console.error('Failed to create session:', error);
      setError('无法创建会话，请刷新页面重试');
    }
  };

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 添加消息到列表
  const addMessage = (role, content) => {
    setMessages(prev => [
      ...prev,
      {
        role,
        content,
        timestamp: Date.now(),
      },
    ]);
  };

  // 添加系统消息
  const addSystemMessage = (content) => {
    setMessages(prev => [
      ...prev,
      {
        role: 'system',
        content,
        timestamp: Date.now(),
      },
    ]);
  };

  // 更新最后一条助手消息（用于流式响应）
  const updateLastAssistantMessage = (content) => {
    setMessages(prev => {
      const newMessages = [...prev];
      const lastIndex = newMessages.length - 1;

      if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
        newMessages[lastIndex] = {
          ...newMessages[lastIndex],
          content: newMessages[lastIndex].content + content,
        };
      } else {
        // 如果最后一条不是助手消息，创建新的
        newMessages.push({
          role: 'assistant',
          content,
          timestamp: Date.now(),
        });
      }

      return newMessages;
    });
  };

  // 发送消息（使用 SSE 流式响应）
  const sendMessage = async () => {
    const userMessage = inputMessage.trim();

    if (!userMessage || !sessionId || isLoading) {
      return;
    }

    setInputMessage('');
    setIsLoading(true);
    setError(null);

    // 添加用户消息到界面
    addMessage('user', userMessage);

    try {
      // 使用 SSE 流式响应
      eventSourceRef.current = apiService.queryStream(
        sessionId,
        userMessage,
        // onMessage - 接收流式数据
        (data) => {
          if (data.type === 'message') {
            updateLastAssistantMessage(data.content);
          } else if (data.type === 'session') {
            console.log('Session info:', data);
          } else if (data.type === 'error') {
            console.error('Server error:', data);
            setError(`错误: ${data.message || '未知错误'}`);
            setIsLoading(false);
          }
        },
        // onError - 错误处理
        async (error) => {
          console.error('Stream error:', error);

          // 尝试重新创建会话
          try {
            console.log('尝试重新创建会话...');
            const result = await apiService.createSession();
            setSessionId(result.session_id);
            setError('会话已过期，已自动创建新会话。请重新发送消息。');
            addSystemMessage('会话已过期，已自动创建新会话，请重新发送您的消息');
          } catch (retryError) {
            console.error('Failed to recreate session:', retryError);
            setError('会话已过期且无法重新创建，请刷新页面');
          }

          setIsLoading(false);
        },
        // onComplete - 完成回调
        () => {
          setIsLoading(false);
          eventSourceRef.current = null;
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      setError('消息发送失败: ' + error.message);
      setIsLoading(false);
    }
  };

  // 处理输入框回车
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-view">
      {/* 头部 */}
      <div className="chat-header">
        <div className="header-title">
          <h1>智能知识库助手</h1>
          <p className="header-subtitle">
            {sessionId ? `会话ID: ${sessionId.substring(0, 8)}...` : '初始化中...'}
          </p>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>x</button>
        </div>
      )}

      {/* 消息列表 */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon">:)</div>
            <h2>欢迎使用智能知识库助手</h2>
            <p>你可以：</p>
            <ul>
              <li>询问知识库中的任何问题</li>
              <li>智能搜索和多轮对话</li>
              <li>获取专业的知识解答</li>
            </ul>
          </div>
        )}

        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}

        {/* 加载中提示 */}
        {isLoading && (
          <div className="loading-indicator">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>正在思考...</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="input-container">
        <textarea
          ref={inputRef}
          className="message-input"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="输入你的问题... (Shift+Enter 换行)"
          rows={3}
          disabled={!sessionId || isLoading}
        />
        <button
          className="btn-send"
          onClick={() => sendMessage()}
          disabled={!sessionId || isLoading || !inputMessage.trim()}
        >
          {isLoading ? '发送中...' : '发送'}
        </button>
      </div>
    </div>
  );
};

export default EmployeeChatView;
