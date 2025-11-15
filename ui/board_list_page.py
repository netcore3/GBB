"""
Board List Page for P2P Encrypted BBS

Displays boards as CardWidget components in a scrollable layout.
Shows board name, description, and activity status.
Provides "Create Board" button with dialog.
"""

import logging
from typing import Optional, Callable
from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import (
    ScrollArea,
    CardWidget,
    PushButton,
    FluentIcon,
    MessageBox,
    LineEdit,
    TextEdit,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel
)

from logic.board_manager import BoardManager, BoardManagerError
from models.database import Board


logger = logging.getLogger(__name__)


class BoardCard(CardWidget):
    """
    Card widget displaying board information.
    
    Shows board name, description, creator, and last activity.
    Emits signal when clicked to navigate to thread list.
    """
    
    clicked = Signal(str)  # Emits board_id when clicked
    
    def __init__(self, board: Board, parent=None):
        """
        Initialize board card.
        
        Args:
            board: Board object to display
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.board = board
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up card UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Board name (title)
        name_label = SubtitleLabel(self.board.name)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Board description
        if self.board.description:
            desc_label = BodyLabel(self.board.description)
            desc_label.setWordWrap(True)
            desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(desc_label)
        
        # Metadata row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(16)
        
        # Creator
        creator_label = CaptionLabel(f"Created by: {self.board.creator_peer_id[:8]}...")
        creator_label.setStyleSheet("color: gray;")
        meta_layout.addWidget(creator_label)
        
        # Created date
        created_str = self.board.created_at.strftime("%Y-%m-%d %H:%M")
        date_label = CaptionLabel(f"Created: {created_str}")
        date_label.setStyleSheet("color: gray;")
        meta_layout.addWidget(date_label)
        
        meta_layout.addStretch()
        
        layout.addLayout(meta_layout)
        
        # Make card clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(140)
    
    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.board.id)
        super().mousePressEvent(event)


class CreateBoardDialog(MessageBox):
    """
    Dialog for creating a new board.
    
    Prompts user for board name and description.
    """
    
    def __init__(self, parent=None):
        """
        Initialize create board dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(
            title="Create New Board",
            content="",
            parent=parent
        )
        
        self.board_name = ""
        self.board_description = ""
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up dialog UI."""
        # Create input widgets
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Name input
        name_label = BodyLabel("Board Name (3-50 characters):")
        self.name_input = LineEdit()
        self.name_input.setPlaceholderText("Enter board name...")
        self.name_input.setMaxLength(50)
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        
        # Description input
        desc_label = BodyLabel("Description (optional):")
        self.desc_input = TextEdit()
        self.desc_input.setPlaceholderText("Enter board description...")
        self.desc_input.setMaximumHeight(100)
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_input)
        
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
        self.board_name = self.name_input.text().strip()
        self.board_description = self.desc_input.toPlainText().strip()
        
        if len(self.board_name) < 3:
            return False
        
        return True


class BoardListPage(ScrollArea):
    """
    Page displaying list of boards.
    
    Shows boards as card widgets in a scrollable layout.
    Provides button to create new boards.
    Emits signal when board is selected to navigate to thread list.
    
    Signals:
        board_selected: Emitted when a board is clicked (board_id)
        board_created: Emitted when a new board is created (board)
    """
    
    board_selected = Signal(str)  # Emits board_id
    board_created = Signal(Board)  # Emits Board object
    
    def __init__(
        self,
        board_manager: BoardManager,
        parent=None
    ):
        """
        Initialize board list page.
        
        Args:
            board_manager: BoardManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.board_manager = board_manager
        
        # Setup UI
        self._setup_ui()
        
        # Load boards
        self.refresh_boards()
        
        logger.info("BoardListPage initialized")
    
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
        
        # Header with title and create button
        header_layout = QHBoxLayout()
        
        # Title
        title_label = SubtitleLabel("Discussion Boards")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Create board button
        self.create_button = PushButton(FluentIcon.ADD, "Create Board")
        self.create_button.clicked.connect(self._on_create_board_clicked)
        header_layout.addWidget(self.create_button)
        
        self.main_layout.addLayout(header_layout)
        
        # Boards container
        self.boards_layout = QVBoxLayout()
        self.boards_layout.setSpacing(12)
        self.main_layout.addLayout(self.boards_layout)
        
        # Add stretch at bottom
        self.main_layout.addStretch()
        
        # Style
        self.setObjectName("boardListPage")
    
    def refresh_boards(self):
        """Refresh the list of boards from database."""
        try:
            # Clear existing boards
            self._clear_boards()
            
            # Get all boards
            boards = self.board_manager.get_all_boards()
            
            if not boards:
                # Show empty state
                empty_label = BodyLabel("No boards yet. Create one to get started!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setStyleSheet("color: gray; padding: 40px;")
                self.boards_layout.addWidget(empty_label)
            else:
                # Add board cards
                for board in boards:
                    card = BoardCard(board)
                    card.clicked.connect(self._on_board_clicked)
                    self.boards_layout.addWidget(card)
            
            logger.debug(f"Refreshed board list: {len(boards)} boards")
            
        except Exception as e:
            logger.error(f"Failed to refresh boards: {e}")
    
    def _clear_boards(self):
        """Clear all board widgets from layout."""
        while self.boards_layout.count():
            item = self.boards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _on_create_board_clicked(self):
        """Handle create board button click."""
        try:
            # Show create dialog
            dialog = CreateBoardDialog(self)
            
            if dialog.exec():
                # Validate input
                if not dialog.validate():
                    self._show_error("Invalid Input", "Board name must be 3-50 characters")
                    return
                
                # Create board
                board = self.board_manager.create_board(
                    name=dialog.board_name,
                    description=dialog.board_description
                )
                
                # Refresh list
                self.refresh_boards()
                
                # Emit signal
                self.board_created.emit(board)
                
                logger.info(f"Created board: {board.name}")
                
        except ValueError as e:
            logger.error(f"Invalid board input: {e}")
            self._show_error("Invalid Input", str(e))
        except BoardManagerError as e:
            logger.error(f"Failed to create board: {e}")
            self._show_error("Creation Failed", str(e))
        except Exception as e:
            logger.error(f"Unexpected error creating board: {e}")
            self._show_error("Error", "An unexpected error occurred")
    
    def _on_board_clicked(self, board_id: str):
        """
        Handle board card click.
        
        Args:
            board_id: ID of clicked board
        """
        logger.info(f"Board selected: {board_id[:8]}")
        self.board_selected.emit(board_id)
    
    def _show_error(self, title: str, message: str):
        """
        Show error message box.
        
        Args:
            title: Error title
            message: Error message
        """
        msg_box = MessageBox(title, message, self)
        msg_box.exec()
