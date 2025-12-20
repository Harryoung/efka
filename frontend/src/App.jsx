/**
 * App Main Component
 * EFKA - Embed-Free Knowledge Agent Frontend
 * Supports Admin and User modes
 */

import React from 'react';
import ChatView from './components/ChatView';
import UserChatView from './components/UserChatView';
import './App.css';

// 根据环境变量决定加载哪个视图
const APP_MODE = import.meta.env.VITE_APP_MODE || 'admin';

function App() {
  return (
    <div className="app">
      <div className="app-background"></div>
      {APP_MODE === 'user' ? <UserChatView /> : <ChatView />}
    </div>
  );
}

export default App;
