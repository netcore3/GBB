"""
Peer Monitor Page for P2P Encrypted BBS

Displays list of discovered peers with connection status, trust, and ban status.
Provides buttons to trust, ban, or start chat with peers.
"""

import logging
from typing import Optional, Dict
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from qfluentwidgets import (
    ScrollArea,
    CardWidget,
    PrimaryPushButton,
    FluentIcon,
    MessageBox,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    TableWidget,
    ToolButton,
    InfoBar,
    InfoBarPosition,
    isDarkTheme,
    SwitchButton
)

from core.network_manager import NetworkManager, PeerConnection, ConnectionState
from core.db_manager import DBManager
from models.database import PeerInfo
from ui.theme_utils import GhostTheme, get_page_margins, get_card_margins, SPACING_MEDIUM, SPACING_LARGE
from ui.hover_card import apply_hover_glow


logger = logging.getLogger(__name__)


class PeerMonitorPage(ScrollArea):
    """
    Page displaying list of discovered peers.
    
    Shows peer information including:
    - Peer ID
    - Connection status (connected/disconnected)
    - Last seen timestamp
    - Trust status
    - Ban status
    
    Provides actions:
    - Trust peer
    - Ban peer
    - Start chat with peer
    
    Signals:
        peer_trusted: Emitted when a peer is trusted (peer_id)
        peer_banned: Emitted when a peer is banned (peer_id)
        chat_requested: Emitted when user wants to chat with peer (peer_id)
    """
    
    peer_trusted = Signal(str)  # Emits peer_id
    peer_banned = Signal(str)  # Emits peer_id
    chat_requested = Signal(str)  # Emits peer_id
    
    def __init__(
        self,
        network_manager: Optional[NetworkManager] = None,
        db_manager: Optional[DBManager] = None,
        parent=None,
        moderation_manager=None,
        identity: Optional[str] = None
    ):
        """
        Initialize peer monitor page.
        
        Args:
            network_manager: NetworkManager instance for connection status
            db_manager: DBManager instance for peer info
            parent: Parent widget
            moderation_manager: Optional ModerationManager instance (for compatibility)
            identity: Optional peer identity (for compatibility)
        """
        super().__init__(parent)
        
        self.network_manager = network_manager
        self.db_manager = db_manager
        self.moderation_manager = moderation_manager
        self.identity = identity
        
        # Setup UI
        self._setup_ui()
        
        # Setup refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_peers)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Initial load
        self.refresh_peers()
        
        logger.info("PeerMonitorPage initialized")
    
    def _setup_ui(self):
        """Set up page UI."""
        # Create main widget
        self.view = QWidget()
        # Outer thin border to encapsulate internal cards
        self.view.setObjectName("panelContainer")
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Apply dark theme styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {GhostTheme.get_background()};
                color: {GhostTheme.get_text_primary()};
            }}
            QScrollArea#peerMonitorPage {{
                border: none;
                background-color: {GhostTheme.get_background()};
            }}
        """)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        margins = get_page_margins()
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(SPACING_MEDIUM)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Title
        title_label = SubtitleLabel("Peer Monitor")
        title_label.setStyleSheet(f"color: {GhostTheme.get_text_primary()};")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Refresh button
        self.refresh_button = PrimaryPushButton(FluentIcon.SYNC, "Refresh")
        self.refresh_button.clicked.connect(self.refresh_peers)
        header_layout.addWidget(self.refresh_button)
        
        self.main_layout.addLayout(header_layout)
        
        # Stats card
        self.stats_card = self._create_stats_card()
        self.main_layout.addWidget(self.stats_card)
        
        # Peers table
        self.peers_table = self._create_peers_table()
        self.peers_table.setStyleSheet(f"""
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
        """)
        self.main_layout.addWidget(self.peers_table)
        
        # Add stretch at bottom
        self.main_layout.addStretch()
        
        # Style
        self.setObjectName("peerMonitorPage")
    
    def _create_stats_card(self) -> CardWidget:
        """Create statistics card showing peer counts."""
        card = CardWidget()
        layout = QHBoxLayout(card)
        margins = get_card_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(SPACING_LARGE)
        
        # Connected peers
        self.connected_label = self._create_stat_widget("Connected", "0", FluentIcon.CONNECT)
        layout.addWidget(self.connected_label)
        
        # Discovered peers
        self.discovered_label = self._create_stat_widget("Discovered", "0", FluentIcon.SEARCH)
        layout.addWidget(self.discovered_label)
        
        # Trusted peers
        self.trusted_label = self._create_stat_widget("Trusted", "0", FluentIcon.ACCEPT)
        layout.addWidget(self.trusted_label)
        
        # Banned peers
        self.banned_label = self._create_stat_widget("Banned", "0", FluentIcon.CANCEL)
        layout.addWidget(self.banned_label)
        
        layout.addStretch()
        # Apply hover glow to the stats card for consistent UI
        apply_hover_glow(card, color=GhostTheme.get_purple_primary())

        return card
    
    def _create_stat_widget(self, label: str, value: str, icon: FluentIcon) -> QWidget:
        """Create a stat display widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Value
        value_label = SubtitleLabel(value)
        value_label.setObjectName(f"{label.lower()}Value")
        layout.addWidget(value_label)
        
        # Label - using centralized theme
        label_widget = CaptionLabel(label)
        label_widget.setStyleSheet(f"color: {GhostTheme.get_text_tertiary()};")
        layout.addWidget(label_widget)
        
        return widget
    
    def _create_peers_table(self) -> TableWidget:
        """Create peers table widget."""
        table = TableWidget()
        
        # Set columns
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Name",
            "Peer ID",
            "Status",
            "Last Seen",
            "Ban/Trust",
            "Actions"
        ])
        
        # Configure table
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # Set column widths
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Peer ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Last Seen
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Ban/Trust
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Actions

        
        return table
    
    def refresh_peers(self):
        """Refresh the peer list from network manager and database."""
        try:
            # Collect peer information
            peers_data = self._collect_peer_data()
            
            # Update stats
            self._update_stats(peers_data)
            
            # Update table
            self._update_table(peers_data)
            
            logger.debug(f"Refreshed peer list: {len(peers_data)} peers")
            
        except Exception as e:
            logger.error(f"Failed to refresh peers: {e}")
    
    def _collect_peer_data(self) -> Dict[str, Dict]:
        """
        Collect peer data from network manager and database.
        
        Returns:
            Dictionary mapping peer_id to peer data
        """
        peers_data = {}
        
        # Get connected peers from network manager
        if self.network_manager:
            for peer_id, peer_conn in self.network_manager.peers.items():
                peers_data[peer_id] = {
                    'peer_id': peer_id,
                    'status': peer_conn.state.value,
                    'address': peer_conn.address,
                    'port': peer_conn.port,
                    'last_seen': peer_conn.connected_at,
                    'is_trusted': True,
                    'is_banned': False,
                    'connected': True
                }
            
            # Get available (discovered but not connected) peers
            for peer_id, peer_info in self.network_manager.available_peers.items():
                if peer_id not in peers_data:
                    peers_data[peer_id] = {
                        'peer_id': peer_id,
                        'status': 'discovered',
                        'address': peer_info.get('address', 'Unknown'),
                        'port': peer_info.get('port', 0),
                        'last_seen': peer_info.get('discovered_at', datetime.utcnow()),
                        'is_trusted': True,
                        'is_banned': False,
                        'connected': False
                    }
        
        # Get peer info from database (trust/ban status)
        if self.db_manager:
            try:
                db_peers = self.db_manager.get_all_peers()
                for db_peer in db_peers:
                    if db_peer.peer_id in peers_data:
                        peers_data[db_peer.peer_id]['is_banned'] = db_peer.is_banned
                        peers_data[db_peer.peer_id]['last_seen'] = db_peer.last_seen
                        peers_data[db_peer.peer_id]['display_name'] = db_peer.display_name or 'Unknown'
                        if db_peer.is_banned:
                            peers_data[db_peer.peer_id]['is_trusted'] = False
                    else:
                        # Peer in database but not currently connected/discovered
                        peers_data[db_peer.peer_id] = {
                            'peer_id': db_peer.peer_id,
                            'status': 'offline',
                            'address': db_peer.address or 'Unknown',
                            'port': db_peer.port or 0,
                            'last_seen': db_peer.last_seen,
                            'display_name': db_peer.display_name or 'Unknown',
                            'is_trusted': not db_peer.is_banned,
                            'is_banned': db_peer.is_banned,
                            'connected': False
                        }
            except Exception as e:
                logger.error(f"Failed to get peers from database: {e}")
        
        return peers_data
    
    def _update_stats(self, peers_data: Dict[str, Dict]):
        """Update statistics display."""
        connected_count = sum(1 for p in peers_data.values() if p['connected'])
        discovered_count = len(peers_data)
        trusted_count = sum(1 for p in peers_data.values() if p['is_trusted'])
        banned_count = sum(1 for p in peers_data.values() if p['is_banned'])
        
        # Update labels
        self.connected_label.findChild(SubtitleLabel).setText(str(connected_count))
        self.discovered_label.findChild(SubtitleLabel).setText(str(discovered_count))
        self.trusted_label.findChild(SubtitleLabel).setText(str(trusted_count))
        self.banned_label.findChild(SubtitleLabel).setText(str(banned_count))
    
    def _update_table(self, peers_data: Dict[str, Dict]):
        """Update peers table with current data."""
        # Clear existing rows
        self.peers_table.setRowCount(0)
        
        if not peers_data:
            return
        
        # Sort peers by status (connected first) then by peer_id
        sorted_peers = sorted(
            peers_data.values(),
            key=lambda p: (not p['connected'], p['peer_id'])
        )
        
        # Add rows
        for row, peer in enumerate(sorted_peers):
            self.peers_table.insertRow(row)
            
            # Name
            name = peer.get('display_name', 'Unknown')
            name_item = QTableWidgetItem(name)
            self.peers_table.setItem(row, 0, name_item)
            
            # Peer ID (truncated)
            peer_id_display = peer['peer_id'][:16] + "..." if len(peer['peer_id']) > 16 else peer['peer_id']
            peer_id_item = QTableWidgetItem(peer_id_display)
            peer_id_item.setToolTip(peer['peer_id'])  # Full ID in tooltip
            self.peers_table.setItem(row, 1, peer_id_item)
            
            # Status - show ban status if banned, otherwise connection status
            if peer['is_banned']:
                status_item = QTableWidgetItem("Banned")
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status = peer['status']
                status_item = QTableWidgetItem(status.capitalize())
                if status == 'connected':
                    status_item.setForeground(Qt.GlobalColor.green)
                elif status == 'discovered':
                    status_item.setForeground(Qt.GlobalColor.yellow)
                else:
                    status_item.setForeground(Qt.GlobalColor.gray)
            self.peers_table.setItem(row, 2, status_item)
            
            # Last Seen
            last_seen = peer['last_seen']
            if isinstance(last_seen, datetime):
                time_diff = datetime.utcnow() - last_seen
                if time_diff.total_seconds() < 60:
                    last_seen_str = "Just now"
                elif time_diff.total_seconds() < 3600:
                    minutes = int(time_diff.total_seconds() / 60)
                    last_seen_str = f"{minutes}m ago"
                elif time_diff.total_seconds() < 86400:
                    hours = int(time_diff.total_seconds() / 3600)
                    last_seen_str = f"{hours}h ago"
                else:
                    last_seen_str = last_seen.strftime("%Y-%m-%d")
            else:
                last_seen_str = "Unknown"
            last_seen_item = QTableWidgetItem(last_seen_str)
            self.peers_table.setItem(row, 3, last_seen_item)
            
            # Ban/Trust switch
            switch_widget = self._create_ban_switch_widget(peer)
            self.peers_table.setCellWidget(row, 4, switch_widget)
            
            # Actions
            actions_widget = self._create_actions_widget(peer)
            self.peers_table.setCellWidget(row, 5, actions_widget)
    
    def _create_ban_switch_widget(self, peer: Dict) -> QWidget:
        """Create ban/trust switch widget for a peer row. ON=Trusted, OFF=Banned."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        peer_id = peer['peer_id']
        
        switch = SwitchButton()
        switch.setChecked(not peer['is_banned'])  # ON = trusted, OFF = banned
        switch.checkedChanged.connect(lambda checked: self._on_ban_switch_toggled(peer_id, not checked))
        layout.addWidget(switch)
        
        return widget
    
    def _create_actions_widget(self, peer: Dict) -> QWidget:
        """Create actions widget for a peer row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        peer_id = peer['peer_id']
        
        # Edit name button
        edit_btn = ToolButton(FluentIcon.EDIT)
        edit_btn.setToolTip("Edit name")
        edit_btn.clicked.connect(lambda: self._on_edit_name_clicked(peer_id))
        layout.addWidget(edit_btn)
        
        # Chat button
        chat_btn = ToolButton(FluentIcon.CHAT)
        chat_btn.setToolTip("Start chat")
        chat_btn.clicked.connect(lambda: self._on_chat_clicked(peer_id))
        layout.addWidget(chat_btn)
        
        return widget
    
    def _on_ban_switch_toggled(self, peer_id: str, is_banned: bool):
        """Handle ban/trust switch toggle. Switch ON=trusted, OFF=banned."""
        try:
            if self.db_manager:
                peer_info = self.db_manager.get_peer_info(peer_id)
                if not peer_info:
                    # Need to get public key from network manager
                    if self.network_manager and peer_id in self.network_manager.peers:
                        peer_conn = self.network_manager.peers[peer_id]
                        public_key = peer_conn.public_key if hasattr(peer_conn, 'public_key') else b''
                    else:
                        # Use placeholder if peer not connected
                        public_key = b''
                    
                    from models.database import PeerInfo
                    peer_info = PeerInfo(
                        peer_id=peer_id,
                        public_key=public_key,
                        last_seen=datetime.utcnow()
                    )
                
                peer_info.is_banned = is_banned
                self.db_manager.save_peer_info(peer_info)
                
                if is_banned:
                    self.peer_banned.emit(peer_id)
                    logger.info(f"Banned peer: {peer_id[:8]}")
                else:
                    self.peer_trusted.emit(peer_id)
                    logger.info(f"Trusted peer: {peer_id[:8]}")
                
                self.refresh_peers()
        except Exception as e:
            logger.error(f"Failed to toggle ban status: {e}")
    
    def _on_edit_name_clicked(self, peer_id: str):
        """Handle edit name button click."""
        try:
            if not self.db_manager:
                return
            
            peer_info = self.db_manager.get_peer_info(peer_id)
            current_name = peer_info.display_name if peer_info and peer_info.display_name else ""
            
            # Create dialog
            dialog = MessageBox("Edit Peer Name", "", self)
            
            # Add input field
            from qfluentwidgets import LineEdit
            name_input = LineEdit()
            name_input.setPlaceholderText("Enter display name...")
            name_input.setText(current_name)
            name_input.setMaxLength(50)
            dialog.textLayout.addWidget(name_input)
            
            if dialog.exec():
                new_name = name_input.text().strip()
                
                if not peer_info:
                    # Create new peer info if doesn't exist
                    if self.network_manager and peer_id in self.network_manager.peers:
                        peer_conn = self.network_manager.peers[peer_id]
                        public_key = peer_conn.public_key if hasattr(peer_conn, 'public_key') else b''
                    else:
                        public_key = b''
                    
                    from models.database import PeerInfo
                    peer_info = PeerInfo(
                        peer_id=peer_id,
                        public_key=public_key,
                        last_seen=datetime.utcnow()
                    )
                
                peer_info.display_name = new_name if new_name else None
                self.db_manager.save_peer_info(peer_info)
                
                logger.info(f"Updated peer name: {peer_id[:8]} -> {new_name}")
                self.refresh_peers()
                
        except Exception as e:
            logger.error(f"Failed to edit peer name: {e}")
    
    def _on_chat_clicked(self, peer_id: str):
        """Handle chat button click."""
        logger.info(f"Chat requested with peer: {peer_id[:8]}")
        self.chat_requested.emit(peer_id)
    

    

    
    def closeEvent(self, event):
        """Handle widget close event."""
        # Stop refresh timer
        if self.refresh_timer:
            self.refresh_timer.stop()
        
        event.accept()
