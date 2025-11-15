"""
Main Window for P2P Encrypted BBS Application

Implements the primary application window using QFluentWidgets with Fluent Design.
Provides navigation interface, content area, and notification system.
"""

import logging
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QApplication, QWidget, QStackedWidget, QVBoxLayout
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    Theme,
    setTheme,
    isDarkTheme
)

from core.qt_asyncio import QtAsyncioEventLoop
from config.config_manager import ConfigManager
from ui.settings_page import SettingsPage
from core.error_handler import ErrorHandler, ErrorSeverity, get_error_handler
from core.notification_manager import (
    NotificationManager,
    NotificationType,
    NotificationPriority,
    get_notification_manager
)


logger = logging.getLogger(__name__)


class MainWindow(FluentWindow):
    """
    Main application window with Fluent Design navigation.
    
    Provides:
    - Sidebar navigation with Boards, Private Chats, Peers, Settings, About
    - Stacked widget content area for different pages
    - InfoBar notification system
    - Theme support (light/dark mode)
    - Asyncio event loop integration
    
    Signals:
        theme_changed: Emitted when theme is changed
        navigation_changed: Emitted when navigation item is selected
    """
    
    # Qt signals
    theme_changed = Signal(Theme)
    navigation_changed = Signal(str)
    
    def __init__(
        self,
        config_manager: ConfigManager,
        board_manager=None,
        thread_manager=None,
        chat_manager=None,
        error_handler: Optional[ErrorHandler] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        """
        Initialize main window.
        
        Args:
            config_manager: Configuration manager instance
            board_manager: Optional BoardManager instance
            thread_manager: Optional ThreadManager instance
            chat_manager: Optional ChatManager instance
            error_handler: Optional ErrorHandler instance (uses global if not provided)
            notification_manager: Optional NotificationManager instance (uses global if not provided)
        """
        super().__init__()
        
        self.config_manager = config_manager
        self.board_manager = board_manager
        self.thread_manager = thread_manager
        self.chat_manager = chat_manager
        
        # Initialize error handler and notification manager
        self.error_handler = error_handler or get_error_handler()
        self.notification_manager = notification_manager or get_notification_manager()
        
        # Set up error handler callback
        self.error_handler.set_notification_callback(self._handle_error_notification)
        
        # Set up notification manager callback
        self.notification_manager.set_notification_callback(self._handle_notification)
        
        # Initialize asyncio event loop integration
        self.event_loop = QtAsyncioEventLoop(QApplication.instance())
        
        # Page widgets (will be created by subclasses or set externally)
        self.boards_page: Optional[QWidget] = None
        self.chats_page: Optional[QWidget] = None
        self.peers_page: Optional[QWidget] = None
        self.settings_page: Optional[QWidget] = None
        self.about_page: Optional[QWidget] = None
        
        # Setup UI
        self._setup_window()
        self._setup_navigation()
        self._load_theme()
        self._connect_signals()
        
        logger.info("Main window initialized")
    
    def _setup_window(self):
        """Configure main window properties."""
        self.setWindowTitle("P2P Encrypted BBS")
        self.resize(1200, 800)
        
        # Set window icon if available
        # TODO: Add application icon
        
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)
    
    def _setup_navigation(self):
        """Set up navigation interface with sidebar items."""
        # Add navigation items
        
        # Boards page
        self.boards_page = self._create_placeholder_page("Boards")
        self.addSubInterface(
            self.boards_page,
            FluentIcon.FOLDER,
            "Boards",
            NavigationItemPosition.TOP
        )
        
        # Private Chats page
        self.chats_page = self._create_placeholder_page("Private Chats")
        self.addSubInterface(
            self.chats_page,
            FluentIcon.CHAT,
            "Private Chats",
            NavigationItemPosition.TOP
        )
        
        # Peers page
        self.peers_page = self._create_placeholder_page("Peers")
        self.addSubInterface(
            self.peers_page,
            FluentIcon.PEOPLE,
            "Peers",
            NavigationItemPosition.TOP
        )
        
        # Settings page (bottom of navigation)
        self.settings_page = SettingsPage(self.config_manager)
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "Settings",
            NavigationItemPosition.BOTTOM
        )
        
        # About page (bottom of navigation)
        self.about_page = self._create_placeholder_page("About")
        self.addSubInterface(
            self.about_page,
            FluentIcon.INFO,
            "About",
            NavigationItemPosition.BOTTOM
        )
        
        # Set default page
        self.stackedWidget.setCurrentWidget(self.boards_page)
        
        logger.debug("Navigation interface configured")
    
    def _create_placeholder_page(self, title: str) -> QWidget:
        """
        Create a placeholder page widget.
        
        This will be replaced with actual page implementations.
        
        Args:
            title: Page title
            
        Returns:
            QWidget placeholder
        """
        from PySide6.QtWidgets import QLabel
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel(f"{title} Page\n\nComing soon...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: gray;")
        
        layout.addWidget(label)
        
        return widget
    
    def _load_theme(self):
        """Load and apply theme from configuration."""
        try:
            ui_config = self.config_manager.get_ui_config()
            theme_name = ui_config.theme.lower()
            
            if theme_name == "dark":
                self.apply_theme(Theme.DARK)
            elif theme_name == "light":
                self.apply_theme(Theme.LIGHT)
            else:
                # Default to dark theme
                self.apply_theme(Theme.DARK)
            
            logger.info(f"Applied theme: {theme_name}")
            
        except Exception as e:
            logger.error(f"Failed to load theme from config: {e}")
            # Fallback to dark theme
            self.apply_theme(Theme.DARK)
    
    def apply_theme(self, theme: Theme):
        """
        Apply a theme to the application.
        
        Args:
            theme: Theme to apply (Theme.LIGHT or Theme.DARK)
        """
        try:
            setTheme(theme)
            
            # Apply acrylic effect if enabled
            ui_config = self.config_manager.get_ui_config()
            if ui_config.enable_acrylic:
                self._apply_acrylic_effect()
            
            # Emit signal
            self.theme_changed.emit(theme)
            
            logger.info(f"Theme applied: {theme}")
            
        except Exception as e:
            logger.error(f"Failed to apply theme: {e}")
    
    def _apply_acrylic_effect(self):
        """Apply acrylic (translucent) effect to window if supported."""
        try:
            # Acrylic effect is platform-specific
            # QFluentWidgets handles this internally
            # We just need to ensure the window has the right attributes
            
            # Enable translucent background
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            logger.debug("Acrylic effect applied")
            
        except Exception as e:
            logger.warning(f"Failed to apply acrylic effect: {e}")
    
    def _connect_signals(self):
        """Connect signals between UI components and application logic."""
        try:
            # Connect settings page signals
            if isinstance(self.settings_page, SettingsPage):
                self.settings_page.theme_changed.connect(self.apply_theme)
                self.settings_page.settings_saved.connect(self._on_settings_saved)
            
            # Connect navigation signals
            # The FluentWindow handles navigation internally, but we can emit our own signals
            
            logger.debug("Signals connected")
            
        except Exception as e:
            logger.error(f"Failed to connect signals: {e}")
    
    def _on_settings_saved(self):
        """Handle settings saved event."""
        try:
            logger.info("Settings saved, some changes may require restart")
            
            # Show notification
            self.show_info(
                "Settings Saved",
                "Some changes may require restarting the application"
            )
            
        except Exception as e:
            logger.error(f"Error handling settings saved: {e}")
    
    def show_notification(
        self,
        title: str,
        content: str,
        duration: int = 3000,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT
    ):
        """
        Display a notification using InfoBar.
        
        Args:
            title: Notification title
            content: Notification content
            duration: Display duration in milliseconds (default: 3000)
            position: Position on screen (default: TOP_RIGHT)
        """
        try:
            InfoBar.success(
                title=title,
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )
            
            logger.debug(f"Notification shown: {title}")
            
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
    
    def show_error(
        self,
        title: str,
        content: str,
        duration: int = 5000,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT
    ):
        """
        Display an error notification using InfoBar.
        
        Args:
            title: Error title
            content: Error content
            duration: Display duration in milliseconds (default: 5000)
            position: Position on screen (default: TOP_RIGHT)
        """
        try:
            InfoBar.error(
                title=title,
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )
            
            logger.debug(f"Error notification shown: {title}")
            
        except Exception as e:
            logger.error(f"Failed to show error notification: {e}")
    
    def show_warning(
        self,
        title: str,
        content: str,
        duration: int = 4000,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT
    ):
        """
        Display a warning notification using InfoBar.
        
        Args:
            title: Warning title
            content: Warning content
            duration: Display duration in milliseconds (default: 4000)
            position: Position on screen (default: TOP_RIGHT)
        """
        try:
            InfoBar.warning(
                title=title,
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )
            
            logger.debug(f"Warning notification shown: {title}")
            
        except Exception as e:
            logger.error(f"Failed to show warning notification: {e}")
    
    def show_info(
        self,
        title: str,
        content: str,
        duration: int = 3000,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT
    ):
        """
        Display an info notification using InfoBar.
        
        Args:
            title: Info title
            content: Info content
            duration: Display duration in milliseconds (default: 3000)
            position: Position on screen (default: TOP_RIGHT)
        """
        try:
            InfoBar.info(
                title=title,
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )
            
            logger.debug(f"Info notification shown: {title}")
            
        except Exception as e:
            logger.error(f"Failed to show info notification: {e}")
    
    def set_boards_page(self, page: QWidget):
        """
        Set the boards page widget.
        
        Args:
            page: Boards page widget
        """
        if self.boards_page:
            # Remove old page
            index = self.stackedWidget.indexOf(self.boards_page)
            if index >= 0:
                self.stackedWidget.removeWidget(self.boards_page)
        
        self.boards_page = page
        # Note: With FluentWindow, we need to use addSubInterface
        # This method is for external page injection
    
    def set_chats_page(self, page: QWidget):
        """
        Set the private chats page widget.
        
        Args:
            page: Chats page widget
        """
        if self.chats_page:
            index = self.stackedWidget.indexOf(self.chats_page)
            if index >= 0:
                self.stackedWidget.removeWidget(self.chats_page)
        
        self.chats_page = page
    
    def set_peers_page(self, page: QWidget):
        """
        Set the peers page widget.
        
        Args:
            page: Peers page widget
        """
        if self.peers_page:
            index = self.stackedWidget.indexOf(self.peers_page)
            if index >= 0:
                self.stackedWidget.removeWidget(self.peers_page)
        
        self.peers_page = page
    
    def set_settings_page(self, page: QWidget):
        """
        Set the settings page widget.
        
        Args:
            page: Settings page widget
        """
        if self.settings_page:
            index = self.stackedWidget.indexOf(self.settings_page)
            if index >= 0:
                self.stackedWidget.removeWidget(self.settings_page)
        
        self.settings_page = page
    
    def set_about_page(self, page: QWidget):
        """
        Set the about page widget.
        
        Args:
            page: About page widget
        """
        if self.about_page:
            index = self.stackedWidget.indexOf(self.about_page)
            if index >= 0:
                self.stackedWidget.removeWidget(self.about_page)
        
        self.about_page = page
    
    def switch_to_boards(self):
        """Switch to boards page."""
        if self.boards_page:
            self.stackedWidget.setCurrentWidget(self.boards_page)
            self.navigation_changed.emit("boards")
    
    def switch_to_chats(self):
        """Switch to private chats page."""
        if self.chats_page:
            self.stackedWidget.setCurrentWidget(self.chats_page)
            self.navigation_changed.emit("chats")
    
    def switch_to_peers(self):
        """Switch to peers page."""
        if self.peers_page:
            self.stackedWidget.setCurrentWidget(self.peers_page)
            self.navigation_changed.emit("peers")
    
    def switch_to_settings(self):
        """Switch to settings page."""
        if self.settings_page:
            self.stackedWidget.setCurrentWidget(self.settings_page)
            self.navigation_changed.emit("settings")
    
    def switch_to_about(self):
        """Switch to about page."""
        if self.about_page:
            self.stackedWidget.setCurrentWidget(self.about_page)
            self.navigation_changed.emit("about")
    
    def _handle_error_notification(
        self,
        title: str,
        content: str,
        severity: ErrorSeverity
    ):
        """
        Handle error notifications from error handler.
        
        Args:
            title: Error title
            content: Error content
            severity: Error severity level
        """
        try:
            # Map severity to InfoBar method
            if severity == ErrorSeverity.CRITICAL or severity == ErrorSeverity.ERROR:
                self.show_error(title, content, duration=5000)
            elif severity == ErrorSeverity.WARNING:
                self.show_warning(title, content, duration=4000)
            else:
                self.show_info(title, content, duration=3000)
                
        except Exception as e:
            logger.error(f"Failed to handle error notification: {e}")
    
    def _handle_notification(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        priority: NotificationPriority
    ):
        """
        Handle notifications from notification manager.
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Notification priority
        """
        try:
            # Determine duration based on priority
            duration_map = {
                NotificationPriority.LOW: 2000,
                NotificationPriority.NORMAL: 3000,
                NotificationPriority.HIGH: 4000,
                NotificationPriority.URGENT: 5000
            }
            duration = duration_map.get(priority, 3000)
            
            # Map notification type to InfoBar method
            if notification_type == NotificationType.ERROR:
                self.show_error(title, message, duration=duration)
            elif notification_type == NotificationType.CONNECTION:
                # Connection events are low priority, use info
                self.show_info(title, message, duration=duration)
            elif notification_type == NotificationType.MESSAGE:
                # New messages are important, use success
                self.show_notification(title, message, duration=duration)
            elif notification_type == NotificationType.POST:
                # New posts use info
                self.show_info(title, message, duration=duration)
            elif notification_type == NotificationType.MODERATION:
                # Moderation actions use warning
                self.show_warning(title, message, duration=duration)
            elif notification_type == NotificationType.SYSTEM:
                # System notifications use info
                self.show_info(title, message, duration=duration)
            else:
                # Default to info
                self.show_info(title, message, duration=duration)
                
        except Exception as e:
            logger.error(f"Failed to handle notification: {e}")
    
    def closeEvent(self, event):
        """
        Handle window close event.
        
        Cleanup resources before closing.
        
        Args:
            event: Close event
        """
        try:
            # Stop asyncio event loop
            self.event_loop.stop()
            
            logger.info("Main window closing")
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during window close: {e}")
            event.accept()
