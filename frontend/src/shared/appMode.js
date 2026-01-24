export const getAppMode = () => {
  // VITE_APP_MODE is set via Vite's env system (envPrefix or define)
  // In dev: set by each vite config; In build: set by VITE_APP_MODE env var
  const mode = import.meta.env.VITE_APP_MODE;
  if (mode === 'user' || mode === 'admin') {
    return mode;
  }

  // Fallback: port-based detection for dev mode
  if (typeof window !== 'undefined' && window.location?.port === '3001') {
    return 'user';
  }

  return 'admin';
};
