/**
 * User ID 管理模块（统一版本）
 * 负责管理用户标识（基于 localStorage）
 * 支持 Admin 和 User 两种模式
 */

// 使用统一的 localStorage key
const APP_MODE = import.meta.env.VITE_APP_MODE || 'admin';
const USER_ID_KEY = 'kb_user_id';

/**
 * 生成 UUID v4
 * @returns {string} UUID
 */
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * 获取或创建 user_id
 * @returns {string} user_id
 */
export function getUserId() {
  let userId = localStorage.getItem(USER_ID_KEY);

  if (!userId) {
    userId = generateUUID();
    localStorage.setItem(USER_ID_KEY, userId);
    console.log(`[UserManager:${APP_MODE}] 生成新的 user_id:`, userId);
  } else {
    console.log(`[UserManager:${APP_MODE}] 加载已有 user_id:`, userId);
  }

  return userId;
}

/**
 * 清除 user_id
 */
export function clearUserId() {
  localStorage.removeItem(USER_ID_KEY);
  console.log(`[UserManager:${APP_MODE}] user_id 已清除`);
}

/**
 * 设置 user_id（用于对接外部系统）
 * @param {string} userId
 */
export function setUserId(userId) {
  localStorage.setItem(USER_ID_KEY, userId);
  console.log(`[UserManager:${APP_MODE}] user_id 已设置:`, userId);
}

export default {
  getUserId,
  clearUserId,
  setUserId
};
