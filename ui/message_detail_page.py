"""
Message Detail Page - Shows full message content with attachments
"""

import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPixmap
from qfluentwidgets import (
    ScrollArea, CardWidget, PushButton, FluentIcon,
    BodyLabel, SubtitleLabel, CaptionLabel, StrongBodyLabel, TitleLabel
)

from ui.theme_utils import GhostTheme, get_page_margins, SPACING_SMALL, SPACING_MEDIUM
from models.database import Thread

logger = logging.getLogger(__name__)


class MessageDetailPage(QWidget):
    """Page showing full message content and attachments."""
    
    back_clicked = Signal()
    
    def __init__(self, thread: Thread, db_manager, parent=None):
        super().__init__(parent)
        self.thread = thread
        self.db = db_manager
        self._setup_ui()
        self._load_content()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        margins = get_page_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(SPACING_MEDIUM)
        
        # Header with back button
        header_layout = QHBoxLayout()
        self.back_btn = PushButton(FluentIcon.RETURN, "Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(self.back_btn)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Scrollable content area
        self.scroll = ScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(SPACING_MEDIUM)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll, 1)
    
    def _load_content(self):
        """Load message content and attachments."""
        try:
            # Clear existing
            while self.scroll_layout.count():
                item = self.scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Message header card
            header_card = CardWidget()
            header_layout = QVBoxLayout(header_card)
            header_layout.setSpacing(SPACING_SMALL)
            
            # Title
            title_label = TitleLabel(self.thread.title)
            title_label.setWordWrap(True)
            title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()}; font-size: 20px; font-weight: bold;")
            header_layout.addWidget(title_label)
            
            # Author and date
            author_name = self.thread.creator_peer_id[:8]
            peer_info = self.db.get_peer_info(self.thread.creator_peer_id)
            if peer_info and peer_info.display_name:
                author_name = peer_info.display_name
            
            meta_layout = QHBoxLayout()
            author_label = BodyLabel(f"👤 {author_name}")
            author_label.setStyleSheet(f"color: {GhostTheme.get_purple_secondary()}; font-size: 13px;")
            date_label = BodyLabel(f"🕒 {self.thread.created_at.strftime('%Y-%m-%d %H:%M')}")
            date_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 13px;")
            meta_layout.addWidget(author_label)
            meta_layout.addStretch()
            meta_layout.addWidget(date_label)
            header_layout.addLayout(meta_layout)
            
            self.scroll_layout.addWidget(header_card)
            
            # Get all posts for this thread
            posts = self.db.get_posts_for_thread(self.thread.id)
            
            for post in posts:
                # Post content card
                post_card = CardWidget()
                post_layout = QVBoxLayout(post_card)
                post_layout.setSpacing(SPACING_SMALL)
                
                post_card.setStyleSheet(f"""
                    CardWidget {{
                        background-color: {GhostTheme.get_secondary_background()};
                        border-left: 3px solid {GhostTheme.get_purple_tertiary()};
                        border-radius: 6px;
                    }}
                """)
                
                # Post content
                content_label = BodyLabel(post.content)
                content_label.setWordWrap(True)
                content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                content_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()}; font-size: 14px; line-height: 1.6;")
                post_layout.addWidget(content_label)
                
                # Attachments
                attachments = self.db.get_attachments_for_post(post.id)
                if attachments:
                    attach_label = StrongBodyLabel(f"📎 Attachments ({len(attachments)}):")
                    attach_label.setStyleSheet(f"color: {GhostTheme.get_purple_secondary()}; margin-top: 12px;")
                    post_layout.addWidget(attach_label)
                    
                    for attachment in attachments:
                        attach_layout = QHBoxLayout()
                        
                        # File info
                        file_label = BodyLabel(f"📄 {attachment.filename}")
                        file_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()}; font-size: 13px;")
                        attach_layout.addWidget(file_label)
                        
                        # File size
                        size_kb = attachment.file_size / 1024
                        size_label = CaptionLabel(f"({size_kb:.1f} KB)")
                        size_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 11px;")
                        attach_layout.addWidget(size_label)
                        
                        attach_layout.addStretch()
                        
                        # Download button
                        download_btn = PushButton(FluentIcon.DOWNLOAD, "Download")
                        download_btn.setFixedHeight(28)
                        download_btn.clicked.connect(lambda checked, a=attachment: self._on_download(a))
                        attach_layout.addWidget(download_btn)
                        
                        post_layout.addLayout(attach_layout)
                
                self.scroll_layout.addWidget(post_card)
            
            self.scroll_layout.addStretch()
            
        except Exception as e:
            logger.error(f"Failed to load message content: {e}")
    
    def _on_download(self, attachment):
        """Handle file download."""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            # Ask user where to save
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save File",
                attachment.filename,
                "All Files (*.*)"
            )
            
            if save_path:
                # Write decrypted data to file
                with open(save_path, 'wb') as f:
                    f.write(attachment.encrypted_data)
                
                logger.info(f"Downloaded file: {attachment.filename}")
                
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
