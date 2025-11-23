"""
审计日志系统

职责：
- 记录低置信度路由决策
- JSON Lines格式存储
- 提供人工复核接口（预留）
"""

import logging
import json
import aiofiles
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志（用于人工复核）"""

    def __init__(self, log_dir: Path):
        """
        初始化审计日志

        Args:
            log_dir: 日志目录
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
        记录低置信度路由决策

        Args:
            user_id: 用户ID
            message: 用户消息
            result: Router返回结果
            audit_required: 是否需要人工审核
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "low_confidence_routing",
            "user_id": user_id,
            "message_preview": message[:100],  # 截断敏感信息
            "decision": result['decision'],
            "confidence": result['confidence'],
            "reasoning": result['reasoning'],
            "matched_role": result.get('matched_role'),
            "audit_required": audit_required,
            "reviewed": False
        }

        try:
            # 写入审计日志文件（JSON Lines格式）
            async with aiofiles.open(self.routing_audit_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            logger.info(f"Logged low confidence routing: {user_id} -> {result['decision']} (conf={result['confidence']})")

            # 如果置信度极低（<0.5），发送告警（可选）
            if result['confidence'] < 0.5:
                await self._send_alert(
                    f"极低置信度路由：user={user_id}, confidence={result['confidence']}"
                )

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    async def _send_alert(self, message: str):
        """
        发送告警（预留接口）

        Args:
            message: 告警消息
        """
        # TODO: Integrate with messaging platform or notification channels
        logger.warning(f"ALERT: {message}")


# 全局单例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_dir: Optional[Path] = None) -> AuditLogger:
    """
    获取AuditLogger单例

    Args:
        log_dir: 日志目录

    Returns:
        AuditLogger实例
    """
    global _audit_logger

    if _audit_logger is None:
        if log_dir is None:
            log_dir = Path("logs")

        _audit_logger = AuditLogger(log_dir=log_dir)

    return _audit_logger


# 导出
__all__ = [
    "AuditLogger",
    "get_audit_logger"
]
