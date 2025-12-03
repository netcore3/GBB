"""
Error Handler for P2P Encrypted BBS Application

Provides centralized error handling with categorization, logging, and user-friendly notifications.
Handles crypto, network, storage, and UI errors with appropriate responses.
"""

import logging
import traceback
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification."""
    CRYPTO = "crypto"
    NETWORK = "network"
    STORAGE = "storage"
    UI = "ui"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for an error."""
    category: ErrorCategory
    severity: ErrorSeverity
    operation: str
    user_message: str
    technical_details: str
    peer_id: Optional[str] = None
    board_id: Optional[str] = None
    thread_id: Optional[str] = None


# Custom Exception Classes

class BBSError(Exception):
    """Base exception for BBS application errors."""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN):
        super().__init__(message)
        self.category = category


class CryptoError(BBSError):
    """Cryptographic operation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.CRYPTO)


class SignatureVerificationError(CryptoError):
    """Signature verification failed."""
    pass


class DecryptionError(CryptoError):
    """Decryption operation failed."""
    pass


class KeystoreError(CryptoError):
    """Keystore operation failed."""
    pass


class NetworkError(BBSError):
    """Network operation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.NETWORK)


class ConnectionError(NetworkError):
    """Connection establishment or maintenance failed."""
    pass


class HandshakeError(NetworkError):
    """Handshake protocol failed."""
    pass


class ProtocolError(NetworkError):
    """Protocol violation or invalid message."""
    pass


class StorageError(BBSError):
    """Storage operation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.STORAGE)


class DatabaseError(StorageError):
    """Database operation failed."""
    pass


class DiskSpaceError(StorageError):
    """Insufficient disk space."""
    pass


class UIError(BBSError):
    """UI operation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.UI)


class ValidationError(BBSError):
    """Data validation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.UNKNOWN)


class ErrorHandler:
    """
    Global error handler for the BBS application.
    
    Provides centralized error handling with:
    - Error categorization (crypto, network, storage, UI)
    - Severity classification
    - User-friendly error messages
    - Detailed logging for debugging
    - Notification callbacks for UI integration
    
    Usage:
        error_handler = ErrorHandler()
        error_handler.set_notification_callback(main_window.show_error)
        
        try:
            # Some operation
            pass
        except Exception as e:
            error_handler.handle_error(e, "operation_name")
    """
    
    def __init__(self):
        """Initialize error handler."""
        self._notification_callback: Optional[Callable] = None
        self._error_count = 0
        self._security_event_callback: Optional[Callable] = None
    
    def set_notification_callback(self, callback: Callable):
        """
        Set callback for displaying notifications to user.
        
        Args:
            callback: Function(title: str, content: str, severity: ErrorSeverity)
        """
        self._notification_callback = callback
    
    def set_security_event_callback(self, callback: Callable):
        """
        Set callback for security events (signature failures, etc.).
        
        Args:
            callback: Function(event_type: str, details: dict)
        """
        self._security_event_callback = callback
    
    def handle_error(
        self,
        error: Exception,
        context: str,
        peer_id: Optional[str] = None,
        board_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        show_notification: bool = True
    ) -> ErrorContext:
        """
        Handle an error with appropriate categorization and response.
        
        Args:
            error: The exception that occurred
            context: Description of the operation that failed
            peer_id: Optional peer ID if error relates to a peer
            board_id: Optional board ID if error relates to a board
            thread_id: Optional thread ID if error relates to a thread
            show_notification: Whether to show user notification (default: True)
            
        Returns:
            ErrorContext with categorized error information
        """
        self._error_count += 1
        
        # Categorize the error
        if isinstance(error, BBSError):
            category = error.category
        else:
            category = self._categorize_error(error)
        
        # Determine severity
        severity = self._determine_severity(error, category)
        
        # Generate user-friendly message
        user_message = self._generate_user_message(error, category, context)
        
        # Get technical details
        technical_details = self._get_technical_details(error)
        
        # Create error context
        error_context = ErrorContext(
            category=category,
            severity=severity,
            operation=context,
            user_message=user_message,
            technical_details=technical_details,
            peer_id=peer_id,
            board_id=board_id,
            thread_id=thread_id
        )
        
        # Log the error
        self._log_error(error_context)
        
        # Handle security events
        if category == ErrorCategory.CRYPTO and peer_id:
            self._handle_security_event(error_context)
        
        # Show notification if requested
        if show_notification and self._notification_callback:
            self._show_notification(error_context)
        
        return error_context
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Categorize an error based on its type and message.
        
        Args:
            error: The exception to categorize
            
        Returns:
            ErrorCategory
        """
        error_type = type(error).__name__.lower()
        error_msg = str(error).lower()
        
        # Check for crypto-related errors
        if any(keyword in error_type or keyword in error_msg for keyword in [
            'crypto', 'signature', 'encrypt', 'decrypt', 'key', 'hash'
        ]):
            return ErrorCategory.CRYPTO
        
        # Check for network-related errors
        if any(keyword in error_type or keyword in error_msg for keyword in [
            'connection', 'network', 'socket', 'timeout', 'peer', 'handshake'
        ]):
            return ErrorCategory.NETWORK
        
        # Check for storage-related errors
        if any(keyword in error_type or keyword in error_msg for keyword in [
            'database', 'storage', 'disk', 'file', 'sqlite', 'integrity'
        ]):
            return ErrorCategory.STORAGE
        
        # Check for UI-related errors
        if any(keyword in error_type or keyword in error_msg for keyword in [
            'widget', 'window', 'ui', 'qt', 'display', 'render'
        ]):
            return ErrorCategory.UI
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(
        self,
        error: Exception,
        category: ErrorCategory
    ) -> ErrorSeverity:
        """
        Determine the severity of an error.
        
        Args:
            error: The exception
            category: Error category
            
        Returns:
            ErrorSeverity
        """
        # Critical errors that require immediate attention
        if isinstance(error, (KeystoreError, DiskSpaceError)):
            return ErrorSeverity.CRITICAL
        
        # Security-related errors are always at least ERROR level
        if category == ErrorCategory.CRYPTO:
            if isinstance(error, SignatureVerificationError):
                return ErrorSeverity.ERROR
            return ErrorSeverity.ERROR
        
        # Network errors are usually warnings (transient)
        if category == ErrorCategory.NETWORK:
            if isinstance(error, HandshakeError):
                return ErrorSeverity.ERROR
            return ErrorSeverity.WARNING
        
        # Storage errors are serious
        if category == ErrorCategory.STORAGE:
            return ErrorSeverity.ERROR
        
        # UI errors are usually warnings
        if category == ErrorCategory.UI:
            return ErrorSeverity.WARNING
        
        # Default to ERROR for unknown issues
        return ErrorSeverity.ERROR
    
    def _generate_user_message(
        self,
        error: Exception,
        category: ErrorCategory,
        context: str
    ) -> str:
        """
        Generate a user-friendly error message.
        
        Args:
            error: The exception
            category: Error category
            context: Operation context
            
        Returns:
            User-friendly error message
        """
        if category == ErrorCategory.CRYPTO:
            return self._generate_crypto_message(error, context)
        elif category == ErrorCategory.NETWORK:
            return self._generate_network_message(error, context)
        elif category == ErrorCategory.STORAGE:
            return self._generate_storage_message(error, context)
        elif category == ErrorCategory.UI:
            return self._generate_ui_message(error, context)
        else:
            return f"An error occurred during {context}. Please try again."
    
    def _generate_crypto_message(self, error: Exception, context: str) -> str:
        """Generate user message for crypto errors."""
        if isinstance(error, SignatureVerificationError):
            return "Message authentication failed. The message may have been tampered with."
        elif isinstance(error, DecryptionError):
            return "Failed to decrypt message. The message may be corrupted."
        elif isinstance(error, KeystoreError):
            return "Failed to access your identity. Please check your password."
        else:
            return "A security validation failed. The operation was rejected."
    
    def _generate_network_message(self, error: Exception, context: str) -> str:
        """Generate user message for network errors."""
        if isinstance(error, ConnectionError):
            return "Failed to connect to peer. Please check your network connection."
        elif isinstance(error, HandshakeError):
            return "Failed to establish secure connection with peer."
        elif isinstance(error, ProtocolError):
            return "Received invalid message from peer. The peer may be using an incompatible version."
        else:
            return "Network operation failed. Please check your connection."
    
    def _generate_storage_message(self, error: Exception, context: str) -> str:
        """Generate user message for storage errors."""
        if isinstance(error, DiskSpaceError):
            return "Insufficient disk space. Please free up space and try again."
        elif isinstance(error, DatabaseError):
            return "Database operation failed. Your data may be corrupted."
        else:
            return "Failed to save data. Please check available disk space."
    
    def _generate_ui_message(self, error: Exception, context: str) -> str:
        """Generate user message for UI errors."""
        return "A display error occurred. Please try refreshing the view."
    
    def _get_technical_details(self, error: Exception) -> str:
        """
        Get technical details for logging.
        
        Args:
            error: The exception
            
        Returns:
            Technical details string
        """
        details = [
            f"Exception Type: {type(error).__name__}",
            f"Message: {str(error)}",
            f"Traceback:",
            traceback.format_exc()
        ]
        return "\n".join(details)
    
    def _log_error(self, error_context: ErrorContext):
        """
        Log error with appropriate level.
        
        Args:
            error_context: Error context information
        """
        log_message = (
            f"[{error_context.category.value.upper()}] "
            f"{error_context.operation}: {error_context.user_message}"
        )
        
        extra_info = []
        if error_context.peer_id:
            extra_info.append(f"peer_id={error_context.peer_id}")
        if error_context.board_id:
            extra_info.append(f"board_id={error_context.board_id}")
        if error_context.thread_id:
            extra_info.append(f"thread_id={error_context.thread_id}")
        
        if extra_info:
            log_message += f" ({', '.join(extra_info)})"
        
        # Log based on severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
            logger.critical(f"Technical details:\n{error_context.technical_details}")
        elif error_context.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
            logger.debug(f"Technical details:\n{error_context.technical_details}")
        elif error_context.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
            logger.debug(f"Technical details:\n{error_context.technical_details}")
        else:
            logger.info(log_message)
    
    def _handle_security_event(self, error_context: ErrorContext):
        """
        Handle security-related events.
        
        Args:
            error_context: Error context with security implications
        """
        if self._security_event_callback:
            event_details = {
                'operation': error_context.operation,
                'peer_id': error_context.peer_id,
                'message': error_context.user_message,
                'timestamp': None  # Will be set by callback
            }
            
            try:
                self._security_event_callback('signature_failure', event_details)
            except Exception as e:
                logger.error(f"Failed to handle security event: {e}")
        
        # Log security event separately
        security_logger = logging.getLogger('security')
        security_logger.warning(
            f"Security event: {error_context.operation} - "
            f"peer_id={error_context.peer_id} - "
            f"{error_context.user_message}"
        )
    
    def _show_notification(self, error_context: ErrorContext):
        """
        Show notification to user.
        
        Args:
            error_context: Error context information
        """
        if not self._notification_callback:
            return
        
        try:
            # Generate title based on category
            title_map = {
                ErrorCategory.CRYPTO: "Security Error",
                ErrorCategory.NETWORK: "Network Error",
                ErrorCategory.STORAGE: "Storage Error",
                ErrorCategory.UI: "Display Error",
                ErrorCategory.UNKNOWN: "Error"
            }
            
            title = title_map.get(error_context.category, "Error")
            
            # Call notification callback with severity
            self._notification_callback(
                title,
                error_context.user_message,
                error_context.severity
            )
            
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
    
    def get_error_count(self) -> int:
        """
        Get total number of errors handled.
        
        Returns:
            Error count
        """
        return self._error_count
    
    def reset_error_count(self):
        """Reset error counter."""
        self._error_count = 0


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Get the global error handler instance.
    
    Returns:
        Global ErrorHandler instance
    """
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_error_handler(handler: ErrorHandler):
    """
    Set the global error handler instance.
    
    Args:
        handler: ErrorHandler instance to use globally
    """
    global _global_error_handler
    _global_error_handler = handler
