"""
Post View Page for P2P Encrypted BBS

Displays posts in a selected thread with rich text formatting.
Shows author peer ID, timestamp, and signature verification status.
Displays attachments with download buttons.
Provides post composer with markdown editor and file attachment support.
"""

import logging
from typing import Optional
from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QFileDialog
)
from qfluentwidgets import (
    ScrollArea,
    PushButton,
    FluentIcon,
    MessageBox,
    TextEdit,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    StrongBodyLabel,
    CardWidget,
    InfoBar,
    InfoBarPosition
)

from ui.theme_utils import (
    GhostTheme,
    get_metadata_styles,
    get_empty_state_styles,
    get_verified_styles,
    get_unverified_styles,
    get_error_text_styles,
    get_page_margins,
    get_card_margins,
    SPACING_SMALL,
    SPACING_MEDIUM,
)
from ui.hover_card import apply_hover_glow
from logic.thread_manager import ThreadManager, ThreadManagerError
from models.database import Thread, Post


logger = logging.getLogger(__name__)


class PostCard(CardWidget):
    """
    Card widget displaying a single post.
    
    Shows post content, author information, timestamp, signature verification,
    and attachments with download buttons.
    """
    
    reply_clicked = Signal(str)  # Emits post_id when reply is clicked
    
    def __init__(
        self,
        post: Post,
        thread_manager: ThreadManager,
        is_verified: bool = False,
        parent=None
    ):
        """
        Initialize post card.
        
        Args:
            post: Post object to display
            thread_manager: ThreadManager instance for verification
            is_verified: Whether signature has been verified
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.post = post
        self.thread_manager = thread_manager
        self.is_verified = is_verified
        
        self._setup_ui()
        # Apply hover glow for consistent UI
        apply_hover_glow(self, color=GhostTheme.get_purple_primary())
    
    def _setup_ui(self):
        """Set up card UI."""
        # Main layout
        layout = QVBoxLayout(self)
        margins = get_card_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(SPACING_MEDIUM - 4)
        
        # Header row with author and timestamp
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Author
        author_label = StrongBodyLabel(f"@{self.post.author_peer_id[:12]}...")
        header_layout.addWidget(author_label)

        # Signature verification indicator - using centralized theme
        if self.is_verified:
            verified_label = CaptionLabel("✓ Verified")
            verified_label.setStyleSheet(f"color: {GhostTheme.get_success_color()};")
        else:
            verified_label = CaptionLabel("⚠ Unverified")
            verified_label.setStyleSheet(f"color: {GhostTheme.get_warning_color()};")
        header_layout.addWidget(verified_label)

        header_layout.addStretch()

        # Timestamp
        timestamp_str = self.post.created_at.strftime("%Y-%m-%d %H:%M:%S")
        time_label = CaptionLabel(timestamp_str)
        time_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # Post content
        content_label = BodyLabel(self.post.content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(content_label)

        # Attachments section (if any)
        if self.post.attachments:
            attachments_layout = QVBoxLayout()
            attachments_layout.setSpacing(8)

            attachments_label = CaptionLabel(f"📎 {len(self.post.attachments)} attachment(s)")
            attachments_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
            attachments_layout.addWidget(attachments_label)

            for attachment in self.post.attachments:
                attachment_row = QHBoxLayout()

                # Filename
                filename_label = BodyLabel(attachment.filename)
                attachment_row.addWidget(filename_label)

                # File size
                size_kb = attachment.file_size / 1024
                size_label = CaptionLabel(f"({size_kb:.1f} KB)")
                size_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
                attachment_row.addWidget(size_label)
                
                attachment_row.addStretch()
                
                # Download button
                download_btn = PushButton(FluentIcon.DOWNLOAD, "Download")
                download_btn.clicked.connect(
                    lambda checked, att=attachment: self._on_download_attachment(att)
                )
                attachment_row.addWidget(download_btn)
                
                attachments_layout.addLayout(attachment_row)
            
            layout.addLayout(attachments_layout)
        
        # Footer with reply button
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        
        # Reply button
        reply_btn = PushButton(FluentIcon.COMMENT, "Reply")
        reply_btn.clicked.connect(self._on_reply_clicked)
        footer_layout.addWidget(reply_btn)
        
        layout.addLayout(footer_layout)
        
        # Set minimum height
        self.setMinimumHeight(120)
    
    def _on_reply_clicked(self):
        """Handle reply button click."""
        self.reply_clicked.emit(self.post.id)
    
    def _on_download_attachment(self, attachment):
        """
        Handle attachment download.
        
        Args:
            attachment: Attachment object to download
        """
        try:
            # Ask user where to save
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Attachment",
                attachment.filename,
                "All Files (*.*)"
            )
            
            if file_path:
                # Write decrypted data to file
                with open(file_path, 'wb') as f:
                    f.write(attachment.encrypted_data)
                
                logger.info(f"Saved attachment {attachment.filename} to {file_path}")
                
                # Show success notification
                InfoBar.success(
                    title="Download Complete",
                    content=f"Saved {attachment.filename}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self.window()
                )
        
        except Exception as e:
            logger.error(f"Failed to download attachment: {e}")
            InfoBar.error(
                title="Download Failed",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self.window()
            )



class PostComposer(CardWidget):
    """
    Widget for composing new posts.
    
    Provides text editor with markdown support and file attachment button.
    """
    
    post_submitted = Signal(str, str)  # Emits (content, parent_post_id or None)
    
    def __init__(self, parent=None):
        """
        Initialize post composer.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.parent_post_id: Optional[str] = None
        self.attached_file_path: Optional[str] = None
        
        self._setup_ui()
        # Apply hover glow so composer also has the same hover effect
        apply_hover_glow(self, color=GhostTheme.get_purple_primary())
    
    def _setup_ui(self):
        """Set up composer UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_label = StrongBodyLabel("Write a post")
        layout.addWidget(header_label)
        
        # Reply indicator (hidden by default)
        self.reply_indicator = BodyLabel("")
        self.reply_indicator.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-style: italic;")
        self.reply_indicator.hide()
        layout.addWidget(self.reply_indicator)
        
        # Text editor
        self.text_editor = TextEdit()
        self.text_editor.setPlaceholderText("Write your post here... (Markdown supported)")
        self.text_editor.setMinimumHeight(150)
        layout.addWidget(self.text_editor)
        
        # Character count
        self.char_count_label = CaptionLabel("0 / 10000 characters")
        self.char_count_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        self.text_editor.textChanged.connect(self._update_char_count)
        layout.addWidget(self.char_count_label)

        # Attachment indicator
        self.attachment_label = BodyLabel("")
        self.attachment_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        self.attachment_label.hide()
        layout.addWidget(self.attachment_label)
        
        # Button row
        button_layout = QHBoxLayout()
        
        # Attach file button
        self.attach_btn = PushButton(FluentIcon.ATTACH, "Attach File")
        self.attach_btn.clicked.connect(self._on_attach_file_clicked)
        button_layout.addWidget(self.attach_btn)
        
        button_layout.addStretch()
        
        # Cancel button (for replies)
        self.cancel_btn = PushButton("Cancel Reply")
        self.cancel_btn.clicked.connect(self._on_cancel_reply)
        self.cancel_btn.hide()
        button_layout.addWidget(self.cancel_btn)
        
        # Submit button
        self.submit_btn = PushButton(FluentIcon.SEND, "Post")
        self.submit_btn.clicked.connect(self._on_submit_clicked)
        button_layout.addWidget(self.submit_btn)
        
        layout.addLayout(button_layout)
    
    def _update_char_count(self):
        """Update character count label."""
        text = self.text_editor.toPlainText()
        count = len(text)
        self.char_count_label.setText(f"{count} / 10000 characters")
        
        # Change color if over limit - using centralized theme
        if count > 10000:
            self.char_count_label.setStyleSheet(f"color: {GhostTheme.get_error_color()};")
        else:
            self.char_count_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
    
    def set_reply_to(self, post_id: str, author_peer_id: str):
        """
        Set the post being replied to.
        
        Args:
            post_id: ID of post being replied to
            author_peer_id: Author of the post being replied to
        """
        self.parent_post_id = post_id
        self.reply_indicator.setText(f"Replying to @{author_peer_id[:12]}...")
        self.reply_indicator.show()
        self.cancel_btn.show()
        
        # Focus text editor
        self.text_editor.setFocus()
    
    def clear_reply(self):
        """Clear reply state."""
        self.parent_post_id = None
        self.reply_indicator.hide()
        self.cancel_btn.hide()
    
    def _on_cancel_reply(self):
        """Handle cancel reply button click."""
        self.clear_reply()
    
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
                # Check file size (max 50MB)
                import os
                file_size = os.path.getsize(file_path)
                max_size = 50 * 1024 * 1024  # 50 MB
                
                if file_size > max_size:
                    InfoBar.error(
                        title="File Too Large",
                        content="File must be less than 50 MB",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=5000,
                        parent=self.window()
                    )
                    return
                
                self.attached_file_path = file_path
                filename = os.path.basename(file_path)
                size_mb = file_size / (1024 * 1024)
                
                self.attachment_label.setText(f"📎 {filename} ({size_mb:.2f} MB)")
                self.attachment_label.show()
                
                logger.info(f"Attached file: {filename}")
        
        except Exception as e:
            logger.error(f"Failed to attach file: {e}")
            InfoBar.error(
                title="Attachment Failed",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self.window()
            )
    
    def _on_submit_clicked(self):
        """Handle submit button click."""
        content = self.text_editor.toPlainText().strip()
        
        # Validate content
        if not content:
            InfoBar.warning(
                title="Empty Post",
                content="Please write something before posting",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self.window()
            )
            return
        
        if len(content) > 10000:
            InfoBar.error(
                title="Post Too Long",
                content="Post must be 10000 characters or less",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self.window()
            )
            return
        
        # Emit signal
        self.post_submitted.emit(content, self.parent_post_id)
        
        # Clear editor
        self.text_editor.clear()
        self.clear_reply()
        self.attached_file_path = None
        self.attachment_label.hide()



class PostViewPage(ScrollArea):
    """
    Page displaying posts in a thread.
    
    Shows posts as card widgets with author info, content, and attachments.
    Provides post composer at bottom for creating new posts and replies.
    Verifies post signatures and displays verification status.
    
    Signals:
        back_clicked: Emitted when back button is clicked
        post_created: Emitted when a new post is created (post)
    """
    
    back_clicked = Signal()
    post_created = Signal(Post)
    
    def __init__(
        self,
        thread_manager: ThreadManager,
        parent=None
    ):
        """
        Initialize post view page.
        
        Args:
            thread_manager: ThreadManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.thread_manager = thread_manager
        self.current_thread: Optional[Thread] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.info("PostViewPage initialized")
    
    def _setup_ui(self):
        """Set up page UI."""
        # Create main widget
        self.view = QWidget()
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        margins = get_page_margins()
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(SPACING_MEDIUM)
        
        # Header with back button and thread title
        header_layout = QHBoxLayout()
        
        # Back button
        self.back_button = PushButton(FluentIcon.RETURN, "Back to Threads")
        self.back_button.clicked.connect(self._on_back_clicked)
        header_layout.addWidget(self.back_button)
        
        # Thread title
        self.title_label = SubtitleLabel("Thread")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.main_layout.addLayout(header_layout)
        
        # Thread info
        self.thread_info_label = BodyLabel("")
        self.thread_info_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        self.main_layout.addWidget(self.thread_info_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(separator)
        
        # Posts container
        self.posts_layout = QVBoxLayout()
        self.posts_layout.setSpacing(12)
        self.main_layout.addLayout(self.posts_layout)
        
        # Add stretch before composer
        self.main_layout.addStretch()
        
        # Post composer at bottom
        self.composer = PostComposer()
        self.composer.post_submitted.connect(self._on_post_submitted)
        self.main_layout.addWidget(self.composer)
        
        # Style
        self.setObjectName("postViewPage")
    
    def set_thread(self, thread_id: str):
        """
        Set the current thread and load its posts.
        
        Args:
            thread_id: Thread identifier
        """
        try:
            # Get thread from database
            # We need to query through the database manager
            # For now, we'll create a temporary thread object
            # In production, we'd have a method to get thread by ID
            
            # Load posts to verify thread exists
            posts = self.thread_manager.get_thread_posts(thread_id)
            
            if not posts:
                logger.warning(f"No posts found for thread {thread_id[:8]}")
                # Still allow viewing empty thread
            
            # Create a minimal thread object for display
            # In production, we'd fetch the full thread from database
            from models.database import Thread
            self.current_thread = Thread(
                id=thread_id,
                board_id="",  # Will be populated from first post if available
                title="Thread",  # Will be updated if we can get it
                creator_peer_id="",
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b""
            )
            
            # Try to get thread details from database
            # This is a workaround - in production we'd have get_thread_by_id
            try:
                # Get thread info from posts
                if posts:
                    first_post = posts[0]
                    self.current_thread.creator_peer_id = first_post.author_peer_id
                    self.current_thread.created_at = first_post.created_at
            except Exception as e:
                logger.warning(f"Could not get thread details: {e}")
            
            # Update UI
            self.title_label.setText(f"Thread: {thread_id[:12]}...")
            
            # Update thread info
            post_count = len(posts)
            self.thread_info_label.setText(
                f"{post_count} post(s) • Created by @{self.current_thread.creator_peer_id[:12]}..."
            )
            
            # Load posts
            self.refresh_posts()
            
            logger.info(f"Set thread to: {thread_id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to set thread: {e}")
            self._show_error("Error", f"Failed to load thread: {e}")
    
    def refresh_posts(self):
        """Refresh the list of posts for current thread."""
        if not self.current_thread:
            return
        
        try:
            # Clear existing posts
            self._clear_posts()
            
            # Get posts
            posts = self.thread_manager.get_thread_posts(self.current_thread.id)
            
            if not posts:
                # Show empty state
                empty_label = BodyLabel("No posts yet. Be the first to post!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; padding: 40px;")
                self.posts_layout.addWidget(empty_label)
            else:
                # Add post cards
                for post in posts:
                    # Verify signature
                    is_verified = self.thread_manager.verify_post_signature(post)
                    
                    # Create post card
                    card = PostCard(post, self.thread_manager, is_verified)
                    card.reply_clicked.connect(self._on_reply_to_post)
                    self.posts_layout.addWidget(card)
            
            logger.debug(f"Refreshed post list: {len(posts)} posts")
            
        except Exception as e:
            logger.error(f"Failed to refresh posts: {e}")
            self._show_error("Error", f"Failed to load posts: {e}")
    
    def _clear_posts(self):
        """Clear all post widgets from layout."""
        while self.posts_layout.count():
            item = self.posts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _on_reply_to_post(self, post_id: str):
        """
        Handle reply button click on a post.
        
        Args:
            post_id: ID of post being replied to
        """
        try:
            # Get post to show author
            post = self.thread_manager.get_post_by_id(post_id)
            if post:
                self.composer.set_reply_to(post_id, post.author_peer_id)
                
                # Scroll to composer
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().maximum()
                )
        
        except Exception as e:
            logger.error(f"Failed to set reply: {e}")
    
    def _on_post_submitted(self, content: str, parent_post_id: Optional[str]):
        """
        Handle post submission from composer.
        
        Args:
            content: Post content
            parent_post_id: Optional parent post ID for replies
        """
        if not self.current_thread:
            return
        
        try:
            # Create post
            post = self.thread_manager.add_post_to_thread(
                thread_id=self.current_thread.id,
                content=content,
                parent_post_id=parent_post_id
            )
            
            # Refresh posts
            self.refresh_posts()
            
            # Emit signal
            self.post_created.emit(post)
            
            # Show success notification
            InfoBar.success(
                title="Post Created",
                content="Your post has been published",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self.window()
            )
            
            logger.info(f"Created post in thread {self.current_thread.id[:8]}")
            
        except ValueError as e:
            logger.error(f"Invalid post input: {e}")
            self._show_error("Invalid Input", str(e))
        except ThreadManagerError as e:
            logger.error(f"Failed to create post: {e}")
            self._show_error("Post Failed", str(e))
        except Exception as e:
            logger.error(f"Unexpected error creating post: {e}")
            self._show_error("Error", "An unexpected error occurred")
    
    def _on_back_clicked(self):
        """Handle back button click."""
        logger.info("Back to threads clicked")
        self.back_clicked.emit()
    
    def _show_error(self, title: str, message: str):
        """
        Show error message box.
        
        Args:
            title: Error title
            message: Error message
        """
        msg_box = MessageBox(title, message, self)
        msg_box.exec()
