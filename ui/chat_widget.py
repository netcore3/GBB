"""
Chat Widget for P2P Encrypted BBS

Displays private message conversation with a peer as chat bubbles.
Provides message input field and file attachment support.
"""

import logging
from typing import List, Optional
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QTextEdit, QFileDialog
)
from PySide6.QtGui import QFont, QTextCursor
from qfluentwidgets import (
    PushButton, PrimaryPushButton, FluentIcon,
    BodyLabel, CaptionLabel, StrongBodyLabel,
    ScrollArea, LineEdit, PlainTextEdit, isDarkTheme
)

from logic.chat_manager import ChatManager
from models.database import PrivateMessage
from ui.theme_utils import GhostTheme, get_title_styles


logger = logging.getLogger(__name__)


class MessageBubble(QFrame):
    """
    Chat bubble widget for displaying a single message.
    
    Displays:
    - User avatar
    - Message content
    - Timestamp
    - Encryption indicator
    - Sent/received styling with unique colors
    """
    
    def __init__(self, message: PrivateMessage, content: str, is_sent: bool, sender_id: str, avatar_path: Optional[str] = None, parent=None):
        """
        Initialize message bubble.
        
        Args:
            message: PrivateMessage object
            content: Decrypted message content
            is_sent: True if message was sent by us, False if received
            sender_id: Peer ID of sender for color generation
            avatar_path: Path to user avatar image
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.message = message
        self.content = content
        self.is_sent = is_sent
        self.sender_id = sender_id
        self.avatar_path = avatar_path
        
        self._setup_ui()
    
    def _get_user_color(self, peer_id: str) -> str:
        """Generate unique color for user based on peer ID."""
        import hashlib
        hash_val = int(hashlib.md5(peer_id.encode()).hexdigest()[:6], 16)
        hue = hash_val % 360
        return f"hsl({hue}, 65%, 55%)"
    
    def _setup_ui(self):
        """Set up the bubble UI with avatar."""
        from PySide6.QtGui import QPixmap
        
        # Main horizontal layout for avatar + bubble
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # Avatar
        avatar_label = QLabel()
        avatar_label.setFixedSize(36, 36)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.avatar_path and Path(self.avatar_path).exists():
            pixmap = QPixmap(self.avatar_path)
            if not pixmap.isNull():
                avatar_label.setPixmap(pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            avatar_label.setText("👤")
            avatar_label.setStyleSheet("font-size: 24px;")
        
        avatar_label.setStyleSheet(avatar_label.styleSheet() + "border-radius: 18px; background-color: rgba(255,255,255,0.1);")
        
        # Bubble content
        bubble_frame = QFrame()
        bubble_layout = QVBoxLayout(bubble_frame)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)
        
        # Message content
        content_label = BodyLabel(self.content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.PlainText)
        content_label.setFont(QFont("Segoe UI", 10))
        bubble_layout.addWidget(content_label)
        
        # Bottom row: timestamp and encryption indicator
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        
        # Encryption indicator
        encryption_label = CaptionLabel("🔒")
        encryption_label.setToolTip("End-to-end encrypted")
        bottom_layout.addWidget(encryption_label)
        
        # Timestamp
        timestamp_str = self._format_timestamp(self.message.created_at)
        timestamp_label = CaptionLabel(timestamp_str)
        bottom_layout.addWidget(timestamp_label)
        bottom_layout.addStretch()
        bubble_layout.addLayout(bottom_layout)
        
        # Style the bubble based on sent/received with unique colors
        if self.is_sent:
            main_layout.addStretch()
            main_layout.addWidget(bubble_frame)
            main_layout.addWidget(avatar_label)
            
            bubble_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {GhostTheme.get_purple_primary()};
                    border-radius: 16px;
                    border-top-right-radius: 4px;
                }}
            """)
            content_label.setStyleSheet("color: white;")
            timestamp_label.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        else:
            main_layout.addWidget(avatar_label)
            main_layout.addWidget(bubble_frame)
            main_layout.addStretch()
            
            user_color = self._get_user_color(self.sender_id)
            bubble_frame.setStyleSheet(f"""
                QFrame {{
                    background: {user_color};
                    border-radius: 16px;
                    border-top-left-radius: 4px;
                }}
            """)
            content_label.setStyleSheet("color: white;")
            timestamp_label.setStyleSheet("color: rgba(255, 255, 255, 0.9);")
        
        bubble_frame.setMaximumWidth(450)
        self.setStyleSheet("background: transparent; border: none;")
    
    def _format_timestamp(self, dt: datetime) -> str:
        """
        Format timestamp for display.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Formatted string (e.g., "14:30", "Yesterday 14:30")
        """
        now = datetime.utcnow()
        diff = now - dt
        
        time_str = dt.strftime("%H:%M")
        
        if diff.days == 0:
            return time_str
        elif diff.days == 1:
            return f"Yesterday {time_str}"
        elif diff.days < 7:
            return dt.strftime(f"%A {time_str}")
        else:
            return dt.strftime(f"%b %d {time_str}")


class ChatWidget(QWidget):
    """
    Chat widget for displaying and sending private messages.
    
    Displays messages as chat bubbles (sent/received) with timestamps
    and encryption indicators. Provides message input field and
    file attachment button.
    
    Signals:
        message_sent: Emitted when a message is sent
        file_attached: Emitted when a file is attached (file_path)
    """
    
    message_sent = Signal(str)  # message content
    file_attached = Signal(str)  # file path
    
    def __init__(self, chat_manager: ChatManager, peer_id: str, parent=None):
        """
        Initialize chat widget.
        
        Args:
            chat_manager: ChatManager instance
            peer_id: Peer ID of conversation partner
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.chat_manager = chat_manager
        self.peer_id = peer_id
        self.message_bubbles: List[MessageBubble] = []
        
        self._setup_ui()
        self._load_messages()
        
        logger.info(f"ChatWidget initialized for peer {peer_id[:8]}")
    
    def _setup_ui(self):
        """Set up the widget UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Set minimum height to maximize vertical space
        self.setMinimumHeight(600)
        
        # Header with peer info
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Messages scroll area - maximize height
        self.scroll_area = ScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {GhostTheme.get_background()};
                border: none;
            }}
        """)
        
        # Container for message bubbles
        self.messages_container = QWidget()
        self.messages_container.setStyleSheet(f"background-color: {GhostTheme.get_background()};")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(8)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.messages_container)
        main_layout.addWidget(self.scroll_area, stretch=1)
        
        # Message input area at bottom
        input_area = self._create_input_area()
        main_layout.addWidget(input_area)
    
    def _create_header(self) -> QWidget:
        """
        Create header widget with peer info.
        
        Returns:
            Header widget
        """
        header = QFrame()
        header.setFixedHeight(70)  # Increased height to accommodate larger title
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {GhostTheme.get_background()};
                border-bottom: 1px solid {GhostTheme.get_tertiary_background()};
            }}
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Peer name/ID - Apply standardized title style
        peer_display = self.peer_id[:16] + "..." if len(self.peer_id) > 16 else self.peer_id
        peer_label = StrongBodyLabel(peer_display)
        peer_label.setStyleSheet(get_title_styles())  # Apply standardized title style
        layout.addWidget(peer_label)
        
        layout.addStretch()
        
        # Encryption indicator
        encryption_label = BodyLabel("🔒 End-to-end encrypted")
        encryption_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 11px;")
        layout.addWidget(encryption_label)
        
        return header
    
    def _create_input_area(self) -> QWidget:
        """
        Create message input area with text field and buttons at bottom.
        
        Returns:
            Input area widget
        """
        input_container = QFrame()
        input_container.setFixedHeight(90)
        input_container.setStyleSheet(f"""
            QFrame {{
                background-color: {GhostTheme.get_background()};
                border-top: 2px solid {GhostTheme.get_tertiary_background()};
            }}
        """)
        
        layout = QHBoxLayout(input_container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # File attachment button
        self.attach_btn = PushButton(FluentIcon.ATTACH, "")
        self.attach_btn.setFixedSize(48, 48)
        self.attach_btn.setToolTip("Attach file")
        self.attach_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {GhostTheme.get_secondary_background()};
                border-radius: 24px;
                border: 2px solid {GhostTheme.get_tertiary_background()};
            }}
            QPushButton:hover {{
                background-color: {GhostTheme.get_purple_primary()};
                border-color: {GhostTheme.get_purple_primary()};
            }}
        """)
        self.attach_btn.clicked.connect(self._on_attach_file_clicked)
        layout.addWidget(self.attach_btn)
        
        # Message input field
        self.message_input = PlainTextEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setFixedHeight(58)
        self.message_input.setFocus()  # Auto-focus on input
        self.message_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.message_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {GhostTheme.get_secondary_background()};
                border: 2px solid {GhostTheme.get_tertiary_background()};
                border-radius: 8px;
                padding: 12px;
                color: {GhostTheme.get_text_primary()};
                font-size: 13px;
            }}
            QPlainTextEdit:focus {{
                border: 2px solid {GhostTheme.get_purple_primary()};
            }}
        """)
        layout.addWidget(self.message_input, stretch=1)
        
        # Send button
        self.send_btn = PrimaryPushButton(FluentIcon.SEND, "Send")
        self.send_btn.setFixedSize(90, 48)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {GhostTheme.get_purple_primary()};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {GhostTheme.get_purple_secondary()};
            }}
            QPushButton:pressed {{
                background-color: {GhostTheme.get_purple_tertiary()};
            }}
        """)
        self.send_btn.clicked.connect(self._on_send_clicked)
        layout.addWidget(self.send_btn)
        
        return input_container
    
    def _load_messages(self):
        """Load all messages in the conversation."""
        try:
            # Clear existing bubbles
            self._clear_messages()
            
            # Get conversation messages
            messages = self.chat_manager.get_conversation(self.peer_id)
            
            if not messages:
                logger.debug(f"No messages in conversation with {self.peer_id[:8]}")
                return
            
            # Create message bubbles
            local_peer_id = self.chat_manager.identity.peer_id
            
            for message in messages:
                # Determine if message was sent by us
                is_sent = (message.sender_peer_id == local_peer_id)
                
                # Decrypt message content
                try:
                    if is_sent:
                        # For sent messages, we need to handle differently
                        # Since we encrypted with recipient's key, we can't decrypt
                        # In a real implementation, we'd store plaintext locally
                        content = "[Sent message]"
                    else:
                        # Decrypt received message
                        content = self.chat_manager.decrypt_message(message)
                except Exception as e:
                    logger.error(f"Failed to decrypt message {message.id[:8]}: {e}")
                    content = "[Decryption failed]"
                
                # Get avatar path
                avatar_path = None
                try:
                    peer_info = self.chat_manager.db.get_peer_info(message.sender_peer_id)
                    if peer_info and hasattr(peer_info, 'avatar_path'):
                        avatar_path = peer_info.avatar_path
                except Exception:
                    pass
                
                # Create bubble with avatar
                bubble = MessageBubble(message, content, is_sent, message.sender_peer_id, avatar_path)
                self.messages_layout.addWidget(bubble)
                self.message_bubbles.append(bubble)
            
            # Scroll to bottom
            self._scroll_to_bottom()
            
            # Mark messages as read
            self._mark_messages_read()
            
            logger.info(f"Loaded {len(self.message_bubbles)} messages")
            
        except Exception as e:
            logger.error(f"Failed to load messages: {e}")
    
    def _clear_messages(self):
        """Clear all message bubbles."""
        for bubble in self.message_bubbles:
            bubble.deleteLater()
        
        self.message_bubbles.clear()
        
        # Clear layout
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    widget = item.layout().takeAt(0).widget()
                    if widget:
                        widget.deleteLater()
                item.layout().deleteLater()
    
    def _scroll_to_bottom(self):
        """Scroll to the bottom of the messages area."""
        # Schedule scroll after layout is updated
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
    
    def _mark_messages_read(self):
        """Mark all received messages as read."""
        try:
            messages = self.chat_manager.get_conversation(self.peer_id)
            local_peer_id = self.chat_manager.identity.peer_id
            
            for message in messages:
                # Only mark received messages
                if message.sender_peer_id != local_peer_id and message.read_at is None:
                    self.chat_manager.mark_as_read(message.id)
            
        except Exception as e:
            logger.error(f"Failed to mark messages as read: {e}")
    
    def _on_send_clicked(self):
        """Handle send button click."""
        try:
            # Get message content
            content = self.message_input.toPlainText().strip()
            
            if not content:
                logger.debug("Empty message, not sending")
                return
            
            # Validate length
            if len(content) > 10000:
                logger.warning("Message too long")
                # TODO: Show error notification
                return
            
            # Clear input field
            self.message_input.clear()
            
            # Emit signal (actual sending will be handled by parent)
            self.message_sent.emit(content)
            
            logger.debug(f"Message send requested: {len(content)} characters")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    def _on_attach_file_clicked(self):
        """Handle attach file button click."""
        try:
            # Open file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File to Attach",
                "",
                "All Files (*.*)"
            )
            
            if file_path:
                logger.debug(f"File selected: {file_path}")
                self.file_attached.emit(file_path)
            
        except Exception as e:
            logger.error(f"Failed to attach file: {e}")
    
    def add_message(self, message: PrivateMessage, content: str):
        """
        Add a new message to the chat display.
        
        Args:
            message: PrivateMessage object
            content: Decrypted message content
        """
        try:
            # Determine if message was sent by us
            local_peer_id = self.chat_manager.identity.peer_id
            is_sent = (message.sender_peer_id == local_peer_id)
            
            # Get avatar path
            avatar_path = None
            try:
                peer_info = self.chat_manager.db.get_peer_info(message.sender_peer_id)
                if peer_info and hasattr(peer_info, 'avatar_path'):
                    avatar_path = peer_info.avatar_path
            except Exception:
                pass
            
            # Create bubble with avatar
            bubble = MessageBubble(message, content, is_sent, message.sender_peer_id, avatar_path)
            self.messages_layout.addWidget(bubble)
            self.message_bubbles.append(bubble)
            
            # Scroll to bottom
            self._scroll_to_bottom()
            
            logger.debug(f"Added message bubble: {message.id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
    
    def refresh(self):
        """Refresh the message display."""
        logger.debug("Refreshing chat widget")
        self._load_messages()
