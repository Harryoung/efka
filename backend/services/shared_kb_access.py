"""
Shared Knowledge Base Access Layer

Provides file-level locking for concurrent write operations to FAQ.md and BADCASE.md.
Uses fcntl for cross-process locking, supporting future microservices architecture.
"""

import fcntl
import contextlib
import signal
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FileLockTimeout(Exception):
    """Raised when file lock acquisition times out"""
    pass


class SharedKBAccess:
    """
    Shared knowledge base access layer

    Provides file-level mutex locks to prevent concurrent write conflicts,
    especially for FAQ.md and BADCASE.md which can be updated by both:
    - Employee Agent (satisfaction feedback)
    - Admin Agent (manual edits)

    Uses fcntl for cross-process locking, which will work even when
    services are split into separate processes/containers.

    Example:
        kb_access = SharedKBAccess('/path/to/knowledge_base')

        with kb_access.file_lock('FAQ.md'):
            # Read current content
            content = read_file('FAQ.md')
            # Modify content
            content += new_entry
            # Write back atomically
            write_file('FAQ.md', content)
    """

    def __init__(self, kb_root: str):
        """
        Initialize shared KB access layer

        Args:
            kb_root: Knowledge base root directory path
        """
        self.kb_root = Path(kb_root)
        self.lock_dir = self.kb_root / ".locks"
        self.lock_dir.mkdir(exist_ok=True)
        logger.info(f"SharedKBAccess initialized with kb_root={kb_root}")

    @contextlib.contextmanager
    def file_lock(self, file_path: str, timeout: int = 5):
        """
        Acquire an exclusive file lock

        This is a context manager that ensures only one process can write
        to the specified file at a time. Uses fcntl for cross-process locking.

        Args:
            file_path: Relative path to file (e.g., 'FAQ.md', 'BADCASE.md')
            timeout: Lock acquisition timeout in seconds (default: 5)

        Raises:
            FileLockTimeout: If lock cannot be acquired within timeout

        Example:
            with kb_access.file_lock('FAQ.md', timeout=10):
                # Atomic read-modify-write operation
                content = read_file('FAQ.md')
                content += new_entry
                write_file('FAQ.md', content)
        """
        # Create lock file path
        file_name = Path(file_path).name
        lock_file_path = self.lock_dir / f"{file_name}.lock"

        logger.debug(f"Attempting to acquire lock for {file_path}")

        with open(lock_file_path, 'w') as lock_file:
            try:
                # Try non-blocking lock first
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"Lock acquired immediately for {file_path}")
                yield

            except BlockingIOError:
                # Lock is held by another process, wait with timeout
                logger.debug(f"Lock busy for {file_path}, waiting up to {timeout}s")

                # Set up timeout handler
                def timeout_handler(signum, frame):
                    raise FileLockTimeout(
                        f"Failed to acquire lock for {file_path} within {timeout}s"
                    )

                # Set alarm signal
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)

                try:
                    # Block until lock is acquired or timeout
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    signal.alarm(0)  # Cancel alarm
                    logger.debug(f"Lock acquired after waiting for {file_path}")
                    yield

                except FileLockTimeout:
                    logger.error(f"Lock timeout for {file_path}")
                    raise

                finally:
                    # Restore old signal handler
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            finally:
                # Release lock
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                logger.debug(f"Lock released for {file_path}")

    def safe_append_to_file(
        self,
        file_path: str,
        content: str,
        timeout: int = 5
    ) -> None:
        """
        Safely append content to a file with file locking

        Convenience method for common append operations.

        Args:
            file_path: Relative path to file
            content: Content to append
            timeout: Lock acquisition timeout in seconds

        Example:
            kb_access.safe_append_to_file(
                'BADCASE.md',
                '## Case #5\\n\\nUser question...\\n'
            )
        """
        full_path = self.kb_root / file_path

        with self.file_lock(file_path, timeout=timeout):
            # Ensure file exists
            if not full_path.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.touch()

            # Append content
            with open(full_path, 'a', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Appended content to {file_path}")

    def safe_read_file(
        self,
        file_path: str,
        timeout: int = 5
    ) -> Optional[str]:
        """
        Safely read file content with file locking

        Args:
            file_path: Relative path to file
            timeout: Lock acquisition timeout in seconds

        Returns:
            File content as string, or None if file doesn't exist

        Example:
            content = kb_access.safe_read_file('FAQ.md')
        """
        full_path = self.kb_root / file_path

        if not full_path.exists():
            return None

        with self.file_lock(file_path, timeout=timeout):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.debug(f"Read {len(content)} chars from {file_path}")
            return content

    def safe_write_file(
        self,
        file_path: str,
        content: str,
        timeout: int = 5
    ) -> None:
        """
        Safely write content to file with file locking

        Args:
            file_path: Relative path to file
            content: Content to write
            timeout: Lock acquisition timeout in seconds

        Example:
            kb_access.safe_write_file('FAQ.md', updated_content)
        """
        full_path = self.kb_root / file_path

        with self.file_lock(file_path, timeout=timeout):
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Wrote {len(content)} chars to {file_path}")


# Singleton instance
_shared_kb_access_instance: Optional[SharedKBAccess] = None


def get_shared_kb_access(kb_root: Optional[str] = None) -> SharedKBAccess:
    """
    Get singleton instance of SharedKBAccess

    Args:
        kb_root: Knowledge base root path (required on first call)

    Returns:
        SharedKBAccess instance

    Raises:
        ValueError: If kb_root not provided on first call
    """
    global _shared_kb_access_instance

    if _shared_kb_access_instance is None:
        if kb_root is None:
            raise ValueError("kb_root must be provided on first call")
        _shared_kb_access_instance = SharedKBAccess(kb_root)

    return _shared_kb_access_instance


__all__ = [
    'SharedKBAccess',
    'FileLockTimeout',
    'get_shared_kb_access'
]
