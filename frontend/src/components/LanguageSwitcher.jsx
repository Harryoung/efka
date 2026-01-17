import React from 'react';
import { useTranslation } from 'react-i18next';
import { Dropdown } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();

  const items = [
    {
      key: 'en',
      label: 'English',
    },
    {
      key: 'zh-CN',
      label: '中文',
    },
  ];

  const handleLanguageChange = ({ key }) => {
    i18n.changeLanguage(key);
  };

  const currentLang = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en';

  return (
    <Dropdown
      menu={{ items, onClick: handleLanguageChange, selectedKeys: [currentLang] }}
      placement="bottomRight"
    >
      <span style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', padding: '4px 8px' }}>
        <GlobalOutlined style={{ fontSize: '16px' }} />
      </span>
    </Dropdown>
  );
};

export default LanguageSwitcher;
