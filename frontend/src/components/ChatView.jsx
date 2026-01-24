/**
 * ChatView Main Component
 * EFKA Admin Interface with message list, input, file upload, SSE streaming
 */

import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
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
import LanguageSwitcher from './LanguageSwitcher';
import './ChatView.css';

const ChatView = () => {
  const { t } = useTranslation();

  // State management
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeTools, setActiveTools] = useState([]);
  const [pendingToolCalls, setPendingToolCalls] = useState([]);

  // refs
  const messagesEndRef = useRef(null);
  const eventSourceRef = useRef(null);
  const inputRef = useRef(null);
  const isInitializedRef = useRef(false);
  const pendingToolCallsRef = useRef([]);

  // Initialize: create session
  useEffect(() => {
    if (isInitializedRef.current) {
      return;
    }
    isInitializedRef.current = true;

    initializeSession();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Auto scroll to bottom
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize session
  const initializeSession = async () => {
    try {
      const result = await apiService.createSession();
      setSessionId(result.session_id);
    } catch (error) {
      console.error('Failed to create session:', error);
      setError(t('session.createFailed'));
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const addMessage = (role, content) => {
    setMessages(prev => [
      ...prev,
      {
        role,
        content,
        timestamp: Date.now(),
        canFeedback: role === 'assistant',
        feedbackGiven: false,
      },
    ]);
  };

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
        newMessages.push({
          role: 'assistant',
          content,
          timestamp: Date.now(),
          canFeedback: true,
          feedbackGiven: false,
        });
      }

      return newMessages;
    });
  };

  // Send message (SSE streaming)
  const sendMessage = async (messageToSend = null) => {
    const userMessage = messageToSend || inputMessage.trim();

    if (!userMessage || !sessionId || isLoading) {
      return;
    }

    if (!messageToSend) {
      setInputMessage('');
    }

    setIsLoading(true);
    setError(null);
    setActiveTools([]);
    setPendingToolCalls([]);
    pendingToolCallsRef.current = [];

    setMessages(prev => prev.map(msg => ({
      ...msg,
      canFeedback: false,
    })));

    let actualMessage = userMessage;
    if (uploadedFiles.length > 0) {
      const fileList = uploadedFiles
        .map(f => `- ${f.originalName} (path: ${f.tempPath})`)
        .join('\n');
      actualMessage = `[UPLOADED_FILES]\n${fileList}\n\n${userMessage}`;
    }

    addMessage('user', userMessage);
    setUploadedFiles([]);

    try {
      eventSourceRef.current = apiService.queryStream(
        sessionId,
        actualMessage,
        (data) => {
          if (data.type === 'message') {
            updateLastAssistantMessage(data.content);
          } else if (data.type === 'session') {
            console.log('Session info:', data);
          } else if (data.type === 'tool_use') {
            setActiveTools(prev => {
              const filtered = prev.filter(tool => tool.id !== data.id);
              return [...filtered, { id: data.id, tool: data.tool, input: data.input }].slice(-3);
            });
            setPendingToolCalls(prev => {
              const next = [...prev, { id: data.id, tool: data.tool, input: data.input }];
              pendingToolCallsRef.current = next;
              return next;
            });
          } else if (data.type === 'done') {
            const toolCalls = pendingToolCallsRef.current;
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = {
                  ...newMessages[lastIndex],
                  toolCalls,
                };
              }
              return newMessages;
            });
            setActiveTools([]);
            setPendingToolCalls([]);
            pendingToolCallsRef.current = [];
          } else if (data.type === 'error') {
            console.error('Server error:', data);
            setError(`${t('chat.error')}: ${data.message || t('chat.unknownError')}`);
            setIsLoading(false);
            setActiveTools([]);
            setPendingToolCalls([]);
            pendingToolCallsRef.current = [];
          }
        },
        async (error) => {
          console.error('Stream error:', error);

          setError(`${t('chat.error')}: ${t('chat.streamDisconnected')}`);
          setIsLoading(false);
          setActiveTools([]);
          setPendingToolCalls([]);
          pendingToolCallsRef.current = [];
        },
        () => {
          setIsLoading(false);
          eventSourceRef.current = null;
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      setError(`${t('actions.messageFailed')}: ${error.message}`);
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const isTableFile = (fileName) => {
    const ext = fileName.toLowerCase().split('.').pop();
    return ['xlsx', 'xls', 'csv', 'tsv'].includes(ext);
  };

  const isDocumentFile = (fileName) => {
    const ext = fileName.toLowerCase().split('.').pop();
    return ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'md', 'txt'].includes(ext);
  };

  const handleUploadComplete = (uploadedFilesData, originalFiles) => {
    console.log('Upload complete:', uploadedFilesData);

    setShowUpload(false);

    const fileInfoList = uploadedFilesData.map((f, i) => ({
      originalName: originalFiles[i].name,
      tempPath: f.temp_path,
    }));
    setUploadedFiles(fileInfoList);

    const hasTableFiles = originalFiles.some(f => isTableFile(f.name));
    const allDocumentFiles = originalFiles.every(f => isDocumentFile(f.name));

    const fileNameList = originalFiles
      .map(f => `- ${f.name}`)
      .join('\n');

    let message;
    if (hasTableFiles) {
      message = '';
      addSystemMessage(`${t('upload.uploadedFiles')}:\n${fileNameList}\n\n${t('upload.batchNotifyHint')}`);
    } else if (allDocumentFiles) {
      message = t('upload.addToKb');
      addSystemMessage(`${t('upload.uploadedFiles')}:\n${fileNameList}`);
    } else {
      message = '';
      addSystemMessage(`${t('upload.uploadedFiles')}:\n${fileNameList}`);
    }

    setInputMessage(message);
    inputRef.current?.focus();
  };

  const handleUploadError = (error) => {
    console.error('Upload error:', error);
    setError(`${t('upload.failed')}: ${error.message}`);
  };

  const handleFeedback = async (assistantMessage, isSatisfied) => {
    if (!sessionId || isLoading) {
      return;
    }

    setMessages(prev => prev.map(msg =>
      msg.timestamp === assistantMessage.timestamp
        ? { ...msg, feedbackGiven: true }
        : msg
    ));

    const feedbackMessage = isSatisfied ? t('feedback.satisfied') : t('feedback.unsatisfied');
    await sendMessage(feedbackMessage);
  };

  const handleClearChat = async () => {
    if (!window.confirm(t('actions.confirmClear'))) {
      return;
    }

    try {
      const result = await apiService.clearContext();

      if (result.new_session_id) {
        setSessionId(result.new_session_id);
      }

      setMessages([]);
      setUploadedFiles([]);
      addSystemMessage(t('session.cleared'));
    } catch (error) {
      console.error('Failed to clear context:', error);
      setError(`${t('session.clearFailed')}: ${error.message}`);
    }
  };

  return (
    <div className="chat-view">
      {/* Header */}
      <div className="chat-header">
        <div className="header-title">
          <h1><CicadaLogo size={24} color="#f97316" /> {t('header.adminTitle')}</h1>
          <p className="header-subtitle">
            {sessionId ? `${t('header.sessionId')}: ${sessionId.substring(0, 8)}...` : t('header.initializing')}
          </p>
        </div>
        <div className="header-actions">
          <LanguageSwitcher />
          <button
            className="btn-secondary"
            onClick={() => setShowUpload(!showUpload)}
            title={t('upload.title')}
          >
            <FolderOutlined /> {showUpload ? t('upload.close') : t('upload.title')}
          </button>
          <button
            className="btn-secondary"
            onClick={handleClearChat}
            title={t('actions.clearChat')}
          >
            <DeleteOutlined /> {t('actions.clearChat')}
          </button>
        </div>
      </div>

      {/* File upload area */}
      {showUpload && (
        <div className="upload-section">
          <FileUpload
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
          />
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="error-banner">
          <span><WarningOutlined /> {error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Message list */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon"><CicadaLogo size={48} color="#f97316" /></div>
            <h2>{t('welcome.title')}</h2>
            <p>{t('welcome.canDo')}</p>
            <ul>
              <li><BookOutlined /> {t('features.askKnowledge')}</li>
              <li><FileTextOutlined /> {t('features.uploadFiles')}</li>
              <li><BulbOutlined /> {t('features.addToFaq')}</li>
              <li><SearchOutlined /> {t('features.smartSearch')}</li>
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

        {/* Loading indicator with tool display */}
        {isLoading && (
          <div className="loading-indicator">
            {activeTools.length > 0 ? (
              <div className="tool-indicator">
                {activeTools.map((tool, index) => (
                  <span key={tool.id || index} className="tool-badge">
                    <span className="tool-dot"></span>
                    {t(`tools.${(tool.tool || tool).toLowerCase()}`, `Using ${tool.tool || tool}...`)}
                  </span>
                ))}
              </div>
            ) : (
              <>
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <p>{t('chat.thinking')}</p>
              </>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="input-container">
        <textarea
          ref={inputRef}
          className="message-input"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={t('chat.placeholder')}
          rows={3}
          disabled={!sessionId || isLoading}
        />
        <button
          className="btn-send"
          onClick={() => sendMessage()}
          disabled={!sessionId || isLoading || !inputMessage.trim()}
        >
          {isLoading ? t('chat.sending') : `${t('chat.send')} ▶`}
        </button>
      </div>
    </div>
  );
};

export default ChatView;
