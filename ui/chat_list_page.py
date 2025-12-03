"""
Chat List Page for P2P Encrypted BBS

Displays list of active private message conversations with peers.
Shows peer name, last message preview, and unread count.
"""

import logging
from typing import Optional, List
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtGui import QFont
from qfluentwidgets import (
    PrimaryPushButton, CardWidget,
    FluentIcon, CaptionLabel,
    StrongBodyLabel, SubtitleLabel, ScrollArea
)

from ui.theme_utils import (
    GhostTheme, get_page_margins, get_card_margins,
    SPACING_MEDIUM
)
from ui.hover_card import apply_hover_glow
from logic.chat_manager import ChatManager
from models.database import PrivateMessage


logger = logging.getLogger(__name__)


class ConversationCard(CardWidget):
    """
    Card widget representing a single conversation.
    
    Displays:
    - Peer name/ID
    - Last message preview
    - Timestamp
    - Unread count badge
    
    Signals:
        clicked: Emitted when conversation is selected
    """
    
    clicked = Signal(str)  # peer_id
    
    def __init__(self, peer_id: str, last_message: Optional[PrivateMessage], unread_count: int, parent=None):
        """
        Initialize conversation card.
        
        Args:
            peer_id: Peer identifier
            last_message: Most recent message in conversation (None if no messages)
            unread_count: Number of unread messages
            parent: Parent widget
        """
        super().__init__(parent)

        self.peer_id = peer_id
        self.last_message = last_message
        self.unread_count = unread_count

        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Set up the card UI."""
        # Main layout
        layout = QHBoxLayout(self)
        margins = get_card_margins()
        layout.setContentsMargins(margins[0], margins[1] - 4, margins[2], margins[3] - 4)  # Slightly less vertical
        layout.setSpacing(SPACING_MEDIUM - 4)
        
        # Left side: Peer info and message preview
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)
        
        # Peer name/ID (truncated)
        peer_display = self.peer_id[:16] + "..." if len(self.peer_id) > 16 else self.peer_id
        self.peer_label = StrongBodyLabel(peer_display)
        self.peer_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        left_layout.addWidget(self.peer_label)
        
        # Last message preview
        if self.last_message:
            preview_text = "[Encrypted Message]"  # We don't decrypt here for privacy
            self.preview_label = CaptionLabel(preview_text)
            self.preview_label.setTextFormat(Qt.TextFormat.PlainText)

            # Style preview text using centralized theme
            self.preview_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")

            left_layout.addWidget(self.preview_label)
        else:
            self.preview_label = CaptionLabel("No messages yet")
            self.preview_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-style: italic;")
            left_layout.addWidget(self.preview_label)

        layout.addLayout(left_layout, stretch=1)

        # Right side: Timestamp and unread badge
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # Timestamp
        if self.last_message:
            timestamp_str = self._format_timestamp(self.last_message.created_at)
            self.timestamp_label = CaptionLabel(timestamp_str)
            self.timestamp_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
            right_layout.addWidget(self.timestamp_label)

        # Unread count badge
        if self.unread_count > 0:
            self.unread_badge = QLabel(str(self.unread_count))
            self.unread_badge.setFixedSize(24, 24)
            self.unread_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.unread_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {GhostTheme.get_purple_primary()};
                    color: {GhostTheme.get_text_primary()};
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            right_layout.addWidget(self.unread_badge)
        
        layout.addLayout(right_layout)
        
        # Make card clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(80)

        # Apply hover glow
        apply_hover_glow(self, color=GhostTheme.get_purple_primary())
    
    def _format_timestamp(self, dt: datetime) -> str:
        """
        Format timestamp for display.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Formatted string (e.g., "2 hours ago", "Yesterday", "Jan 15")
        """
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.days == 0:
            # Today
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                if minutes == 0:
                    return "Just now"
                elif minutes == 1:
                    return "1 min ago"
                else:
                    return f"{minutes} mins ago"
            elif hours == 1:
                return "1 hour ago"
            else:
                return f"{hours} hours ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            return dt.strftime("%b %d")
    
    def _connect_signals(self):
        """Connect internal signals."""
        pass
    
    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.peer_id)
        super().mousePressEvent(event)
    
    def update_unread_count(self, count: int):
        """
        Update the unread count badge.
        
        Args:
            count: New unread count
        """
        self.unread_count = count
        # Refresh UI
        self._setup_ui()


class ChatListPage(QWidget):
    """
    Page displaying list of active conversations.
    
    Shows all conversations with peers, sorted by most recent activity.
    Allows starting new conversations and selecting existing ones.
    
    Signals:
        conversation_selected: Emitted when a conversation is clicked (peer_id)
        new_chat_requested: Emitted when "New Chat" button is clicked
    """
    
    conversation_selected = Signal(str)  # peer_id
    new_chat_requested = Signal()
    
    def __init__(self, chat_manager: ChatManager, parent=None):
        """
        Initialize chat list page.
        
        Args:
            chat_manager: ChatManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.chat_manager = chat_manager
        self.conversation_cards: List[ConversationCard] = []
        
        self._setup_ui()
        self._load_conversations()
        
        logger.info("ChatListPage initialized")
    
    def _setup_ui(self):
        """Set up the page UI with layout matching PeerMonitorPage and BoardListPage."""
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        margins = get_page_margins()
        main_layout.setContentsMargins(*margins)
        main_layout.setSpacing(SPACING_MEDIUM)

        # Add outer border to the page (like PeerMonitorPage)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                border: 1.5px solid {GhostTheme.get_tertiary_background()};
                border-radius: 10px;
            }}
            QScrollArea {{
                background-color: {GhostTheme.get_background()};
                border: none;
            }}
        """)

        # Header with title and New Chat button (same row)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(SPACING_MEDIUM)

        # Title (top-left) — match PeerMonitorPage style
        title_label = SubtitleLabel("Private Chats")
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # New Chat button (PrimaryPushButton, like Create BBS)
        self.new_chat_btn = PrimaryPushButton(FluentIcon.ADD, "New Chat")
        self.new_chat_btn.setIconSize(QSize(18, 18))
        try:
            from ui.theme_utils import get_button_styles
            self.new_chat_btn.setStyleSheet(get_button_styles("primary") + "\nQPushButton { padding: 8px 14px; text-align: left; }")
        except Exception:
            self.new_chat_btn.setStyleSheet(f"background-color: {GhostTheme.get_purple_primary()}; color: {GhostTheme.get_text_primary()}; padding: 8px 14px;")
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        header_layout.addWidget(self.new_chat_btn)

        main_layout.addLayout(header_layout)

        # Scroll area for conversations (with border)
        self.scroll_area = ScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {GhostTheme.get_background()};
                border: 1.5px solid {GhostTheme.get_tertiary_background()};
                border-radius: 8px;
            }}
        """)

        # Container for conversation cards
        self.conversations_container = QWidget()
        self.conversations_container.setStyleSheet(f"background-color: {GhostTheme.get_background()};")
        self.conversations_layout = QVBoxLayout(self.conversations_container)
        self.conversations_layout.setContentsMargins(0, 0, 0, 0)
        self.conversations_layout.setSpacing(8)
        self.conversations_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.conversations_container)
        main_layout.addWidget(self.scroll_area, 1)  # Expand to fill available space

        # Empty state label (shown when no conversations)
        self.empty_label = QLabel("No conversations yet\n\nClick 'New Chat' to start messaging")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 14px;")
        self.empty_label.hide()

        self.conversations_container.layout().addWidget(self.empty_label)

    def _load_conversations(self):
        """Load all conversations from chat manager."""
        try:
            # Clear existing cards
            self._clear_conversations()

            # Get all conversation peer IDs
            peer_ids = self.chat_manager.get_all_conversations()

            if not peer_ids:
                # Show empty state
                self.scroll_area.hide()
                self.empty_label.show()
                logger.debug("No conversations to display")
                return

            # Hide empty state
            self.empty_label.hide()
            self.scroll_area.show()

            # Create conversation cards
            conversations_data = []

            for peer_id in peer_ids:
                # Get conversation messages
                messages = self.chat_manager.get_conversation(peer_id)

                if not messages:
                    continue

                # Get last message
                last_message = messages[-1] if messages else None

                # Get unread count
                unread_count = self.chat_manager.get_unread_count(peer_id)

                conversations_data.append({
                    'peer_id': peer_id,
                    'last_message': last_message,
                    'unread_count': unread_count,
                    'timestamp': last_message.created_at if last_message else datetime.min
                })

            # Sort by most recent activity
            conversations_data.sort(key=lambda x: x['timestamp'], reverse=True)

            # Create cards
            for conv_data in conversations_data:
                card = ConversationCard(
                    peer_id=conv_data['peer_id'],
                    last_message=conv_data['last_message'],
                    unread_count=conv_data['unread_count']
                )
                card.clicked.connect(self._on_conversation_clicked)

                self.conversations_layout.addWidget(card)
                self.conversation_cards.append(card)

            logger.info(f"Loaded {len(self.conversation_cards)} conversations")

        except Exception as e:
            logger.error(f"Failed to load conversations: {e}")
    
    def _clear_conversations(self):
        """Clear all conversation cards."""
        for card in self.conversation_cards:
            self.conversations_layout.removeWidget(card)
            card.deleteLater()
        
        self.conversation_cards.clear()
    
    def _on_conversation_clicked(self, peer_id: str):
        """
        Handle conversation card click.
        
        Args:
            peer_id: Peer ID of selected conversation
        """
        logger.debug(f"Conversation selected: {peer_id[:8]}")
        self.conversation_selected.emit(peer_id)
    
    def _on_new_chat_clicked(self):
        """Handle new chat button click."""
        logger.debug("New chat requested")
        self.new_chat_requested.emit()
    
    def refresh(self):
        """Refresh the conversation list."""
        logger.debug("Refreshing conversation list")
        self._load_conversations()
    
    def mark_conversation_read(self, peer_id: str):
        """
        Mark all messages in a conversation as read.
        
        Args:
            peer_id: Peer ID of conversation
        """
        try:
            # Find the card and update unread count
            for card in self.conversation_cards:
                if card.peer_id == peer_id:
                    card.update_unread_count(0)
                    break
            
            logger.debug(f"Marked conversation {peer_id[:8]} as read")
            
        except Exception as e:
            logger.error(f"Failed to mark conversation as read: {e}")
