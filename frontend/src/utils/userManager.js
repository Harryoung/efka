/**
 * User ID 管理模块
 * 重新导出共享模块（保持向后兼容）
 */

export { getUserId, clearUserId, setUserId } from '../shared/userManager';
import userManager from '../shared/userManager';
export default userManager;
