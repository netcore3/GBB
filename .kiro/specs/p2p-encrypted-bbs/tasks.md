# Implementation Plan

- [-] 1. Project Setup and Core Infrastructure

  - Create project directory structure with core/, ui/, models/, logic/, tests/, docs/, config/ folders
  - Set up requirements.txt with PySide6, qfluentwidgets, cryptography, zeroconf, sqlalchemy, pytest, cbor2
  - Create pyproject.toml for project metadata and build configuration
  - Initialize git repository with .gitignore for Python projects
  - _Requirements: 15.5, 17.4_

- [ ] 2. Cryptography Module Implementation
- [ ] 2.1 Implement Identity and key generation
  - Create Identity dataclass with Ed25519 and X25519 keypairs
  - Implement generate_identity() method to create signing and encryption keypairs
  - Implement peer_id derivation from Ed25519 public key using SHA-256
  - _Requirements: 1.1, 1.3_

- [ ] 2.2 Implement signing and verification
  - Implement sign_data() method using Ed25519 private key
  - Implement verify_signature() method using Ed25519 public key
  - Add error handling for invalid signatures
  - _Requirements: 6.2, 6.3, 6.4_

- [ ] 2.3 Implement encryption and decryption
  - Implement encrypt_message() using X25519 sealed box for private messages
  - Implement decrypt_message() for sealed box decryption
  - Implement derive_session_key() using ECDH and HKDF
  - Implement encrypt_with_session_key() and decrypt_with_session_key() using ChaCha20-Poly1305 AEAD
  - _Requirements: 4.2, 4.3, 4.4, 8.2, 8.3_

- [ ] 2.4 Implement keystore encryption
  - Implement save_keystore() with Argon2id key derivation and AES-GCM encryption
  - Implement load_keystore() with password verification and decryption
  - Add support for keystore export and import
  - _Requirements: 1.2, 1.4, 1.5_

- [ ] 2.5 Write unit tests for crypto module
  - Test key generation produces valid keypairs
  - Test signing and verification with valid and tampered data
  - Test encryption/decryption round-trip
  - Test keystore save/load with correct and incorrect passwords
  - _Requirements: 15.1_

- [ ] 3. Database Layer Implementation
- [ ] 3.1 Define SQLAlchemy models
  - Create Board model with id, name, description, creator_peer_id, created_at, signature
  - Create Thread model with id, board_id, title, creator_peer_id, created_at, last_activity, signature
  - Create Post model with id, thread_id, author_peer_id, content, created_at, sequence_number, signature, parent_post_id
  - Create PrivateMessage model with id, sender_peer_id, recipient_peer_id, encrypted_content, created_at, read_at
  - Create Attachment model with id, post_id, message_id, filename, file_hash, file_size, mime_type, encrypted_data
  - Create PeerInfo model with peer_id, public_key, last_seen, address, port, is_trusted, is_banned, reputation_score
  - Create ModerationAction model with id, moderator_peer_id, action_type, target_id, reason, created_at, signature
  - _Requirements: 13.1_

- [ ] 3.2 Implement DBManager
  - Implement initialize_database() to create schema
  - Implement save_post(), get_posts_for_thread(), save_board(), get_all_boards()
  - Implement save_private_message(), get_private_messages()
  - Implement save_peer_info(), get_trusted_peers()
  - Add transaction management with rollback on error
  - _Requirements: 13.2, 13.4_

- [ ] 3.3 Write database tests
  - Test CRUD operations for all models
  - Test foreign key constraints
  - Test transaction rollback
  - _Requirements: 15.1_

- [ ] 4. Configuration Management
- [ ] 4.1 Create configuration system
  - Create default settings.yaml with network, ui, security, storage, sync, logging sections
  - Implement configuration loader with YAML parsing
  - Implement configuration validator for required fields and types
  - Create user data directory structure (~/.bbs_p2p/) on first launch
  - _Requirements: 13.5, 14.1_

- [ ] 4.2 Implement settings persistence
  - Implement save_config() to write changes to YAML file
  - Implement get_config() and set_config() for individual settings
  - Add support for environment variable overrides
  - _Requirements: 14.2, 14.3, 14.4, 14.5, 14.6_

- [ ] 5. Network Manager Core
- [ ] 5.1 Implement TCP server and client
  - Create asyncio TCP server listening on configured port
  - Implement accept_connection() to handle incoming peer connections
  - Implement connect_to_peer() to initiate outgoing connections
  - Add connection timeout and error handling
  - _Requirements: 4.1, 18.2_

- [ ] 5.2 Implement handshake protocol
  - Implement perform_handshake() with HELLO message exchange
  - Generate ephemeral X25519 keypairs for each connection
  - Exchange ephemeral public keys and Ed25519 signatures
  - Verify signatures using peer's identity public key
  - Derive session key using ECDH and HKDF
  - Exchange CAPS messages with supported features and board subscriptions
  - _Requirements: 4.1, 4.2, 2.3_

- [ ] 5.3 Implement encrypted message transport
  - Implement send_message() with CBOR encoding and AEAD encryption
  - Implement receive_message() with AEAD decryption and CBOR decoding
  - Implement nonce management (increment per message)
  - Add message authentication verification
  - Handle decryption failures and invalid messages
  - _Requirements: 4.3, 4.4, 4.5_

- [ ] 5.4 Implement peer connection management
  - Maintain active peer connections in dictionary
  - Implement disconnect_peer() for clean connection closure
  - Implement broadcast_to_board() to send message to all peers on a board
  - Add connection state tracking (connecting, connected, disconnected)
  - _Requirements: 2.5_

- [ ] 5.5 Write handshake integration test
  - Test two peers performing successful handshake
  - Test handshake with invalid signature
  - Test session key derivation matches on both sides
  - _Requirements: 15.3_

- [ ] 6. mDNS Peer Discovery
- [ ] 6.1 Implement mDNS service
  - Create mDNSService class using zeroconf library
  - Implement start_advertising() to broadcast "_bbs-p2p._tcp" service
  - Include peer_id, version, and signature in service properties
  - Implement start_browsing() to listen for peer announcements
  - Implement stop() to clean up service
  - _Requirements: 2.1, 2.4_

- [ ] 6.2 Integrate mDNS with NetworkManager
  - Connect mDNS discovery callback to NetworkManager
  - Verify peer signatures from mDNS service records
  - Add discovered peers to available peers list
  - Remove peers when they disappear from network
  - _Requirements: 2.2, 2.3, 2.5_

- [ ] 6.3 Write mDNS discovery test
  - Test two instances discover each other via mDNS
  - Test service record contains valid signature
  - Test peer removal on disconnect
  - _Requirements: 15.3_

- [ ] 7. Synchronization Manager
- [ ] 7.1 Implement vector clock
  - Create VectorClock class with clock dictionary (peer_id -> sequence_number)
  - Implement increment() to update local sequence number
  - Implement merge() to combine two vector clocks
  - Implement compare() to detect concurrent updates
  - _Requirements: 7.3_

- [ ] 7.2 Implement sync protocol
  - Implement sync_board() to synchronize all threads in a board
  - Exchange vector clocks with peer for each board
  - Identify missing posts by comparing vector clocks
  - Implement request_missing_posts() to fetch specific posts
  - Implement handle_incoming_post() to validate, store, and propagate posts
  - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [ ] 7.3 Implement periodic synchronization
  - Implement start_periodic_sync() as asyncio background task
  - Sync with all connected peers at configured interval (default 30s)
  - Add exponential backoff for failed sync attempts
  - _Requirements: 7.4_

- [ ]* 7.4 Write sync integration test
  - Test post created on peer A appears on peer B
  - Test concurrent posts on both peers converge to same state
  - Test sync after simulated network partition
  - _Requirements: 15.3_

- [ ] 8. Application Logic Layer
- [ ] 8.1 Implement BoardManager
  - Implement create_board() to generate board with unique ID and signature
  - Implement join_board() to subscribe to board and request sync
  - Implement get_board_threads() to retrieve threads from database
  - Announce new boards to connected peers
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 8.2 Implement ThreadManager
  - Implement create_thread() to create thread with title and initial post
  - Implement add_post_to_thread() to create signed post
  - Implement get_thread_posts() to retrieve posts from database
  - Broadcast new threads and posts to peers
  - _Requirements: 5.5, 6.1, 6.5_

- [ ] 8.3 Implement ChatManager
  - Implement send_private_message() with sealed box encryption
  - Implement get_conversation() to retrieve messages for a peer
  - Implement mark_as_read() to update read timestamp
  - Send encrypted messages directly to recipient peer
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [ ] 8.4 Implement ModerationManager
  - Implement delete_post() to create signed moderation action
  - Implement ban_peer() to create ban moderation action
  - Implement trust_peer() to add peer to trust list
  - Implement is_peer_banned() to check ban status
  - Broadcast moderation actions to peers
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 9. File Attachment Support
- [ ] 9.1 Implement file attachment handling
  - Implement attach_file_to_post() to compute SHA-256 hash and encrypt file
  - Implement split file into 64KB chunks for transmission
  - Implement send_file_chunks() with AEAD encryption per chunk
  - Implement receive_file_chunks() to reassemble and verify hash
  - Store encrypted file data in Attachment model
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ]* 9.2 Write file transfer test
  - Test 1MB file attachment and transfer
  - Test hash verification on recipient
  - Test chunked transfer with simulated packet loss
  - _Requirements: 15.3_

- [ ] 10. Qt Event Loop Integration
- [ ] 10.1 Implement asyncio-Qt bridge
  - Create QtAsyncioEventLoop class to integrate asyncio with Qt
  - Use QTimer to process asyncio events every 10ms
  - Implement run_coroutine() to schedule async tasks from UI
  - Ensure UI remains responsive during async operations
  - _Requirements: 12.1, 12.2, 12.4, 12.5_

- [ ] 10.2 Create signal/slot infrastructure
  - Define Qt signals for network events (peer_connected, peer_disconnected, message_received)
  - Define Qt signals for data events (post_created, board_joined, message_sent)
  - Connect signals to UI update slots
  - _Requirements: 12.4_

- [ ] 11. Main Window UI
- [ ] 11.1 Create main window structure
  - Create MainWindow class inheriting from FluentWindow
  - Set up NavigationInterface with sidebar
  - Add navigation items: Boards, Private Chats, Peers, Settings, About
  - Create StackedWidget for content area
  - Initialize InfoBarManager for notifications
  - _Requirements: 11.1, 11.2, 11.10_

- [ ] 11.2 Implement theme support
  - Implement apply_theme() to switch between light and dark themes
  - Load theme from configuration on startup
  - Add theme toggle in settings
  - Apply acrylic effects if enabled in config
  - _Requirements: 11.9_

- [ ] 11.3 Connect UI to application logic
  - Inject BoardManager, ThreadManager, ChatManager into MainWindow
  - Connect navigation item clicks to page switching
  - Set up asyncio event loop integration
  - _Requirements: 12.1, 12.2_

- [ ] 12. Board and Thread Views
- [ ] 12.1 Implement BoardListPage
  - Display boards as CardWidget components in scrollable layout
  - Show board name, description, and activity status
  - Add "Create Board" button with dialog
  - Handle board selection to navigate to thread list
  - _Requirements: 11.3_

- [ ] 12.2 Implement ThreadListPage
  - Display threads in selected board as list items
  - Show thread title, author, and last activity timestamp
  - Add "Create Thread" button with dialog
  - Handle thread selection to navigate to post view
  - _Requirements: 11.4_

- [ ] 12.3 Implement PostViewPage
  - Display posts in selected thread with rich text formatting
  - Show author peer ID, timestamp, and signature verification status
  - Display attachments with download buttons
  - Add reply button for each post
  - Implement post composer at bottom with markdown editor
  - Add file attachment button
  - _Requirements: 11.5, 11.6_

- [ ] 13. Private Chat UI
- [ ] 13.1 Implement ChatListPage
  - Display list of active conversations
  - Show peer name, last message preview, and unread count
  - Add "New Chat" button to start conversation with peer
  - _Requirements: 11.7_

- [ ] 13.2 Implement ChatWidget
  - Display messages as chat bubbles (sent/received)
  - Show timestamps and encryption indicators
  - Implement message input field at bottom
  - Add file attachment button for private messages
  - Auto-scroll to latest message
  - _Requirements: 11.7_

- [ ] 14. Peers and Settings UI
- [ ] 14.1 Implement PeerMonitorPage
  - Display list of discovered peers (mDNS and DHT)
  - Show peer ID, connection status, last seen
  - Display trust and ban status
  - Add buttons to trust, ban, or start chat with peer
  - _Requirements: 10.5_

- [ ] 14.2 Implement SettingsPage
  - Create tabs for Network, Security, Storage, UI, About
  - Add input fields for listen port, bootstrap nodes, sync interval
  - Add checkboxes for enable_mdns, enable_dht
  - Add theme selector and font size slider
  - Add button to export/import identity
  - Display storage usage and database path
  - Add "Save" button to persist configuration
  - _Requirements: 11.8, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [ ] 15. Error Handling and Notifications
- [ ] 15.1 Implement global error handler
  - Create ErrorHandler class with handle_error() method
  - Categorize errors: crypto, network, storage, UI
  - Display user-friendly error messages via InfoBar
  - Log detailed error information for debugging
  - _Requirements: 4.5, 8.4_

- [ ] 15.2 Implement notification system
  - Show InfoBar notifications for connection events
  - Show notifications for new messages and posts
  - Show notifications for moderation actions
  - Add notification sound (optional, configurable)
  - _Requirements: 11.10_

- [ ] 16. Application Entry Point
- [ ] 16.1 Create main.py
  - Parse command-line arguments (--demo, --port, --connect)
  - Initialize configuration system
  - Load or create user identity
  - Initialize database
  - Start network manager and mDNS service
  - Create and show main window
  - Start Qt application event loop
  - _Requirements: 13.3, 18.1, 18.2, 18.3, 18.4, 18.5_

- [ ] 16.2 Implement demo mode
  - Use unique data directory based on port when --demo flag is set
  - Auto-connect to specified peer when --connect flag is provided
  - Generate demo identity if keystore doesn't exist
  - _Requirements: 18.1, 18.4, 18.5_

- [ ] 17. Documentation
- [ ] 17.1 Create README.md
  - Write installation instructions for Windows, macOS, Linux
  - Document configuration options
  - Provide usage examples and screenshots
  - Include demo mode instructions
  - _Requirements: 16.1_

- [ ] 17.2 Create architecture.md
  - Document layered architecture with diagrams
  - Describe component interactions
  - Explain data flow for key operations
  - _Requirements: 16.2_

- [ ] 17.3 Create protocol.md
  - Specify handshake process step-by-step
  - Document all message types and formats
  - Explain encryption and signing flows
  - _Requirements: 16.3_

- [ ] 17.4 Create threat_model.md
  - Identify adversaries and attack vectors
  - Document security mechanisms and mitigations
  - List known limitations and future improvements
  - _Requirements: 16.4_

- [ ]* 17.5 Add docstrings to all modules
  - Write docstrings for all public classes and methods
  - Follow Google or NumPy docstring format
  - Include parameter types and return types
  - _Requirements: 16.5_

- [ ] 18. Packaging and Distribution
- [ ] 18.1 Create PyInstaller configuration
  - Write build.py script with PyInstaller configuration
  - Include all dependencies and resources
  - Configure for single-file executable
  - Add platform-specific settings (icon, etc.)
  - _Requirements: 17.1, 17.2, 17.4_

- [ ] 18.2 Test packaged executable
  - Build executable for current platform
  - Test executable launches without Python installed
  - Verify all features work in packaged version
  - Test demo mode with packaged executable
  - _Requirements: 17.3, 17.5_

- [ ]* 18.3 Create CI/CD workflow
  - Write GitHub Actions workflow for automated testing
  - Run tests on Windows, macOS, Linux
  - Test with Python 3.11 and 3.12
  - Upload test coverage reports
  - _Requirements: 15.6_

- [ ] 19. Integration and End-to-End Testing
- [ ] 19.1 Create integration test suite
  - Write test for two peers discovering via mDNS and syncing posts
  - Write test for private message exchange
  - Write test for file attachment transfer
  - Write test for moderation action propagation
  - _Requirements: 15.3_

- [ ]* 19.2 Create UI smoke tests
  - Test main window launches successfully
  - Test all navigation items are accessible
  - Test theme switching works
  - Test no exceptions during initialization
  - _Requirements: 15.4_

- [ ] 20. Final Polish and Optimization
- [ ] 20.1 Performance optimization
  - Add database indexes for frequently queried fields
  - Implement lazy loading for large thread views
  - Optimize message serialization
  - Profile and optimize hot paths
  - _Requirements: 12.5_

- [ ] 20.2 User experience improvements
  - Add loading indicators for async operations
  - Implement smooth scrolling and animations
  - Add keyboard shortcuts for common actions
  - Improve error messages and help text
  - _Requirements: 12.3_

- [ ] 20.3 Security audit
  - Review all cryptographic operations
  - Verify signature checks are not bypassed
  - Test error handling for malicious inputs
  - Review keystore security
  - _Requirements: 6.4, 4.5_
