"""
Qt-Asyncio Event Loop Integration

This module provides integration between Python's asyncio event loop and Qt's event loop,
allowing async operations to run without blocking the UI.
"""

import asyncio
from typing import Coroutine, Any
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication


class QtAsyncioEventLoop(QObject):
    """
    Integrates asyncio event loop with Qt event loop.
    
    This class creates a bridge between asyncio and Qt, allowing coroutines
    to be executed without blocking the Qt UI. It uses a QTimer to periodically
    process asyncio events.
    """
    
    def __init__(self, app: QApplication):
        """
        Initialize the Qt-Asyncio event loop bridge.
        
        Args:
            app: The QApplication instance
        """
        super().__init__()
        self.app = app
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create timer to process asyncio events every 10ms
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_events)
        self.timer.start(10)  # Process every 10ms for responsive UI
        
        self._running = True
    
    def _process_events(self):
        """
        Process pending asyncio events.
        
        This method is called by the QTimer to process asyncio events
        without blocking the Qt event loop.
        """
        if not self._running:
            return
        
        # Process all ready callbacks
        self.loop.stop()
        self.loop.run_forever()
    
    def run_coroutine(self, coro: Coroutine) -> asyncio.Task:
        """
        Schedule a coroutine to run in the asyncio event loop.
        
        This method allows UI code to schedule async operations without
        blocking the UI thread.
        
        Args:
            coro: The coroutine to execute
            
        Returns:
            asyncio.Task: The task object representing the scheduled coroutine
            
        Example:
            task = event_loop.run_coroutine(network_manager.connect_to_peer(address, port))
        """
        return asyncio.ensure_future(coro, loop=self.loop)
    
    def stop(self):
        """
        Stop the event loop integration.
        
        This should be called when the application is shutting down.
        """
        self._running = False
        self.timer.stop()
        
        # Cancel all pending tasks
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        
        # Run loop one final time to process cancellations
        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()
    
    def get_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get the underlying asyncio event loop.
        
        Returns:
            The asyncio event loop instance
        """
        return self.loop
