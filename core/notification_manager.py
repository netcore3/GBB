"""
Notification Manager for P2P Encrypted BBS Application

Provides centralized notification system for connection events, messages, posts,
and moderation actions. Integrates with UI InfoBar system and optional sound notifications.
"""

import logging
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl


logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    CONNECTION = "connection"
    MESSAGE = "message"
    POST = "post"
    MODERATION = "moderation"
    SYSTEM = "system"
    ERROR = "error"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Notification data structure."""
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    timestamp: datetime
    peer_id: Optional[str] = None
    board_id: Optional[str] = None
    thread_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class NotificationManager(QObject):
    """
    Manages application notifications.
    
    Provides:
    - Connection event notifications (peer connected/disconnected)
    - New message notifications (private messages)
    - New post notifications (board posts)
    - Moderation action notifications
    - System notifications
    - Optional sound notifications
    - Notification history
    
    Signals:
        notification_received: Emitted when a new notification is created
        notification_dismissed: Emitted when a notification is dismissed
    """
    
    # Qt signals
    notification_received = Signal(Notification)
    notification_dismissed = Signal(str)  # notification_id
    
    def __init__(self, config_manager=None):
        """
        Initialize notification manager.
        
        Args:
            config_manager: Optional ConfigManager for settings
        """
        super().__init__()
        
        self.config_manager = config_manager
        self._notification_callback: Optional[Callable] = None
        self._sound_enabled = True
        self._sound_effect: Optional[QSoundEffect] = None
        self._notification_history = []
        self._max_history = 100
        
        # Load settings
        if config_manager:
            self._load_settings()
        
        # Initialize sound effect
        self._init_sound()
        
        logger.info("Notification manager initialized")
    
    def _load_settings(self):
        """Load notification settings from config."""
        try:
            # TODO: Add notification settings to config
            # For now, use defaults
            self._sound_enabled = True
            
        except Exception as e:
            logger.warning(f"Failed to load notification settings: {e}")
    
    def _init_sound(self):
        """Initialize notification sound effect."""
        try:
            # Ensure a QCoreApplication exists before creating Qt multimedia objects.
            # Creating QSoundEffect before a QApplication/QCoreApplication is constructed
            # will raise: "QWidget: Must construct a QApplication before a QWidget".
            from PySide6.QtCore import QCoreApplication

            if QCoreApplication.instance() is None:
                # Defer sound initialization until an application exists
                self._sound_effect = None
                logger.debug("QCoreApplication not yet available; deferring sound initialization")
                return

            # Create sound effect
            self._sound_effect = QSoundEffect()
            
            # TODO: Add notification sound file to resources
            # For now, we'll skip loading the sound file
            # sound_path = "resources/notification.wav"
            # self._sound_effect.setSource(QUrl.fromLocalFile(sound_path))
            
            logger.debug("Notification sound initialized")
            
        except Exception as e:
            logger.warning(f"Failed to initialize notification sound: {e}")
            self._sound_effect = None
    
    def set_notification_callback(self, callback: Callable):
        """
        Set callback for displaying notifications in UI.
        
        Args:
            callback: Function(title: str, message: str, type: NotificationType, priority: NotificationPriority)
        """
        self._notification_callback = callback
    
    def set_sound_enabled(self, enabled: bool):
        """
        Enable or disable notification sounds.
        
        Args:
            enabled: True to enable sounds, False to disable
        """
        self._sound_enabled = enabled
        logger.info(f"Notification sounds {'enabled' if enabled else 'disabled'}")
    
    def notify_peer_connected(self, peer_id: str, peer_name: Optional[str] = None):
        """
        Notify that a peer has connected.
        
        Args:
            peer_id: Peer identifier
            peer_name: Optional peer display name
        """
        display_name = peer_name or peer_id[:8]
        
        notification = Notification(
            type=NotificationType.CONNECTION,
            priority=NotificationPriority.LOW,
            title="Peer Connected",
            message=f"{display_name} has connected",
            timestamp=datetime.now(),
            peer_id=peer_id
        )
        
        self._process_notification(notification)
    
    def notify_peer_disconnected(self, peer_id: str, peer_name: Optional[str] = None):
        """
        Notify that a peer has disconnected.
        
        Args:
            peer_id: Peer identifier
            peer_name: Optional peer display name
        """
        display_name = peer_name or peer_id[:8]
        
        notification = Notification(
            type=NotificationType.CONNECTION,
            priority=NotificationPriority.LOW,
            title="Peer Disconnected",
            message=f"{display_name} has disconnected",
            timestamp=datetime.now(),
            peer_id=peer_id
        )
        
        self._process_notification(notification)
    
    def notify_new_message(
        self,
        sender_id: str,
        sender_name: Optional[str] = None,
        preview: Optional[str] = None
    ):
        """
        Notify about a new private message.
        
        Args:
            sender_id: Sender peer identifier
            sender_name: Optional sender display name
            preview: Optional message preview
        """
        display_name = sender_name or sender_id[:8]
        message = preview[:50] + "..." if preview and len(preview) > 50 else preview or "New message"
        
        notification = Notification(
            type=NotificationType.MESSAGE,
            priority=NotificationPriority.HIGH,
            title=f"New message from {display_name}",
            message=message,
            timestamp=datetime.now(),
            peer_id=sender_id
        )
        
        self._process_notification(notification, play_sound=True)
    
    def notify_new_post(
        self,
        board_name: str,
        thread_title: str,
        author_id: str,
        author_name: Optional[str] = None,
        board_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ):
        """
        Notify about a new post in a board.
        
        Args:
            board_name: Board name
            thread_title: Thread title
            author_id: Author peer identifier
            author_name: Optional author display name
            board_id: Optional board identifier
            thread_id: Optional thread identifier
        """
        display_name = author_name or author_id[:8]
        
        notification = Notification(
            type=NotificationType.POST,
            priority=NotificationPriority.NORMAL,
            title=f"New post in {board_name}",
            message=f"{display_name} posted in '{thread_title}'",
            timestamp=datetime.now(),
            peer_id=author_id,
            board_id=board_id,
            thread_id=thread_id
        )
        
        self._process_notification(notification, play_sound=True)
    
    def notify_moderation_action(
        self,
        action_type: str,
        moderator_id: str,
        target_description: str,
        moderator_name: Optional[str] = None
    ):
        """
        Notify about a moderation action.
        
        Args:
            action_type: Type of moderation action (delete, ban, trust)
            moderator_id: Moderator peer identifier
            target_description: Description of the target
            moderator_name: Optional moderator display name
        """
        display_name = moderator_name or moderator_id[:8]
        
        action_messages = {
            'delete': f"{display_name} deleted {target_description}",
            'ban': f"{display_name} banned {target_description}",
            'trust': f"{display_name} trusted {target_description}"
        }
        
        message = action_messages.get(action_type, f"{display_name} performed {action_type}")
        
        notification = Notification(
            type=NotificationType.MODERATION,
            priority=NotificationPriority.NORMAL,
            title="Moderation Action",
            message=message,
            timestamp=datetime.now(),
            peer_id=moderator_id,
            data={'action_type': action_type}
        )
        
        self._process_notification(notification)
    
    def notify_system(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ):
        """
        Send a system notification.
        
        Args:
            title: Notification title
            message: Notification message
            priority: Notification priority
        """
        notification = Notification(
            type=NotificationType.SYSTEM,
            priority=priority,
            title=title,
            message=message,
            timestamp=datetime.now()
        )
        
        self._process_notification(notification)
    
    def notify_error(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.HIGH
    ):
        """
        Send an error notification.
        
        Args:
            title: Error title
            message: Error message
            priority: Notification priority
        """
        notification = Notification(
            type=NotificationType.ERROR,
            priority=priority,
            title=title,
            message=message,
            timestamp=datetime.now()
        )
        
        self._process_notification(notification)
    
    def _process_notification(self, notification: Notification, play_sound: bool = False):
        """
        Process and display a notification.
        
        Args:
            notification: Notification to process
            play_sound: Whether to play notification sound
        """
        try:
            # Add to history
            self._add_to_history(notification)
            
            # Emit signal
            self.notification_received.emit(notification)
            
            # Display via callback
            if self._notification_callback:
                self._notification_callback(
                    notification.title,
                    notification.message,
                    notification.type,
                    notification.priority
                )
            
            # Play sound if requested and enabled
            if play_sound and self._sound_enabled:
                self._play_sound()
            
            logger.debug(f"Notification processed: {notification.title}")
            
        except Exception as e:
            logger.error(f"Failed to process notification: {e}")
    
    def _add_to_history(self, notification: Notification):
        """
        Add notification to history.
        
        Args:
            notification: Notification to add
        """
        self._notification_history.append(notification)
        
        # Trim history if too long
        if len(self._notification_history) > self._max_history:
            self._notification_history = self._notification_history[-self._max_history:]
    
    def _play_sound(self):
        """Play notification sound."""
        try:
            if self._sound_effect and self._sound_effect.source().isValid():
                self._sound_effect.play()
            
        except Exception as e:
            logger.debug(f"Failed to play notification sound: {e}")
    
    def get_notification_history(self, limit: Optional[int] = None) -> list:
        """
        Get notification history.
        
        Args:
            limit: Optional limit on number of notifications to return
            
        Returns:
            List of Notification objects
        """
        if limit:
            return self._notification_history[-limit:]
        return self._notification_history.copy()
    
    def clear_history(self):
        """Clear notification history."""
        self._notification_history.clear()
        logger.info("Notification history cleared")
    
    def get_unread_count(self, notification_type: Optional[NotificationType] = None) -> int:
        """
        Get count of unread notifications.
        
        Args:
            notification_type: Optional filter by notification type
            
        Returns:
            Count of unread notifications
        """
        # TODO: Implement read/unread tracking
        # For now, return 0
        return 0


# Global notification manager instance
_global_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """
    Get the global notification manager instance.
    
    Returns:
        Global NotificationManager instance
    """
    global _global_notification_manager
    if _global_notification_manager is None:
        _global_notification_manager = NotificationManager()
    return _global_notification_manager


def set_notification_manager(manager: NotificationManager):
    """
    Set the global notification manager instance.
    
    Args:
        manager: NotificationManager instance to use globally
    """
    global _global_notification_manager
    _global_notification_manager = manager
