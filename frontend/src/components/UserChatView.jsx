/**
 * UserChatView - User Q&A Interface
 * Simplified ChatView with Q&A only, no file upload
 */

import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { DeleteOutlined } from '@ant-design/icons';
import apiService from '../shared/api';
import Message from './Message';
import CicadaLogo from './CicadaLogo';
import LanguageSwitcher from './LanguageSwitcher';
import './ChatView.css';

const UserChatView = () => {
  const { t, i18n } = useTranslation();

  // State management
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

  // Update welcome message on language change
  useEffect(() => {
    setMessages(prev => {
      if (prev.length > 0 && prev[0].role === 'system') {
        const newMessages = [...prev];
        newMessages[0] = { ...newMessages[0], content: t('welcome.userGreeting') };
        return newMessages;
      }
      return prev;
    });
  }, [i18n.language, t]);

  // Initialize session
  const initializeSession = async () => {
    try {
      const result = await apiService.createSession();
      setSessionId(result.session_id);

      addSystemMessage(t('welcome.userGreeting'));
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
        });
      }

      return newMessages;
    });
  };

  // Send message (SSE streaming)
  const sendMessage = async () => {
    const userMessage = inputMessage.trim();

    if (!userMessage || !sessionId || isLoading) {
      return;
    }

    setInputMessage('');
    setIsLoading(true);
    setError(null);

    addMessage('user', userMessage);

    try {
      eventSourceRef.current = apiService.queryStream(
        sessionId,
        userMessage,
        (data) => {
          if (data.type === 'message') {
            updateLastAssistantMessage(data.content);
          } else if (data.type === 'session') {
            console.log('Session info:', data);
          } else if (data.type === 'error') {
            console.error('Server error:', data);
            setError(`${t('chat.error')}: ${data.message || t('chat.unknownError')}`);
            setIsLoading(false);
          }
        },
        async (error) => {
          console.error('Stream error:', error);

          try {
            console.log(t('session.recreating'));
            const result = await apiService.createSession();
            setSessionId(result.session_id);
            setError(t('session.expired'));
            addSystemMessage(t('session.expired'));
          } catch (retryError) {
            console.error('Failed to recreate session:', retryError);
            setError(t('session.expiredCannotRecreate'));
          }

          setIsLoading(false);
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
          <h1><CicadaLogo size={24} color="#10b981" /> {t('header.userTitle')}</h1>
          <p className="header-subtitle">
            {sessionId ? `${t('header.sessionId')}: ${sessionId.substring(0, 8)}...` : t('header.initializing')}
          </p>
        </div>
        <div className="header-actions">
          <LanguageSwitcher />
          <button
            className="btn-secondary"
            onClick={handleClearChat}
            title={t('actions.clearSession')}
          >
            <DeleteOutlined /> {t('actions.clearSession')}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>x</button>
        </div>
      )}

      {/* Message list */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon"><CicadaLogo size={48} color="#10b981" /></div>
            <h2>{t('welcome.title')}</h2>
            <p>{t('welcome.canDo')}</p>
            <ul>
              <li>{t('features.userAskKnowledge')}</li>
              <li>{t('features.userSmartSearch')}</li>
              <li>{t('features.userGetAnswers')}</li>
            </ul>
          </div>
        )}

        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="loading-indicator">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>{t('chat.thinking')}</p>
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
          {isLoading ? t('chat.sending') : t('chat.send')}
        </button>
      </div>
    </div>
  );
};

export default UserChatView;
