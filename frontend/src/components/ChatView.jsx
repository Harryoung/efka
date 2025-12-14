/**
 * ChatView Main Component
 * EFKA Admin Interface with message list, input, file upload, SSE streaming
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  FolderOutlined,
  DeleteOutlined,
  WarningOutlined,
  BookOutlined,
  FileTextOutlined,
  BulbOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import apiService from '../services/api';
import Message from './Message';
import FileUpload from './FileUpload';
import CicadaLogo from './CicadaLogo';
import './ChatView.css';

const ChatView = () => {
  // 状态管理
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]); // 存储已上传文件信息

  // refs
  const messagesEndRef = useRef(null);
  const eventSourceRef = useRef(null);
  const inputRef = useRef(null);
  const isInitializedRef = useRef(false); // 跟踪是否已初始化

  // 初始化：创建会话
  useEffect(() => {
    // 防止 React StrictMode 导致的双重调用
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
      addSystemMessage('会话已创建，我是知了，有什么可以帮你的吗？');
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
        canFeedback: role === 'assistant', // 助手消息默认可反馈
        feedbackGiven: false, // 默认未反馈
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
          canFeedback: true, // 新创建的助手消息可反馈
          feedbackGiven: false,
        });
      }

      return newMessages;
    });
  };

  // 发送消息（使用 SSE 流式响应）
  const sendMessage = async (messageToSend = null) => {
    // 如果提供了参数，使用参数；否则使用输入框内容
    const userMessage = messageToSend || inputMessage.trim();

    if (!userMessage || !sessionId || isLoading) {
      return;
    }

    // 只有当使用输入框消息时才清空输入框
    if (!messageToSend) {
      setInputMessage('');
    }

    setIsLoading(true);
    setError(null);

    // 发送新消息时，禁用所有历史助手消息的反馈功能
    setMessages(prev => prev.map(msg => ({
      ...msg,
      canFeedback: false, // 禁用所有历史消息的反馈
    })));

    // 构建实际发送的消息（文件信息在前，用户消息在后）
    let actualMessage = userMessage;
    if (uploadedFiles.length > 0) {
      const fileList = uploadedFiles
        .map(f => `- ${f.originalName} (路径: ${f.tempPath})`)
        .join('\n');
      actualMessage = `[已上传文件]\n${fileList}\n\n${userMessage}`;
    }

    // 添加用户消息到界面（只显示用户输入的内容，不显示文件路径）
    addMessage('user', userMessage);

    // 清空已上传文件状态（消息已发送）
    setUploadedFiles([]);

    try {
      // 使用 SSE 流式响应（发送包含文件路径的完整消息）
      eventSourceRef.current = apiService.queryStream(
        sessionId,
        actualMessage,
        // onMessage - 接收流式数据
        (data) => {
          if (data.type === 'message') {
            updateLastAssistantMessage(data.content);
          } else if (data.type === 'session') {
            // 会话信息（可选处理）
            console.log('Session info:', data);
          } else if (data.type === 'error') {
            // 处理服务端返回的错误
            console.error('Server error:', data);
            setError(`错误: ${data.message || '未知错误'}`);
            setIsLoading(false);
          }
        },
        // onError - 错误处理（EventSource 连接错误）
        async (error) => {
          console.error('Stream error:', error);

          // EventSource 错误通常意味着会话可能过期或网络问题
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

  // 判断文件是否为表格类型
  const isTableFile = (fileName) => {
    const ext = fileName.toLowerCase().split('.').pop();
    return ['xlsx', 'xls', 'csv', 'tsv'].includes(ext);
  };

  // 判断文件是否为文档类型
  const isDocumentFile = (fileName) => {
    const ext = fileName.toLowerCase().split('.').pop();
    return ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'md', 'txt'].includes(ext);
  };

  // 文件上传完成处理
  const handleUploadComplete = (uploadedFilesData, originalFiles) => {
    console.log('Upload complete:', uploadedFilesData);

    // 关闭上传界面
    setShowUpload(false);

    // 保存上传文件信息（用于后续发送消息时附加）
    const fileInfoList = uploadedFilesData.map((f, i) => ({
      originalName: originalFiles[i].name,
      tempPath: f.temp_path,
    }));
    setUploadedFiles(fileInfoList);

    // 判断文件类型，决定是否预填消息
    const hasTableFiles = originalFiles.some(f => isTableFile(f.name));
    const allDocumentFiles = originalFiles.every(f => isDocumentFile(f.name));

    // 构建文件名列表（不含路径）用于显示
    const fileNameList = originalFiles
      .map(f => `- ${f.name}`)
      .join('\n');

    let message;
    if (hasTableFiles) {
      // 有表格文件：不预填具体操作，空白输入框
      message = '';
      // 添加系统提示
      addSystemMessage(`已上传文件:\n${fileNameList}\n\n您可以：\n1. 批量通知：描述通知对象和筛选条件（如"通知福利积分>0的员工"）\n2. 文档入库：输入"请将这些文件入库"`);
    } else if (allDocumentFiles) {
      // 全是文档文件：预填入库消息（不含路径）
      message = `请将上面的文件添加到知识库`;
      // 添加系统提示显示文件列表
      addSystemMessage(`已上传文件:\n${fileNameList}`);
    } else {
      // 其他情况：不预填，空白输入框
      message = '';
      addSystemMessage(`已上传文件:\n${fileNameList}`);
    }

    setInputMessage(message);

    // 聚焦到输入框
    inputRef.current?.focus();
  };

  // 文件上传错误处理
  const handleUploadError = (error) => {
    console.error('Upload error:', error);
    setError('文件上传失败: ' + error.message);
  };

  // 处理满意度反馈
  const handleFeedback = async (assistantMessage, isSatisfied) => {
    if (!sessionId || isLoading) {
      return;
    }

    // 立即标记该消息已反馈，禁用按钮
    setMessages(prev => prev.map(msg =>
      msg.timestamp === assistantMessage.timestamp
        ? { ...msg, feedbackGiven: true }
        : msg
    ));

    // 发送满意度反馈消息（作为普通的多轮对话）
    const feedbackMessage = isSatisfied ? '我对结果满意' : '我对结果不满意';
    await sendMessage(feedbackMessage);
  };

  // 清空对话
  const handleClearChat = async () => {
    if (!window.confirm('确定要清空对话记录和上下文吗？')) {
      return;
    }

    try {
      // 调用清空上下文API（基于 user_id）
      const result = await apiService.clearContext();

      // 更新 session_id（虽然不再直接使用，但保持向后兼容）
      if (result.new_session_id) {
        setSessionId(result.new_session_id);
      }

      // 清空消息和已上传文件
      setMessages([]);
      setUploadedFiles([]);
      addSystemMessage('对话和上下文已清空，新会话已创建');
    } catch (error) {
      console.error('Failed to clear context:', error);
      setError('清空对话失败: ' + error.message);
    }
  };

  return (
    <div className="chat-view">
      {/* 头部 */}
      <div className="chat-header">
        <div className="header-title">
          <h1><CicadaLogo size={24} color="#10b981" /> 知了 · 管理端</h1>
          <p className="header-subtitle">
            {sessionId ? `会话ID: ${sessionId.substring(0, 8)}...` : '初始化中...'}
          </p>
        </div>
        <div className="header-actions">
          <button
            className="btn-secondary"
            onClick={() => setShowUpload(!showUpload)}
            title="上传文件"
          >
            <FolderOutlined /> {showUpload ? '关闭上传' : '上传文件'}
          </button>
          <button
            className="btn-secondary"
            onClick={handleClearChat}
            title="清空对话"
          >
            <DeleteOutlined /> 清空对话
          </button>
        </div>
      </div>

      {/* 文件上传区域 */}
      {showUpload && (
        <div className="upload-section">
          <FileUpload
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
          />
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="error-banner">
          <span><WarningOutlined /> {error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* 消息列表 */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon"><CicadaLogo size={48} color="#10b981" /></div>
            <h2>欢迎使用知了</h2>
            <p>你可以：</p>
            <ul>
              <li><BookOutlined /> 询问知识库中的任何问题</li>
              <li><FileTextOutlined /> 上传文件并自动归档到知识库</li>
              <li><BulbOutlined /> 将满意的回答添加到 FAQ</li>
              <li><SearchOutlined /> 智能搜索和多轮对话</li>
            </ul>
          </div>
        )}

        {messages.map((message, index) => (
          <Message
            key={index}
            message={message}
            onFeedback={message.role === 'assistant' ? handleFeedback : null}
          />
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
          {isLoading ? '发送中...' : '发送 ▶'}
        </button>
      </div>
    </div>
  );
};

export default ChatView;
