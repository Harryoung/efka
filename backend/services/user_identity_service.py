"""
User Identity Recognition Service

Responsibilities:
- Identify expert identity from domain_experts.xlsx
- Cache expert list (5-minute TTL)
- Return user information (is_expert, expert_domains)
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UserIdentityService:
    """User identity recognition service"""

    def __init__(self, kb_root: Path):
        """
        Initialize user identity recognition service

        Args:
            kb_root: Knowledge base root directory
        """
        self.kb_root = kb_root
        self.expert_table_path = kb_root / "企业管理/人力资源/domain_experts.xlsx"

        # Cache
        self._expert_cache: Dict[str, List[str]] = {}  # {userid: [domains]}
        self._expert_name_cache: Dict[str, str] = {}  # {userid: name}
        self._cache_expires_at: Optional[datetime] = None

        logger.info("UserIdentityService initialized")

    async def identify_user_role(self, user_id: str) -> Dict:
        """
        Identify user role

        Args:
            user_id: WeChat Work (企业微信) userid

        Returns:
            {
                "user_id": str,
                "name": str,  # Name (if retrievable from table)
                "is_expert": bool,
                "expert_domains": List[str]
            }
        """
        # Refresh cache (every 5 minutes)
        if not self._cache_expires_at or datetime.now() > self._cache_expires_at:
            await self._refresh_expert_cache()

        is_expert = user_id in self._expert_cache
        domains = self._expert_cache.get(user_id, [])
        name = self._expert_name_cache.get(user_id, "")  # Get name from cache

        return {
            "user_id": user_id,
            "name": name,
            "is_expert": is_expert,
            "expert_domains": domains
        }

    async def _refresh_expert_cache(self):
        """Refresh cache from domain_experts.xlsx"""
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
                userid = str(row.get('负责人UserID', row.get('userid', '')))  # Support old and new column names
                domain = str(row.get('工作领域', row.get('domain', '')))  # Support Chinese and English column names
                name = str(row.get('负责人姓名', row.get('姓名', row.get('name', ''))))  # Support old and new column names

                if userid not in self._expert_cache:
                    self._expert_cache[userid] = []
                self._expert_cache[userid].append(domain)

                # Cache name (save only once per userid)
                if userid not in self._expert_name_cache:
                    self._expert_name_cache[userid] = name

            self._cache_expires_at = datetime.now() + timedelta(minutes=5)
            logger.info(f"Expert cache refreshed: {len(self._expert_cache)} experts loaded")

        except Exception as e:
            logger.error(f"Failed to refresh expert cache: {e}")
            self._expert_cache = {}
            self._expert_name_cache = {}
            self._cache_expires_at = datetime.now() + timedelta(minutes=1)  # Retry in 1 minute on failure


# Global singleton
_user_identity_service: Optional[UserIdentityService] = None


def get_user_identity_service(kb_root: Optional[Path] = None) -> UserIdentityService:
    """
    Get UserIdentityService singleton

    Args:
        kb_root: Knowledge base root directory

    Returns:
        UserIdentityService instance
    """
    global _user_identity_service

    if _user_identity_service is None:
        from backend.config.settings import get_settings

        if kb_root is None:
            settings = get_settings()
            kb_root = Path(settings.KB_ROOT_PATH)

        _user_identity_service = UserIdentityService(kb_root=kb_root)

    return _user_identity_service


# Export
__all__ = [
    "UserIdentityService",
    "get_user_identity_service"
]
