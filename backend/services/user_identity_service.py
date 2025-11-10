"""
用户身份识别服务

职责：
- 从domain_experts.xlsx识别专家身份
- 缓存专家列表（5分钟TTL）
- 返回用户信息（is_expert, expert_domains）
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UserIdentityService:
    """用户身份识别服务"""

    def __init__(self, kb_root: Path):
        """
        初始化用户身份识别服务

        Args:
            kb_root: 知识库根目录
        """
        self.kb_root = kb_root
        self.expert_table_path = kb_root / "企业管理/人力资源/domain_experts.xlsx"

        # 缓存
        self._expert_cache: Dict[str, List[str]] = {}  # {userid: [domains]}
        self._expert_name_cache: Dict[str, str] = {}  # {userid: name}
        self._cache_expires_at: Optional[datetime] = None

        logger.info("UserIdentityService initialized")

    async def identify_user_role(self, user_id: str) -> Dict:
        """
        识别用户角色

        Args:
            user_id: 企业微信userid

        Returns:
            {
                "user_id": str,
                "name": str,  # 姓名（如果能从表中获取）
                "is_expert": bool,
                "expert_domains": List[str]
            }
        """
        # 刷新缓存（每5分钟）
        if not self._cache_expires_at or datetime.now() > self._cache_expires_at:
            await self._refresh_expert_cache()

        is_expert = user_id in self._expert_cache
        domains = self._expert_cache.get(user_id, [])
        name = self._expert_name_cache.get(user_id, "")  # 从缓存获取姓名

        return {
            "user_id": user_id,
            "name": name,
            "is_expert": is_expert,
            "expert_domains": domains
        }

    async def _refresh_expert_cache(self):
        """从domain_experts.xlsx刷新缓存"""
        try:
            import pandas as pd

            if not self.expert_table_path.exists():
                logger.warning(f"Expert table not found: {self.expert_table_path}")
                self._expert_cache = {}
                self._expert_name_cache = {}
                self._cache_expires_at = datetime.now() + timedelta(minutes=5)
                return

            df = pd.read_excel(self.expert_table_path)
            self._expert_cache = {}
            self._expert_name_cache = {}

            for _, row in df.iterrows():
                userid = str(row['userid'])
                domain = str(row.get('工作领域', row.get('domain', '')))  # 支持中英文列名
                name = str(row.get('姓名', row.get('name', '')))  # 支持中英文列名

                if userid not in self._expert_cache:
                    self._expert_cache[userid] = []
                self._expert_cache[userid].append(domain)

                # 缓存姓名（每个userid只保存一次）
                if userid not in self._expert_name_cache:
                    self._expert_name_cache[userid] = name

            self._cache_expires_at = datetime.now() + timedelta(minutes=5)
            logger.info(f"Expert cache refreshed: {len(self._expert_cache)} experts loaded")

        except Exception as e:
            logger.error(f"Failed to refresh expert cache: {e}")
            self._expert_cache = {}
            self._expert_name_cache = {}
            self._cache_expires_at = datetime.now() + timedelta(minutes=1)  # 失败时1分钟后重试


# 全局单例
_user_identity_service: Optional[UserIdentityService] = None


def get_user_identity_service(kb_root: Optional[Path] = None) -> UserIdentityService:
    """
    获取UserIdentityService单例

    Args:
        kb_root: 知识库根目录

    Returns:
        UserIdentityService实例
    """
    global _user_identity_service

    if _user_identity_service is None:
        from backend.config.settings import get_settings

        if kb_root is None:
            settings = get_settings()
            kb_root = Path(settings.KB_ROOT_PATH)

        _user_identity_service = UserIdentityService(kb_root=kb_root)

    return _user_identity_service


# 导出
__all__ = [
    "UserIdentityService",
    "get_user_identity_service"
]
