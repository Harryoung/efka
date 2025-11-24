import React, { useMemo } from 'react';
import { marked } from 'marked';
import './Message.css';

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
  headerIds: false,
  mangle: false,
});

const Message = ({ message }) => {
  const { role, content, timestamp } = message;

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

  return (
    <div className={`message message-${role}`}>
      <div className="message-header">
        <span className="message-role">
          {role === 'user' ? (
            <>👤 你</>
          ) : role === 'system' ? (
            <>💡 系统</>
          ) : (
            <>🤖 助手</>
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
    </div>
  );
};

export default Message;
