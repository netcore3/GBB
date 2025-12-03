"""
Tests for Notification Manager

Tests notification system functionality including connection events,
messages, posts, and moderation actions.
"""

import pytest
import sys
from datetime import datetime
from PySide6.QtWidgets import QApplication

from core.notification_manager import (
    NotificationManager,
    NotificationType,
    NotificationPriority,
    Notification
)


# Ensure QApplication exists for Qt widgets
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestNotificationManager:
    """Test NotificationManager functionality."""
    
    def test_initialization(self, qapp):
        """Test notification manager initialization."""
        manager = NotificationManager()
        
        assert manager is not None
        assert manager._notification_history == []
        assert manager._sound_enabled is True
    
    def test_peer_connected_notification(self, qapp):
        """Test peer connected notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_peer_connected("peer123", "TestPeer")
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert title == "Peer Connected"
        assert "TestPeer" in message
        assert ntype == NotificationType.CONNECTION
        assert priority == NotificationPriority.LOW
    
    def test_peer_disconnected_notification(self, qapp):
        """Test peer disconnected notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_peer_disconnected("peer456", "AnotherPeer")
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert title == "Peer Disconnected"
        assert "AnotherPeer" in message
        assert ntype == NotificationType.CONNECTION
        assert priority == NotificationPriority.LOW
    
    def test_new_message_notification(self, qapp):
        """Test new private message notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_new_message(
            "sender789",
            "SenderName",
            "Hello, this is a test message"
        )
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert "SenderName" in title
        assert "Hello" in message
        assert ntype == NotificationType.MESSAGE
        assert priority == NotificationPriority.HIGH
    
    def test_new_post_notification(self, qapp):
        """Test new post notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_new_post(
            "General Discussion",
            "Welcome Thread",
            "author123",
            "AuthorName",
            "board1",
            "thread1"
        )
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert "General Discussion" in title
        assert "AuthorName" in message
        assert "Welcome Thread" in message
        assert ntype == NotificationType.POST
        assert priority == NotificationPriority.NORMAL
    
    def test_moderation_action_notification(self, qapp):
        """Test moderation action notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_moderation_action(
            "delete",
            "mod123",
            "a post",
            "ModeratorName"
        )
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert title == "Moderation Action"
        assert "ModeratorName" in message
        assert "deleted" in message
        assert ntype == NotificationType.MODERATION
        assert priority == NotificationPriority.NORMAL
    
    def test_system_notification(self, qapp):
        """Test system notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_system(
            "System Update",
            "Application updated successfully",
            NotificationPriority.NORMAL
        )
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert title == "System Update"
        assert "updated successfully" in message
        assert ntype == NotificationType.SYSTEM
        assert priority == NotificationPriority.NORMAL
    
    def test_error_notification(self, qapp):
        """Test error notification."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        manager.notify_error(
            "Connection Error",
            "Failed to connect to peer"
        )
        
        assert len(notifications) == 1
        title, message, ntype, priority = notifications[0]
        assert title == "Connection Error"
        assert "Failed to connect" in message
        assert ntype == NotificationType.ERROR
        assert priority == NotificationPriority.HIGH
    
    def test_notification_history(self, qapp):
        """Test notification history tracking."""
        manager = NotificationManager()
        
        manager.notify_peer_connected("peer1")
        manager.notify_peer_connected("peer2")
        manager.notify_new_message("sender1", preview="Test")
        
        history = manager.get_notification_history()
        assert len(history) == 3
        assert all(isinstance(n, Notification) for n in history)
    
    def test_notification_history_limit(self, qapp):
        """Test notification history size limit."""
        manager = NotificationManager()
        manager._max_history = 5
        
        # Add more notifications than the limit
        for i in range(10):
            manager.notify_peer_connected(f"peer{i}")
        
        history = manager.get_notification_history()
        assert len(history) == 5
        # Should keep the most recent ones
        assert history[-1].peer_id == "peer9"
    
    def test_clear_history(self, qapp):
        """Test clearing notification history."""
        manager = NotificationManager()
        
        manager.notify_peer_connected("peer1")
        manager.notify_peer_connected("peer2")
        
        assert len(manager.get_notification_history()) == 2
        
        manager.clear_history()
        assert len(manager.get_notification_history()) == 0
    
    def test_sound_enable_disable(self, qapp):
        """Test enabling and disabling notification sounds."""
        manager = NotificationManager()
        
        assert manager._sound_enabled is True
        
        manager.set_sound_enabled(False)
        assert manager._sound_enabled is False
        
        manager.set_sound_enabled(True)
        assert manager._sound_enabled is True
    
    def test_notification_signal(self, qapp):
        """Test notification signal emission."""
        manager = NotificationManager()
        received_notifications = []
        
        def on_notification(notification):
            received_notifications.append(notification)
        
        manager.notification_received.connect(on_notification)
        manager.notify_peer_connected("peer1", "TestPeer")
        
        assert len(received_notifications) == 1
        assert isinstance(received_notifications[0], Notification)
        assert received_notifications[0].peer_id == "peer1"
    
    def test_message_preview_truncation(self, qapp):
        """Test that long message previews are truncated."""
        manager = NotificationManager()
        notifications = []
        
        def callback(title, message, ntype, priority):
            notifications.append((title, message, ntype, priority))
        
        manager.set_notification_callback(callback)
        
        long_message = "A" * 100
        manager.notify_new_message("sender1", preview=long_message)
        
        _, message, _, _ = notifications[0]
        assert len(message) <= 53  # 50 chars + "..."
        assert message.endswith("...")
    
    def test_notification_without_callback(self, qapp):
        """Test that notifications work without callback set."""
        manager = NotificationManager()
        
        # Should not raise exception
        manager.notify_peer_connected("peer1")
        manager.notify_new_message("sender1")
        
        # History should still be tracked
        assert len(manager.get_notification_history()) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
