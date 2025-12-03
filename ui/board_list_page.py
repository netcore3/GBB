"""
Board List Page for P2P Encrypted BBS

Displays boards as CardWidget components in a scrollable layout.
Shows board name, description, and activity status.
Provides "Create Board" button with dialog.
"""

import logging
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect, QSizePolicy
from qfluentwidgets import (
    ScrollArea,
    CardWidget,
    PushButton,
    PrimaryPushButton,
    FluentIcon,
    MessageBox,
    LineEdit,
    TextEdit,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    SwitchButton,
    isDarkTheme,
    StrongBodyLabel
)
from PySide6.QtWidgets import QTabWidget, QFormLayout, QPushButton, QFileDialog, QTextEdit

from logic.board_manager import BoardManager, BoardManagerError
from ui.theme_utils import (
    get_button_styles, GhostTheme, apply_window_theme,
    get_page_margins, get_card_margins, SPACING_SMALL, SPACING_MEDIUM
)
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
        margins = get_card_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(SPACING_SMALL)
        
        # Apply dark theme styling. Use a 2px border to match design and
        # prepare for a glow effect on hover (the glow is implemented with a
        # QGraphicsDropShadowEffect because Qt stylesheets don't support
        # box-shadow).
        self.setStyleSheet(f"""
            CardWidget {{
                background-color: {GhostTheme.get_secondary_background()};
                border-radius: 6px;
                border: 2px solid {GhostTheme.get_purple_border()};
            }}
            CardWidget:hover {{
                border-color: {GhostTheme.get_purple_primary()};
                background-color: {GhostTheme.get_tertiary_background()};
            }}
        """
        )

        # Prepare drop shadow effect for hover glow
        from PySide6.QtGui import QColor
        glow_color = QColor(GhostTheme.get_purple_primary())
        glow_color.setAlpha(160)
        self._hover_shadow = QGraphicsDropShadowEffect(self)
        self._hover_shadow.setBlurRadius(24)
        self._hover_shadow.setColor(glow_color)
        self._hover_shadow.setOffset(0, 0)
        # Board name (title)
        name_label = SubtitleLabel(self.board.name)
        name_label.setWordWrap(True)
        name_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        layout.addWidget(name_label)
        
        # Board description
        if self.board.description:
            desc_label = BodyLabel(self.board.description)
            desc_label.setWordWrap(True)
            desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            desc_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()};")
            layout.addWidget(desc_label)
        # Welcome message (optional)
        if getattr(self.board, 'welcome_message', None):
            welcome_label = CaptionLabel(f"Welcome: {self.board.welcome_message}")
            welcome_label.setWordWrap(True)
            welcome_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
            layout.addWidget(welcome_label)
        
        # Metadata row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(16)
        
        # Creator
        creator_label = CaptionLabel(f"Created by: {self.board.creator_peer_id[:8]}...")
        creator_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        meta_layout.addWidget(creator_label)
        
        # Created date
        created_str = self.board.created_at.strftime("%Y-%m-%d %H:%M")
        date_label = CaptionLabel(f"Created: {created_str}")
        date_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
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

    def enterEvent(self, event):
        """Show glow on hover."""
        try:
            # Attach shadow effect to create a glow
            self.setGraphicsEffect(self._hover_shadow)
        except Exception:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Remove glow when no longer hovered."""
        try:
            self.setGraphicsEffect(None)
        except Exception:
            pass
        super().leaveEvent(event)


class CreateBoardDialog(MessageBox):
    """
    Dialog for creating a new board.

    Prompts user for board name, description, welcome message, and optional image.
    """

    def __init__(self, parent=None, image_manager=None):
        """
        Initialize create board dialog.

        Args:
            parent: Parent widget
            image_manager: BoardImageManager instance for image handling
        """
        super().__init__(
            title="Create New Board",
            content="",
            parent=parent
        )

        self.image_manager = image_manager
        self.board_name = ""
        self.board_description = ""
        self.welcome_message = ""
        self.image_path = None  # Relative path in DB
        self.selected_source_path = None  # Source path user selected
        self.is_private = False

        self._setup_ui()

        # Set fixed width to prevent layout shifts
        self.widget.setFixedWidth(500)

    def _setup_ui(self):
        """Set up dialog UI with polished layout."""
        # Create main layout with consistent spacing
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # === Board Name Section ===
        name_section = QVBoxLayout()
        name_section.setSpacing(6)
        name_label = StrongBodyLabel("Board Name")
        name_hint = CaptionLabel("3-50 characters")
        name_hint.setStyleSheet("color: #888888;")
        self.name_input = LineEdit()
        self.name_input.setPlaceholderText("Enter board name...")
        self.name_input.setMaxLength(50)
        self.name_input.setFixedHeight(36)
        name_section.addWidget(name_label)
        name_section.addWidget(name_hint)
        name_section.addWidget(self.name_input)
        layout.addLayout(name_section)

        # === Description Section ===
        desc_section = QVBoxLayout()
        desc_section.setSpacing(6)
        desc_label = StrongBodyLabel("Description")
        desc_hint = CaptionLabel("Optional - describe what this board is about")
        desc_hint.setStyleSheet("color: #888888;")
        self.desc_input = TextEdit()
        self.desc_input.setPlaceholderText("Enter board description...")
        self.desc_input.setFixedHeight(80)
        desc_section.addWidget(desc_label)
        desc_section.addWidget(desc_hint)
        desc_section.addWidget(self.desc_input)
        layout.addLayout(desc_section)

        # === Welcome Message Section ===
        welcome_section = QVBoxLayout()
        welcome_section.setSpacing(6)
        welcome_label = StrongBodyLabel("Welcome Message")
        welcome_hint = CaptionLabel("Optional - shown when users enter the board")
        welcome_hint.setStyleSheet("color: #888888;")
        self.welcome_input = TextEdit()
        self.welcome_input.setPlaceholderText("Welcome message shown on board entry...")
        self.welcome_input.setFixedHeight(80)
        welcome_section.addWidget(welcome_label)
        welcome_section.addWidget(welcome_hint)
        welcome_section.addWidget(self.welcome_input)
        layout.addLayout(welcome_section)

        # === Image Selection Section ===
        img_section = QVBoxLayout()
        img_section.setSpacing(6)
        img_label = StrongBodyLabel("Board Image")
        img_hint = CaptionLabel("Optional - add a cover image for the board")
        img_hint.setStyleSheet("color: #888888;")
        img_row = QHBoxLayout()
        img_row.setSpacing(12)
        self.img_path_label = BodyLabel("No image selected")
        self.img_path_label.setStyleSheet("color: #888888;")
        self.img_path_label.setMinimumWidth(200)
        self.img_browse_btn = QPushButton("Choose Image...")
        self.img_browse_btn.setFixedWidth(120)
        self.img_browse_btn.clicked.connect(self._on_browse_image)
        img_row.addWidget(self.img_path_label, 1)
        img_row.addWidget(self.img_browse_btn, 0)
        img_section.addWidget(img_label)
        img_section.addWidget(img_hint)
        img_section.addLayout(img_row)
        layout.addLayout(img_section)

        # === Privacy Section ===
        privacy_section = QVBoxLayout()
        privacy_section.setSpacing(6)
        privacy_label = StrongBodyLabel("Board Visibility")
        privacy_section.addWidget(privacy_label)

        # Privacy toggle row with fixed-width label to prevent layout shifts
        privacy_row = QHBoxLayout()
        privacy_row.setSpacing(12)
        self.private_switch = SwitchButton()
        self.private_switch.setChecked(False)
        self.private_switch.checkedChanged.connect(self._on_privacy_changed)
        # Use fixed-width label to prevent layout shifts when text changes
        self.privacy_status_label = BodyLabel("Public - visible to all peers")
        self.privacy_status_label.setMinimumWidth(220)
        privacy_row.addWidget(self.private_switch)
        privacy_row.addWidget(self.privacy_status_label, 1)
        privacy_section.addLayout(privacy_row)
        layout.addLayout(privacy_section)

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
        # collect extra inputs
        self.welcome_message = self.welcome_input.toPlainText().strip()
        self.image_path = getattr(self, 'image_path', '')
        self.is_private = self.private_switch.isChecked()

        return True

    def _on_privacy_changed(self, checked: bool):
        """Update privacy status label when switch changes."""
        if checked:
            self.privacy_status_label.setText("Private - invite only")
        else:
            self.privacy_status_label.setText("Public - visible to all peers")

    def _on_browse_image(self):
        """Handle image browse button click."""
        path, _ = QFileDialog.getOpenFileName(self, "Select board image", "", "Images (*.png *.jpg *.jpeg *.gif)")
        if path:
            self.selected_source_path = path
            self.img_path_label.setText(Path(path).name)
            self.img_path_label.setStyleSheet("")  # Reset to default color when image selected


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
        thread_manager=None,
        identity: Optional[str]=None,
        image_manager=None,
        parent=None
    ):
        """
        Initialize board list page.
        
        Args:
            board_manager: BoardManager instance
            thread_manager: ThreadManager instance (optional)
            identity: Local peer identity (optional)
            image_manager: BoardImageManager instance for image handling (optional)
            parent: Parent widget
        """
        super().__init__(parent)

        self.board_manager = board_manager
        # Optional references passed from main window for navigation/context
        self.thread_manager = thread_manager
        self.identity = identity
        self.image_manager = image_manager

        # Setup UI
        self._setup_ui()
        
        # Load boards
        self.refresh_boards()
        
        logger.info("BoardListPage initialized")
    
    def _setup_ui(self):
        """Set up page UI."""
        # Create main widget
        self.view = QWidget()
        # Encapsulate the list of board cards in a single thin border panel
        self.view.setObjectName("panelContainer")
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        margins = get_page_margins()
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(SPACING_MEDIUM)

        # Apply dark theme styling
        apply_window_theme(self.view)
        self.setStyleSheet(f"""
            QScrollArea#boardListPage {{
                background-color: {GhostTheme.get_background()};
            }}
            QTabWidget::pane {{
                border: 1px solid {GhostTheme.get_purple_tertiary()};
                background-color: {GhostTheme.get_background()};
            }}
            QTabBar::tab {{
                background-color: {GhostTheme.get_secondary_background()};
                color: {GhostTheme.get_text_secondary()};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {GhostTheme.get_purple_secondary()};
                color: {GhostTheme.get_text_primary()};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {GhostTheme.get_purple_primary()};
            }}
        """)

        # Header with title and create button
        header_layout = QHBoxLayout()

        # Title
        title_label = SubtitleLabel("Discussion Boards")
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Create BBS button (use PrimaryPushButton to match New Chat styling)
        self.create_button = PrimaryPushButton(FluentIcon.ADD, "Create BBS")
        try:
            self.create_button.setIconSize(QSize(18, 18))
        except Exception:
            pass
        # Use centralized primary button styles from theme utilities
        try:
            self.create_button.setStyleSheet(get_button_styles("primary") + "\nQPushButton { padding: 8px 14px; text-align: left; }")
        except Exception:
            # Fallback minimal styling
            self.create_button.setStyleSheet(f"background-color: {GhostTheme.get_purple_primary()}; color: {GhostTheme.get_text_primary()}; padding: 8px 14px;")
        self.create_button.clicked.connect(self._on_create_board_clicked)
        header_layout.addWidget(self.create_button)

        self.main_layout.addLayout(header_layout)

        # Tab widget to separate All Boards and My Boards
        self.tab_widget = QTabWidget(self.view)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {GhostTheme.get_purple_tertiary()};
                background-color: {GhostTheme.get_background()};
            }}
            QTabBar::tab {{
                background-color: {GhostTheme.get_secondary_background()};
                color: {GhostTheme.get_text_secondary()};
                padding: 8px 16px;
                margin-right: 8px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QTabBar::tab:selected {{
                background-color: {GhostTheme.get_purple_secondary()};
                color: {GhostTheme.get_text_primary()};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {GhostTheme.get_purple_primary()};
            }}
        """)

        # All Boards tab
        all_tab = QWidget()
        all_layout = QVBoxLayout(all_tab)
        all_layout.setContentsMargins(0, 0, 0, 0)
        # Add column headers (styled like peers table header)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        name_h = QLabel("Board Name")
        desc_h = QLabel("Description")
        creator_h = QLabel("Creator")
        created_h = QLabel("Created")
        for h in (name_h, desc_h, creator_h, created_h):
            h.setStyleSheet(f"background-color: {GhostTheme.get_secondary_background()}; color: {GhostTheme.get_text_primary()}; padding: 8px; border: 1px solid {GhostTheme.get_tertiary_background()};")
        header_row.addWidget(name_h, 2)
        header_row.addWidget(desc_h, 3)
        header_row.addWidget(creator_h, 1)
        header_row.addWidget(created_h, 1)
        all_layout.addLayout(header_row)
        self.boards_container = QWidget()
        self.boards_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.boards_layout = QVBoxLayout(self.boards_container)
        self.boards_layout.setSpacing(12)
        all_layout.addWidget(self.boards_container)
        self.tab_widget.addTab(all_tab, "All Boards")

        # My Boards tab (changed from "My BBS" to "My Boards")
        my_tab = QWidget()
        my_layout = QVBoxLayout(my_tab)
        my_layout.setContentsMargins(0, 0, 0, 0)
        # Add column headers to My Boards tab (styled)
        my_header_row = QHBoxLayout()
        my_header_row.setSpacing(8)
        my_name_h = QLabel("Board Name")
        my_desc_h = QLabel("Description")
        my_creator_h = QLabel("Creator")
        my_created_h = QLabel("Created")
        for h in (my_name_h, my_desc_h, my_creator_h, my_created_h):
            h.setStyleSheet(f"background-color: {GhostTheme.get_secondary_background()}; color: {GhostTheme.get_text_primary()}; padding: 8px; border: 1px solid {GhostTheme.get_tertiary_background()};")
        my_header_row.addWidget(my_name_h, 2)
        my_header_row.addWidget(my_desc_h, 3)
        my_header_row.addWidget(my_creator_h, 1)
        my_header_row.addWidget(my_created_h, 1)
        my_layout.addLayout(my_header_row)
        self.my_bbs_container = QWidget()
        self.my_bbs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.my_bbs_layout = QVBoxLayout(self.my_bbs_container)
        self.my_bbs_layout.setSpacing(12)
        my_layout.addWidget(self.my_bbs_container)
        self.tab_widget.addTab(my_tab, "My Boards")

        self.main_layout.addWidget(self.tab_widget)

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
                # Show empty state - using centralized theme
                empty_label = BodyLabel("No boards yet. Create one to get started!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; padding: 40px;")
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
        finally:
            # keep My BBS in sync; ignore errors here
            try:
                self.refresh_my_bbs()
            except Exception:
                logger.exception("Failed to refresh My BBS tab during boards refresh")
    
    def _clear_boards(self):
        """Clear all board widgets from layout."""
        while self.boards_layout.count():
            item = self.boards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_my_bbs(self):
        """Clear widgets from the My BBS layout."""
        while self.my_bbs_layout.count():
            item = self.my_bbs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_my_bbs(self):
        """Populate the My BBS tab with boards created by the local identity."""
        try:
            self._clear_my_bbs()

            if not self.identity:
                info = BodyLabel("Identity not available. Your boards will appear when your identity is set.")
                info.setAlignment(Qt.AlignmentFlag.AlignCenter)
                info.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; padding: 24px;")
                self.my_bbs_layout.addWidget(info)
                return

            boards = self.board_manager.get_all_boards()
            my_boards = [b for b in boards if b.creator_peer_id == self.identity]

            if not my_boards:
                empty = BodyLabel("You haven't created any BBS yet.")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet("color: gray; padding: 24px;")
                self.my_bbs_layout.addWidget(empty)
                return

            for board in my_boards:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(8, 8, 8, 8)

                name = SubtitleLabel(board.name)
                row_layout.addWidget(name)

                row_layout.addStretch()

                edit_btn = QPushButton("Edit")
                edit_btn.setProperty("board_id", board.id)
                edit_btn.clicked.connect(lambda _, b=board: self._on_edit_board_clicked(b))
                row_layout.addWidget(edit_btn)

                self.my_bbs_layout.addWidget(row)

        except Exception as e:
            logger.error(f"Failed to refresh My BBS tab: {e}")
    
    def _on_create_board_clicked(self):
        """Handle create board button click."""
        try:
            # Show create dialog
            dialog = CreateBoardDialog(self, image_manager=self.image_manager)
            
            if dialog.exec():
                # Validate input
                if not dialog.validate():
                    self._show_error("Invalid Input", "Board name must be 3-50 characters")
                    return
                
                # If image was selected and we have an image manager, copy it
                image_path_db = None
                if dialog.selected_source_path and self.image_manager:
                    # Generate board ID first (we don't have it yet, use a temp name)
                    import uuid
                    temp_board_id = str(uuid.uuid4())
                    image_path_db = self.image_manager.copy_board_image(dialog.selected_source_path, temp_board_id)
                
                # Create board (include welcome message, image path, and privacy setting)
                board = self.board_manager.create_board(
                    name=dialog.board_name,
                    description=dialog.board_description,
                    welcome_message=getattr(dialog, 'welcome_message', ''),
                    image_path=image_path_db or '',
                    is_private=getattr(dialog, 'is_private', False)
                )
                
                # Now that we have the real board ID, update the image filename if needed
                if image_path_db and board.id:
                    try:
                        old_path = self.image_manager.app_data_dir / image_path_db
                        if old_path.exists():
                            new_dest = self.image_manager.board_images_dir / f"{board.id}{old_path.suffix}"
                            if old_path != new_dest:
                                old_path.rename(new_dest)
                                image_path_db = str(new_dest.relative_to(self.image_manager.app_data_dir))
                                # Update board in DB
                                board.image_path = image_path_db
                                self.board_manager.db.update_board(board)
                                logger.info(f"Renamed board image from temp ID to {board.id}")
                    except Exception as e:
                        logger.warning(f"Failed to rename board image: {e}")
                
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

    def _on_edit_board_clicked(self, board: Board):
        """Open edit dialog for a board and persist updates."""
        try:
            dialog = CreateBoardDialog(self, image_manager=self.image_manager)
            # Pre-fill dialog
            dialog.name_input.setText(board.name)
            dialog.desc_input.setPlainText(board.description or "")
            dialog.welcome_input.setPlainText(getattr(board, 'welcome_message', '') or "")
            # Pre-fill privacy setting
            is_private = getattr(board, 'is_private', False)
            dialog.private_switch.setChecked(is_private)
            dialog._on_privacy_changed(is_private)  # Update label
            if getattr(board, 'image_path', None):
                # Resolve relative path to show in label
                if self.image_manager:
                    abs_path = self.image_manager.get_image_path(board.image_path)
                    if abs_path:
                        dialog.img_path_label.setText(abs_path.name)
                        dialog.img_path_label.setStyleSheet("")  # Reset to default color
                        dialog.selected_source_path = str(abs_path)

            if dialog.exec():
                if not dialog.validate():
                    self._show_error("Invalid Input", "Board name must be 3-50 characters")
                    return

                # Handle image update
                image_path_db = getattr(board, 'image_path', None)
                if dialog.selected_source_path and self.image_manager:
                    # If user selected a new image, copy it
                    if dialog.selected_source_path != str(self.image_manager.get_image_path(board.image_path)):
                        # Delete old image if it exists
                        if image_path_db:
                            self.image_manager.delete_board_image(image_path_db)
                        # Copy new image
                        image_path_db = self.image_manager.copy_board_image(dialog.selected_source_path, board.id)

                updated = self.board_manager.update_board(
                    board.id,
                    dialog.board_name,
                    dialog.board_description,
                    welcome_message=getattr(dialog, 'welcome_message', ''),
                    image_path=image_path_db or '',
                    is_private=getattr(dialog, 'is_private', False)
                )

                # Refresh both tabs
                self.refresh_boards()
                self.board_created.emit(updated)

        except BoardManagerError as e:
            logger.error(f"Failed to update board: {e}")
            self._show_error("Update Failed", str(e))
        except Exception as e:
            logger.error(f"Unexpected error updating board: {e}")
            self._show_error("Error", "An unexpected error occurred while updating the board")
