# Requirements Document

## Introduction

This document specifies the requirements for a decentralized Bulletin Board System (BBS) desktop application that operates peer-to-peer without central servers. The system enables users to discover peers automatically via mDNS (local network) and DHT (internet-wide), exchange encrypted messages, participate in threaded discussions, send private messages, share files, and moderate content through cryptographic signatures. The application provides a modern Fluent Design UI using QFluentWidgets (Dark mode) and PySide6, ensuring privacy through end-to-end encryption and forward secrecy.

## Glossary

- **BBS_Application**: The desktop application implementing the peer-to-peer bulletin board system
- **User_Identity**: A cryptographic identity consisting of Ed25519 signing keypair and X25519 encryption keypair, the user only choose a display name (no configuration needed). 
- **Peer**: Another instance of the BBS_Application running on a different device
- **Board**: A public discussion space containing threads and posts
- **Thread**: A collection of posts organized around a topic
- **Post**: A signed message created by a user within a thread
- **Private_Message**: An encrypted direct message between two users
- **mDNS_Service**: Multicast DNS service for automatic peer discovery on local networks
- **DHT_Network**: Distributed Hash Table network for global peer lookup using Kademlia protocol
- **Sync_Manager**: Component responsible for replicating posts and threads across peers
- **Crypto_Manager**: Component handling key generation, signing, encryption, and decryption
- **Network_Manager**: Component managing peer connections, discovery, and encrypted transport
- **Vector_Clock**: Logical timestamp mechanism for conflict resolution in distributed systems
- **AEAD**: Authenticated Encryption with Associated Data (ChaCha20-Poly1305 or AES-GCM)
- **ECDH**: Elliptic Curve Diffie-Hellman key exchange protocol
- **Moderation_Action**: A signed operation to delete, ban, or trust a peer
- **Session_Key**: Ephemeral symmetric key derived from ECDH for encrypting peer-to-peer communication

## Requirements

### Requirement 1: Identity Creation and Management

**User Story:** As a new user, I want to create a cryptographic identity automatically on first launch, so that I can participate in the BBS network without manual configuration. All the cryptography configuration is by default hide to the user who only choose a display name.

#### Acceptance Criteria

1.1 WHEN the BBS_Application launches for the first time, THE Crypto_Manager SHALL generate an Ed25519 signing keypair and an X25519 encryption keypair (behind the scene, no intervention of the user).

1.2 WHEN the Crypto_Manager generates keypairs, THE Crypto_Manager SHALL store the private keys in an encrypted keystore using Argon2 key derivation and AES-GCM encryption.

1.3 WHEN a User_Identity is created, THE BBS_Application SHALL derive a unique peer identifier from the Ed25519 public key.

1.4 THE BBS_Application SHALL allow users to export their User_Identity to a file for backup purposes.

1.5 THE BBS_Application SHALL allow users to import a User_Identity from a backup file to restore their identity on a different device.

### Requirement 2: Local Peer Discovery

**User Story:** As a user on a local network, I want the application to automatically discover other peers without configuration, so that I can immediately start participating in discussions.

#### Acceptance Criteria

2.1 WHEN the Network_Manager starts, THE mDNS_Service SHALL broadcast the peer's presence on the local network using the service type "_bbs-p2p._tcp".

2.2 WHEN the mDNS_Service detects another peer on the local network, THE Network_Manager SHALL add the peer to the available peers list.

2.3 WHEN a peer is discovered via mDNS, THE Network_Manager SHALL verify the peer's signed identity record before establishing a connection.

2.4 WHILE the BBS_Application is running, THE mDNS_Service SHALL continuously monitor for new peers joining the local network.

2.5 WHEN a peer disconnects or becomes unavailable, THE mDNS_Service SHALL remove the peer from the available peers list within 10 seconds.

### Requirement 3: Global Peer Discovery

**User Story:** As a user, I want to discover and connect to peers outside my local network, so that I can participate in a wider community.

#### Acceptance Criteria

3.1 WHEN the Network_Manager starts, THE DHT_Network SHALL connect to at least one bootstrap node from the configured list.

3.2 WHEN the DHT_Network successfully connects to a bootstrap node, THE DHT_Network SHALL announce the peer's presence by storing its contact information in the DHT.

3.3 WHEN a user requests to find peers for a specific Board, THE DHT_Network SHALL query the DHT for peer records associated with that Board identifier.

3.4 WHEN the DHT_Network retrieves peer records, THE Network_Manager SHALL verify the cryptographic signatures before adding peers to the connection pool.

3.5 WHILE the BBS_Application is running, THE DHT_Network SHALL refresh its presence in the DHT every 15 minutes.

### Requirement 4: Encrypted Peer Communication

**User Story:** As a privacy-conscious user, I want all communication with peers to be encrypted, so that my messages cannot be intercepted or read by third parties.

#### Acceptance Criteria

4.1 WHEN the Network_Manager establishes a connection to a Peer, THE Network_Manager SHALL perform a handshake by exchanging ephemeral X25519 public keys and Ed25519 signatures.

4.2 WHEN the handshake completes, THE Crypto_Manager SHALL derive a Session_Key using ECDH and HKDF from the ephemeral keys.

4.3 WHEN transmitting data to a Peer, THE Network_Manager SHALL encrypt the data using the Session_Key with AEAD encryption.

4.4 WHEN receiving encrypted data from a Peer, THE Network_Manager SHALL decrypt and authenticate the data using the Session_Key.

4.5 IF authentication of received data fails, THEN THE Network_Manager SHALL discard the data and log a security warning.

### Requirement 5: Board and Thread Management

**User Story:** As a participant, I want to join public boards and create threads, so that I can organize discussions by topic.

#### Acceptance Criteria

5.1 THE BBS_Application SHALL allow users to create a new Board with a unique name and description.

5.2 WHEN a user creates a Board, THE BBS_Application SHALL generate a unique Board identifier and announce it to connected Peers.

5.3 THE BBS_Application SHALL allow users to browse a list of available Boards discovered from Peers.

5.4 WHEN a user joins a Board, THE Sync_Manager SHALL request the complete thread and post history from connected Peers.

5.5 THE BBS_Application SHALL allow users to create a new Thread within a Board by providing a title and initial Post.

### Requirement 6: Post Creation and Signing

**User Story:** As a participant, I want to create posts that are cryptographically signed, so that others can verify my identity and the integrity of my messages.

#### Acceptance Criteria

6.1 WHEN a user creates a Post, THE BBS_Application SHALL include the post content, timestamp, Thread identifier, and author's public key.

6.2 WHEN a Post is created, THE Crypto_Manager SHALL sign the Post using the user's Ed25519 private key.

6.3 WHEN a Post is received from a Peer, THE Crypto_Manager SHALL verify the signature using the author's Ed25519 public key.

6.4 IF a Post signature verification fails, THEN THE BBS_Application SHALL reject the Post and not display it to the user.

6.5 THE BBS_Application SHALL display the author's peer identifier and signature verification status alongside each Post.

### Requirement 7: Post Synchronization

**User Story:** As a participant, I want my posts to be automatically shared with other peers, so that everyone can see the latest discussions.

#### Acceptance Criteria

7.1 WHEN a user creates a Post, THE Sync_Manager SHALL broadcast the Post to all Peers connected to the same Board.

7.2 WHEN the Sync_Manager receives a Post from a Peer, THE Sync_Manager SHALL store the Post in the local database after signature verification.

7.3 WHEN the Sync_Manager detects missing Posts based on Vector_Clock comparison, THE Sync_Manager SHALL request the missing Posts from connected Peers.

7.4 WHILE the BBS_Application is running, THE Sync_Manager SHALL perform periodic synchronization with connected Peers every 30 seconds.

7.5 WHEN the Sync_Manager receives duplicate Posts, THE Sync_Manager SHALL deduplicate based on Post identifier and signature.

### Requirement 8: Private Messaging

**User Story:** As a private user, I want to send encrypted direct messages to another peer, so that we can communicate privately.

#### Acceptance Criteria

8.1 THE BBS_Application SHALL allow users to initiate a private chat with any discovered Peer.

8.2 WHEN a user sends a Private_Message, THE Crypto_Manager SHALL encrypt the message using the recipient's X25519 public key via sealed box encryption.

8.3 WHEN a Private_Message is received, THE Crypto_Manager SHALL decrypt the message using the user's X25519 private key.

8.4 IF decryption of a Private_Message fails, THEN THE BBS_Application SHALL discard the message and notify the user of a decryption error.

8.5 THE BBS_Application SHALL display Private_Messages in a dedicated chat interface separate from public Boards.

### Requirement 9: File Sharing

**User Story:** As a user, I want to attach files to my posts and private messages, so that I can share documents, images, and other content with peers.

#### Acceptance Criteria

9.1 THE BBS_Application SHALL allow users to attach files up to 50 megabytes to a Post or Private_Message.

9.2 WHEN a file is attached to a Post, THE Crypto_Manager SHALL compute a SHA-256 hash of the file for integrity verification.

9.3 WHEN transmitting a file, THE Network_Manager SHALL split the file into chunks of 64 kilobytes and transmit each chunk with AEAD encryption.

9.4 WHEN receiving file chunks, THE Network_Manager SHALL reassemble the file and verify the SHA-256 hash matches the expected value.

9.5 IF file hash verification fails, THEN THE BBS_Application SHALL discard the file and request retransmission from the sender.

### Requirement 10: Moderation Actions

**User Story:** As a moderator, I want to delete inappropriate posts, ban malicious peers, and trust reputable peers, so that I can maintain a healthy community.

#### Acceptance Criteria

10.1 THE BBS_Application SHALL allow users to create a Moderation_Action to delete a specific Post by referencing its identifier.

10.2 WHEN a Moderation_Action is created, THE Crypto_Manager SHALL sign the action using the moderator's Ed25519 private key.

10.3 WHEN a Moderation_Action is received, THE BBS_Application SHALL verify the signature and check if the moderator has sufficient reputation or trust.

10.4 WHEN a valid delete Moderation_Action is processed, THE BBS_Application SHALL hide the referenced Post from the user interface.

10.5 THE BBS_Application SHALL allow users to maintain a local trust list of peer identifiers they consider trustworthy moderators.

### Requirement 11: User Interface with QFluentWidgets

**User Story:** As a user, I want a modern, intuitive interface that follows Fluent Design (Dark Mode) principles, so that the application is pleasant and easy to use.

#### Acceptance Criteria

11.1 THE BBS_Application SHALL implement the main window using QFluentWidgets NavigationInterface with sidebar navigation.

11.2 THE BBS_Application SHALL provide navigation items for Boards, Private Chats, Peers, Settings, and About sections.

11.3 THE BBS_Application SHALL display Boards as a list of CardWidget components showing board name, description, and activity status.

11.4 THE BBS_Application SHALL display Threads within a Board as a scrollable list with thread title, author, and last activity timestamp.

11.5 THE BBS_Application SHALL display Posts within a Thread with rich text formatting, author information, timestamp, and signature verification status.

11.6 THE BBS_Application SHALL provide a post composer with a text editor supporting markdown formatting and file attachment buttons.

11.7 THE BBS_Application SHALL display Private_Messages in a chat interface with message bubbles, timestamps, and encryption indicators.

11.8 THE BBS_Application SHALL provide a Settings panel for configuring network options, theme selection, and key management.

11.9 THE BBS_Application SHALL support light and dark theme modes with smooth transitions.

11.10 THE BBS_Application SHALL display notifications using InfoBar components for connection events, new messages, and errors.

### Requirement 12: Asynchronous Operations

**User Story:** As a user, I want the application to remain responsive during network operations, so that I can continue using the interface without freezing or delays.

#### Acceptance Criteria

12.1 THE Network_Manager SHALL perform all network I/O operations using Python asyncio to avoid blocking the main thread.

12.2 THE BBS_Application SHALL integrate asyncio event loop with Qt event loop to enable concurrent execution.

12.3 WHEN a long-running operation starts, THE BBS_Application SHALL display a progress indicator or loading state in the user interface.

12.4 THE BBS_Application SHALL use Qt signals and slots to communicate between asyncio tasks and UI components.

12.5 THE BBS_Application SHALL remain responsive to user input during peer discovery, synchronization, and file transfers.

### Requirement 13: Data Persistence

**User Story:** As a user, I want my posts, messages, and settings to be saved locally, so that I can access them when I restart the application.

#### Acceptance Criteria

13.1 THE BBS_Application SHALL use SQLite database for storing Boards, Threads, Posts, Private_Messages, and Peer information.

13.2 THE BBS_Application SHALL use SQLAlchemy ORM for database operations to ensure type safety and maintainability.

13.3 WHEN the BBS_Application starts, THE BBS_Application SHALL load the user's User_Identity from the encrypted keystore.

13.4 WHEN the BBS_Application starts, THE BBS_Application SHALL load all Boards, Threads, and Posts from the local database.

13.5 THE BBS_Application SHALL persist configuration settings in a YAML file located in the user's home directory.

### Requirement 14: Configuration Management

**User Story:** As a user, I want to configure network settings, bootstrap nodes, and application behavior, so that I can customize the application to my needs.

#### Acceptance Criteria

14.1 THE BBS_Application SHALL load configuration from a YAML file at startup with default values if the file does not exist.

14.2 THE BBS_Application SHALL allow users to configure the network listen port through the Settings panel.

14.3 THE BBS_Application SHALL allow users to enable or disable mDNS discovery through the Settings panel.

14.4 THE BBS_Application SHALL allow users to enable or disable DHT discovery through the Settings panel.

14.5 THE BBS_Application SHALL allow users to add or remove bootstrap nodes for DHT discovery through the Settings panel.

14.6 THE BBS_Application SHALL allow users to configure the synchronization interval through the Settings panel.

14.7 WHEN configuration changes are saved, THE BBS_Application SHALL apply the changes without requiring a restart where possible.

### Requirement 15: Testing and Quality Assurance

**User Story:** As a developer, I want comprehensive tests to ensure the application works correctly, so that I can confidently make changes and improvements.

#### Acceptance Criteria

15.1 THE BBS_Application project SHALL include unit tests for Crypto_Manager covering key generation, signing, encryption, and decryption.

15.2 THE BBS_Application project SHALL include unit tests for message serialization and deserialization.

15.3 THE BBS_Application project SHALL include integration tests simulating two Peers discovering each other via mDNS and exchanging Posts.

15.4 THE BBS_Application project SHALL include a smoke test verifying the main window launches successfully.

15.5 THE BBS_Application project SHALL use pytest and pytest-asyncio for running all tests.

15.6 THE BBS_Application project SHALL achieve test execution with all tests passing before release.

### Requirement 16: Documentation

**User Story:** As a developer or user, I want comprehensive documentation explaining the architecture, protocols, and usage, so that I can understand and extend the application.

#### Acceptance Criteria

16.1 THE BBS_Application project SHALL include a README.md file with installation instructions, configuration guide, and usage examples.

16.2 THE BBS_Application project SHALL include an architecture.md document describing the layered architecture and component interactions.

16.3 THE BBS_Application project SHALL include a protocol.md document specifying the handshake process, message types, and encoding format.

16.4 THE BBS_Application project SHALL include a threat_model.md document identifying potential adversaries, attack vectors, and mitigations.

16.5 THE BBS_Application project SHALL include docstrings for all public classes and methods following Python conventions.

### Requirement 17: Packaging and Distribution

**User Story:** As a user, I want to download and run the application as a standalone executable, so that I don't need to install Python or dependencies manually.

#### Acceptance Criteria

17.1 THE BBS_Application project SHALL include a PyInstaller configuration for building standalone executables.

17.2 THE BBS_Application SHALL be packageable as a single executable file for Windows, macOS, and Linux platforms.

17.3 WHEN the standalone executable runs, THE BBS_Application SHALL create necessary configuration and data directories in the user's home directory.

17.4 THE BBS_Application SHALL include all required dependencies and assets in the packaged executable.

17.5 THE BBS_Application executable SHALL be launchable without requiring Python installation on the target system.

### Requirement 18: Demo Mode

**User Story:** As a developer or tester, I want to run multiple instances of the application in demo mode, so that I can test peer-to-peer functionality locally.

#### Acceptance Criteria

18.1 THE BBS_Application SHALL support a --demo command-line flag to enable demo mode with isolated data directories.

18.2 THE BBS_Application SHALL support a --port command-line flag to specify the network listen port.

18.3 THE BBS_Application SHALL support a --connect command-line flag to specify a peer address to connect to on startup.

18.4 WHEN running in demo mode, THE BBS_Application SHALL use a unique data directory based on the specified port number.

18.5 WHEN the --connect flag is provided, THE Network_Manager SHALL attempt to connect to the specified peer address immediately after startup.
