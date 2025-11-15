"""
Demo script for testing PeerMonitorPage and enhanced SettingsPage.

This script demonstrates the peer monitoring and settings functionality
without requiring a full application setup.
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_manager import ConfigManager
from ui.peer_monitor_page import PeerMonitorPage
from ui.settings_page import SettingsPage


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class DemoWindow(FluentWindow):
    """Demo window for testing peer monitor and settings pages."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize config manager
        config_path = Path.home() / ".bbs_p2p" / "config" / "settings.yaml"
        self.config_manager = ConfigManager(config_path)
        
        # Setup window
        self.setWindowTitle("Peer Monitor & Settings Demo")
        self.resize(1000, 700)
        
        # Create pages
        self.peer_page = PeerMonitorPage(
            network_manager=None,  # No network manager in demo
            db_manager=None  # No database in demo
        )
        
        self.settings_page = SettingsPage(self.config_manager)
        
        # Add to navigation
        self.addSubInterface(
            self.peer_page,
            FluentIcon.PEOPLE,
            "Peers",
            NavigationItemPosition.TOP
        )
        
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "Settings",
            NavigationItemPosition.TOP
        )
        
        # Connect signals
        self.peer_page.peer_trusted.connect(self._on_peer_trusted)
        self.peer_page.peer_banned.connect(self._on_peer_banned)
        self.peer_page.chat_requested.connect(self._on_chat_requested)
        
        self.settings_page.settings_saved.connect(self._on_settings_saved)
        
        # Set default page
        self.stackedWidget.setCurrentWidget(self.peer_page)
    
    def _on_peer_trusted(self, peer_id: str):
        """Handle peer trusted event."""
        print(f"Peer trusted: {peer_id[:16]}...")
    
    def _on_peer_banned(self, peer_id: str):
        """Handle peer banned event."""
        print(f"Peer banned: {peer_id[:16]}...")
    
    def _on_chat_requested(self, peer_id: str):
        """Handle chat request event."""
        print(f"Chat requested with: {peer_id[:16]}...")
    
    def _on_settings_saved(self):
        """Handle settings saved event."""
        print("Settings saved successfully")


def main():
    """Run the demo application."""
    app = QApplication(sys.argv)
    
    # Create and show window
    window = DemoWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
