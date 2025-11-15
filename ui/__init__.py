"""
UI module for BBS P2P application.

This module contains all user interface components built with
PySide6 and QFluentWidgets, including:
- Main window and navigation
- Board and thread views
- Chat interface
- Peer monitor
- Settings panels
"""

from ui.main_window import MainWindow
from ui.settings_page import SettingsPage
from ui.peer_monitor_page import PeerMonitorPage

__all__ = [
    'MainWindow',
    'SettingsPage',
    'PeerMonitorPage',
]
