"""Debug and crash helper utilities.

Provides a small helper to enable Python's faulthandler and register a
signal to dump tracebacks to a .faulth file for post-mortem analysis.
"""
from __future__ import annotations

import faulthandler
import signal
import sys
import logging
from pathlib import Path
from typing import Optional

_log_file_handle: Optional[object] = None


def enable_crash_handlers(log_path: Path) -> None:
    """Enable faulthandler and register SIGUSR1 to dump tracebacks.

    Args:
        log_path: Base path to write a .faulth file alongside the regular log.
    """
    global _log_file_handle
    logger = logging.getLogger(__name__)
    try:
        faulth_path = Path(str(log_path) + ".faulth")
        # Keep the file handle open for the process lifetime so faulthandler
        # can write into it on demand (and on crashes).
        _log_file_handle = faulth_path.open("a")
        faulthandler.enable(file=_log_file_handle, all_threads=True)

        def _sigusr1_handler(signum, frame):
            try:
                if _log_file_handle:
                    faulthandler.dump_traceback(file=_log_file_handle, all_threads=True)
                    _log_file_handle.flush()
                else:
                    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
            except Exception:
                # Don't let debugging helpers crash the app
                pass

        # Register signal handler for SIGUSR1 to dump tracebacks on demand
        try:
            signal.signal(signal.SIGUSR1, _sigusr1_handler)
        except Exception:
            # Some platforms (Windows) may not support SIGUSR1 – ignore in that case
            logger.debug("SIGUSR1 not available on this platform; skipping registration")

        logger.info(f"Faulthandler enabled; traces will be written to {faulth_path}")
    except Exception as e:
        logger.warning(f"Failed to enable faulthandler: {e}")
"""Debug and crash helper utilities.

Provides a small helper to enable Python's faulthandler and register a
signal to dump tracebacks to a .faulth file for post-mortem analysis.
"""
from __future__ import annotations

import faulthandler
import signal
import sys
import logging
from pathlib import Path
from typing import Optional

_log_file_handle: Optional[object] = None


def enable_crash_handlers(log_path: Path) -> None:
    """Enable faulthandler and register SIGUSR1 to dump tracebacks.

    Args:
        log_path: Base path to write a .faulth file alongside the regular log.
    """
    global _log_file_handle
    logger = logging.getLogger(__name__)
    try:
        faulth_path = Path(str(log_path) + ".faulth")
        # Keep the file handle open for the process lifetime so faulthandler
        # can write into it on demand (and on crashes).
        _log_file_handle = faulth_path.open("a")
        faulthandler.enable(file=_log_file_handle, all_threads=True)

        def _sigusr1_handler(signum, frame):
            try:
                """Debug and crash helper utilities.

                Provides a small helper to enable Python's faulthandler and register a
                signal to dump tracebacks to a .faulth file for post-mortem analysis.
                """
                from __future__ import annotations

                import faulthandler
                import signal
                import sys
                import logging
                from pathlib import Path
                from typing import Optional

                _log_file_handle: Optional[object] = None


                def enable_crash_handlers(log_path: Path) -> None:
                    """Enable faulthandler and register SIGUSR1 to dump tracebacks.

                    Args:
                        log_path: Base path to write a .faulth file alongside the regular log.
                    """
                    global _log_file_handle
                    logger = logging.getLogger(__name__)
                    try:
                        faulth_path = Path(str(log_path) + ".faulth")
                        # Keep the file handle open for the process lifetime so faulthandler
                        # can write into it on demand (and on crashes).
                        _log_file_handle = faulth_path.open("a")
                        faulthandler.enable(file=_log_file_handle, all_threads=True)

                        def _sigusr1_handler(signum, frame):
                            try:
                                if _log_file_handle:
                                    faulthandler.dump_traceback(file=_log_file_handle, all_threads=True)
                                    _log_file_handle.flush()
                                else:
                                    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
                            except Exception:
                                # Don't let debugging helpers crash the app
                                pass

                        # Register signal handler for SIGUSR1 to dump tracebacks on demand
                        try:
                            signal.signal(signal.SIGUSR1, _sigusr1_handler)
                        except Exception:
                            # Some platforms (Windows) may not support SIGUSR1 – ignore in that case
                            logger.debug("SIGUSR1 not available on this platform; skipping registration")

                        logger.info(f"Faulthandler enabled; traces will be written to {faulth_path}")
                    except Exception as e:
                        logger.warning(f"Failed to enable faulthandler: {e}")