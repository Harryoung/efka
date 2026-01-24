export const getAppMode = () => {
  const forcedMode = typeof globalThis !== 'undefined' ? globalThis.__EFKA_APP_MODE__ : undefined;
  if (forcedMode === 'user' || forcedMode === 'admin') {
    return forcedMode;
  }

  const envMode = import.meta?.env?.VITE_APP_MODE;
  if (envMode === 'user' || envMode === 'admin') {
    return envMode;
  }

  if (typeof window !== 'undefined' && window.location?.port === '3001') {
    return 'user';
  }

  return 'admin';
};
