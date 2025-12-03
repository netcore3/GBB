"""Login and profile selection window for GhostBBs.

This window appears at startup before any P2P networking is initialized.
It allows the user to select an existing profile or create a new one.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtGui import QPainter, QColor, QFont, QPainterPath
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QSizePolicy,
)

from qfluentwidgets import (
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    LineEdit,
    InfoBar,
    InfoBarPosition,
    ScrollArea,
    CardWidget,
    TitleLabel,
)

from qframelesswindow import FramelessDialog, FramelessWindow, TitleBar, TitleBarBase, StandardTitleBar
from PySide6.QtWidgets import QDialog

from .theme_utils import (
    GhostTheme,
    get_button_styles,
    get_title_styles,
    get_card_styles,
    get_dialog_styles,
    get_scroll_area_styles,
    get_card_margins_large,
    apply_window_theme,
)
from qfluentwidgets import Theme
from ui.hover_card import apply_hover_glow

from core.db_manager import DBManager
from models.database import Profile


@dataclass
class SelectedProfile:
    profile: Profile


class CustomTitleBar(StandardTitleBar):
    """Custom title bar for login windows."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        # Hide the close button (the 'X') — leave other title controls intact.
        # Some versions may name the button differently; guard access.
        # Try a few common attribute names for the close button used by
        # different qframelesswindow versions and hide it if present.
        for name in ("closeButton", "closeBtn", "btnClose", "btn_close"):
            close_btn = getattr(self, name, None)
            if close_btn is not None:
                try:
                    close_btn.setVisible(False)
                except Exception:
                    # If it fails for some reason, continue trying others
                    pass

        # Style the title label from StandardTitleBar using the theme.
        # Use a slightly smaller/contrasted title so it reads well in the
        # compact login dialog while remaining consistent with app styles.
        small_title_style = get_title_styles().replace("28px", "16px")
        self.titleLabel.setStyleSheet(f"""
            QLabel {{
                color: {GhostTheme.get_text_primary()};
                {small_title_style}
                margin-left: 6px;
            }}
        """)


class ProfileCard(CardWidget):
    """Card showing profile avatar + display name with selection and double-click support."""

    selected = Signal()  # Emitted when profile is selected (single click)
    double_clicked = Signal()  # Emitted on double-click for immediate login

    def __init__(self, profile: Profile, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.profile = profile
        # Use a compact profile tile height for the login list so multiple
        # profiles fit comfortably without excessive scrolling.
        self.setFixedHeight(72)
        self._is_selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        self.avatar_label = QLabel()
        # Avatar size for compact profile tile
        self.avatar_label.setFixedSize(48, 48)
        # Do not use scaledContents so our generated pixmap keeps correct aspect
        self.avatar_label.setScaledContents(False)
        # Rounded avatar background and placeholder styling for better visuals
        self.avatar_label.setStyleSheet(f"border-radius: 24px; background-color: {GhostTheme.get_tertiary_background()};")
        self._set_avatar(profile.avatar_path, profile.display_name)

        self.name_label = QLabel(profile.display_name or "Unnamed profile")
        self.name_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.name_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()}; font-weight: 600;")

        layout.addWidget(self.avatar_label)
        layout.addWidget(self.name_label, 1)

        # Apply initial styling
        self._update_styling()

        # Apply hover glow effect for consistent UI
        apply_hover_glow(self, color=GhostTheme.get_purple_primary())

    def _set_avatar(self, avatar_path: Optional[str], display_name: Optional[str] = None) -> None:
        """Set avatar pixmap from file, or generate a default circular avatar.

        If a valid image path is provided it will be used. Otherwise a simple
        circular colored pixmap with initials will be generated to act as a
        default avatar.
        """
        # Keep avatar generation consistent with the label size above
        size = 48

        # If an avatar file exists, load and crop it to a circular pixmap.
        if avatar_path and Path(avatar_path).is_file():
            pix = QPixmap(str(avatar_path)).scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            if not pix.isNull():
                out = QPixmap(size, size)
                out.fill(Qt.transparent)
                painter = QPainter(out)
                try:
                    painter.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, size, size)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pix)
                finally:
                    painter.end()
                self.avatar_label.setPixmap(out)
                return

        # Fallback: generate a circular avatar with initials.
        out = QPixmap(size, size)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            # Derive a deterministic background color from the display name so
            # each profile has a visually distinct avatar color.
            name_hash = sum(ord(c) for c in (display_name or "")) if display_name else 0
            hue = name_hash % 360
            bg_color = QColor.fromHsv(hue, 160, 220)
            painter.setBrush(bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, size, size)

            initials = "?"
            if display_name:
                parts = display_name.strip().split()
                if len(parts) >= 2:
                    initials = (parts[0][0] + parts[1][0]).upper()
                else:
                    initials = parts[0][0].upper()

            painter.setPen(QColor(GhostTheme.get_text_primary()))
            font = QFont()
            font.setBold(True)
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(out.rect(), Qt.AlignCenter, initials)
        finally:
            painter.end()

        self.avatar_label.setPixmap(out)

    def _update_styling(self):
        """Update card styling based on selection state."""
        if self._is_selected:
            border_color = GhostTheme.get_purple_primary()
            bg_color = GhostTheme.get_purple_secondary()
            text_color = GhostTheme.get_text_primary()
        else:
            border_color = GhostTheme.get_purple_tertiary()
            bg_color = GhostTheme.get_secondary_background()
            text_color = GhostTheme.get_text_primary()

        self.setStyleSheet(f"""
            CardWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                margin: 2px;
            }}
            CardWidget:hover {{
                border-color: {GhostTheme.get_purple_secondary()};
                background-color: {GhostTheme.get_tertiary_background()};
            }}
            QLabel {{
                color: {text_color};
            }}
        """)

    def set_selected(self, selected: bool):
        """Set the selection state of this card."""
        self._is_selected = selected
        self._update_styling()

    def is_selected(self) -> bool:
        """Return whether this card is currently selected."""
        return self._is_selected

    def mousePressEvent(self, event):
        """Handle mouse press: select on single left-click."""
        if event.button() == Qt.LeftButton:
            self.selected.emit()
        super().mousePressEvent(event)

    def _reset_click_count(self):
        """Reset click count after timeout."""
        # Legacy timer reset; kept for compatibility but not used with
        # the new mouseDoubleClickEvent implementation.
        return

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to trigger immediate login."""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        # Accept the event to avoid base class emitting a mismatched signal
        event.accept()


class CreateProfileDialog(FramelessDialog):
    """Dialog for creating a new local profile."""

    def __init__(self, db: DBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.avatar_path: Optional[str] = None
        self.shared_folder: Optional[str] = None
        self.setWindowTitle("Create Profile")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        # Add custom title bar
        self.titleBar = CustomTitleBar(self)
        self.setTitleBar(self.titleBar)

        # Make the dialog a bit wider so form controls have room.
        self.setMinimumWidth(520)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)


        # Display the dialog's window title as a visible header inside the
        # dialog (redundant with the frameless title bar but helpful for
        # accessibility and consistency with other dialogs).
        header_title = TitleLabel(self.windowTitle())
        header_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setBold(False)
        header_title.setFont(header_font)
        header_title.setStyleSheet(get_title_styles().replace("28px", "20px").replace("font-weight: 700;", "font-weight: 400;"))
        main_layout.addWidget(header_title)


        # --- Name input ---
        name_label = QLabel("Display name")
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("Your display name")

        # --- Avatar preview and button ---
        self.avatar_preview = QLabel()
        self.avatar_preview.setFixedSize(100, 100)
        self.avatar_preview.setScaledContents(False)
        self.avatar_preview.setStyleSheet(f"border-radius: 50px; background-color: {GhostTheme.get_tertiary_background()};")
        self.name_edit.textChanged.connect(lambda _: self._update_avatar_preview())
        self._update_avatar_preview()

        avatar_btn = PushButton(FluentIcon.PEOPLE, "Choose avatar", self)
        avatar_btn.clicked.connect(self._choose_avatar)

        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(12)
        avatar_row.addWidget(self.avatar_preview)
        avatar_row.addWidget(avatar_btn)
        avatar_row.addStretch(1)

        # --- Shared folder input and button ---
        shared_label = QLabel("Shared folder")
        self.shared_folder_edit = LineEdit(self)
        self.shared_folder_edit.setPlaceholderText("Choose or enter shared folder path")
        shared_btn = PushButton(FluentIcon.FOLDER, "Choose shared folder", self)
        shared_btn.clicked.connect(self._choose_shared_folder)

        shared_row = QHBoxLayout()
        shared_row.setSpacing(12)
        shared_row.addWidget(self.shared_folder_edit, 1)
        shared_row.addWidget(shared_btn)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        self.cancel_btn = PushButton("Cancel", self)
        self.ok_btn = PrimaryPushButton("Create", self)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)

        # --- Add widgets to main layout ---
        main_layout.addWidget(name_label)
        main_layout.addWidget(self.name_edit)
        main_layout.addLayout(avatar_row)
        main_layout.addWidget(shared_label)
        main_layout.addLayout(shared_row)
        main_layout.addStretch(1)
        main_layout.addLayout(btn_row)

        # Now that the dialog controls (buttons) are created, apply theme
        # styling which may reference these controls.
        self._apply_dark_theme()


    def _choose_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose avatar image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.avatar_path = path
            self._update_avatar_preview()

    def _choose_shared_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose shared folder", "")
        if path:
            self.shared_folder_edit.setText(path)
    def _update_avatar_preview(self) -> None:
        size = 100
        from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPainterPath
        from pathlib import Path
        if self.avatar_path and Path(self.avatar_path).is_file():
            pix = QPixmap(str(self.avatar_path)).scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            out = QPixmap(size, size)
            out.fill(Qt.transparent)
            painter = QPainter(out)
            try:
                painter.setRenderHint(QPainter.Antialiasing)
                pathp = QPainterPath()
                pathp.addEllipse(0, 0, size, size)
                painter.setClipPath(pathp)
                painter.drawPixmap(0, 0, pix)
            finally:
                painter.end()
            self.avatar_preview.setPixmap(out)
            return

        # Fallback placeholder
        out = QPixmap(size, size)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            name_hash = sum(ord(c) for c in (self.name_edit.text() or "")) if self.name_edit.text() else 0
            hue = name_hash % 360
            bg_color = QColor.fromHsv(hue, 160, 220)
            painter.setBrush(bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, size, size)

            initials = "?"
            text = self.name_edit.text().strip()
            if text:
                parts = text.split()
                initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()

            painter.setPen(QColor(GhostTheme.get_text_primary()))
            font = QFont()
            font.setBold(True)
            font.setPointSize(32)
            painter.setFont(font)
            painter.drawText(out.rect(), Qt.AlignCenter, initials)
        finally:
            painter.end()

        self.avatar_preview.setPixmap(out)

    def _apply_dark_theme(self):
        """Apply dark theme styling to the create profile dialog."""
        # Use theme utility for consistent base styling
        from ui.theme_utils import apply_window_theme
        apply_window_theme(self)
        
        self.setStyleSheet(self.styleSheet() + f"""
            QDialog {{
                border-radius: 8px;
            }}
            QLabel {{
                color: {GhostTheme.get_text_primary()};
            }}
            LineEdit:focus {{
                border: 2px solid {GhostTheme.get_purple_primary()};
            }}
        """)
        # Apply button styles using utility function
        self.ok_btn.setStyleSheet(get_button_styles("primary"))
        self.cancel_btn.setStyleSheet(get_button_styles("secondary"))

    def get_profile(self) -> Optional[Profile]:
        name = self.name_edit.text().strip()
        if not name:
            return None
        profile_id = str(uuid.uuid4())
        shared_folder = self.shared_folder_edit.text().strip() if self.shared_folder_edit.text().strip() else None
        return self.db.create_profile(
            profile_id=profile_id,
            display_name=name,
            avatar_path=self.avatar_path,
            shared_folder=shared_folder,
        )


class LoginWindow(FramelessDialog):
    """Startup window for selecting or creating a profile.

    Usage: construct with a DBManager, call ``exec()``; if accepted, read
    ``selected_profile`` attribute.
    """

    def __init__(self, db: DBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.selected_profile: Optional[Profile] = None

        self.setWindowTitle("GhostBBs – Select Profile")
        self.resize(480, 360)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        # Add custom title bar
        self.titleBar = CustomTitleBar(self)
        self.setTitleBar(self.titleBar)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Use the same prominent title component and sizing as the
        # Create Board dialog so the login dialog feels consistent.
        title_lbl = TitleLabel("Choose a profile to continue")
        title_lbl.setObjectName("titleLabel")  # Add object name for styling
        # Left-align the title within the dialog and make it expand to the
        # available width so it appears flush-left relative to the dialog
        # content area. Match Create Board dialog: larger, bold title.
        title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_lbl.setContentsMargins(0, 0, 0, 0)
        # Match Create Profile title appearance (smaller, normal weight)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(False)
        title_lbl.setFont(title_font)
        # Apply the same title stylesheet as CreateProfileDialog header
        title_lbl.setStyleSheet(get_title_styles().replace("28px", "20px").replace("font-weight: 700;", "font-weight: 400;"))
        title_font.setPointSize(22)
        title_font.setBold(False)
        title_lbl.setFont(title_font)
        title_style = get_title_styles().replace("28px", "22px")
        title_style = title_style.replace("font-weight: 700;", "font-weight: 400;")
        title_style = title_style + "\nbackground-color: transparent;"
        title_lbl.setStyleSheet(title_style)

        self.scroll = ScrollArea(self)
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(container)

        btn_row = QHBoxLayout()
        self.new_profile_btn = PrimaryPushButton("Create new profile", self)
        self.new_profile_btn.setIcon(FluentIcon.ADD)
        self.new_profile_btn.clicked.connect(self._on_create_profile)

        self.login_btn = PrimaryPushButton("Login", self)
        self.login_btn.setIcon(FluentIcon.ACCEPT)
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.login_btn.setVisible(False)  # Initially hidden
        self.login_btn.setEnabled(False)  # Initially disabled

        self.quit_btn = PushButton("Quit", self)
        self.quit_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.new_profile_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.quit_btn)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(self.scroll, 1)
        main_layout.addLayout(btn_row)

        # Apply dark theme styling after all UI components are created
        self._apply_dark_theme()

        # Improve button icon/text alignment and sizing for consistent visuals
        try:
            self.new_profile_btn.setIconSize(QSize(18, 18))
            self.login_btn.setIconSize(QSize(18, 18))
            self.quit_btn.setIconSize(QSize(16, 16))
            # Add a small left-aligned layout for primary buttons so the icon
            # and text look balanced in the dialog
            btn_icon_text_style = """
                QPushButton { text-align: left; padding: 8px 14px; }
            """
            # Append to existing button styles applied in _apply_dark_theme
            self.new_profile_btn.setStyleSheet(self.new_profile_btn.styleSheet() + btn_icon_text_style)
            self.login_btn.setStyleSheet(self.login_btn.styleSheet() + btn_icon_text_style)
            self.quit_btn.setStyleSheet(self.quit_btn.styleSheet() + "QPushButton { padding: 6px 10px; }")
        except Exception:
            # Be forgiving on platforms where icon sizing may not be supported
            pass

        self._load_profiles()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_profiles(self) -> None:
        # Clear existing
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        profiles: List[Profile] = self.db.get_all_profiles()
        if not profiles:
            self._show_info("No profiles", "Create your first profile to start using GhostBBs.")
            return
        for profile in profiles:
            card = ProfileCard(profile, self)
            # Capture both profile and card in the lambda defaults so each
            # connection references the correct instance from the loop.
            card.selected.connect(lambda p=profile, c=card: self._on_profile_selected(p, c))
            card.double_clicked.connect(lambda p=profile: self._on_profile_double_clicked(p))
            self.list_layout.addWidget(card)
        self.list_layout.addStretch(1)

    def _on_profile_selected(self, profile: Profile, card: ProfileCard) -> None:
        """Handle profile selection (single click)."""
        # Clear previous selection
        self._clear_profile_selections()
        
        # Set new selection
        self.selected_profile = profile
        card.set_selected(True)
        
        # Show and enable login button
        self.login_btn.setVisible(True)
        self.login_btn.setEnabled(True)

    def _on_profile_double_clicked(self, profile: Profile) -> None:
        """Handle profile double-click for immediate login."""
        self.selected_profile = profile
        self._perform_login()

    def _on_login_clicked(self) -> None:
        """Handle login button click."""
        if self.selected_profile:
            self._perform_login()

    def _perform_login(self) -> None:
        """Perform the actual login process."""
        if self.selected_profile:
            # update last_used timestamp
            from datetime import datetime
            self.selected_profile.last_used = datetime.utcnow()
            self.db.update_profile(self.selected_profile)
            self.accept()

    def _clear_profile_selections(self) -> None:
        """Clear all profile selections."""
        for i in range(self.list_layout.count()):
            item = self.list_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, ProfileCard):
                widget.set_selected(False)
        
        # Hide and disable login button
        self.login_btn.setVisible(False)
        self.login_btn.setEnabled(False)

    def _on_create_profile(self) -> None:
        dialog = CreateProfileDialog(self.db, self)
        if dialog.exec() == QDialog.Accepted:
            profile = dialog.get_profile()
            if profile is None:
                self._show_error("Invalid profile", "Please enter a display name.")
                return
            self.selected_profile = profile
            self.db.update_profile(profile)
            self.accept()

    def _apply_dark_theme(self):
        """Apply dark theme styling to the login window."""
        # Ensure the application/window is using the dark theme for
        # consistent colors from GhostTheme (this sets qfluentwidgets theme).
        try:
            GhostTheme.apply_theme(Theme.DARK)
        except Exception:
            # If setting global theme fails, continue — apply_window_theme will
            # still set per-window stylesheet using GhostTheme colors.
            pass

        from ui.theme_utils import apply_window_theme
        apply_window_theme(self)
        
        # Reuse the same window theming as CreateProfileDialog so the
        # login window uses consistent background and widget styles.
        # Ensure the dialog surface uses the same app background color.
        self.setStyleSheet(self.styleSheet() + f"""
            QDialog {{
                border-radius: 8px;
                background-color: {GhostTheme.get_background()};
            }}
            QLabel {{
                color: {GhostTheme.get_text_primary()};
            }}
            /* Text input focus rings - purple accent */
            LineEdit:focus {{
                border: 2px solid {GhostTheme.get_purple_primary()};
            }}
        """)
        # Apply button styles using utility functions
        # Primary action buttons: ensure icon size and left-aligned text
        self.new_profile_btn.setIconSize(QSize(20, 20))
        self.login_btn.setIconSize(QSize(20, 20))
        # Apply base button styles from theme then append alignment tweaks
        self.new_profile_btn.setStyleSheet(get_button_styles("primary") + "\n" +
                                           "QPushButton { text-align: left; padding: 8px 14px; }")
        self.login_btn.setStyleSheet(get_button_styles("primary") + "\n" +
                                      "QPushButton { text-align: left; padding: 8px 14px; }")
        # Quit remains secondary
        self.quit_btn.setStyleSheet(get_button_styles("secondary"))

    # ------------------------------------------------------------------
    # InfoBar helpers
    # ------------------------------------------------------------------

    def _show_info(self, title: str, content: str) -> None:
        InfoBar.success(
            title=title,
            content=content,
            position=InfoBarPosition.TOP,
            parent=self,
            duration=3000,
        )

    def _show_error(self, title: str, content: str) -> None:
        InfoBar.error(
            title=title,
            content=content,
            position=InfoBarPosition.TOP,
            parent=self,
            duration=4000,
        )

