"""
Core module for BBS P2P application.

This module contains the core functionality including:
- Cryptography (key management, signing, encryption)
- Network management (peer connections, discovery)
- Database operations
- Synchronization logic
- Vector clocks for distributed synchronization
- File attachment management
"""

__version__ = "0.1.0"

from core.vector_clock import VectorClock, ClockComparison
from core.sync_manager import SyncManager, SyncError
from core.file_manager import (
    FileManager,
    FileAttachment,
    FileChunk,
    FileTransfer,
    FileError,
    FileTooLargeError,
    FileTransferError,
    FileVerificationError
)

__all__ = [
    'VectorClock',
    'ClockComparison',
    'SyncManager',
    'SyncError',
    'FileManager',
    'FileAttachment',
    'FileChunk',
    'FileTransfer',
    'FileError',
    'FileTooLargeError',
    'FileTransferError',
    'FileVerificationError',
]
