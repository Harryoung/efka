/**
 * App Main Component
 * EFKA - Embed-Free Knowledge Agent Frontend
 * Supports Admin and User modes with i18n
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { ConfigProvider } from 'antd';
import enUS from 'antd/locale/en_US';
import zhCN from 'antd/locale/zh_CN';
import ChatView from './components/ChatView';
import UserChatView from './components/UserChatView';
import { getAppMode } from './shared/appMode';
import './App.css';

const APP_MODE = getAppMode();

const antdLocales = {
  'en': enUS,
  'zh-CN': zhCN
};

function App() {
  const { i18n } = useTranslation();
  const currentLang = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en';
  const currentLocale = antdLocales[currentLang] || antdLocales['en'];

  return (
    <ConfigProvider locale={currentLocale}>
      <div className="app">
        <div className="app-background"></div>
        {APP_MODE === 'user' ? <UserChatView /> : <ChatView />}
      </div>
    </ConfigProvider>
  );
}

export default App;
