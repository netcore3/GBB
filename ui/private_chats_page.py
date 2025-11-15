"""
Private Chats Page for P2P Encrypted BBS

Container page that manages chat list and active chat widget.
Provides split view with conversation list on left and chat on right.
"""

import logging
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QStackedWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QFont
from qfluentwidgets import InfoBar, InfoBarPosition

from logic.chat_manager import ChatManager
from ui.chat_list_page import ChatListPage
from ui.chat_widget import ChatWidget


logger = logging.getLogger(__name__)


class PrivateChatsPage(QWidget):
    """
    Container page for private messaging.
    
    Displays:
    - Left panel: List of conversations (ChatListPage)
    - Right panel: Active chat widget (ChatWidget) or empty state
    
    Manages navigation between conversation list and individual chats.
    
    Signals:
        error_occurred: Emitted when an error occurs (error_message)
    """
    
    error_occurred = Signal(str)
    
    def __init__(self, chat_manager: ChatManager, parent=None):
        """
        Initialize private chats page.
        
        Args:
            chat_manager: ChatManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.chat_manager = chat_manager
        self.current_chat_widget = None
        self.current_peer_id = None
        
        self._setup_ui()
        self._connect_signals()
        
        logger.info("PrivateChatsPage initialized")
    
    def _setup_ui(self):
        """Set up the page UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.chat_list = ChatListPage(self.chat_manager)
        self.chat_list.setFixedWidth(350)
        main_layout.addWidget(self.chat_list)
        
        self.right_panel = QStackedWidget()
        
        self.empty_state = self._create_empty_state()
        self.right_panel.addWidget(self.empty_state)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.right_panel.addWidget(self.chat_container)
        
        main_layout.addWidget(self.right_panel, stretch=1)
        
        self.right_panel.setCurrentWidget(self.empty_state)
    
    def _create_empty_state(self):
        """Create empty state widget shown when no chat is selected."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("💬")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)
        
        message_label = QLabel("Select a conversation to start chatting")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setFont(QFont("Segoe UI", 14))
        message_label.setStyleSheet("color: #999999; margin-top: 16px;")
        layout.addWidget(message_label)
        
        return widget
    
    def _connect_signals(self):
        """Connect signals between components."""
        self.chat_list.conversation_selected.connect(self._on_conversation_selected)
        self.chat_list.new_chat_requested.connect(self._on_new_chat_requested)
    
    def _on_conversation_selected(self, peer_id):
        """Handle conversation selection from chat list."""
        try:
            logger.info(f"Opening conversation with {peer_id[:8]}")
            
            if self.current_chat_widget:
                self.chat_layout.removeWidget(self.current_chat_widget)
                self.current_chat_widget.deleteLater()
                self.current_chat_widget = None
            
            self.current_chat_widget = ChatWidget(self.chat_manager, peer_id)
            self.current_chat_widget.message_sent.connect(
                lambda content: self._on_message_sent(peer_id, content)
            )
            self.current_chat_widget.file_attached.connect(
                lambda file_path: self._on_file_attached(peer_id, file_path)
            )
            
            self.chat_layout.addWidget(self.current_chat_widget)
            
            self.right_panel.setCurrentWidget(self.chat_container)
            
            self.current_peer_id = peer_id
            
            self.chat_list.mark_conversation_read(peer_id)
            
        except Exception as e:
            logger.error(f"Failed to open conversation: {e}")
            self.error_occurred.emit(f"Failed to open conversation: {e}")
    
    def _on_new_chat_requested(self):
        """Handle new chat request."""
        try:
            logger.info("New chat requested")
            self._show_info("New Chat", "Peer selection dialog coming soon")
            
        except Exception as e:
            logger.error(f"Failed to start new chat: {e}")
            self.error_occurred.emit(f"Failed to start new chat: {e}")
    
    async def _on_message_sent(self, peer_id, content):
        """Handle message send request."""
        try:
            logger.info(f"Sending message to {peer_id[:8]}")
            
            message = await self.chat_manager.send_private_message(peer_id, content)
            
            if self.current_chat_widget and self.current_peer_id == peer_id:
                self.current_chat_widget.add_message(message, content)
            
            self.chat_list.refresh()
            
            logger.info(f"Message sent successfully: {message.id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self._show_error("Send Failed", f"Failed to send message: {e}")
    
    def _on_file_attached(self, peer_id, file_path):
        """Handle file attachment."""
        try:
            logger.info(f"Attaching file to message: {file_path}")
            self._show_info("File Attachment", "File attachment feature coming soon")
            
        except Exception as e:
            logger.error(f"Failed to attach file: {e}")
            self._show_error("Attachment Failed", f"Failed to attach file: {e}")
    
    def _show_info(self, title, content):
        """Show info notification."""
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )
    
    def _show_error(self, title, content):
        """Show error notification."""
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
    
    def refresh(self):
        """Refresh the page (reload conversations)."""
        logger.debug("Refreshing private chats page")
        self.chat_list.refresh()
        
        if self.current_chat_widget:
            self.current_chat_widget.refresh()
    
    def close_current_chat(self):
        """Close the currently open chat."""
        if self.current_chat_widget:
            self.chat_layout.removeWidget(self.current_chat_widget)
            self.current_chat_widget.deleteLater()
            self.current_chat_widget = None
            self.current_peer_id = None
            
            self.right_panel.setCurrentWidget(self.empty_state)
            
            logger.debug("Closed current chat")
