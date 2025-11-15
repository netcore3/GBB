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
    PushButton,
    FluentIcon,
    MessageBox,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    TableWidget,
    ToolButton,
    InfoBar,
    InfoBarPosition
)

from core.network_manager import NetworkManager, PeerConnection, ConnectionState
from core.db_manager import DBManager
from models.database import PeerInfo


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
        parent=None
    ):
        """
        Initialize peer monitor page.
        
        Args:
            network_manager: NetworkManager instance for connection status
            db_manager: DBManager instance for peer info
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.network_manager = network_manager
        self.db_manager = db_manager
        
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
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Title
        title_label = SubtitleLabel("Peer Monitor")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Refresh button
        self.refresh_button = PushButton(FluentIcon.SYNC, "Refresh")
        self.refresh_button.clicked.connect(self.refresh_peers)
        header_layout.addWidget(self.refresh_button)
        
        self.main_layout.addLayout(header_layout)
        
        # Stats card
        self.stats_card = self._create_stats_card()
        self.main_layout.addWidget(self.stats_card)
        
        # Peers table
        self.peers_table = self._create_peers_table()
        self.main_layout.addWidget(self.peers_table)
        
        # Add stretch at bottom
        self.main_layout.addStretch()
        
        # Style
        self.setObjectName("peerMonitorPage")
    
    def _create_stats_card(self) -> CardWidget:
        """Create statistics card showing peer counts."""
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(32)
        
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
        
        # Label
        label_widget = CaptionLabel(label)
        label_widget.setStyleSheet("color: gray;")
        layout.addWidget(label_widget)
        
        return widget
    
    def _create_peers_table(self) -> TableWidget:
        """Create peers table widget."""
        table = TableWidget()
        
        # Set columns
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Peer ID",
            "Status",
            "Last Seen",
            "Trust",
            "Ban",
            "Actions"
        ])
        
        # Configure table
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # Set column widths
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Peer ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Last Seen
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Trust
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Ban
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
                    'is_trusted': False,
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
                        'is_trusted': False,
                        'is_banned': False,
                        'connected': False
                    }
        
        # Get peer info from database (trust/ban status)
        if self.db_manager:
            try:
                db_peers = self.db_manager.get_all_peers()
                for db_peer in db_peers:
                    if db_peer.peer_id in peers_data:
                        peers_data[db_peer.peer_id]['is_trusted'] = db_peer.is_trusted
                        peers_data[db_peer.peer_id]['is_banned'] = db_peer.is_banned
                        peers_data[db_peer.peer_id]['last_seen'] = db_peer.last_seen
                    else:
                        # Peer in database but not currently connected/discovered
                        peers_data[db_peer.peer_id] = {
                            'peer_id': db_peer.peer_id,
                            'status': 'offline',
                            'address': db_peer.address or 'Unknown',
                            'port': db_peer.port or 0,
                            'last_seen': db_peer.last_seen,
                            'is_trusted': db_peer.is_trusted,
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
            
            # Peer ID (truncated)
            peer_id_display = peer['peer_id'][:16] + "..." if len(peer['peer_id']) > 16 else peer['peer_id']
            peer_id_item = QTableWidgetItem(peer_id_display)
            peer_id_item.setToolTip(peer['peer_id'])  # Full ID in tooltip
            self.peers_table.setItem(row, 0, peer_id_item)
            
            # Status
            status = peer['status']
            status_item = QTableWidgetItem(status.capitalize())
            if status == 'connected':
                status_item.setForeground(Qt.GlobalColor.green)
            elif status == 'discovered':
                status_item.setForeground(Qt.GlobalColor.yellow)
            else:
                status_item.setForeground(Qt.GlobalColor.gray)
            self.peers_table.setItem(row, 1, status_item)
            
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
            self.peers_table.setItem(row, 2, last_seen_item)
            
            # Trust status
            trust_item = QTableWidgetItem("✓" if peer['is_trusted'] else "")
            trust_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if peer['is_trusted']:
                trust_item.setForeground(Qt.GlobalColor.green)
            self.peers_table.setItem(row, 3, trust_item)
            
            # Ban status
            ban_item = QTableWidgetItem("✗" if peer['is_banned'] else "")
            ban_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if peer['is_banned']:
                ban_item.setForeground(Qt.GlobalColor.red)
            self.peers_table.setItem(row, 4, ban_item)
            
            # Actions
            actions_widget = self._create_actions_widget(peer)
            self.peers_table.setCellWidget(row, 5, actions_widget)
    
    def _create_actions_widget(self, peer: Dict) -> QWidget:
        """Create actions widget for a peer row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        peer_id = peer['peer_id']
        
        # Chat button
        chat_btn = ToolButton(FluentIcon.CHAT)
        chat_btn.setToolTip("Start chat")
        chat_btn.clicked.connect(lambda: self._on_chat_clicked(peer_id))
        layout.addWidget(chat_btn)
        
        # Trust button
        if not peer['is_trusted']:
            trust_btn = ToolButton(FluentIcon.ACCEPT)
            trust_btn.setToolTip("Trust peer")
            trust_btn.clicked.connect(lambda: self._on_trust_clicked(peer_id))
            layout.addWidget(trust_btn)
        
        # Ban button
        if not peer['is_banned']:
            ban_btn = ToolButton(FluentIcon.CANCEL)
            ban_btn.setToolTip("Ban peer")
            ban_btn.clicked.connect(lambda: self._on_ban_clicked(peer_id))
            layout.addWidget(ban_btn)
        
        return widget
    
    def _on_chat_clicked(self, peer_id: str):
        """Handle chat button click."""
        logger.info(f"Chat requested with peer: {peer_id[:8]}")
        self.chat_requested.emit(peer_id)
    
    def _on_trust_clicked(self, peer_id: str):
        """Handle trust button click."""
        try:
            # Show confirmation dialog
            msg_box = MessageBox(
                "Trust Peer",
                f"Do you want to trust this peer?\n\nPeer ID: {peer_id[:16]}...",
                self
            )
            
            if msg_box.exec():
                logger.info(f"Trusting peer: {peer_id[:8]}")
                self.peer_trusted.emit(peer_id)
                
                # Refresh display
                self.refresh_peers()
                
                # Show notification
                InfoBar.success(
                    title="Peer Trusted",
                    content="Peer has been added to trust list",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
        
        except Exception as e:
            logger.error(f"Failed to trust peer: {e}")
    
    def _on_ban_clicked(self, peer_id: str):
        """Handle ban button click."""
        try:
            # Show confirmation dialog
            msg_box = MessageBox(
                "Ban Peer",
                f"Do you want to ban this peer?\n\nPeer ID: {peer_id[:16]}...\n\nBanned peers will be disconnected and blocked.",
                self
            )
            
            if msg_box.exec():
                logger.info(f"Banning peer: {peer_id[:8]}")
                self.peer_banned.emit(peer_id)
                
                # Refresh display
                self.refresh_peers()
                
                # Show notification
                InfoBar.warning(
                    title="Peer Banned",
                    content="Peer has been banned and will be disconnected",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
        
        except Exception as e:
            logger.error(f"Failed to ban peer: {e}")
    
    def closeEvent(self, event):
        """Handle widget close event."""
        # Stop refresh timer
        if self.refresh_timer:
            self.refresh_timer.stop()
        
        event.accept()
