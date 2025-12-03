"""About Page for GhostBBs Application.

Displays application information, version, license, and links.
"""

import logging
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import (
    ScrollArea,
    BodyLabel,
    CaptionLabel,
    HyperlinkButton,
    TitleLabel,
    isDarkTheme
)

from ui.theme_utils import (
    GhostTheme,
    get_scroll_area_styles,
    get_separator_styles,
    get_metadata_styles,
    get_page_margins_large,
    SPACING_MEDIUM,
    SPACING_LARGE,
)


logger = logging.getLogger(__name__)


class AboutPage(ScrollArea):
    """
    About page displaying application information.
    
    Shows:
    - Application logo/icon
    - Application name and version
    - Description
    - Author/Organization information
    - License
    - External links (GitHub, Website, etc.)
    """
    
    def __init__(self, parent=None):
        """
        Initialize about page.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create main widget and layout
        self.view = QWidget()
        self.main_layout = QVBoxLayout(self.view)
        margins = get_page_margins_large()
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(SPACING_LARGE)
        
        # Setup UI
        self._setup_ui()
        
        # Configure scroll area
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("aboutPage")
        
        # Apply stylesheet
        self.view.setObjectName("view")
        self.setStyleSheet("QScrollArea {border: none; background: transparent}")
        self.view.setStyleSheet("QWidget#view {background: transparent}")
        
        # Apply theme
        self._apply_theme()
        
        logger.info("About page initialized")
    
    def _apply_theme(self):
        """Apply dark/light theme styling."""
        if isDarkTheme():
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
    
    def _apply_dark_theme(self):
        """Apply dark theme styling - uses centralized GhostTheme."""
        pass  # Theme is applied via GhostTheme utilities in _setup_ui

    def _apply_light_theme(self):
        """Apply light theme styling - uses centralized GhostTheme."""
        pass  # Theme is applied via GhostTheme utilities in _setup_ui

    def _setup_ui(self):
        """Set up the about page UI for GhostBBs."""
        # Use centralized theme colors
        separator_color = GhostTheme.get_separator_color()
        text_secondary = GhostTheme.get_text_secondary()

        # Header section with logo and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(30)

        # Application icon/logo
        icon_label = QLabel()
        icon_label.setFixedSize(120, 120)

        # Load the image from file
        pixmap = QPixmap("./glogo.jpeg")

        # If the image fails to load, use a fallback color
        if pixmap.isNull():
            pixmap = QPixmap(120, 120)
            pixmap.fill(GhostTheme.get_purple_primary())  # Fallback to purple

        icon_label.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        header_layout.addWidget(icon_label)

        # Title and description
        title_layout = QVBoxLayout()

        app_name = TitleLabel("GhostBBs")
        app_name.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_layout.addWidget(app_name)

        version_label = BodyLabel("Version 0.1.0 (Alpha)")
        version_label.setStyleSheet(f"color: {text_secondary};")
        title_layout.addWidget(version_label)

        tagline = BodyLabel("A decentralized, encrypted P2P bulletin board system")
        tagline.setStyleSheet(f"color: {text_secondary}; font-style: italic;")
        title_layout.addWidget(tagline)

        title_layout.addStretch()

        header_layout.addLayout(title_layout, 1)
        self.main_layout.addLayout(header_layout)

        # Separator
        separator = QLabel()
        separator.setFixedHeight(2)
        separator.setStyleSheet(f"background-color: {separator_color};")
        self.main_layout.addWidget(separator)
        
        # Description section
        desc_title = BodyLabel("About This Application")
        desc_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(desc_title)
        
        description = BodyLabel(
            "GhostBBs is a decentralized, privacy-focused bulletin board system built "
            "on peer-to-peer networking principles. It enables users to create and participate "
            "in discussion boards with end-to-end encryption, ensuring data privacy and security.\n\n"
            "Key Features:\n"
            "• Fully decentralized - no central server\n"
            "• End-to-end encrypted communications\n"
            "• Peer-to-peer synchronization of boards and posts\n"
            "• Multi-board discussions with attachments\n"
            "• Encrypted private messaging between peers\n"
            "• Moderation and trust controls\n"
            "• Cross-platform, Qt-based Fluent UI"
        )
        description.setWordWrap(True)
        description.setStyleSheet("line-height: 1.6;")
        self.main_layout.addWidget(description)
        
        # Separator
        separator2 = QLabel()
        separator2.setFixedHeight(2)
        separator2.setStyleSheet(f"background-color: {separator_color};")
        self.main_layout.addWidget(separator2)
        
        # Organization and contact section
        org_title = BodyLabel("Organization")
        org_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(org_title)
        
        org_label = BodyLabel("GhostBBs Project")
        org_label.setStyleSheet(f"margin-left: 10px; color: {text_secondary};")
        self.main_layout.addWidget(org_label)
        
        # Separator
        separator3 = QLabel()
        separator3.setFixedHeight(2)
        separator3.setStyleSheet(f"background-color: {separator_color};")
        self.main_layout.addWidget(separator3)
        
        # License section
        license_title = BodyLabel("License")
        license_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(license_title)
        
        license_label = BodyLabel("MIT License - Open Source")
        license_label.setStyleSheet(f"margin-left: 10px; color: {text_secondary};")
        self.main_layout.addWidget(license_label)
        
        license_info = CaptionLabel(
            "This software is provided 'as is', without warranty of any kind. "
            "See LICENSE file for full details."
        )
        license_info.setStyleSheet(f"margin-left: 10px; color: {text_secondary};")
        license_info.setWordWrap(True)
        self.main_layout.addWidget(license_info)
        
        # Separator
        separator4 = QLabel()
        separator4.setFixedHeight(2)
        separator4.setStyleSheet(f"background-color: {separator_color};")
        self.main_layout.addWidget(separator4)
        
        # Links section
        links_title = BodyLabel("Links & Resources")
        links_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(links_title)
        
        # Create links layout
        links_layout = QVBoxLayout()
        links_layout.setSpacing(10)
        links_layout.setContentsMargins(10, 0, 0, 0)
        
        # GitHub link
        github_btn = HyperlinkButton(
            url="https://github.com/ghostbbs/ghostbbs",
            text="GitHub Repository",
            parent=self
        )
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/ghostbbs/ghostbbs")))
        links_layout.addWidget(github_btn)
        
        # Website link
        website_btn = HyperlinkButton(
            url="https://ghostbbs.example.com",
            text="Official Website",
            parent=self
        )
        website_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ghostbbs.example.com")))
        links_layout.addWidget(website_btn)
        
        # Documentation link
        docs_btn = HyperlinkButton(
            url="https://github.com/ghostbbs/ghostbbs/wiki",
            text="Documentation & Wiki",
            parent=self
        )
        docs_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/ghostbbs/ghostbbs/wiki")))
        links_layout.addWidget(docs_btn)
        
        self.main_layout.addLayout(links_layout)
        
        # Add stretch at the bottom
        self.main_layout.addStretch(1)
