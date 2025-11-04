/**
 * Message 消息组件
 * 用于显示单条消息（用户或助手）
 */

import React, { useMemo } from 'react';
import { marked } from 'marked';
import { UserOutlined, RobotOutlined, BulbOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import './Message.css';

// 配置 marked
marked.setOptions({
  breaks: true, // 支持 GitHub Flavored Markdown 的换行
  gfm: true,
  headerIds: false,
  mangle: false,
});

const Message = ({ message, onAddToFAQ, onFeedback }) => {
  const { role, content, timestamp, canFeedback = true, feedbackGiven = false } = message;

  // 渲染 Markdown
  const htmlContent = useMemo(() => {
    if (!content) return '';
    return marked.parse(content);
  }, [content]);

  // 格式化时间
  const formattedTime = useMemo(() => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }, [timestamp]);

  // 检测是否为符合标准格式的知识问答回复（带参考来源）
  const isStandardKnowledgeAnswer = useMemo(() => {
    if (!content || role !== 'assistant') return false;

    // 检测是否包含标准格式的特征：
    // 1. 包含"答案"标题（允许 ## 答案 或 ##答案）
    // 2. 包含"参考来源"或"来源"相关内容
    // 3. 或者包含 knowledge_base/ 路径引用

    const hasAnswerSection = /##\s*答案/i.test(content);
    const hasSourceSection = /##\s*(参考)?来源|来源[:：]/i.test(content);
    const hasKBPath = /knowledge_base\//i.test(content);

    // 必须同时包含答案标识和来源标识（或知识库路径）
    return hasAnswerSection && (hasSourceSection || hasKBPath);
  }, [content, role]);

  return (
    <div className={`message message-${role}`}>
      <div className="message-header">
        <span className="message-role">
          {role === 'user' ? (
            <><UserOutlined /> 你</>
          ) : (
            <><RobotOutlined /> 助手</>
          )}
        </span>
        {formattedTime && (
          <span className="message-time">{formattedTime}</span>
        )}
      </div>

      <div
        className="message-content"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />

      {/* 满意度反馈按钮 - 仅当助手回答符合标准格式且允许反馈时显示 */}
      {role === 'assistant' && isStandardKnowledgeAnswer && onFeedback && canFeedback && (
        <div className="message-feedback">
          <div className="feedback-hint">
            <BulbOutlined /> 满意的回答会被加入FAQ列表，用于直接回答同类问题
          </div>
          <div className="feedback-actions">
            <button
              className="btn-feedback btn-satisfied"
              onClick={() => onFeedback(message, true)}
              disabled={feedbackGiven}
              title={feedbackGiven ? "已反馈" : "对这个回答满意"}
            >
              <LikeOutlined /> {feedbackGiven ? '已反馈' : '满意'}
            </button>
            <button
              className="btn-feedback btn-unsatisfied"
              onClick={() => onFeedback(message, false)}
              disabled={feedbackGiven}
              title={feedbackGiven ? "已反馈" : "对这个回答不满意"}
            >
              <DislikeOutlined /> {feedbackGiven ? '已反馈' : '不满意'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Message;
