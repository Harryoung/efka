import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from './locales/en/common.json';
import zhCN from './locales/zh-CN/common.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      'zh-CN': { translation: zhCN }
    },
    fallbackLng: 'zh-CN',
    supportedLngs: ['en', 'zh-CN'],
    defaultNS: 'translation',
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      convertDetectedLanguage: (lng) => {
        if (lng.startsWith('zh')) return 'zh-CN';
        if (lng.startsWith('en')) return 'en';
        return lng;
      }
    },
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
