"""
Audit Logging System

Responsibilities:
- Record low-confidence routing decisions
- JSON Lines format storage
- Provide human review interface (reserved)
"""

import logging
import json
import aiofiles
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging (for human review)"""

    def __init__(self, log_dir: Path):
        """
        Initialize audit logger

        Args:
            log_dir: Log directory
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.routing_audit_file = log_dir / "routing_audit.jsonl"

        logger.info(f"AuditLogger initialized (log_dir={log_dir})")

    async def log_low_confidence_routing(
        self,
        user_id: str,
        message: str,
        result: Dict,
        audit_required: bool = False
    ):
        """
        Record low-confidence routing decision

        Args:
            user_id: User ID
            message: User message
            result: Router returned result
            audit_required: Whether human review is required
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "low_confidence_routing",
            "user_id": user_id,
            "message_preview": message[:100],  # Truncate sensitive information
            "decision": result['decision'],
            "confidence": result['confidence'],
            "reasoning": result['reasoning'],
            "matched_role": result.get('matched_role'),
            "audit_required": audit_required,
            "reviewed": False
        }

        try:
            # Write to audit log file (JSON Lines format)
            async with aiofiles.open(self.routing_audit_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            logger.info(f"Logged low confidence routing: {user_id} -> {result['decision']} (conf={result['confidence']})")

            # If confidence is extremely low (<0.5), send alert (optional)
            if result['confidence'] < 0.5:
                await self._send_alert(
                    f"Extremely low confidence routing: user={user_id}, confidence={result['confidence']}"
                )

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    async def _send_alert(self, message: str):
        """
        Send alert (reserved interface)

        Args:
            message: Alert message
        """
        # TODO: Integrate WeChat Work (企业微信) alerts or other notification channels
        logger.warning(f"ALERT: {message}")


# Global singleton
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_dir: Optional[Path] = None) -> AuditLogger:
    """
    Get AuditLogger singleton

    Args:
        log_dir: Log directory

    Returns:
        AuditLogger instance
    """
    global _audit_logger

    if _audit_logger is None:
        if log_dir is None:
            log_dir = Path("logs")

        _audit_logger = AuditLogger(log_dir=log_dir)

    return _audit_logger


# Export
__all__ = [
    "AuditLogger",
    "get_audit_logger"
]
