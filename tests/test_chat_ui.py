"""
Tests for Private Chat UI Components

Tests the ChatListPage, ChatWidget, and PrivateChatsPage components.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QApplication
import sys

# Ensure QApplication exists for Qt widgets
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_chat_manager():
    """Create mock ChatManager."""
    manager = Mock()
    manager.identity = Mock()
    manager.identity.peer_id = "local_peer_123"
    manager.get_all_conversations = Mock(return_value=[])
    manager.get_conversation = Mock(return_value=[])
    manager.get_unread_count = Mock(return_value=0)
    manager.decrypt_message = Mock(return_value="Test message")
    return manager


@pytest.fixture
def mock_private_message():
    """Create mock PrivateMessage."""
    message = Mock()
    message.id = "msg_123"
    message.sender_peer_id = "peer_456"
    message.recipient_peer_id = "local_peer_123"
    message.encrypted_content = b"encrypted_data"
    message.created_at = datetime.utcnow()
    message.read_at = None
    return message


def test_chat_list_page_initialization(qapp, mock_chat_manager):
    """Test ChatListPage initializes correctly."""
    from ui.chat_list_page import ChatListPage
    
    page = ChatListPage(mock_chat_manager)
    
    assert page is not None
    assert page.chat_manager == mock_chat_manager
    assert len(page.conversation_cards) == 0


def test_chat_list_page_empty_state(qapp, mock_chat_manager):
    """Test ChatListPage shows empty state when no conversations."""
    from ui.chat_list_page import ChatListPage
    
    mock_chat_manager.get_all_conversations.return_value = []
    
    page = ChatListPage(mock_chat_manager)
    
    # Empty label should be visible
    assert page.empty_label.isVisible()
    assert not page.scroll_area.isVisible()


def test_chat_list_page_with_conversations(qapp, mock_chat_manager, mock_private_message):
    """Test ChatListPage displays conversations."""
    from ui.chat_list_page import ChatListPage
    
    mock_chat_manager.get_all_conversations.return_value = ["peer_456"]
    mock_chat_manager.get_conversation.return_value = [mock_private_message]
    mock_chat_manager.get_unread_count.return_value = 2
    
    page = ChatListPage(mock_chat_manager)
    
    # Should have one conversation card
    assert len(page.conversation_cards) == 1
    assert not page.empty_label.isVisible()
    assert page.scroll_area.isVisible()


def test_conversation_card_creation(qapp, mock_private_message):
    """Test ConversationCard creates correctly."""
    from ui.chat_list_page import ConversationCard
    
    card = ConversationCard(
        peer_id="peer_456",
        last_message=mock_private_message,
        unread_count=3
    )
    
    assert card is not None
    assert card.peer_id == "peer_456"
    assert card.unread_count == 3


def test_conversation_card_click_signal(qapp, mock_private_message):
    """Test ConversationCard emits clicked signal."""
    from ui.chat_list_page import ConversationCard
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import Qt, QEvent
    
    card = ConversationCard(
        peer_id="peer_456",
        last_message=mock_private_message,
        unread_count=0
    )
    
    # Connect signal to mock
    clicked_peer_id = []
    card.clicked.connect(lambda pid: clicked_peer_id.append(pid))
    
    # Simulate mouse click
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    card.mousePressEvent(event)
    
    # Check signal was emitted
    assert len(clicked_peer_id) == 1
    assert clicked_peer_id[0] == "peer_456"


def test_chat_widget_initialization(qapp, mock_chat_manager):
    """Test ChatWidget initializes correctly."""
    from ui.chat_widget import ChatWidget
    
    mock_chat_manager.get_conversation.return_value = []
    
    widget = ChatWidget(mock_chat_manager, "peer_456")
    
    assert widget is not None
    assert widget.chat_manager == mock_chat_manager
    assert widget.peer_id == "peer_456"


def test_chat_widget_displays_messages(qapp, mock_chat_manager, mock_private_message):
    """Test ChatWidget displays messages."""
    from ui.chat_widget import ChatWidget
    
    mock_chat_manager.get_conversation.return_value = [mock_private_message]
    
    widget = ChatWidget(mock_chat_manager, "peer_456")
    
    # Should have one message bubble
    assert len(widget.message_bubbles) == 1


def test_message_bubble_creation(qapp, mock_private_message):
    """Test MessageBubble creates correctly."""
    from ui.chat_widget import MessageBubble
    
    bubble = MessageBubble(
        message=mock_private_message,
        content="Hello, world!",
        is_sent=False
    )
    
    assert bubble is not None
    assert bubble.content == "Hello, world!"
    assert not bubble.is_sent


def test_message_bubble_styling(qapp, mock_private_message):
    """Test MessageBubble applies correct styling for sent/received."""
    from ui.chat_widget import MessageBubble
    
    # Sent message
    sent_bubble = MessageBubble(
        message=mock_private_message,
        content="Sent message",
        is_sent=True
    )
    assert "#0078D4" in sent_bubble.styleSheet()  # Blue background
    
    # Received message
    received_bubble = MessageBubble(
        message=mock_private_message,
        content="Received message",
        is_sent=False
    )
    # Should have gray background (color depends on theme)
    assert "background-color" in received_bubble.styleSheet()


def test_private_chats_page_initialization(qapp, mock_chat_manager):
    """Test PrivateChatsPage initializes correctly."""
    from ui.private_chats_page import PrivateChatsPage
    
    page = PrivateChatsPage(mock_chat_manager)
    
    assert page is not None
    assert page.chat_manager == mock_chat_manager
    assert page.current_chat_widget is None
    assert page.current_peer_id is None


def test_private_chats_page_empty_state(qapp, mock_chat_manager):
    """Test PrivateChatsPage shows empty state by default."""
    from ui.private_chats_page import PrivateChatsPage
    
    mock_chat_manager.get_all_conversations.return_value = []
    
    page = PrivateChatsPage(mock_chat_manager)
    
    # Should show empty state
    assert page.right_panel.currentWidget() == page.empty_state


def test_private_chats_page_conversation_selection(qapp, mock_chat_manager, mock_private_message):
    """Test PrivateChatsPage opens chat when conversation selected."""
    from ui.private_chats_page import PrivateChatsPage
    
    mock_chat_manager.get_all_conversations.return_value = ["peer_456"]
    mock_chat_manager.get_conversation.return_value = [mock_private_message]
    mock_chat_manager.get_unread_count.return_value = 0
    
    page = PrivateChatsPage(mock_chat_manager)
    
    # Simulate conversation selection
    page._on_conversation_selected("peer_456")
    
    # Should have created chat widget
    assert page.current_chat_widget is not None
    assert page.current_peer_id == "peer_456"
    assert page.right_panel.currentWidget() == page.chat_container


def test_chat_widget_send_message_signal(qapp, mock_chat_manager):
    """Test ChatWidget emits message_sent signal."""
    from ui.chat_widget import ChatWidget
    
    mock_chat_manager.get_conversation.return_value = []
    
    widget = ChatWidget(mock_chat_manager, "peer_456")
    
    # Connect signal to mock
    sent_messages = []
    widget.message_sent.connect(lambda content: sent_messages.append(content))
    
    # Set message content
    widget.message_input.setPlainText("Test message")
    
    # Trigger send
    widget._on_send_clicked()
    
    # Check signal was emitted
    assert len(sent_messages) == 1
    assert sent_messages[0] == "Test message"
    
    # Input should be cleared
    assert widget.message_input.toPlainText() == ""


def test_chat_widget_empty_message_not_sent(qapp, mock_chat_manager):
    """Test ChatWidget doesn't send empty messages."""
    from ui.chat_widget import ChatWidget
    
    mock_chat_manager.get_conversation.return_value = []
    
    widget = ChatWidget(mock_chat_manager, "peer_456")
    
    # Connect signal to mock
    sent_messages = []
    widget.message_sent.connect(lambda content: sent_messages.append(content))
    
    # Try to send empty message
    widget.message_input.setPlainText("")
    widget._on_send_clicked()
    
    # No signal should be emitted
    assert len(sent_messages) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
