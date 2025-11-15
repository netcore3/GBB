"""
Demo script to test the main window UI.

This script launches the main window without requiring full application setup.
Useful for UI development and testing.
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.main_window import MainWindow
from config.config_manager import ConfigManager


def setup_logging():
    """Configure logging for demo."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Run the main window demo."""
    setup_logging()
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("P2P Encrypted BBS")
    app.setOrganizationName("BBS-P2P")
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Create main window
    window = MainWindow(
        config_manager=config_manager,
        board_manager=None,  # Not needed for UI demo
        thread_manager=None,
        chat_manager=None
    )
    
    # Show window
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
