"""
Settings Page for P2P Encrypted BBS Application

Provides configuration interface for network, security, storage, UI, and other settings.
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog
)
from qfluentwidgets import (
    ScrollArea,
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
from qfluentwidgets import LineEdit, CaptionLabel, PrimaryPushButton
from PySide6.QtWidgets import QPushButton

from config.config_manager import ConfigManager
from core.db_manager import DBManager
from models.database import Profile
from ui.theme_utils import (
    get_title_styles, GhostTheme, get_page_margins, SPACING_MEDIUM, SPACING_LARGE
)


logger = logging.getLogger(__name__)


class DummyConfigItem(QObject):
    """Dummy config item for use with qfluentwidgets setting cards that require configItem."""
    
    valueChanged = Signal()
    
    def __init__(self, value=None, options=None, range_tuple=None):
        super().__init__()
        self.value = value
        self.options = options or []
        self.range = range_tuple or (0, 100)
        self.restart = False  # Add missing restart attribute


class SettingsHeaderWidget(QWidget):
    """Header widget for profile display name and shared folder.

    Historically these values lived in the YAML config only. With the
    introduction of Profiles, the authoritative source is now the active
    Profile row in the database. We still fall back to config values for
    backwards compatibility if the profile fields are empty.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        profile: Profile,
        db_manager: DBManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.profile = profile
        self.db_manager = db_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Avatar / display name (from profile, with config fallback)
        self.avatar_label = QLabel("Display name:")
        self.avatar_input = LineEdit()
        name = (self.profile.display_name or "").strip()
        if not name:
            try:
                ui_cfg = self.config_manager.get_ui_config()
                name = getattr(ui_cfg, "avatar_name", "") or ""
            except Exception:  # noqa: BLE001
                name = ""
        self.avatar_input.setText(name)

        layout.addWidget(self.avatar_label)
        layout.addWidget(self.avatar_input, stretch=1)

        # Shared folder selector (from profile.shared_folder with config fallback)
        self.shared_label = QLabel("Shared folder:")
        self.shared_path = CaptionLabel("")
        shared_folder = (self.profile.shared_folder or "").strip()
        if not shared_folder:
            try:
                cfg_path = self.config_manager.get_config("storage").get(
                    "shared_folder", ""
                )
                shared_folder = str(cfg_path) if cfg_path else ""
            except Exception:  # noqa: BLE001
                shared_folder = ""
        self.shared_path.setText(shared_folder)

        # Browse button for choosing folder
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("PrimaryPushButton")
        self.browse_btn.clicked.connect(self._on_browse_clicked)

        layout.addWidget(self.shared_label)
        layout.addWidget(self.shared_path, stretch=2)
        layout.addWidget(self.browse_btn)

    def set_shared_path(self, path: str):
        self.shared_path.setText(path)

    def get_avatar_name(self) -> str:
        return self.avatar_input.text().strip()

    def get_shared_folder(self) -> str:
        return self.shared_path.text().strip()

    def _on_browse_clicked(self):
        path = QFileDialog.getExistingDirectory(self, "Select shared folder")
        if path:
            self.set_shared_path(path)


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
    
    def __init__(
        self,
        config_manager: ConfigManager,
        profile: Profile,
        db_manager: DBManager,
        parent=None,
    ):
        """
        Initialize settings page.
        
        Args:
            config_manager: Configuration manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.profile = profile
        self.db_manager = db_manager
        
        # Create main widget and layout
        self.view = QWidget()
        self.vBoxLayout = QVBoxLayout(self.view)
        margins = get_page_margins()
        self.vBoxLayout.setContentsMargins(*margins)
        self.vBoxLayout.setSpacing(SPACING_MEDIUM)

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
        # Apply dark purple theme stylesheet for Settings page
        self.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QWidget#view {{
                background: transparent;
            }}
            QLabel[objectName="titleLabel"] {{
                {get_title_styles()}
            }}
            /* Primary buttons - using centralized theme */
            QPushButton[objectName="PrimaryPushButton"],
            PrimaryPushButton {{
                background-color: {GhostTheme.get_purple_primary()};
                color: {GhostTheme.get_text_primary()};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }}
            QPushButton[objectName="PrimaryPushButton"]:hover,
            PrimaryPushButton:hover {{
                background-color: {GhostTheme.get_purple_secondary()};
            }}
            QPushButton[objectName="PrimaryPushButton"]:pressed,
            PrimaryPushButton:pressed {{
                background-color: {GhostTheme.get_purple_tertiary()};
            }}
            /* Selection and focus */
            QListView::item:selected {{
                background-color: {GhostTheme.get_purple_primary()};
                color: {GhostTheme.get_text_primary()};
            }}
            QComboBox::item:selected {{
                background-color: {GhostTheme.get_purple_primary()};
            }}
            /* ComboBox dropdown */
            ComboBox QAbstractItemView {{
                selection-background-color: {GhostTheme.get_purple_primary()};
            }}
            /* Slider styling */
            Slider::groove:horizontal {{
                background: {GhostTheme.get_tertiary_background()};
            }}
            Slider::handle:horizontal {{
                background: {GhostTheme.get_purple_primary()};
            }}
            Slider::handle:horizontal:hover {{
                background: {GhostTheme.get_purple_secondary()};
            }}
            Slider::sub-page:horizontal {{
                background: {GhostTheme.get_purple_primary()};
            }}
        """)
        
        # Add title and save button in header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Settings")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(get_title_styles())
        
        self.save_button = PrimaryPushButton("Save Settings")
        self.save_button.setFixedWidth(150)
        self.save_button.clicked.connect(self._on_save_settings)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.save_button)
        
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        self.vBoxLayout.addWidget(header_widget)
        
        # Add avatar and shared folder header widget (profile-backed)
        try:
            header = SettingsHeaderWidget(
                self.config_manager,
                self.profile,
                self.db_manager,
                parent=self.view,
            )
            self.vBoxLayout.addWidget(header)
            self._settings_header = header
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to create settings header: {e}")
            self._settings_header = None
        
        # Create setting groups
        self._create_ui_settings()
        self._create_network_settings()
        self._create_security_settings()
        self._create_storage_settings()
        self._create_sync_settings()
        
        # Add stretch to push everything to the top
        self.vBoxLayout.addStretch(1)
    
    def _create_ui_settings(self):
        """Create UI settings group."""
        ui_config = self.config_manager.get_ui_config()

        """ # Create group container
        self.ui_group = SettingCardGroup("User Interface", self.view)

        # Theme selector
        theme_config_item = DummyConfigItem(value=ui_config.theme.lower(), options=["dark", "light", "auto"])
        self.theme_card = ComboBoxSettingCard(
            configItem=theme_config_item,
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
        font_size_config_item = DummyConfigItem(value=ui_config.font_size, range_tuple=(8, 24))
        self.font_size_card = RangeSettingCard(
            configItem=font_size_config_item,
            icon=FluentIcon.FONT,
            title="Font Size",
            content="Adjust text size",
            parent=self.ui_group
        )
        self.font_size_card.slider.setRange(8, 24)
        self.font_size_card.slider.setValue(ui_config.font_size)
        self.font_size_card.valueLabel.setText(str(ui_config.font_size))
        self.font_size_card.slider.valueChanged.connect(self._on_font_size_changed)

        # Acrylic effect toggle
        acrylic_config_item = DummyConfigItem(value=ui_config.enable_acrylic)
        self.acrylic_card = SwitchSettingCard(
            icon=FluentIcon.TRANSPARENT,
            title="Acrylic Effect",
            content="Enable translucent window effect (requires restart)",
            configItem=acrylic_config_item,
            parent=self.ui_group
        )
        self.acrylic_card.switchButton.setChecked(ui_config.enable_acrylic)

        # Add cards to group
        self.ui_group.addSettingCard(self.theme_card)
        self.ui_group.addSettingCard(self.font_size_card)
        self.ui_group.addSettingCard(self.acrylic_card)

        self.vBoxLayout.addWidget(self.ui_group)
 """    
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
        port_config_item = DummyConfigItem(value=network_config.listen_port, range_tuple=(1024, 65535))
        self.port_card = RangeSettingCard(
            configItem=port_config_item,
            icon=FluentIcon.CONNECT,
            title="Listen Port",
            content="Network port for incoming connections",
            parent=self.network_group
        )
        self.port_card.slider.valueChanged.connect(
            lambda v: self.port_card.valueLabel.setText(str(v))
        )
        
        # Max peers
        max_peers_config_item = DummyConfigItem(value=network_config.max_peers, range_tuple=(1, 100))
        self.max_peers_card = RangeSettingCard(
            configItem=max_peers_config_item,
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
            icon=FluentIcon.DOWNLOAD,
            title="Storage Usage",
            content="Calculating...",
            parent=self.storage_group
        )
        self.storage_usage_card.button.clicked.connect(self._update_storage_usage)
        self._update_storage_usage()  # Initial calculation
        
        # Max attachment size
        max_attachment_config_item = DummyConfigItem(value=storage_config.max_attachment_size, range_tuple=(1, 100))
        self.max_attachment_card = RangeSettingCard(
            configItem=max_attachment_config_item,
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
        cache_size_config_item = DummyConfigItem(value=storage_config.cache_size, range_tuple=(50, 1000))
        self.cache_size_card = RangeSettingCard(
            configItem=cache_size_config_item,
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
        sync_interval_config_item = DummyConfigItem(value=sync_config.interval, range_tuple=(1, 60))
        self.sync_interval_card = RangeSettingCard(
            configItem=sync_interval_config_item,
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
        batch_size_config_item = DummyConfigItem(value=sync_config.batch_size, range_tuple=(10, 500))
        self.batch_size_card = RangeSettingCard(
            configItem=batch_size_config_item,
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
    

    
    def _on_theme_changed(self, theme_text: str):
        """
        Handle theme change and apply immediately.
        
        Args:
            theme_text: Theme name ("Dark", "Light", or "Auto")
        """
        try:
            if theme_text == "Dark":
                GhostTheme.apply_theme(Theme.DARK)
                self.theme_changed.emit(Theme.DARK)
            elif theme_text == "Light":
                GhostTheme.apply_theme(Theme.LIGHT)
                self.theme_changed.emit(Theme.LIGHT)
            else:
                # Auto theme - use system default, for now default to dark
                GhostTheme.apply_theme(Theme.DARK)
                self.theme_changed.emit(Theme.DARK)
            
            logger.info(f"Theme changed to: {theme_text}")
            
        except Exception as e:
            logger.error(f"Failed to change theme: {e}")
    
    def _on_font_size_changed(self, value: int):
        """
        Handle font size change and apply immediately.
        
        Args:
            value: New font size
        """
        try:
            self.font_size_card.valueLabel.setText(str(value))
            GhostTheme.set_font_size(value)
            logger.info(f"Font size changed to: {value}")
        except Exception as e:
            logger.error(f"Failed to change font size: {e}")

    def _on_save_settings(self):
        """Save all settings to configuration and active profile.

        Profile-backed fields:
            - display_name
            - shared_folder

        Other fields remain in the YAML config via ConfigManager.
        """
        try:
            # Avatar / display name and shared folder (profile-backed)
            if hasattr(self, "_settings_header") and self._settings_header:
                avatar = self._settings_header.get_avatar_name()
                shared = self._settings_header.get_shared_folder()

                # Update profile object
                if avatar:
                    self.profile.display_name = avatar
                if shared:
                    self.profile.shared_folder = shared

                # Persist profile to DB
                try:
                    self.db_manager.update_profile(self.profile)
                    logger.info(
                        "Updated profile %s (display_name=%r, shared_folder=%r)",
                        getattr(self.profile, "id", "<unknown>"),
                        self.profile.display_name,
                        self.profile.shared_folder,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Failed to update profile: {exc}")

                # Also mirror into config for backward compatibility
                if avatar:
                    self.config_manager.set_config("ui", "avatar_name", avatar)
                if shared:
                    self.config_manager.set_config("storage", "shared_folder", shared)

            # Update UI settings (if they exist)
            if hasattr(self, 'theme_card'):
                theme_text = self.theme_card.comboBox.currentText().lower()
                self.config_manager.set_config("ui", "theme", theme_text)
            if hasattr(self, 'font_size_card'):
                self.config_manager.set_config(
                    "ui", "font_size", self.font_size_card.slider.value()
                )
            if hasattr(self, 'acrylic_card'):
                self.config_manager.set_config(
                    "ui",
                    "enable_acrylic",
                    self.acrylic_card.switchButton.isChecked(),
                )

            # Update network settings
            self.config_manager.set_config(
                "network", "enable_mdns", self.mdns_card.switchButton.isChecked()
            )
            self.config_manager.set_config(
                "network", "enable_dht", self.dht_card.switchButton.isChecked()
            )
            self.config_manager.set_config(
                "network", "listen_port", self.port_card.slider.value()
            )
            self.config_manager.set_config(
                "network", "max_peers", self.max_peers_card.slider.value()
            )

            # Update security settings
            self.config_manager.set_config(
                "security",
                "require_signature_verification",
                self.signature_verification_card.switchButton.isChecked(),
            )

            # Update storage settings
            max_attachment_mb = self.max_attachment_card.slider.value()
            max_attachment_bytes = max_attachment_mb * 1024 * 1024
            self.config_manager.set_config(
                "storage", "max_attachment_size", max_attachment_bytes
            )

            cache_size_gb = self.cache_size_card.slider.value()
            cache_size_bytes = max(0, cache_size_gb) * 1024 * 1024 * 1024
            self.config_manager.set_config(
                "storage", "cache_size", cache_size_bytes
            )

            # Update sync settings
            self.config_manager.set_config(
                "sync", "interval", self.sync_interval_card.slider.value()
            )
            self.config_manager.set_config(
                "sync", "batch_size", self.batch_size_card.slider.value()
            )

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
                parent=self,
            )

            logger.info("Settings saved successfully")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to save settings: {e}")

            InfoBar.error(
                title="Save Failed",
                content=f"Failed to save settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self,
            )
    
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
    
    # NOTE: Legacy duplicate _on_save_settings implementation removed.
    # All save operations are handled by the main _on_save_settings method
    # defined earlier in this class, which also persists profile data.
    
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
