"""
Board Detail Page - Shows board info and threads/messages
"""

import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from PySide6.QtGui import QPixmap
from qfluentwidgets import (
    ScrollArea, CardWidget, PrimaryPushButton, PushButton,
    FluentIcon, MessageBox, LineEdit, TextEdit, BodyLabel,
    SubtitleLabel, CaptionLabel, StrongBodyLabel, TitleLabel
)

from ui.theme_utils import GhostTheme, get_page_margins, get_card_margins, SPACING_SMALL, SPACING_MEDIUM
from models.database import Board, Thread
from core.db_manager import DBManager

logger = logging.getLogger(__name__)


class ThreadCard(CardWidget):
    """Card displaying a thread (message) on the board."""
    
    thread_clicked = Signal(str)  # thread_id
    delete_clicked = Signal(str)  # thread_id
    
    def __init__(self, thread: Thread, author_name: str, message_preview: str = "",
                 has_attachments: bool = False, can_delete: bool = False, parent=None):
        super().__init__(parent)
        self.thread = thread
        self.author_name = author_name
        self.message_preview = message_preview
        self.has_attachments = has_attachments
        self.can_delete = can_delete
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        self.setStyleSheet(f"""
            CardWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {GhostTheme.get_secondary_background()},
                    stop:1 {GhostTheme.get_tertiary_background()});
                border-left: 3px solid {GhostTheme.get_purple_primary()};
                border-radius: 6px;
            }}
            CardWidget:hover {{
                border-left: 3px solid {GhostTheme.get_purple_secondary()};
                background: {GhostTheme.get_secondary_background()};
            }}
        """)
        
        # Top row: Title with file indicator and delete button
        top_layout = QHBoxLayout()
        
        # Title with file indicator
        title_container = QHBoxLayout()
        title_container.setSpacing(8)
        
        if self.has_attachments:
            file_icon = BodyLabel("📎")
            file_icon.setStyleSheet(f"color: {GhostTheme.get_purple_secondary()}; font-size: 16px;")
            title_container.addWidget(file_icon)
        
        title_label = StrongBodyLabel(self.thread.title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()}; font-size: 15px; font-weight: 600;")
        title_container.addWidget(title_label, 1)
        
        top_layout.addLayout(title_container, 1)
        
        layout.addLayout(top_layout)
        
        # Message preview (first 50 chars)
        if self.message_preview:
            preview_label = BodyLabel(self.message_preview)
            preview_label.setWordWrap(True)
            preview_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()}; font-size: 13px; margin-top: 4px;")
            layout.addWidget(preview_label)
        
        # Delete button (only if user can delete)
        if self.can_delete:
            delete_btn = PushButton(FluentIcon.DELETE, "")
            delete_btn.setFixedSize(32, 32)
            delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.thread.id))
            delete_btn.setStyleSheet(f"""
                PushButton {{
                    background-color: transparent;
                    border: 1px solid {GhostTheme.get_red_accent()};
                    border-radius: 4px;
                }}
                PushButton:hover {{
                    background-color: {GhostTheme.get_red_accent()};
                }}
            """)
            top_layout.addWidget(delete_btn)
        
        # Metadata row
        meta_layout = QHBoxLayout()
        author_label = CaptionLabel(f"👤 {self.author_name}")
        author_label.setStyleSheet(f"color: {GhostTheme.get_purple_secondary()}; font-size: 12px;")
        date_label = CaptionLabel(f"🕒 {self.thread.created_at.strftime('%Y-%m-%d %H:%M')}")
        date_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 12px;")
        meta_layout.addWidget(author_label)
        meta_layout.addStretch()
        meta_layout.addWidget(date_label)
        layout.addLayout(meta_layout)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.thread_clicked.emit(self.thread.id)
        super().mousePressEvent(event)


class NewThreadDialog(MessageBox):
    """Dialog for creating a new thread/message."""
    
    def __init__(self, username: str, parent=None):
        super().__init__("New Message", "", parent)
        self.username = username
        self.title_text = ""
        self.content_text = ""
        self.attachment_paths = []
        self._setup_ui()
        self.widget.setFixedWidth(600)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        
        # Username (read-only)
        layout.addWidget(StrongBodyLabel("Username"))
        self.username_input = LineEdit()
        self.username_input.setText(self.username)
        self.username_input.setReadOnly(True)
        layout.addWidget(self.username_input)
        
        # Title
        layout.addWidget(StrongBodyLabel("Title"))
        self.title_input = LineEdit()
        self.title_input.setPlaceholderText("Enter message title (3-200 characters)")
        layout.addWidget(self.title_input)
        
        # Content
        layout.addWidget(StrongBodyLabel("Content"))
        self.content_input = TextEdit()
        self.content_input.setPlaceholderText("Enter message content (1-10000 characters)")
        self.content_input.setMinimumHeight(200)
        layout.addWidget(self.content_input)
        
        # Attachments
        attach_layout = QHBoxLayout()
        attach_layout.addWidget(StrongBodyLabel("Attachments"))
        attach_layout.addStretch()
        self.attach_btn = PushButton(FluentIcon.FOLDER_ADD, "Add Files")
        self.attach_btn.clicked.connect(self._on_add_files)
        attach_layout.addWidget(self.attach_btn)
        layout.addLayout(attach_layout)
        
        self.attach_label = CaptionLabel("No files attached")
        self.attach_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        layout.addWidget(self.attach_label)
        
        self.textLayout.addLayout(layout)
        
        self.yesButton.setText("Post")
        self.cancelButton.setText("Cancel")
    
    def _on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self.attachment_paths = files
            self.attach_label.setText(f"{len(files)} file(s) selected")
    
    def validate(self):
        self.title_text = self.title_input.text().strip()
        self.content_text = self.content_input.toPlainText().strip()
        
        if not self.title_text or len(self.title_text) < 3:
            return False
        if not self.content_text or len(self.content_text) < 1:
            return False
        return True


class BoardDetailPage(QWidget):
    """Page showing board details and threads."""
    
    back_clicked = Signal()
    
    def __init__(self, board: Board, db_manager, thread_manager, profile, parent=None):
        super().__init__(parent)
        self.board = board
        self.db = db_manager
        self.thread_manager = thread_manager
        self.profile = profile
        self._setup_ui()
        self._load_threads()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        margins = get_page_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(SPACING_MEDIUM)
        
        # Header with back button and title
        header_layout = QHBoxLayout()
        self.back_btn = PushButton(FluentIcon.RETURN, "Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(self.back_btn)
        header_layout.addStretch()
        
        self.add_msg_btn = PrimaryPushButton(FluentIcon.ADD, "Add Message")
        self.add_msg_btn.clicked.connect(self._on_add_message)
        header_layout.addWidget(self.add_msg_btn)
        layout.addLayout(header_layout)
        
        # Board info card
        info_card = CardWidget()
        info_card_layout = QHBoxLayout(info_card)
        info_card_layout.setSpacing(16)
        
        # Board image or default icon (left side) - ALWAYS show
        from PySide6.QtWidgets import QLabel as QtLabel
        img_label = QtLabel()
        img_label.setFixedSize(120, 120)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        image_loaded = False
        if self.board.image_path:
            image_path = Path(self.board.image_path)
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                if not pixmap.isNull():
                    img_label.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    img_label.setStyleSheet("border-radius: 8px; background-color: transparent;")
                    image_loaded = True
        
        if not image_loaded:
            # Default icon if no image or image fails to load
            img_label.setText("📝")
            img_label.setStyleSheet(f"font-size: 64px; border-radius: 8px; background-color: {GhostTheme.get_tertiary_background()};")
        
        info_card_layout.addWidget(img_label)
        
        # Board info (right side) - no hover effects
        info_layout = QVBoxLayout()
        info_layout.setSpacing(SPACING_SMALL)
        
        # Board name
        name_label = TitleLabel(self.board.name)
        name_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()}; font-size: 24px; font-weight: bold;")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(name_label)
        
        # Description
        if self.board.description:
            desc_label = BodyLabel(self.board.description)
            desc_label.setWordWrap(True)
            desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            desc_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()}; font-size: 14px; line-height: 1.5; margin-top: 8px;")
            info_layout.addWidget(desc_label)
        
        # Welcome message
        if self.board.welcome_message:
            welcome_label = BodyLabel(f"💬 {self.board.welcome_message}")
            welcome_label.setWordWrap(True)
            welcome_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            welcome_label.setStyleSheet(f"color: {GhostTheme.get_purple_secondary()}; font-size: 13px; font-style: italic; margin-top: 8px; padding: 8px; background-color: {GhostTheme.get_tertiary_background()}; border-radius: 4px;")
            info_layout.addWidget(welcome_label)
        
        info_layout.addStretch()
        info_card_layout.addLayout(info_layout, 1)
        
        # Remove hover cursor from info card
        info_card.setCursor(Qt.CursorShape.ArrowCursor)
        
        layout.addWidget(info_card)
        
        # Messages section
        msg_header = SubtitleLabel("Messages")
        msg_header.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        layout.addWidget(msg_header)
        
        # Scrollable thread list
        self.scroll = ScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(SPACING_SMALL)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll, 1)
    
    def _load_threads(self):
        """Load threads for this board ordered by creation date (latest first)."""
        try:
            logger.info(f"Loading threads for board: {self.board.name} (ID: {self.board.id})")
            
            # Clear existing
            while self.scroll_layout.count():
                item = self.scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            threads = self.db.get_threads_for_board(self.board.id)
            logger.info(f"Found {len(threads)} threads for board {self.board.id}")
            
            if not threads:
                no_msg = BodyLabel("No messages yet. Be the first to post!")
                no_msg.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; padding: 40px; font-size: 14px;")
                no_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.scroll_layout.addWidget(no_msg)
            else:
                # Sort by created_at descending (latest first)
                threads.sort(key=lambda t: t.created_at, reverse=True)
                
                # Get current user's peer_id
                current_user_id = self.profile.peer_id if self.profile and hasattr(self.profile, 'peer_id') else None
                
                for thread in threads:
                    author_name = thread.creator_peer_id[:8]
                    peer_info = self.db.get_peer_info(thread.creator_peer_id)
                    if peer_info and peer_info.display_name:
                        author_name = peer_info.display_name
                    
                    # Get first post content for preview
                    posts = self.db.get_posts_for_thread(thread.id)
                    message_preview = ""
                    has_attachments = False
                    
                    if posts:
                        # Get first 50 chars of first post
                        first_post = posts[0]
                        message_preview = first_post.content[:50]
                        if len(first_post.content) > 50:
                            message_preview += "..."
                        
                        # Check if any post has attachments
                        for post in posts:
                            attachments = self.db.get_attachments_for_post(post.id)
                            if attachments:
                                has_attachments = True
                                break
                    
                    # Check if current user can delete this thread
                    can_delete = current_user_id and thread.creator_peer_id == current_user_id
                    
                    card = ThreadCard(thread, author_name, message_preview, has_attachments, can_delete)
                    card.thread_clicked.connect(self._on_thread_clicked)
                    card.delete_clicked.connect(self._on_delete_thread)
                    self.scroll_layout.addWidget(card)
            
            self.scroll_layout.addStretch()
            
        except Exception as e:
            logger.error(f"Failed to load threads: {e}")
    
    def _on_add_message(self):
        """Show dialog to create new message."""
        username = self.profile.display_name if self.profile else "Anonymous"
        dialog = NewThreadDialog(username, self)
        
        if dialog.exec() and dialog.validate():
            try:
                thread = self.thread_manager.create_thread(
                    board_id=self.board.id,
                    title=dialog.title_text,
                    initial_post_content=dialog.content_text
                )
                logger.info(f"Created thread: {thread.title}")
                # Refresh the thread list to show new message
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._load_threads)
            except Exception as e:
                logger.error(f"Failed to create thread: {e}")
    
    def _on_thread_clicked(self, thread_id: str):
        """Handle thread click - open message detail view."""
        try:
            # Get thread
            threads = self.db.get_threads_for_board(self.board.id)
            thread = next((t for t in threads if t.id == thread_id), None)
            if not thread:
                return
            
            # Create and show message detail page
            from ui.message_detail_page import MessageDetailPage
            detail_page = MessageDetailPage(thread, self.db, self)
            detail_page.back_clicked.connect(lambda: self._close_detail_page(detail_page))
            
            # Add to parent's stack if available
            if self.parent() and hasattr(self.parent(), 'stackedWidget'):
                parent = self.parent()
                parent.stackedWidget.addWidget(detail_page)
                parent.stackedWidget.setCurrentWidget(detail_page)
            
            logger.info(f"Opened message detail: {thread.title}")
            
        except Exception as e:
            logger.error(f"Failed to open message detail: {e}")
    
    def _close_detail_page(self, detail_page):
        """Close message detail page and return to board view."""
        try:
            if self.parent() and hasattr(self.parent(), 'stackedWidget'):
                parent = self.parent()
                parent.stackedWidget.setCurrentWidget(self)
                parent.stackedWidget.removeWidget(detail_page)
                detail_page.deleteLater()
        except Exception as e:
            logger.error(f"Failed to close detail page: {e}")
    
    def _on_delete_thread(self, thread_id: str):
        """Handle delete thread request."""
        try:
            # Get thread info for confirmation
            threads = self.db.get_threads_for_board(self.board.id)
            thread = next((t for t in threads if t.id == thread_id), None)
            if not thread:
                return
            
            # Show confirmation dialog
            msg_box = MessageBox(
                "Delete Message",
                f"Are you sure you want to delete '{thread.title}'?\n\nThis will permanently delete the message and all its content.",
                self
            )
            
            if msg_box.exec():
                # Delete thread from database (cascade deletes posts)
                with self.db.get_session() as session:
                    thread_obj = session.query(Thread).filter(Thread.id == thread_id).first()
                    if thread_obj:
                        session.delete(thread_obj)
                
                logger.info(f"Deleted thread: {thread.title}")
                
                # Refresh thread list
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._load_threads)
                
        except Exception as e:
            logger.error(f"Failed to delete thread: {e}")
