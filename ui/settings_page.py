"""
Settings Page for P2P Encrypted BBS Application

Provides configuration interface for network, security, storage, UI, and other settings.
"""

import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog
)
from qfluentwidgets import (
    ScrollArea,
    ExpandLayout,
    SettingCardGroup,
    SwitchSettingCard,
    ComboBoxSettingCard,
    RangeSettingCard,
    PushSettingCard,
    FluentIcon,
    Theme,
    InfoBar,
    InfoBarPosition
)

from config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class SettingsPage(ScrollArea):
    """
    Settings page with configuration options.
    
    Provides settings for:
    - Network (port, mDNS, DHT, bootstrap nodes)
    - Security (keystore management)
    - Storage (database path, cache size)
    - UI (theme, font size, acrylic effects)
    - Synchronization (interval, batch size)
    
    Signals:
        theme_changed: Emitted when theme setting is changed
        settings_saved: Emitted when settings are saved
    """
    
    # Qt signals
    theme_changed = Signal(Theme)
    settings_saved = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize settings page.
        
        Args:
            config_manager: Configuration manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        
        # Create main widget and layout
        self.view = QWidget()
        self.vBoxLayout = ExpandLayout(self.view)
        
        # Setup UI
        self._setup_ui()
        
        # Configure scroll area
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("settingsPage")
        
        # Apply stylesheet
        self.view.setObjectName("view")
        self.setStyleSheet("QScrollArea {border: none; background: transparent}")
        self.view.setStyleSheet("QWidget#view {background: transparent}")
        
        logger.info("Settings page initialized")
    
    def _setup_ui(self):
        """Set up the settings UI with all configuration cards."""
        # Add title
        title_label = QLabel("Settings")
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; margin: 20px 0;")
        self.vBoxLayout.addWidget(title_label)
        
        # Create setting groups
        self._create_ui_settings()
        self._create_network_settings()
        self._create_security_settings()
        self._create_storage_settings()
        self._create_sync_settings()
        self._create_about_section()
        
        # Add save button at the bottom
        self._create_save_button()
        
        # Add stretch to push everything to the top
        self.vBoxLayout.addStretch(1)
    
    def _create_ui_settings(self):
        """Create UI settings group."""
        ui_config = self.config_manager.get_ui_config()
        
        self.ui_group = SettingCardGroup("User Interface", self.view)
        
        # Theme selector
        self.theme_card = ComboBoxSettingCard(
            configItem=None,
            icon=FluentIcon.BRUSH,
            title="Theme",
            content="Choose application theme",
            texts=["Dark", "Light", "Auto"],
            parent=self.ui_group
        )
        
        # Set current theme
        current_theme = ui_config.theme.capitalize()
        if current_theme in ["Dark", "Light"]:
            self.theme_card.comboBox.setCurrentText(current_theme)
        else:
            self.theme_card.comboBox.setCurrentText("Dark")
        
        # Connect theme change signal
        self.theme_card.comboBox.currentTextChanged.connect(self._on_theme_changed)
        
        # Font size slider
        self.font_size_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.FONT,
            title="Font Size",
            content="Adjust text size",
            parent=self.ui_group
        )
        self.font_size_card.slider.setRange(8, 24)
        self.font_size_card.slider.setValue(ui_config.font_size)
        self.font_size_card.valueLabel.setText(str(ui_config.font_size))
        self.font_size_card.slider.valueChanged.connect(
            lambda v: self.font_size_card.valueLabel.setText(str(v))
        )
        
        # Acrylic effect toggle
        self.acrylic_card = SwitchSettingCard(
            icon=FluentIcon.TRANSPARENT,
            title="Acrylic Effect",
            content="Enable translucent window effect (requires restart)",
            configItem=None,
            parent=self.ui_group
        )
        self.acrylic_card.switchButton.setChecked(ui_config.enable_acrylic)
        
        # Add cards to group
        self.ui_group.addSettingCard(self.theme_card)
        self.ui_group.addSettingCard(self.font_size_card)
        self.ui_group.addSettingCard(self.acrylic_card)
        
        self.vBoxLayout.addWidget(self.ui_group)
    
    def _create_network_settings(self):
        """Create network settings group."""
        network_config = self.config_manager.get_network_config()
        
        self.network_group = SettingCardGroup("Network", self.view)
        
        # mDNS toggle
        self.mdns_card = SwitchSettingCard(
            icon=FluentIcon.WIFI,
            title="Enable mDNS Discovery",
            content="Automatically discover peers on local network",
            configItem=None,
            parent=self.network_group
        )
        self.mdns_card.switchButton.setChecked(network_config.enable_mdns)
        
        # DHT toggle
        self.dht_card = SwitchSettingCard(
            icon=FluentIcon.GLOBE,
            title="Enable DHT Discovery",
            content="Discover peers globally via distributed hash table",
            configItem=None,
            parent=self.network_group
        )
        self.dht_card.switchButton.setChecked(network_config.enable_dht)
        
        # Listen port
        self.port_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.CONNECT,
            title="Listen Port",
            content="Network port for incoming connections",
            parent=self.network_group
        )
        self.port_card.slider.setRange(1024, 65535)
        self.port_card.slider.setValue(network_config.listen_port)
        self.port_card.valueLabel.setText(str(network_config.listen_port))
        self.port_card.slider.valueChanged.connect(
            lambda v: self.port_card.valueLabel.setText(str(v))
        )
        
        # Max peers
        self.max_peers_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.PEOPLE,
            title="Maximum Peers",
            content="Maximum number of simultaneous peer connections",
            parent=self.network_group
        )
        self.max_peers_card.slider.setRange(1, 200)
        self.max_peers_card.slider.setValue(network_config.max_peers)
        self.max_peers_card.valueLabel.setText(str(network_config.max_peers))
        self.max_peers_card.slider.valueChanged.connect(
            lambda v: self.max_peers_card.valueLabel.setText(str(v))
        )
        
        # Bootstrap nodes
        self.bootstrap_card = PushSettingCard(
            text="Edit",
            icon=FluentIcon.CLOUD,
            title="Bootstrap Nodes",
            content=f"{len(network_config.bootstrap_nodes)} nodes configured",
            parent=self.network_group
        )
        self.bootstrap_card.button.clicked.connect(self._on_edit_bootstrap_nodes)
        
        # Add cards to group
        self.network_group.addSettingCard(self.mdns_card)
        self.network_group.addSettingCard(self.dht_card)
        self.network_group.addSettingCard(self.port_card)
        self.network_group.addSettingCard(self.max_peers_card)
        self.network_group.addSettingCard(self.bootstrap_card)
        
        self.vBoxLayout.addWidget(self.network_group)
    
    def _create_security_settings(self):
        """Create security settings group."""
        security_config = self.config_manager.get_security_config()
        
        self.security_group = SettingCardGroup("Security", self.view)
        
        # Export identity button
        self.export_identity_card = PushSettingCard(
            text="Export",
            icon=FluentIcon.SAVE,
            title="Export Identity",
            content="Backup your cryptographic identity",
            parent=self.security_group
        )
        self.export_identity_card.button.clicked.connect(self._on_export_identity)
        
        # Import identity button
        self.import_identity_card = PushSettingCard(
            text="Import",
            icon=FluentIcon.FOLDER,
            title="Import Identity",
            content="Restore identity from backup file",
            parent=self.security_group
        )
        self.import_identity_card.button.clicked.connect(self._on_import_identity)
        
        # Signature verification toggle
        self.signature_verification_card = SwitchSettingCard(
            icon=FluentIcon.CERTIFICATE,
            title="Require Signature Verification",
            content="Reject posts and messages with invalid signatures",
            configItem=None,
            parent=self.security_group
        )
        self.signature_verification_card.switchButton.setChecked(
            security_config.require_signature_verification
        )
        
        # Add cards to group
        self.security_group.addSettingCard(self.export_identity_card)
        self.security_group.addSettingCard(self.import_identity_card)
        self.security_group.addSettingCard(self.signature_verification_card)
        
        self.vBoxLayout.addWidget(self.security_group)
    
    def _create_storage_settings(self):
        """Create storage settings group."""
        storage_config = self.config_manager.get_storage_config()
        
        self.storage_group = SettingCardGroup("Storage", self.view)
        
        # Database path display
        self.db_path_card = PushSettingCard(
            text="Open",
            icon=FluentIcon.FOLDER,
            title="Database Location",
            content=str(self.config_manager.expand_path(storage_config.db_path)),
            parent=self.storage_group
        )
        self.db_path_card.button.clicked.connect(self._on_open_db_location)
        
        # Storage usage display
        self.storage_usage_card = PushSettingCard(
            text="Refresh",
            icon=FluentIcon.STORAGE,
            title="Storage Usage",
            content="Calculating...",
            parent=self.storage_group
        )
        self.storage_usage_card.button.clicked.connect(self._update_storage_usage)
        self._update_storage_usage()  # Initial calculation
        
        # Max attachment size
        self.max_attachment_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.DOCUMENT,
            title="Max Attachment Size (MB)",
            content="Maximum file size for attachments",
            parent=self.storage_group
        )
        self.max_attachment_card.slider.setRange(1, 100)
        current_mb = storage_config.max_attachment_size // (1024 * 1024)
        self.max_attachment_card.slider.setValue(current_mb)
        self.max_attachment_card.valueLabel.setText(f"{current_mb} MB")
        self.max_attachment_card.slider.valueChanged.connect(
            lambda v: self.max_attachment_card.valueLabel.setText(f"{v} MB")
        )
        
        # Cache size
        self.cache_size_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.FOLDER,
            title="Cache Size (GB)",
            content="Maximum cache size for attachments",
            parent=self.storage_group
        )
        self.cache_size_card.slider.setRange(1, 10)
        current_gb = storage_config.cache_size // (1024 * 1024 * 1024)
        self.cache_size_card.slider.setValue(current_gb)
        self.cache_size_card.valueLabel.setText(f"{current_gb} GB")
        self.cache_size_card.slider.valueChanged.connect(
            lambda v: self.cache_size_card.valueLabel.setText(f"{v} GB")
        )
        
        # Add cards to group
        self.storage_group.addSettingCard(self.db_path_card)
        self.storage_group.addSettingCard(self.storage_usage_card)
        self.storage_group.addSettingCard(self.max_attachment_card)
        self.storage_group.addSettingCard(self.cache_size_card)
        
        self.vBoxLayout.addWidget(self.storage_group)
    
    def _create_sync_settings(self):
        """Create synchronization settings group."""
        sync_config = self.config_manager.get_sync_config()
        
        self.sync_group = SettingCardGroup("Synchronization", self.view)
        
        # Sync interval
        self.sync_interval_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.SYNC,
            title="Sync Interval (seconds)",
            content="How often to synchronize with peers",
            parent=self.sync_group
        )
        self.sync_interval_card.slider.setRange(10, 300)
        self.sync_interval_card.slider.setValue(sync_config.interval)
        self.sync_interval_card.valueLabel.setText(f"{sync_config.interval}s")
        self.sync_interval_card.slider.valueChanged.connect(
            lambda v: self.sync_interval_card.valueLabel.setText(f"{v}s")
        )
        
        # Batch size
        self.batch_size_card = RangeSettingCard(
            configItem=None,
            icon=FluentIcon.DOWNLOAD,
            title="Batch Size",
            content="Number of posts to sync at once",
            parent=self.sync_group
        )
        self.batch_size_card.slider.setRange(10, 200)
        self.batch_size_card.slider.setValue(sync_config.batch_size)
        self.batch_size_card.valueLabel.setText(str(sync_config.batch_size))
        self.batch_size_card.slider.valueChanged.connect(
            lambda v: self.batch_size_card.valueLabel.setText(str(v))
        )
        
        # Add cards to group
        self.sync_group.addSettingCard(self.sync_interval_card)
        self.sync_group.addSettingCard(self.batch_size_card)
        
        self.vBoxLayout.addWidget(self.sync_group)
    
    def _create_about_section(self):
        """Create about section."""
        self.about_group = SettingCardGroup("About", self.view)
        
        # Application info
        from qfluentwidgets import HyperlinkCard
        
        self.app_info_card = PushSettingCard(
            text="",
            icon=FluentIcon.INFO,
            title="P2P Encrypted BBS",
            content="Version 1.0.0 - A decentralized bulletin board system",
            parent=self.about_group
        )
        self.app_info_card.button.hide()  # No button needed
        
        # License info
        self.license_card = PushSettingCard(
            text="",
            icon=FluentIcon.CERTIFICATE,
            title="License",
            content="Open Source - MIT License",
            parent=self.about_group
        )
        self.license_card.button.hide()
        
        # Add cards to group
        self.about_group.addSettingCard(self.app_info_card)
        self.about_group.addSettingCard(self.license_card)
        
        self.vBoxLayout.addWidget(self.about_group)
    
    def _create_save_button(self):
        """Create save button at the bottom."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(20, 20, 20, 20)
        
        from qfluentwidgets import PrimaryPushButton
        
        self.save_button = PrimaryPushButton("Save Settings")
        self.save_button.setFixedWidth(200)
        self.save_button.clicked.connect(self._on_save_settings)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch(1)
        
        self.vBoxLayout.addWidget(button_widget)
    
    def _on_theme_changed(self, theme_text: str):
        """
        Handle theme change.
        
        Args:
            theme_text: Theme name ("Dark", "Light", or "Auto")
        """
        try:
            if theme_text == "Dark":
                self.theme_changed.emit(Theme.DARK)
            elif theme_text == "Light":
                self.theme_changed.emit(Theme.LIGHT)
            else:
                # Auto theme - use system default
                # For now, default to dark
                self.theme_changed.emit(Theme.DARK)
            
            logger.info(f"Theme changed to: {theme_text}")
            
        except Exception as e:
            logger.error(f"Failed to change theme: {e}")
    
    def _update_storage_usage(self):
        """Update storage usage display."""
        try:
            storage_config = self.config_manager.get_storage_config()
            db_path = self.config_manager.expand_path(storage_config.db_path)
            
            # Calculate database size
            total_size = 0
            if db_path.exists():
                total_size += db_path.stat().st_size
            
            # Calculate cache size if cache directory exists
            cache_dir = db_path.parent.parent / "cache"
            if cache_dir.exists():
                for file in cache_dir.rglob("*"):
                    if file.is_file():
                        total_size += file.stat().st_size
            
            # Format size
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
            
            self.storage_usage_card.contentLabel.setText(f"Using {size_str}")
            
            logger.debug(f"Storage usage: {size_str}")
            
        except Exception as e:
            logger.error(f"Failed to calculate storage usage: {e}")
            self.storage_usage_card.contentLabel.setText("Unable to calculate")
    
    def _on_edit_bootstrap_nodes(self):
        """Handle edit bootstrap nodes button click."""
        try:
            from qfluentwidgets import MessageBox, TextEdit
            
            network_config = self.config_manager.get_network_config()
            
            # Create dialog
            dialog = MessageBox(
                "Bootstrap Nodes",
                "Enter bootstrap node addresses (one per line):\nFormat: hostname:port",
                self
            )
            
            # Add text edit for bootstrap nodes
            text_edit = TextEdit()
            text_edit.setPlaceholderText("bootstrap1.example.com:8468\nbootstrap2.example.com:8468")
            text_edit.setPlainText("\n".join(network_config.bootstrap_nodes))
            text_edit.setMinimumHeight(150)
            dialog.textLayout.addWidget(text_edit)
            
            if dialog.exec():
                # Parse bootstrap nodes
                nodes_text = text_edit.toPlainText().strip()
                if nodes_text:
                    nodes = [line.strip() for line in nodes_text.split("\n") if line.strip()]
                    self.config_manager.set_config("network", "bootstrap_nodes", nodes)
                    self.bootstrap_card.contentLabel.setText(f"{len(nodes)} nodes configured")
                    
                    InfoBar.success(
                        title="Bootstrap Nodes Updated",
                        content=f"Configured {len(nodes)} bootstrap nodes",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    
                    logger.info(f"Updated bootstrap nodes: {len(nodes)} nodes")
        
        except Exception as e:
            logger.error(f"Failed to edit bootstrap nodes: {e}")
    
    def _on_save_settings(self):
        """Save all settings to configuration."""
        try:
            # Update UI settings
            theme_text = self.theme_card.comboBox.currentText().lower()
            self.config_manager.set_config("ui", "theme", theme_text)
            self.config_manager.set_config("ui", "font_size", self.font_size_card.slider.value())
            self.config_manager.set_config("ui", "enable_acrylic", self.acrylic_card.switchButton.isChecked())
            
            # Update network settings
            self.config_manager.set_config("network", "enable_mdns", self.mdns_card.switchButton.isChecked())
            self.config_manager.set_config("network", "enable_dht", self.dht_card.switchButton.isChecked())
            self.config_manager.set_config("network", "listen_port", self.port_card.slider.value())
            self.config_manager.set_config("network", "max_peers", self.max_peers_card.slider.value())
            
            # Update security settings
            self.config_manager.set_config(
                "security",
                "require_signature_verification",
                self.signature_verification_card.switchButton.isChecked()
            )
            
            # Update storage settings
            max_attachment_mb = self.max_attachment_card.slider.value()
            max_attachment_bytes = max_attachment_mb * 1024 * 1024
            self.config_manager.set_config("storage", "max_attachment_size", max_attachment_bytes)
            
            cache_size_gb = self.cache_size_card.slider.value()
            cache_size_bytes = cache_size_gb * 1024 * 1024 * 1024
            self.config_manager.set_config("storage", "cache_size", cache_size_bytes)
            
            # Update sync settings
            self.config_manager.set_config("sync", "interval", self.sync_interval_card.slider.value())
            self.config_manager.set_config("sync", "batch_size", self.batch_size_card.slider.value())
            
            # Save to file
            self.config_manager.save_config()
            
            # Emit signal
            self.settings_saved.emit()
            
            # Show success notification
            InfoBar.success(
                title="Settings Saved",
                content="Configuration has been saved successfully",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
            
            logger.info("Settings saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            
            InfoBar.error(
                title="Save Failed",
                content=f"Failed to save settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
    
    def _on_export_identity(self):
        """Handle export identity button click."""
        try:
            # Open file dialog to choose export location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Identity",
                str(Path.home() / "bbs_identity.enc"),
                "Identity Files (*.enc);;All Files (*)"
            )
            
            if file_path:
                # TODO: Implement identity export
                logger.info(f"Export identity to: {file_path}")
                
                InfoBar.info(
                    title="Export Identity",
                    content="Identity export feature coming soon",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
        
        except Exception as e:
            logger.error(f"Failed to export identity: {e}")
    
    def _on_import_identity(self):
        """Handle import identity button click."""
        try:
            # Open file dialog to choose import file
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Identity",
                str(Path.home()),
                "Identity Files (*.enc);;All Files (*)"
            )
            
            if file_path:
                # TODO: Implement identity import
                logger.info(f"Import identity from: {file_path}")
                
                InfoBar.info(
                    title="Import Identity",
                    content="Identity import feature coming soon",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
        
        except Exception as e:
            logger.error(f"Failed to import identity: {e}")
    
    def _on_open_db_location(self):
        """Handle open database location button click."""
        try:
            storage_config = self.config_manager.get_storage_config()
            db_path = self.config_manager.expand_path(storage_config.db_path)
            db_dir = db_path.parent
            
            # Open directory in file explorer
            import subprocess
            import sys
            
            if sys.platform == 'win32':
                subprocess.run(['explorer', str(db_dir)])
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(db_dir)])
            else:
                subprocess.run(['xdg-open', str(db_dir)])
            
            logger.info(f"Opened database location: {db_dir}")
            
        except Exception as e:
            logger.error(f"Failed to open database location: {e}")
