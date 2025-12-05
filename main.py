"""GhostBBs Application Entry Point.

Main entry point for the GhostBBs desktop application. It handles
configuration, profile/login flow, initialization of core services,
and launches the Qt application.
"""

import sys
import argparse
import logging
import asyncio
from pathlib import Path
from typing import Optional


# Import configuration
from config.config_manager import ConfigManager

# Import core components
from core.crypto_manager import CryptoManager, Identity, KeystoreError
from core.db_manager import DBManager
from core.network_manager import NetworkManager
from core.sync_manager import SyncManager
from core.error_handler import ErrorHandler, get_error_handler
from core.notification_manager import NotificationManager, get_notification_manager

# Import logic layer
from logic.board_manager import BoardManager
from logic.thread_manager import ThreadManager
from logic.chat_manager import ChatManager
from logic.moderation_manager import ModerationManager

# Import board image manager
from core.board_image_manager import BoardImageManager

# Note: UI and PySide6 imports are delayed until after QApplication is created
# to avoid constructing QWidget/QObjects at module import time which can
# lead to "QWidget: Must construct a QApplication before a QWidget" errors.


# Configure logging
def setup_logging(log_level: str, log_path: Path):
    """
    Configure application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_path: Path to log file
    """
    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {log_level}")
    logger.info(f"Log file: {log_path}")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='GhostBBs - Decentralized Encrypted Bulletin Board System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run normally
  python main.py
  
  # Run in demo mode on port 9001
  python main.py --demo --port 9001
  
  # Run in demo mode and connect to another peer
  python main.py --demo --port 9002 --connect localhost:9001
  
  # Specify custom config file
  python main.py --config /path/to/config.yaml
        """
    )
    
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run in demo mode with isolated data directory based on port'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Network listen port (default: from config or 9000)'
    )
    
    parser.add_argument(
        '--connect',
        type=str,
        default=None,
        metavar='ADDRESS:PORT',
        help='Auto-connect to specified peer on startup (e.g., localhost:9001)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default=None,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Override logging level from config'
    )
    
    return parser.parse_args()


def get_demo_data_directory(port: int) -> Path:
    """
    Get data directory for demo mode based on port.
    
    Args:
        port: Network port number
        
    Returns:
        Path to demo data directory
    """
    return Path.home() / f".bbs_p2p_demo_{port}"


def load_or_create_identity(
    crypto_manager: CryptoManager,
    keystore_path: Path,
    is_demo: bool = False
) -> Identity:
    """
    Load existing identity from keystore or create a new one.
    
    Args:
        crypto_manager: CryptoManager instance
        keystore_path: Path to keystore file
        is_demo: Whether running in demo mode
        
    Returns:
        Identity object
    """
    logger = logging.getLogger(__name__)
    
    # Check if keystore exists
    if keystore_path.exists():
        try:
            # In demo mode, use a simple password
            # In production, this would prompt the user
            password = "demo_password" if is_demo else "default_password"
            
            logger.info(f"Loading identity from keystore: {keystore_path}")
            identity = crypto_manager.load_keystore(password, keystore_path)
            logger.info(f"Identity loaded successfully. Peer ID: {identity.peer_id[:16]}...")
            
            return identity
            
        except KeystoreError as e:
            logger.error(f"Failed to load keystore: {e}")
            logger.info("Creating new identity...")
    
    # Create new identity
    logger.info("Generating new identity...")
    identity = crypto_manager.generate_identity()
    logger.info(f"Identity generated. Peer ID: {identity.peer_id[:16]}...")
    
    # Save to keystore
    try:
        password = "demo_password" if is_demo else "default_password"
        crypto_manager.save_keystore(identity, password, keystore_path)
        logger.info(f"Identity saved to keystore: {keystore_path}")
    except KeystoreError as e:
        logger.warning(f"Failed to save keystore: {e}")
        logger.warning("Identity will not persist across restarts")
    
    return identity


async def auto_connect_to_peer(
    network_manager: NetworkManager,
    connect_address: str
):
    """
    Automatically connect to a specified peer.
    
    Args:
        network_manager: NetworkManager instance
        connect_address: Address in format "host:port"
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Parse address
        if ':' not in connect_address:
            logger.error(f"Invalid connect address format: {connect_address}")
            logger.error("Expected format: host:port (e.g., localhost:9001)")
            return
        
        host, port_str = connect_address.rsplit(':', 1)
        port = int(port_str)
        
        logger.info(f"Auto-connecting to peer at {host}:{port}...")
        
        # Wait a bit for server to start
        await asyncio.sleep(1.0)
        
        # Connect to peer
        peer_id = await network_manager.connect_to_peer(host, port, timeout=10.0)
        logger.info(f"Successfully connected to peer {peer_id[:16]}...")
        
    except ValueError as e:
        logger.error(f"Invalid port number in connect address: {e}")
    except Exception as e:
        logger.error(f"Failed to auto-connect to peer: {e}")


def main():
    """
    Main application entry point.
    
    Initializes all components and starts the Qt application.
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Determine if running in demo mode
    is_demo = args.demo
    
    # Initialize configuration manager
    config_path = Path(args.config) if args.config else None
    
    # In demo mode, use port-specific config directory
    if is_demo and args.port:
        demo_dir = get_demo_data_directory(args.port)
        demo_dir.mkdir(parents=True, exist_ok=True)
        config_path = demo_dir / "config" / "settings.yaml"
    
    config_manager = ConfigManager(config_path)
    
    # Override port if specified
    if args.port:
        config_manager.set_config('network', 'listen_port', args.port)
    
    # Get configuration
    network_config = config_manager.get_network_config()
    security_config = config_manager.get_security_config()
    storage_config = config_manager.get_storage_config()
    logging_config = config_manager.get_logging_config()
    
    # Override log level if specified
    if args.log_level:
        logging_config.level = args.log_level
    
    # Setup logging
    log_path = config_manager.expand_path(logging_config.log_path)
    
    # In demo mode, use port-specific log file
    if is_demo and args.port:
        demo_dir = get_demo_data_directory(args.port)
        log_path = demo_dir / "logs" / "app.log"
    
    setup_logging(logging_config.level, log_path)
    
    # Enable crash/debug helpers (faulthandler + SIGUSR1 dump)
    try:
        from core.debug_utils import enable_crash_handlers
        enable_crash_handlers(log_path)
    except Exception:
        # Best-effort only; don't fail startup if debug helpers cannot be enabled
        pass

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("GhostBBs Application Starting")
    logger.info("=" * 60)
    
    if is_demo:
        logger.info(f"Running in DEMO mode on port {network_config.listen_port}")
        if args.connect:
            logger.info(f"Will auto-connect to: {args.connect}")
    
    # Initialize database first (needed for profiles/login)
    logger.info("Initializing database...")
    db_path = config_manager.expand_path(storage_config.db_path)

    # In demo mode, use port-specific database
    if is_demo and args.port:
        demo_dir = get_demo_data_directory(args.port)
        db_path = demo_dir / "data" / "bbs.db"

    db_manager = DBManager(db_path)
    db_manager.initialize_database()
    logger.info(f"Database initialized: {db_path}")

    # Initialize error handler and notification manager
    logger.info("Initializing error handler and notification manager...")
    error_handler = get_error_handler()
    notification_manager = get_notification_manager()

    # Create Qt application (needed before showing any dialogs)
    logger.info("Creating Qt application...")
    
    # Import PySide6 and UI modules here to avoid import-time widget creation
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # Import UI modules after QApplication exists
    from ui.main_window import MainWindow
    from ui.welcome_page import WelcomePage
    from ui.board_list_page import BoardListPage
    from ui.private_chats_page import PrivateChatsPage
    from ui.peer_monitor_page import PeerMonitorPage
    from ui.settings_page import SettingsPage
    from ui.about_page import AboutPage
    from ui.login_window import LoginWindow

    app.setApplicationName("GhostBBs")
    app.setOrganizationName("GhostBBs")
    app.setApplicationVersion("0.1.0")

    # --- Profile selection / login (before any network or identity) ---
    profiles = db_manager.get_all_profiles()
    
    profile = None  # Initialize profile variable
    
    # If no profiles exist, create a default profile automatically
    if not profiles:
        logger.info("No profiles found. Creating default profile...")
        profile_id = "default-profile"
        default_display_name = "Default User"
        profile = db_manager.create_profile(
            profile_id=profile_id,
            display_name=default_display_name,
            avatar_path=None,
            shared_folder=None
        )
        logger.info(f"Created default profile: {default_display_name}")
        profile.is_guest = False  # Mark this as a real profile
    else:
        # Show login window for profile selection
        logger.info("Showing login/profile selection window...")
        login_window = LoginWindow(db=db_manager)
        
        # Execute login dialog and check result
        dialog_result = login_window.exec()
        
        # Debug logging
        logger.info(f"Dialog result: {dialog_result}")
        logger.info(f"Selected profile: {login_window.selected_profile}")
        
        # Check if dialog was accepted and profile was selected
        from PySide6.QtWidgets import QDialog
        if dialog_result != QDialog.Accepted or not login_window.selected_profile:
            logger.info(f"Login window cancelled or no profile selected. Dialog result: {dialog_result}, profile: {login_window.selected_profile}")
            sys.exit(0)
        
        # Validate that the selected profile actually exists in the database
        selected_profile_id = login_window.selected_profile.id
        profile = db_manager.get_profile(selected_profile_id)
        
        if profile is None:
            logger.error(f"Selected profile {selected_profile_id} not found in database. This may indicate data corruption.")
            logger.error("Cannot proceed with invalid profile. Exiting application.")
            sys.exit(1)
            
        # Profile is valid
        profile.is_guest = False  # Mark this as a real profile
        logger.info(f"Successfully logged in as: {profile.display_name}")

    # Initialize cryptography manager and identity, using keystore from profile
    logger.info("Initializing cryptography manager...")
    crypto_manager = CryptoManager()

    # Determine keystore path: profile-specific if available, otherwise config
    keystore_path = None
    if getattr(profile, "keystore_path", None):
        keystore_path = Path(profile.keystore_path)
    else:
        keystore_path = config_manager.expand_path(security_config.key_store_path)
        if is_demo and args.port:
            demo_dir = get_demo_data_directory(args.port)
            keystore_path = demo_dir / "keys" / "keystore.enc"

    identity = load_or_create_identity(crypto_manager, keystore_path, is_demo)

    # Backfill profile.peer_id / keystore_path if missing
    try:
        updated = False
        if not getattr(profile, "peer_id", None):
            profile.peer_id = identity.peer_id
            updated = True
        if not getattr(profile, "keystore_path", None):
            profile.keystore_path = str(keystore_path)
            updated = True
        if updated:
            from datetime import datetime
            profile.last_used = datetime.utcnow()
            db_manager.update_profile(profile)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to update profile identity metadata: {e}")

    # Initialize network manager
    logger.info("Initializing network manager...")
    network_manager = NetworkManager(
        identity=identity,
        crypto_manager=crypto_manager,
        enable_mdns=network_config.enable_mdns,
    )

    # Initialize sync manager
    logger.info("Initializing sync manager...")
    sync_config = config_manager.get_sync_config()
    sync_manager = SyncManager(
        identity=identity,
        crypto_manager=crypto_manager,
        db_manager=db_manager,
        network_manager=network_manager,
        sync_interval=sync_config.interval,
        batch_size=sync_config.batch_size,
    )

    # Initialize application logic managers
    logger.info("Initializing application logic managers...")
    board_manager = BoardManager(
        identity=identity,
        crypto_manager=crypto_manager,
        db_manager=db_manager,
        network_manager=network_manager,
    )

    thread_manager = ThreadManager(
        identity=identity,
        crypto_manager=crypto_manager,
        db_manager=db_manager,
        network_manager=network_manager,
    )

    chat_manager = ChatManager(
        identity=identity,
        crypto_manager=crypto_manager,
        db_manager=db_manager,
        network_manager=network_manager,
    )

    moderation_manager = ModerationManager(
        identity=identity,
        crypto_manager=crypto_manager,
        db_manager=db_manager,
        network_manager=network_manager,
    )

    # Create main window
    logger.info("Creating main window...")
    main_window = MainWindow(
        config_manager=config_manager,
        board_manager=board_manager,
        thread_manager=thread_manager,
        chat_manager=chat_manager,
        error_handler=error_handler,
        notification_manager=notification_manager,
        profile=profile,
        db_manager=db_manager
    )
    
    # Create and set page widgets
    logger.info("Creating page widgets...")
    
    # Initialize board image manager
    app_data_dir = Path.home() / ".bbs_p2p"
    if is_demo and args.port:
        app_data_dir = get_demo_data_directory(args.port)
    image_manager = BoardImageManager(app_data_dir)

    # Create and set welcome page
    welcome_page = WelcomePage()

    def _on_feature_selected(feature_name: str):
        """Handle feature card selection from welcome page."""
        if feature_name == "boards":
            main_window.switch_to_boards()
        elif feature_name == "chats":
            main_window.switch_to_chats()
        elif feature_name == "peers":
            main_window.switch_to_peers()

    welcome_page.feature_selected.connect(_on_feature_selected)
    main_window.set_welcome_page(welcome_page)

    boards_page = BoardListPage(
        board_manager=board_manager,
        thread_manager=thread_manager,
        identity=identity.peer_id,
        image_manager=image_manager,
    )
    
    # Handle board double-click to show detail view
    from ui.board_detail_page import BoardDetailPage
    
    def _on_board_double_clicked(board_id: str):
        """Show board detail page when board is double-clicked."""
        try:
            board = board_manager.get_board_by_id(board_id)
            if board:
                detail_page = BoardDetailPage(
                    board=board,
                    db_manager=db_manager,
                    thread_manager=thread_manager,
                    profile=profile
                )
                detail_page.back_clicked.connect(lambda: main_window.stackedWidget.setCurrentWidget(boards_page))
                main_window.stackedWidget.addWidget(detail_page)
                main_window.stackedWidget.setCurrentWidget(detail_page)
        except Exception as e:
            logger.error(f"Failed to open board detail: {e}")
    
    boards_page.board_double_clicked.connect(_on_board_double_clicked)
    main_window.set_boards_page(boards_page)

    chats_page = PrivateChatsPage(
        chat_manager=chat_manager,
        db_manager=db_manager,
        identity=identity.peer_id,
    )
    main_window.set_chats_page(chats_page)
    
    peers_page = PeerMonitorPage(
        network_manager=network_manager,
        moderation_manager=moderation_manager,
        db_manager=db_manager,
        identity=identity.peer_id,
    )
    # When a chat is requested from the peers page, open the corresponding
    # conversation in the chats page and switch navigation.
    def _open_chat_from_peers(requested_peer_id: str) -> None:
        try:
            if not requested_peer_id:
                return
            chats_page.open_conversation(requested_peer_id)
            main_window.switch_to_chats()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to open chat from peers page: {exc}")

    peers_page.chat_requested.connect(_open_chat_from_peers)
    main_window.set_peers_page(peers_page)
    
    # Create and set settings page (now also aware of the active profile)
    settings_page = SettingsPage(
        config_manager=config_manager,
        profile=profile,
        db_manager=db_manager,
    )
    main_window.set_settings_page(settings_page)
    
    # Create and set about page
    about_page = AboutPage()
    main_window.set_about_page(about_page)
    
    # Set up navigation interface with proper pages and purple theme
    main_window._setup_navigation()
    
    # Set the default page after all real pages have been injected
    main_window._set_default_page()
    
    # Start network manager
    logger.info(f"Starting network manager on port {network_config.listen_port}...")
    
    # Use asyncio to start the network manager
    async def start_network():
        try:
            await network_manager.start(
                port=network_config.listen_port,
                host='0.0.0.0'
            )
            logger.info(f"Network manager started on port {network_config.listen_port}")
            
            # Auto-connect if specified
            if args.connect:
                await auto_connect_to_peer(network_manager, args.connect)
            
            # Start sync manager
            logger.info("Starting sync manager...")
            await sync_manager.start()
            logger.info("Sync manager started")
            
        except Exception as e:
            logger.error(f"Failed to start network services: {e}")
            error_handler.handle_error(
                e,
                "network_startup",
                "Failed to start network services"
            )
    
    # Schedule network startup after UI is ready
    main_window.event_loop.run_coroutine(start_network())
    
    # Show main window
    logger.info("Showing main window...")
    main_window.show()
    
    logger.info("Application started successfully")
    logger.info(f"Active profile: {getattr(profile, 'display_name', 'unknown')} ({getattr(profile, 'id', '')})")
    logger.info(f"Peer ID: {identity.peer_id}")
    logger.info(f"Listening on port: {network_config.listen_port}")
    
    # Run Qt event loop
    exit_code = app.exec()
    
    # Cleanup on exit
    logger.info("Application shutting down...")
    
    # Stop network services
    async def stop_network():
        try:
            logger.info("Stopping sync manager...")
            await sync_manager.stop()
            
            logger.info("Stopping network manager...")
            await network_manager.stop()
            
            logger.info("Network services stopped")
        except Exception as e:
            logger.error(f"Error stopping network services: {e}")
    
    # Run cleanup
    try:
        # Prefer the Qt-integrated event loop if available. The MainWindow
        # integrates its own asyncio loop and may have already stopped and
        # closed it in closeEvent(). Avoid attempting to run_until_complete
        # on a closed loop which raises "Event loop is closed" and leaves
        # the coroutine un-awaited.
        loop = None
        if hasattr(main_window, 'event_loop'):
            try:
                loop = main_window.event_loop.get_loop()
            except Exception:
                loop = None

        if loop is None:
            loop = asyncio.get_event_loop()

        if loop.is_closed():
            logger.warning("Asyncio event loop already closed; skipping async shutdown of network services.")
        else:
            loop.run_until_complete(stop_network())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    
    logger.info("Application shutdown complete")
    logger.info("=" * 60)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
