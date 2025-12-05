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
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox, ComboBox, isDarkTheme, PrimaryPushButton, FluentIcon, ScrollArea, PushButton, SubtitleLabel

from logic.chat_manager import ChatManager
from ui.chat_list_page import ChatListPage
from ui.chat_widget import ChatWidget
from core.db_manager import DBManager
from ui.theme_utils import GhostTheme, get_page_margins, SPACING_MEDIUM


logger = logging.getLogger(__name__)


class PrivateChatsPage(ScrollArea):
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
    
    def __init__(self, chat_manager: ChatManager, parent=None, identity: Optional[str] = None, db_manager: Optional[DBManager] = None):
        """
        Initialize private chats page.
        
        Args:
            chat_manager: ChatManager instance
            parent: Parent widget
            identity: Optional peer identity (for compatibility)
            db_manager: Optional DBManager instance (for compatibility)
        """
        super().__init__(parent)
        
        self.chat_manager = chat_manager
        self.identity = identity
        self.db_manager = db_manager
        self.current_chat_widget = None
        self.current_peer_id = None
        
        self._setup_ui()
        self._connect_signals()
        
        logger.info("PrivateChatsPage initialized")
    
    def _setup_ui(self):
        """Set up page UI."""
        # Create main widget
        self.view = QWidget()
        # Outer thin border to encapsulate internal content
        self.view.setObjectName("panelContainer")
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Apply dark theme styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                color: {GhostTheme.get_text_primary()};
            }}
            QScrollArea#privateChatsPage {{
                border: none;
                background-color: {GhostTheme.get_background()};
            }}
        """)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        margins = get_page_margins()
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(SPACING_MEDIUM)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Title
        title_label = SubtitleLabel("Private Chats")
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # New Chat button
        self.new_chat_button = PrimaryPushButton(FluentIcon.ADD, "New Chat")
        self.new_chat_button.clicked.connect(self._on_new_chat_requested)
        header_layout.addWidget(self.new_chat_button)
        
        self.main_layout.addLayout(header_layout)
        
        # Main horizontal layout (chat list + right panel)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        self.chat_list = ChatListPage(self.chat_manager)
        self.chat_list.setFixedWidth(350)
        self.chat_list.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                color: {GhostTheme.get_text_primary()};
                border-right: 1px solid {GhostTheme.get_tertiary_background()};
            }}
            QFrame#chatListItem {{
                border-bottom: 1px solid {GhostTheme.get_tertiary_background()};
                padding: 8px;
            }}
            QFrame#chatListItem:hover {{
                background-color: {GhostTheme.get_purple_primary()};  /* New purple color for hover */
            }}
            /* New purple highlight for selected items */
            QFrame#chatListItem:selected {{
                background-color: {GhostTheme.get_purple_secondary()};
                border-left: 4px solid {GhostTheme.get_purple_tertiary()};
            }}
        """)
        content_layout.addWidget(self.chat_list)
        
        self.right_panel = QStackedWidget()
        
        self.empty_state = self._create_empty_state()
        self.empty_state.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                color: {GhostTheme.get_text_primary()};
                border: 1px solid {GhostTheme.get_tertiary_background()};
                border-radius: 4px;
            }}
        """)
        self.right_panel.addWidget(self.empty_state)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_container.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                color: {GhostTheme.get_text_primary()};
                border: 1px solid {GhostTheme.get_tertiary_background()};
                border-radius: 4px;
            }}
        """)
        self.right_panel.addWidget(self.chat_container)
        
        content_layout.addWidget(self.right_panel, stretch=1)
        
        self.main_layout.addLayout(content_layout)
        
        # Add stretch at bottom
        self.main_layout.addStretch()
        
        # Style
        self.setObjectName("privateChatsPage")
        
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
        message_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()}; margin-top: 16px;")
        layout.addWidget(message_label)
        
        return widget
    
    def _connect_signals(self):
        """Connect signals between components."""
        self.chat_list.conversation_selected.connect(self._on_conversation_selected)
        self.chat_list.new_chat_requested.connect(self._on_new_chat_requested)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_conversation(self, peer_id: str) -> None:
        """Open (or create) a conversation with the given peer.

        This is a thin wrapper so other pages (e.g. PeerMonitorPage) or the
        main window can programmatically open a chat with a peer.

        Args:
            peer_id: Target peer identifier.
        """
        if not peer_id:
            logger.warning("open_conversation called with empty peer_id")
            return

        self._on_conversation_selected(peer_id)
    
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
        """Handle new chat request by letting the user pick a peer.

        This uses the database's known peers list to populate a simple
        ComboBox-based selector. Only peers that are not banned are shown.
        """
        try:
            logger.info("New chat requested")

            if not self.db_manager:
                self._show_error(
                    "New Chat",
                    "Peer list is unavailable (no database manager).",
                )
                return

            peers = [p for p in self.db_manager.get_all_peers() if not p.is_banned]
            if not peers:
                self._show_info(
                    "No peers",
                    "No peers available. Connect to peers first.",
                )
                return

            # Build a small dialog using MessageBox and ComboBox
            dialog = MessageBox(
                "Start New Chat",
                "Select a peer to start a private conversation:",
                self,
            )

            combo = ComboBox(dialog)
            for peer in peers:
                label = f"{peer.peer_id[:16]}" + (" (trusted)" if peer.is_trusted else "")
                combo.addItem(label, userData=peer.peer_id)

            dialog.textLayout.addWidget(combo)

            if not dialog.exec():
                return

            peer_id = combo.currentData()
            if not peer_id:
                self._show_error("New Chat", "No peer selected.")
                return

            # Open the selected conversation
            self._on_conversation_selected(peer_id)

        except Exception as e:  # noqa: BLE001
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
