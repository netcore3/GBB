"""
Welcome Page for GhostBBs Application

Displays a landing page with 3 feature panels after login:
- Boards: Browse and create bulletin boards
- Private Chat: Encrypted messaging with peers
- Peers: View and manage connected peers
"""

import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame
)
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QBrush, QPen
from qfluentwidgets import (
    ScrollArea, CardWidget, BodyLabel, TitleLabel,
    SubtitleLabel, CaptionLabel, isDarkTheme
)

from ui.theme_utils import (
    GhostTheme, get_page_margins_large, get_card_margins_large,
    SPACING_SMALL, SPACING_MEDIUM, SPACING_LARGE, SPACING_XLARGE
)
from ui.hover_card import apply_hover_glow


logger = logging.getLogger(__name__)


class FeatureCard(CardWidget):
    """
    Clickable feature card displaying a feature with icon, title, and description.

    Signals:
        clicked: Emitted when the card is clicked
    """

    clicked = Signal(str)  # feature_name

    def __init__(self, feature_name: str, icon: str, title: str, description: str,
                 features_list: list, parent=None):
        """
        Initialize feature card.

        Args:
            feature_name: Internal feature identifier (boards, chats, peers)
            icon: Emoji or icon character
            title: Feature title
            description: Feature description
            features_list: List of feature bullet points
            parent: Parent widget
        """
        super().__init__(parent)
        self.feature_name = feature_name
        self._setup_ui(icon, title, description, features_list)
        self._apply_styling()

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self, icon: str, title: str, description: str, features_list: list):
        """Set up the card UI."""
        layout = QVBoxLayout(self)
        margins = get_card_margins_large()
        layout.setContentsMargins(margins[0] + 8, margins[1] + 8, margins[2] + 8, margins[3] + 8)  # 32px padding
        layout.setSpacing(SPACING_MEDIUM)

        # Icon - larger and more prominent
        # Try to load an image from the project's `img/` directory first.
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Resolve image path relative to project root (ui/../img)
        try:
            project_root = Path(__file__).resolve().parent.parent
            # Prefer image files placed at the repository root (e.g. bbs.png)
            img_path = project_root / icon
            if not img_path.exists():
                # Fallback to legacy img/ directory
                img_path = project_root / 'img' / icon

            if img_path.exists():
                pix = QPixmap(str(img_path))
                if not pix.isNull():
                    size = 108
                    scaled = pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_label.setPixmap(scaled)
                else:
                    # Fallback to emoji/text
                    icon_label.setText(icon)
                    icon_label.setFont(QFont("Segoe UI Emoji", 56))
            else:
                # No image file; treat icon as plain emoji/text
                icon_label.setText(icon)
                icon_label.setFont(QFont("Segoe UI Emoji", 56))
        except Exception:
            icon_label.setText(icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 56))

        layout.addWidget(icon_label)

        # Previously the card displayed a large title under the icon; per
        # request we remove the big title text and instead use the provided
        # PNG image in its place above the description. The feature `title`
        # will still be used for accessibility/logging but not shown as big
        # text in the panel.

        # Description - larger and more readable
        desc_label = BodyLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet(f"color: {GhostTheme.get_text_secondary()}; font-size: 15px; line-height: 1.5;")
        layout.addWidget(desc_label)

        # Add spacing before features list
        layout.addSpacing(SPACING_SMALL)

        # Features list - improved typography
        features_widget = QWidget()
        features_layout = QVBoxLayout(features_widget)
        features_layout.setContentsMargins(SPACING_MEDIUM, SPACING_SMALL, SPACING_MEDIUM, SPACING_SMALL)
        features_layout.setSpacing(SPACING_SMALL)

        for feature in features_list:
            feature_label = BodyLabel(f"• {feature}")
            feature_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 13px;")
            features_layout.addWidget(feature_label)

        layout.addWidget(features_widget)
        layout.addStretch()

        # Click hint - more prominent
        hint_label = BodyLabel("Click to explore →")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet(f"""
            color: {GhostTheme.get_purple_primary()};
            font-weight: 600;
            font-size: 14px;
        """)
        layout.addWidget(hint_label)

    def _apply_styling(self):
        """Apply card styling."""
        self.setFixedSize(320, 420)  # Slightly smaller for better centering
        self.setStyleSheet(f"""
            FeatureCard {{
                background-color: transparent;
                border: 2px solid {GhostTheme.get_tertiary_background()};
                border-radius: 16px;
            }}
            FeatureCard:hover {{
                border-color: {GhostTheme.get_purple_primary()};
                background-color: {GhostTheme.get_tertiary_background()};
            }}
        """)
        # Use hover glow helper for a purple glow on hover; keep a subtle
        # baseline shadow for depth if desired by uncommenting below.
        apply_hover_glow(self, color=GhostTheme.get_purple_primary(), blur_radius=20, alpha=120)

    def mouseReleaseEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.feature_name)
        # Do not call the base implementation: qfluentwidgets.CardWidget
        # may emit the clicked signal itself (without arguments), which can
        # mismatch the Signal signature and raise a TypeError. We've already
        # emitted the correctly-formed signal above, so accept the event
        # and stop propagation here.
        event.accept()


class WelcomePage(ScrollArea):
    """
    Welcome/Landing page displayed after login.

    Shows 3 feature panels that navigate to different sections when clicked.

    Signals:
        feature_selected: Emitted when a feature card is clicked
    """

    feature_selected = Signal(str)  # feature_name: boards, chats, peers

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._setup_ui()

    def _setup_ui(self):
        """Set up the welcome page UI."""
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Main container
        container = QWidget()
        # Encapsulate feature cards in a single thin border panel
        container.setObjectName("panelContainer")
        main_layout = QVBoxLayout(container)
        # Reduced margins for better centering with nav menu visible
        # Left margin smaller to compensate for nav menu width
        main_layout.setContentsMargins(24, 32, 24, 32)
        main_layout.setSpacing(SPACING_LARGE)

        # Header section with logo and title on a single row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(SPACING_LARGE)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Application logo - placed to the left of the title
        logo_label = QLabel()
        logo_label.setFixedSize(120, 120)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap("./glogo.jpeg")
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
        else:
            # Fallback: simple circle without colored background (transparent)
            logo_label.setStyleSheet(f"""
                background-color: transparent;
                border-radius: 60px;
            """)

        # Title/subtitle stack to the right of the logo
        title_stack = QVBoxLayout()
        title_stack.setSpacing(SPACING_SMALL)
        title_stack.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # Welcome title - larger and bolder
        title_label = TitleLabel("Welcome to GhostBBs")
        title_label.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        title_stack.addWidget(title_label)

        # Subtitle - larger and more prominent
        subtitle_label = BodyLabel("A decentralized, encrypted peer-to-peer bulletin board system")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle_label.setStyleSheet(f"""
            color: {GhostTheme.get_text_secondary()};
            font-size: 18px;
            line-height: 1.4;
        """)
        title_stack.addWidget(subtitle_label)

        header_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(title_stack)

        main_layout.addLayout(header_layout)

        # Spacer
        main_layout.addSpacing(SPACING_LARGE)

    # 'Explore Features' heading removed for a cleaner home screen

        # Feature cards container - centered with tighter spacing
        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(SPACING_LARGE)  # Tighter spacing between cards
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Boards card
        boards_card = FeatureCard(
            feature_name="boards",
            icon="bbs.png",
            title="Boards",
            description="Browse, create, and participate in public discussion boards with threaded conversations.",
            features_list=[
                "Create your own BBS",
                "Browse public boards",
                "Threaded discussions",
                "Markdown support",
                "File attachments"
            ]
        )
        boards_card.clicked.connect(self._on_feature_clicked)
        cards_layout.addWidget(boards_card)

        # Private Chat card
        chats_card = FeatureCard(
            feature_name="chats",
            icon="chats.png",
            title="Private Chat",
            description="Send encrypted direct messages to other peers with end-to-end encryption.",
            features_list=[
                "End-to-end encryption",
                "Direct peer messaging",
                "Forward secrecy",
                "File sharing",
                "Message history"
            ]
        )
        chats_card.clicked.connect(self._on_feature_clicked)
        cards_layout.addWidget(chats_card)

        # Peers card
        peers_card = FeatureCard(
            feature_name="peers",
            icon="peers.png",
            title="Peers",
            description="View and manage connected peers on the network with trust management.",
            features_list=[
                "Discover nearby peers",
                "View connection status",
                "Trust management",
                "Ban/unban peers",
                "Network statistics"
            ]
        )
        peers_card.clicked.connect(self._on_feature_clicked)
        cards_layout.addWidget(peers_card)

        # Center the cards container
        main_layout.addWidget(cards_container, 0, Qt.AlignmentFlag.AlignCenter)

        # Bottom info
        main_layout.addStretch()

        # Security badge with improved styling
        info_label = BodyLabel("🔐 Your identity is secured with Ed25519 cryptographic keys • All communications are encrypted")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()}; font-size: 13px;")
        main_layout.addWidget(info_label)

        self.setWidget(container)

    def _on_feature_clicked(self, feature_name: str):
        """Handle feature card click."""
        logger.debug(f"Feature selected: {feature_name}")
        self.feature_selected.emit(feature_name)

