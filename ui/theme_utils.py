"""Theme utilities and color scheme for GhostBBs application.

This module provides consistent colors and theme utilities across all UI components.
"""

from qfluentwidgets import isDarkTheme, setTheme, Theme
from PySide6.QtWidgets import QApplication


class GhostTheme:
    """Centralized theme colors for GhostBBs application."""
    
    _current_font_size = 14  # Default font size
    
    # Dark theme colors (default)
    DARK_BACKGROUND = "#1e1e2e"
    DARK_SECONDARY = "#2D2D2D"
    DARK_TERTIARY = "#404040"
    DARK_TEXT_PRIMARY = "#ffffff"
    DARK_TEXT_SECONDARY = "#A0A0A0"
    DARK_TEXT_TERTIARY = "#999999"
    DARK_PURPLE_PRIMARY = "#4F46E5"
    DARK_PURPLE_SECONDARY = "#6366F1"
    DARK_PURPLE_TERTIARY = "#5B21B6"
    DARK_PURPLE_BORDER = "#3b0764"  # New color for border
    DARK_SUCCESS = "#22c55e"
    DARK_WARNING = "#f59e0b"
    DARK_ERROR = "#ef4444"
    
    # Light theme colors
    LIGHT_BACKGROUND = "#ffffff"
    LIGHT_SECONDARY = "#F0F0F0"
    LIGHT_TERTIARY = "#E0E0E0"
    LIGHT_TEXT_PRIMARY = "#000000"
    LIGHT_TEXT_SECONDARY = "#666666"
    LIGHT_TEXT_TERTIARY = "#999999"
    LIGHT_PURPLE_PRIMARY = "#7C3AED"
    LIGHT_PURPLE_SECONDARY = "#8B5CF6"
    LIGHT_PURPLE_TERTIARY = "#7C2D92"
    LIGHT_PURPLE_BORDER = "#6B21A8"  # New color for border
    LIGHT_SUCCESS = "#16a34a"
    LIGHT_WARNING = "#d97706"
    LIGHT_ERROR = "#dc2626"
    
    @classmethod
    def get_background(cls):
        """Get background color for current theme."""
        return cls.DARK_BACKGROUND if isDarkTheme() else cls.LIGHT_BACKGROUND
    
    @classmethod
    def get_secondary_background(cls):
        """Get secondary background color for current theme."""
        return cls.DARK_SECONDARY if isDarkTheme() else cls.LIGHT_SECONDARY
    
    @classmethod
    def get_tertiary_background(cls):
        """Get tertiary background color for current theme."""
        return cls.DARK_TERTIARY if isDarkTheme() else cls.LIGHT_TERTIARY
    
    @classmethod
    def get_text_primary(cls):
        """Get primary text color for current theme."""
        return cls.DARK_TEXT_PRIMARY if isDarkTheme() else cls.LIGHT_TEXT_PRIMARY
    
    @classmethod
    def get_text_secondary(cls):
        """Get secondary text color for current theme."""
        return cls.DARK_TEXT_SECONDARY if isDarkTheme() else cls.LIGHT_TEXT_SECONDARY
    
    @classmethod
    def get_text_tertiary(cls):
        """Get tertiary text color for current theme."""
        return cls.DARK_TEXT_TERTIARY if isDarkTheme() else cls.LIGHT_TEXT_TERTIARY
    
    @classmethod
    def get_purple_primary(cls):
        """Get primary purple accent color for current theme."""
        return cls.DARK_PURPLE_PRIMARY if isDarkTheme() else cls.LIGHT_PURPLE_PRIMARY
    
    @classmethod
    def get_purple_secondary(cls):
        """Get secondary purple accent color for current theme."""
        return cls.DARK_PURPLE_SECONDARY if isDarkTheme() else cls.LIGHT_PURPLE_SECONDARY
    
    @classmethod
    def get_purple_tertiary(cls):
        """Get tertiary purple accent color for current theme."""
        return cls.DARK_PURPLE_TERTIARY if isDarkTheme() else cls.LIGHT_PURPLE_TERTIARY
    
    @classmethod
    def get_success_color(cls):
        """Get success (green) color for current theme."""
        return cls.DARK_SUCCESS if isDarkTheme() else cls.LIGHT_SUCCESS
    
    @classmethod
    def get_warning_color(cls):
        """Get warning (orange) color for current theme."""
        return cls.DARK_WARNING if isDarkTheme() else cls.LIGHT_WARNING
    
    @classmethod
    def get_error_color(cls):
        """Get error (red) color for current theme."""
        return cls.DARK_ERROR if isDarkTheme() else cls.LIGHT_ERROR
    
    @classmethod
    def get_chat_sent_background(cls):
        """Get background color for sent chat messages."""
        return cls.get_purple_primary()
    
    @classmethod
    def get_chat_received_background(cls):
        """Get background color for received chat messages."""
        return cls.get_secondary_background()
    
    @classmethod
    def get_chat_sent_text(cls):
        """Get text color for sent chat messages."""
        return "#ffffff"  # Always white for contrast with primary purple
    
    @classmethod
    def get_chat_received_text(cls):
        """Get text color for received chat messages."""
        return cls.get_text_primary()
    
    @classmethod
    def get_separator_color(cls):
        """Get separator line color for current theme."""
        return cls.DARK_TERTIARY if isDarkTheme() else cls.LIGHT_TERTIARY
    
    @classmethod
    def set_font_size(cls, size: int):
        """Set application-wide font size."""
        cls._current_font_size = size
        app = QApplication.instance()
        if app:
            font = app.font()
            font.setPointSize(size)
            app.setFont(font)
    
    @classmethod
    def get_font_size(cls) -> int:
        """Get current application font size."""
        return cls._current_font_size

    @classmethod
    def apply_theme(cls, theme: Theme):
        """Apply theme to application."""
        setTheme(theme)
        # Set purple accent color for all QFluentWidgets components
        from qfluentwidgets import setThemeColor
        setThemeColor(cls.DARK_PURPLE_PRIMARY if isDarkTheme() else cls.LIGHT_PURPLE_PRIMARY)


# =============================================================================
# Layout Constants - Standardized margins and spacing across the application
# =============================================================================

# Page content margins (main content area padding)
PAGE_MARGINS = 24  # Standard page margins for all pages
PAGE_MARGINS_LARGE = 32  # For pages that need more breathing room (welcome page)

# Card and component margins
CARD_MARGINS = 16  # Inside card padding
CARD_MARGINS_LARGE = 24  # For larger cards

# Spacing constants
SPACING_SMALL = 8
SPACING_MEDIUM = 16
SPACING_LARGE = 24
SPACING_XLARGE = 32


def get_page_margins() -> tuple:
    """Get standard page content margins.

    Returns:
        tuple: (left, top, right, bottom) margins
    """
    return (PAGE_MARGINS, PAGE_MARGINS, PAGE_MARGINS, PAGE_MARGINS)


def get_page_margins_large() -> tuple:
    """Get large page content margins for welcome/landing pages.

    Returns:
        tuple: (left, top, right, bottom) margins
    """
    return (PAGE_MARGINS_LARGE, PAGE_MARGINS_LARGE, PAGE_MARGINS_LARGE, PAGE_MARGINS_LARGE)


def get_card_margins() -> tuple:
    """Get standard card internal margins.

    Returns:
        tuple: (left, top, right, bottom) margins
    """
    return (CARD_MARGINS, CARD_MARGINS, CARD_MARGINS, CARD_MARGINS)


def get_card_margins_large() -> tuple:
    """Get large card internal margins.

    Returns:
        tuple: (left, top, right, bottom) margins
    """
    return (CARD_MARGINS_LARGE, CARD_MARGINS_LARGE, CARD_MARGINS_LARGE, CARD_MARGINS_LARGE)


def get_title_styles():
    """Get standardized title styles for all screens.
    
    Returns:
        str: CSS stylesheet for titles
    """
    return f"""
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: {GhostTheme.get_text_primary()};
    """


def apply_window_theme(window, base_stylesheet=None):
    """Apply consistent theme styling to a window.
    
    Args:
        window: The window/widget to apply theme to
        base_stylesheet: Base stylesheet to extend (optional)
    """
    if base_stylesheet is None:
        base_stylesheet = ""
    
    theme_stylesheet = f"""
        /* Base window styling */
        QWidget {{
            background-color: {GhostTheme.get_background()};
            color: {GhostTheme.get_text_primary()};
        }}
        
        /* Scroll areas */
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        
        QWidget#view {{
            background: transparent;
        }}
    """
    
    if base_stylesheet:
        # Include card/panel styles so that panelContainer and inner controls
        # inherit the intended transparent backgrounds and border rules.
        full_stylesheet = base_stylesheet + "\n" + theme_stylesheet + "\n" + get_card_styles()
        window.setStyleSheet(full_stylesheet)
    else:
        # Append card styles by default so pages that rely on panelContainer
        # selectors get the correct transparent/background overrides.
        window.setStyleSheet(theme_stylesheet + "\n" + get_card_styles())


def get_button_styles(purpose="primary"):
    """Get consistent button styles for different purposes.
    
    Args:
        purpose: Button purpose ("primary", "secondary", "success", "warning", "error")
    
    Returns:
        str: CSS stylesheet for the button
    """
    if purpose == "primary":
        bg_color = GhostTheme.get_purple_primary()
        hover_color = GhostTheme.get_purple_secondary()
        pressed_color = GhostTheme.get_purple_tertiary()
    elif purpose == "secondary":
        bg_color = GhostTheme.get_secondary_background()
        hover_color = GhostTheme.get_tertiary_background()
        pressed_color = GhostTheme.get_tertiary_background()
    elif purpose == "success":
        bg_color = GhostTheme.get_success_color()
        hover_color = GhostTheme.get_success_color()
        pressed_color = GhostTheme.get_success_color()
    elif purpose == "warning":
        bg_color = GhostTheme.get_warning_color()
        hover_color = GhostTheme.get_warning_color()
        pressed_color = GhostTheme.get_warning_color()
    elif purpose == "error":
        bg_color = GhostTheme.get_error_color()
        hover_color = GhostTheme.get_error_color()
        pressed_color = GhostTheme.get_error_color()
    else:
        bg_color = GhostTheme.get_secondary_background()
        hover_color = GhostTheme.get_tertiary_background()
        pressed_color = GhostTheme.get_tertiary_background()
    
    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {GhostTheme.get_text_primary()};
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {pressed_color};
        }}
        QPushButton:disabled {{
            background-color: {GhostTheme.get_tertiary_background()};
            color: {GhostTheme.get_text_tertiary()};
        }}
    """


def get_chat_bubble_styles(is_sent=True):
    """Get consistent chat bubble styles.
    
    Args:
        is_sent: Whether this is a sent message bubble
    
    Returns:
        str: CSS stylesheet for the chat bubble
    """
    if is_sent:
        bg_color = GhostTheme.get_chat_sent_background()
        text_color = GhostTheme.get_chat_sent_text()
        timestamp_color = "rgba(255, 255, 255, 0.8)"
    else:
        bg_color = GhostTheme.get_chat_received_background()
        text_color = GhostTheme.get_chat_received_text()
        timestamp_color = GhostTheme.get_text_tertiary()
    
    return f"""
        QFrame {{
            background-color: {bg_color};
            border-radius: 12px;
            padding: 8px 12px;
            margin: 2px;
        }}
        
        QLabel {{
            color: {text_color};
        }}
        
        CaptionLabel {{
            color: {timestamp_color};
        }}
    """


def get_navigation_styles():
    """Get consistent navigation interface styles.

    Returns:
        str: CSS stylesheet for navigation interface
    """
    return f"""
        QWidget {{
            background-color: {GhostTheme.get_background()};
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        /* Purple highlighting for active navigation items */
        QWidget[selected="true"] {{
            background-color: {GhostTheme.get_purple_secondary()};
            border: 2px solid {GhostTheme.DARK_PURPLE_BORDER if isDarkTheme() else GhostTheme.LIGHT_PURPLE_BORDER};
            border-radius: 8px;
            color: {GhostTheme.get_text_primary()};
        }}
        QWidget:hover {{
            background-color: {GhostTheme.get_purple_primary()};
            border-radius: 8px;
        }}
        /* Override QFluentWidgets NavigationPushButton selection */
        NavigationPushButton {{
            background-color: transparent;
        }}
        NavigationPushButton:checked {{
            background-color: {GhostTheme.get_purple_secondary()};
            border-radius: 8px;
        }}
        NavigationPushButton:hover {{
            background-color: {GhostTheme.get_purple_primary()};
            border-radius: 8px;
        }}
        NavigationPushButton:pressed {{
            background-color: {GhostTheme.get_purple_tertiary()};
        }}
        /* Navigation tree widget items */
        NavigationTreeWidget::item:selected {{
            background-color: {GhostTheme.get_purple_secondary()};
        }}
        NavigationTreeWidget::item:hover {{
            background-color: {GhostTheme.get_purple_primary()};
        }}
    """


def get_card_styles():
    """Get consistent card widget styles.

    Returns:
        str: CSS stylesheet for card widgets
    """
    # Build the stylesheet using concatenation to avoid f-string brace
    # interpretation issues with CSS curly braces.
    s = ""
    s += "CardWidget {\n"
    s += "    background-color: " + GhostTheme.get_secondary_background() + ";\n"
    s += "    border-radius: 8px;\n"
    s += "    /* Individual cards do not show their own borders; outer container\n"
    s += "       will provide a single thin outline as requested. */\n"
    s += "    border: none;\n"
    s += "}\n"
    s += "CardWidget:hover {\n"
    s += "    background-color: " + GhostTheme.get_tertiary_background() + ";\n"
    s += "    /* Keep hover background change but no per-card border */\n"
    s += "}\n"
    s += "/* Ensure inner container widgets inside a CardWidget do not draw\n"
    s += "   their own borders so the card only shows an external border. */\n"
    s += "CardWidget QFrame,\n"
    s += "CardWidget QGroupBox,\n"
    s += "CardWidget QScrollArea,\n"
    s += "CardWidget QTabWidget::pane {\n"
    s += "    border: none;\n"
    s += "    background: transparent;\n"
    s += "}\n\n"
    s += "/* Panel container: a thin outer border that encapsulates many\n"
    s += "   CardWidget instances (used on home and list pages). */\n"
    s += "QWidget#panelContainer {\n"
    s += "    background-color: " + GhostTheme.get_background() + ";\n"
    s += "    border: 1px solid " + GhostTheme.get_tertiary_background() + ";\n"
    s += "    border-radius: 10px;\n"
    s += "    padding: 12px;\n"
    s += "}\n"
    s += "/* Remove borders for controls inside the panel container so the\n"
    s += "   panel appears as a single framed unit without internal control\n"
    s += "   outlines. This targets only widgets inside the panel. */\n"
    s += "/* Also force transparent background for all descendants so any\n"
    s += "   hard-coded blue/purple backgrounds used by child widgets are\n"
    s += "   removed inside the panel. */\n"
    s += "QWidget#panelContainer * {\n"
    s += "    background-color: transparent;\n"
    s += "    background: transparent;\n"
    s += "}\n"
    s += "QWidget#panelContainer QPushButton,\n"
    s += "QWidget#panelContainer QToolButton {\n"
    s += "    border: none;\n"
    s += "    background: transparent;\n"
    s += "}\n"
    s += "QWidget#panelContainer QLineEdit,\n"
    s += "QWidget#panelContainer QPlainTextEdit,\n"
    s += "QWidget#panelContainer QTextEdit {\n"
    s += "    border: none;\n"
    s += "    background: transparent;\n"
    s += "}\n"
    s += "QWidget#panelContainer QComboBox {\n"
    s += "    border: none;\n"
    s += "    background: transparent;\n"
    s += "}\n"
    return s


def get_scroll_area_styles():
    """Get consistent scroll area styles.

    Returns:
        str: CSS stylesheet for scroll areas
    """
    return f"""
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QWidget#view {{
            background: transparent;
        }}
    """


def get_separator_styles():
    """Get consistent separator/divider styles.

    Returns:
        str: CSS stylesheet for separators
    """
    return f"""
        background-color: {GhostTheme.get_separator_color()};
    """


def get_table_styles():
    """Get consistent table widget styles.

    Returns:
        str: CSS stylesheet for table widgets
    """
    return f"""
        QTableWidget {{
            background-color: {GhostTheme.get_background()};
            color: {GhostTheme.get_text_primary()};
            gridline-color: {GhostTheme.get_tertiary_background()};
            border: 1px solid {GhostTheme.get_tertiary_background()};
        }}
        QTableWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {GhostTheme.get_tertiary_background()};
        }}
        QTableWidget::item:selected {{
            background-color: {GhostTheme.get_purple_primary()};
        }}
        QHeaderView::section {{
            background-color: {GhostTheme.get_secondary_background()};
            color: {GhostTheme.get_text_primary()};
            padding: 8px;
            border: 1px solid {GhostTheme.get_tertiary_background()};
        }}
    """


def get_tab_widget_styles():
    """Get consistent tab widget styles.

    Returns:
        str: CSS stylesheet for tab widgets
    """
    return f"""
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
    """


def get_input_styles():
    """Get consistent text input styles.

    Returns:
        str: CSS stylesheet for text inputs
    """
    return f"""
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background-color: {GhostTheme.get_secondary_background()};
            color: {GhostTheme.get_text_primary()};
            border: 1px solid {GhostTheme.get_tertiary_background()};
            border-radius: 6px;
            padding: 8px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
            border: 2px solid {GhostTheme.get_purple_primary()};
        }}
    """


def get_dialog_styles():
    """Get consistent dialog styles.

    Returns:
        str: CSS stylesheet for dialogs
    """
    return f"""
        QDialog {{
            background-color: {GhostTheme.get_background()};
            color: {GhostTheme.get_text_primary()};
            border-radius: 8px;
        }}
        QLabel {{
            color: {GhostTheme.get_text_primary()};
        }}
    """


def get_empty_state_styles():
    """Get consistent empty state label styles.

    Returns:
        str: CSS stylesheet for empty state messages
    """
    return f"""
        color: {GhostTheme.get_text_tertiary()};
        padding: 40px;
    """


def get_metadata_styles():
    """Get consistent metadata/caption label styles.

    Returns:
        str: CSS stylesheet for metadata labels
    """
    return f"""
        color: {GhostTheme.get_text_tertiary()};
    """


def get_verified_styles():
    """Get styles for verified status indicator.

    Returns:
        str: CSS stylesheet for verified indicator
    """
    return f"""
        color: {GhostTheme.get_success_color()};
    """


def get_unverified_styles():
    """Get styles for unverified/warning status indicator.

    Returns:
        str: CSS stylesheet for unverified indicator
    """
    return f"""
        color: {GhostTheme.get_warning_color()};
    """


def get_error_text_styles():
    """Get styles for error text.

    Returns:
        str: CSS stylesheet for error text
    """
    return f"""
        color: {GhostTheme.get_error_color()};
    """