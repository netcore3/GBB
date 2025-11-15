"""
Thread List Page for P2P Encrypted BBS

Displays threads in a selected board as list items.
Shows thread title, author, and last activity timestamp.
Provides "Create Thread" button with dialog.
"""

import logging
from typing import Optional
from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem
from qfluentwidgets import (
    ScrollArea,
    ListWidget,
    PushButton,
    FluentIcon,
    MessageBox,
    LineEdit,
    TextEdit,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    StrongBodyLabel
)

from logic.board_manager import BoardManager, BoardManagerError
from logic.thread_manager import ThreadManager, ThreadManagerError
from models.database import Board, Thread


logger = logging.getLogger(__name__)


class ThreadListItem(QWidget):
    """
    Widget displaying thread information in list.
    
    Shows thread title, author, post count, and last activity.
    """
    
    def __init__(self, thread: Thread, post_count: int = 0, parent=None):
        """
        Initialize thread list item.
        
        Args:
            thread: Thread object to display
            post_count: Number of posts in thread
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.thread = thread
        self.post_count = post_count
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up item UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Thread title
        title_label = StrongBodyLabel(self.thread.title)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # Metadata row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(16)
        
        # Author
        author_label = CaptionLabel(f"By: {self.thread.creator_peer_id[:8]}...")
        author_label.setStyleSheet("color: gray;")
        meta_layout.addWidget(author_label)
        
        # Post count
        posts_label = CaptionLabel(f"💬 {self.post_count} posts")
        posts_label.setStyleSheet("color: gray;")
        meta_layout.addWidget(posts_label)
        
        # Last activity
        last_activity_str = self.thread.last_activity.strftime("%Y-%m-%d %H:%M")
        activity_label = CaptionLabel(f"Last: {last_activity_str}")
        activity_label.setStyleSheet("color: gray;")
        meta_layout.addWidget(activity_label)
        
        meta_layout.addStretch()
        
        layout.addLayout(meta_layout)


class CreateThreadDialog(MessageBox):
    """
    Dialog for creating a new thread.
    
    Prompts user for thread title and initial post content.
    """
    
    def __init__(self, parent=None):
        """
        Initialize create thread dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(
            title="Create New Thread",
            content="",
            parent=parent
        )
        
        self.thread_title = ""
        self.initial_post = ""
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up dialog UI."""
        # Create input widgets
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Title input
        title_label = BodyLabel("Thread Title (3-200 characters):")
        self.title_input = LineEdit()
        self.title_input.setPlaceholderText("Enter thread title...")
        self.title_input.setMaxLength(200)
        layout.addWidget(title_label)
        layout.addWidget(self.title_input)
        
        # Initial post input
        post_label = BodyLabel("Initial Post (1-10000 characters):")
        self.post_input = TextEdit()
        self.post_input.setPlaceholderText("Write your first post...")
        self.post_input.setMinimumHeight(150)
        layout.addWidget(post_label)
        layout.addWidget(self.post_input)
        
        # Add to dialog
        self.textLayout.addLayout(layout)
        
        # Set button text
        self.yesButton.setText("Create")
        self.cancelButton.setText("Cancel")
    
    def validate(self) -> bool:
        """
        Validate input fields.
        
        Returns:
            True if valid, False otherwise
        """
        self.thread_title = self.title_input.text().strip()
        self.initial_post = self.post_input.toPlainText().strip()
        
        if len(self.thread_title) < 3 or len(self.thread_title) > 200:
            return False
        
        if len(self.initial_post) < 1 or len(self.initial_post) > 10000:
            return False
        
        return True


class ThreadListPage(ScrollArea):
    """
    Page displaying list of threads in a board.
    
    Shows threads as list items with title, author, and activity info.
    Provides button to create new threads.
    Emits signal when thread is selected to navigate to post view.
    
    Signals:
        thread_selected: Emitted when a thread is clicked (thread_id)
        thread_created: Emitted when a new thread is created (thread)
        back_clicked: Emitted when back button is clicked
    """
    
    thread_selected = Signal(str)  # Emits thread_id
    thread_created = Signal(Thread)  # Emits Thread object
    back_clicked = Signal()
    
    def __init__(
        self,
        board_manager: BoardManager,
        thread_manager: ThreadManager,
        parent=None
    ):
        """
        Initialize thread list page.
        
        Args:
            board_manager: BoardManager instance
            thread_manager: ThreadManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.board_manager = board_manager
        self.thread_manager = thread_manager
        self.current_board: Optional[Board] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.info("ThreadListPage initialized")
    
    def _setup_ui(self):
        """Set up page UI."""
        # Create main widget
        self.view = QWidget()
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)
        
        # Header with back button, title, and create button
        header_layout = QHBoxLayout()
        
        # Back button
        self.back_button = PushButton(FluentIcon.RETURN, "Back to Boards")
        self.back_button.clicked.connect(self._on_back_clicked)
        header_layout.addWidget(self.back_button)
        
        # Title
        self.title_label = SubtitleLabel("Threads")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Create thread button
        self.create_button = PushButton(FluentIcon.ADD, "Create Thread")
        self.create_button.clicked.connect(self._on_create_thread_clicked)
        header_layout.addWidget(self.create_button)
        
        self.main_layout.addLayout(header_layout)
        
        # Board info
        self.board_info_label = BodyLabel("")
        self.board_info_label.setStyleSheet("color: gray;")
        self.main_layout.addWidget(self.board_info_label)
        
        # Thread list
        self.thread_list = ListWidget()
        self.thread_list.itemClicked.connect(self._on_thread_item_clicked)
        self.main_layout.addWidget(self.thread_list)
        
        # Style
        self.setObjectName("threadListPage")
    
    def set_board(self, board_id: str):
        """
        Set the current board and load its threads.
        
        Args:
            board_id: Board identifier
        """
        try:
            # Get board
            self.current_board = self.board_manager.get_board_by_id(board_id)
            
            if not self.current_board:
                logger.error(f"Board {board_id[:8]} not found")
                return
            
            # Update UI
            self.title_label.setText(f"Threads in {self.current_board.name}")
            
            # Update board info
            self.board_info_label.setText(
                f"{self.current_board.description or 'No description'}"
            )
            
            # Load threads
            self.refresh_threads()
            
            logger.info(f"Set board to: {self.current_board.name}")
            
        except Exception as e:
            logger.error(f"Failed to set board: {e}")
    
    def refresh_threads(self):
        """Refresh the list of threads for current board."""
        if not self.current_board:
            return
        
        try:
            # Clear existing threads
            self.thread_list.clear()
            
            # Get threads
            threads = self.board_manager.get_board_threads(self.current_board.id)
            
            if not threads:
                # Show empty state
                item = QListWidgetItem(self.thread_list)
                empty_widget = QWidget()
                empty_layout = QVBoxLayout(empty_widget)
                empty_label = BodyLabel("No threads yet. Create one to start a discussion!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setStyleSheet("color: gray; padding: 40px;")
                empty_layout.addWidget(empty_label)
                item.setSizeHint(empty_widget.sizeHint())
                self.thread_list.addItem(item)
                self.thread_list.setItemWidget(item, empty_widget)
            else:
                # Add thread items
                for thread in threads:
                    # Get post count
                    posts = self.thread_manager.get_thread_posts(thread.id)
                    post_count = len(posts)
                    
                    # Create list item
                    item = QListWidgetItem(self.thread_list)
                    thread_widget = ThreadListItem(thread, post_count)
                    item.setSizeHint(thread_widget.sizeHint())
                    item.setData(Qt.ItemDataRole.UserRole, thread.id)
                    
                    self.thread_list.addItem(item)
                    self.thread_list.setItemWidget(item, thread_widget)
            
            logger.debug(f"Refreshed thread list: {len(threads)} threads")
            
        except Exception as e:
            logger.error(f"Failed to refresh threads: {e}")
    
    def _on_create_thread_clicked(self):
        """Handle create thread button click."""
        if not self.current_board:
            return
        
        try:
            # Show create dialog
            dialog = CreateThreadDialog(self)
            
            if dialog.exec():
                # Validate input
                if not dialog.validate():
                    self._show_error(
                        "Invalid Input",
                        "Title must be 3-200 characters and post must be 1-10000 characters"
                    )
                    return
                
                # Create thread
                thread = self.thread_manager.create_thread(
                    board_id=self.current_board.id,
                    title=dialog.thread_title,
                    initial_post_content=dialog.initial_post
                )
                
                # Refresh list
                self.refresh_threads()
                
                # Emit signal
                self.thread_created.emit(thread)
                
                logger.info(f"Created thread: {thread.title}")
                
        except ValueError as e:
            logger.error(f"Invalid thread input: {e}")
            self._show_error("Invalid Input", str(e))
        except ThreadManagerError as e:
            logger.error(f"Failed to create thread: {e}")
            self._show_error("Creation Failed", str(e))
        except Exception as e:
            logger.error(f"Unexpected error creating thread: {e}")
            self._show_error("Error", "An unexpected error occurred")
    
    def _on_thread_item_clicked(self, item: QListWidgetItem):
        """
        Handle thread item click.
        
        Args:
            item: Clicked list item
        """
        thread_id = item.data(Qt.ItemDataRole.UserRole)
        if thread_id:
            logger.info(f"Thread selected: {thread_id[:8]}")
            self.thread_selected.emit(thread_id)
    
    def _on_back_clicked(self):
        """Handle back button click."""
        logger.info("Back to boards clicked")
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
