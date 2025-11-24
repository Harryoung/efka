"""
Domain Expert Router

Routes employee questions to appropriate domain experts based on
semantic domain classification. Uses the domain_experts.xlsx mapping table.
"""

from pathlib import Path
from typing import Dict, Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class DomainExpertNotFoundError(Exception):
    """Raised when no expert is configured for a domain"""
    pass


class DomainExpertRouter:
    """
    Domain expert routing service

    Queries the domain_experts.xlsx mapping table to find the appropriate
    expert for a given work domain.

    Falls back to default expert if no specific expert is configured.

    Example:
        router = DomainExpertRouter('/path/to/knowledge_base')

        expert = router.get_expert_for_domain('薪酬福利')
        # Returns: {
        #     'name': '张三',
        #     'userid': 'zhangsan',
        #     'domain': '薪酬福利',
        #     'contact': 'ext:8001'
        # }
    """

    def __init__(self, kb_root: str):
        """
        Initialize domain expert router

        Args:
            kb_root: Knowledge base root directory path

        The router expects domain_experts.xlsx at:
            {kb_root}/企业管理/人力资源/domain_experts.xlsx
        """
        self.kb_root = Path(kb_root)
        self.expert_table_path = (
            self.kb_root / "企业管理" / "人力资源" / "domain_experts.xlsx"
        )

        if not self.expert_table_path.exists():
            logger.warning(
                f"Domain experts table not found at {self.expert_table_path}"
            )

        logger.info(f"DomainExpertRouter initialized with kb_root={kb_root}")

    def get_expert_for_domain(self, domain: str) -> Dict[str, str]:
        """
        Get expert information for a specific domain

        Args:
            domain: Work domain name (e.g., "薪酬福利", "考勤管理")

        Returns:
            Dictionary with expert information:
                {
                    'name': str,      # Expert's display name
                    'userid': str,    # WeChat Work UserID
                    'domain': str,    # Domain name
                    'contact': str    # Contact info (optional)
                }

        Raises:
            DomainExpertNotFoundError: If no expert is configured (including default)
            FileNotFoundError: If domain_experts.xlsx doesn't exist

        Example:
            expert = router.get_expert_for_domain('薪酬福利')
            print(f"Contact {expert['name']} at {expert['userid']}")
        """
        if not self.expert_table_path.exists():
            raise FileNotFoundError(
                f"Domain experts table not found at {self.expert_table_path}"
            )

        try:
            # Read Excel file
            df = pd.read_excel(self.expert_table_path)

            # Exact match on domain
            result = df[df['工作领域'] == domain]

            # If not found, fall back to default expert
            if result.empty:
                logger.info(
                    f"No specific expert for domain '{domain}', using default"
                )
                result = df[df['工作领域'] == '默认负责人']

            # If still empty, no experts configured at all
            if result.empty:
                raise DomainExpertNotFoundError(
                    "No experts configured in domain_experts.xlsx, "
                    "please add at least a default expert"
                )

            # Extract first match
            row = result.iloc[0]

            expert_info = {
                'name': row['负责人姓名'],
                'userid': row['负责人UserID'],
                'domain': row['工作领域'],
                'contact': row.get('联系方式', '')
            }

            logger.info(
                f"Found expert for domain '{domain}': {expert_info['name']} "
                f"({expert_info['userid']})"
            )

            return expert_info

        except KeyError as e:
            logger.error(f"Invalid column structure in domain_experts.xlsx: {e}")
            raise ValueError(
                f"Domain experts table has invalid structure: missing column {e}"
            )

    def get_all_experts(self) -> Dict[str, Dict[str, str]]:
        """
        Get all configured experts

        Returns:
            Dictionary mapping domain names to expert info

        Example:
            all_experts = router.get_all_experts()
            for domain, expert in all_experts.items():
                print(f"{domain}: {expert['name']}")
        """
        if not self.expert_table_path.exists():
            logger.warning("Domain experts table not found")
            return {}

        try:
            df = pd.read_excel(self.expert_table_path)

            experts = {}
            for _, row in df.iterrows():
                domain = row['工作领域']
                experts[domain] = {
                    'name': row['负责人姓名'],
                    'userid': row['负责人UserID'],
                    'domain': domain,
                    'contact': row.get('联系方式', '')
                }

            logger.debug(f"Loaded {len(experts)} experts from mapping table")
            return experts

        except Exception as e:
            logger.error(f"Failed to load experts: {e}")
            return {}

    def get_default_expert(self) -> Optional[Dict[str, str]]:
        """
        Get the default expert (fallback for unmatched domains)

        Returns:
            Expert info dictionary, or None if not configured
        """
        try:
            return self.get_expert_for_domain('默认负责人')
        except (DomainExpertNotFoundError, FileNotFoundError):
            logger.warning("No default expert configured")
            return None

    def is_expert_userid(self, userid: str) -> bool:
        """
        Check if a userid belongs to any configured expert

        Useful for routing incoming messages (is this an expert replying?)

        Args:
            userid: WeChat Work UserID to check

        Returns:
            True if userid is configured as an expert

        Example:
            if router.is_expert_userid('zhangsan'):
                # This might be an expert reply
                check_pending_questions()
        """
        all_experts = self.get_all_experts()

        for expert in all_experts.values():
            if expert['userid'] == userid:
                logger.debug(f"UserID {userid} is expert: {expert['name']}")
                return True

        return False


# Singleton instance
_domain_expert_router_instance: Optional[DomainExpertRouter] = None


def get_domain_expert_router(kb_root: Optional[str] = None) -> DomainExpertRouter:
    """
    Get singleton instance of DomainExpertRouter

    Args:
        kb_root: Knowledge base root path (required on first call)

    Returns:
        DomainExpertRouter instance

    Raises:
        ValueError: If kb_root not provided on first call
    """
    global _domain_expert_router_instance

    if _domain_expert_router_instance is None:
        if kb_root is None:
            raise ValueError("kb_root must be provided on first call")
        _domain_expert_router_instance = DomainExpertRouter(kb_root)

    return _domain_expert_router_instance


__all__ = [
    'DomainExpertRouter',
    'DomainExpertNotFoundError',
    'get_domain_expert_router'
]
