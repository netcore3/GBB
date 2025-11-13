# Design Document

## Overview

The P2P Encrypted BBS Application is architected as a layered desktop application using Python 3.11+, PySide6, and QFluentWidgets. The system employs a clean separation of concerns across six primary layers: UI, Application Logic, Networking, Cryptography, Storage, and Synchronization. The architecture prioritizes security through defense-in-depth, maintainability through modular design, and user experience through asynchronous operations integrated with Qt's event loop. All peer-to-peer communication uses authenticated encryption with forward secrecy, while local data is protected with encrypted storage.

## Architecture

### Layered Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│  (QFluentWidgets: MainWindow, NavigationInterface, Cards)   │
└────────────────────┬────────────────────────────────────────┘
                     │ Qt Signals/Slots
┌────────────────────▼────────────────────────────────────────┐
│                  Application Logic Layer                     │
│     (BoardManager, ThreadManager, ChatManager, etc.)        │
└────────┬───────────────────────────────────────┬────────────┘
         │                                       │
┌────────▼────────────┐              ┌──────────▼─────────────┐
│  Networking Layer   │              │   Storage Layer        │
│  (NetworkManager,   │◄────────────►│   (DBManager,          │
│   mDNS, DHT)        │              │    SQLAlchemy ORM)     │
└────────┬────────────┘              └────────────────────────┘
         │
┌────────▼────────────┐              ┌────────────────────────┐
│  Crypto Layer       │              │   Sync Layer           │
│  (CryptoManager,    │◄────────────►│   (SyncManager,        │
│   Key Management)   │              │    Vector Clocks)      │
└─────────────────────┘              └────────────────────────┘
```

### Component Responsibilities

**UI Layer**: Renders all visual components using QFluentWidgets, handles user input, displays notifications
**Application Logic Layer**: Coordinates business logic, manages state transitions, validates user actions
**Networking Layer**: Handles peer discovery, connection management, encrypted transport, protocol implementation
**Crypto Layer**: Manages key generation, signing, encryption/decryption, key derivation
**Storage Layer**: Persists data to SQLite, manages database schema, provides ORM abstractions
**Sync Layer**: Replicates data across peers, resolves conflicts, maintains consistency


## Components and Interfaces

### Core Components

#### 1. CryptoManager (`core/crypto_manager.py`)

**Purpose**: Centralized cryptographic operations and key management

**Key Methods**:
- `generate_identity() -> Identity`: Creates Ed25519 signing keypair and X25519 encryption keypair
- `sign_data(data: bytes, private_key: Ed25519PrivateKey) -> bytes`: Signs data with Ed25519
- `verify_signature(data: bytes, signature: bytes, public_key: Ed25519PublicKey) -> bool`: Verifies Ed25519 signature
- `encrypt_message(plaintext: bytes, recipient_public_key: X25519PublicKey) -> bytes`: Encrypts using sealed box
- `decrypt_message(ciphertext: bytes, private_key: X25519PrivateKey) -> bytes`: Decrypts sealed box
- `derive_session_key(local_ephemeral: X25519PrivateKey, remote_ephemeral: X25519PublicKey) -> bytes`: ECDH + HKDF
- `encrypt_with_session_key(plaintext: bytes, session_key: bytes, nonce: bytes) -> bytes`: ChaCha20-Poly1305 AEAD
- `decrypt_with_session_key(ciphertext: bytes, session_key: bytes, nonce: bytes) -> bytes`: ChaCha20-Poly1305 AEAD
- `save_keystore(identity: Identity, password: str, path: Path)`: Encrypts and saves keys using Argon2 + AES-GCM
- `load_keystore(password: str, path: Path) -> Identity`: Loads and decrypts keystore

**Dependencies**: `cryptography` library for all cryptographic primitives

**Security Considerations**:
- Private keys never leave memory unencrypted except when saved to keystore
- Keystore uses Argon2id with time_cost=3, memory_cost=65536, parallelism=4
- Session keys are ephemeral and rotated per connection
- All encryption uses authenticated encryption (AEAD)

#### 2. NetworkManager (`core/network_manager.py`)

**Purpose**: Manages peer connections, handshakes, and encrypted transport

**Key Methods**:
- `start(port: int)`: Starts TCP server and begins listening
- `connect_to_peer(address: str, port: int) -> Peer`: Initiates connection and handshake
- `perform_handshake(connection: Connection) -> Peer`: Executes HELLO/CAPS exchange
- `send_message(peer: Peer, message: Message)`: Encrypts and sends message
- `receive_message(peer: Peer) -> Message`: Receives and decrypts message
- `broadcast_to_board(board_id: str, message: Message)`: Sends to all peers subscribed to board
- `disconnect_peer(peer_id: str)`: Cleanly closes connection

**Protocol Flow**:
1. TCP connection established
2. Both sides generate ephemeral X25519 keypairs
3. Exchange HELLO messages containing: ephemeral public key, identity public key, signature
4. Verify signatures using identity public keys
5. Derive session key via ECDH(local_ephemeral_private, remote_ephemeral_public)
6. Exchange CAPS messages (encrypted) containing: supported features, board subscriptions, vector clocks
7. Begin encrypted message exchange

**Message Format** (CBOR-encoded):
```python
{
    "type": "POST" | "HELLO" | "CAPS" | "REQ_MISSING" | "POST_BATCH" | "PRIVATE_MESSAGE" | "FILE_CHUNK",
    "payload": {...},
    "nonce": bytes(12),  # For AEAD
    "mac": bytes(16)     # Authentication tag
}
```

**Dependencies**: asyncio, cbor2, CryptoManager

#### 3. mDNSService (`core/mdns_service.py`)

**Purpose**: Local network peer discovery using Zeroconf

**Key Methods**:
- `start_advertising(port: int, peer_id: str)`: Broadcasts service on "_bbs-p2p._tcp"
- `start_browsing(callback: Callable)`: Listens for peer announcements
- `stop()`: Stops advertising and browsing

**Service Record Format**:
```python
{
    "name": f"BBS-{peer_id[:8]}._bbs-p2p._tcp.local.",
    "type": "_bbs-p2p._tcp.local.",
    "port": 9000,
    "properties": {
        "peer_id": "base64_encoded_public_key",
        "version": "1.0",
        "signature": "base64_encoded_signature"
    }
}
```

**Dependencies**: zeroconf library

#### 4. DHTManager (`core/dht_manager.py`)

**Purpose**: Global peer discovery using Kademlia DHT

**Key Methods**:
- `bootstrap(bootstrap_nodes: List[Tuple[str, int]])`: Connects to bootstrap nodes
- `announce_presence(peer_id: str, address: str, port: int)`: Stores peer record in DHT
- `find_peers_for_board(board_id: str) -> List[PeerRecord]`: Queries DHT for board participants
- `refresh_presence()`: Periodically re-announces presence (every 15 minutes)

**DHT Key Structure**:
- Peer presence: `peer:{peer_id}` → `{address, port, timestamp, signature}`
- Board participants: `board:{board_id}` → `[peer_id1, peer_id2, ...]`

**Dependencies**: kademlia library (or custom implementation)

**Note**: DHT implementation is marked as TODO for MVP - can use centralized bootstrap server initially

#### 5. SyncManager (`core/sync_manager.py`)

**Purpose**: Replicates posts and threads across peers with conflict resolution

**Key Methods**:
- `sync_board(board_id: str, peers: List[Peer])`: Synchronizes all threads in a board
- `request_missing_posts(board_id: str, peer: Peer, missing_ids: List[str])`: Requests specific posts
- `handle_incoming_post(post: Post)`: Validates, stores, and propagates new post
- `resolve_conflicts(local_posts: List[Post], remote_posts: List[Post]) -> List[Post]`: Merges using vector clocks
- `start_periodic_sync(interval: int)`: Begins background sync task

**Synchronization Algorithm**:
1. Exchange vector clocks with peer for each board
2. Identify missing posts (posts in remote clock but not in local)
3. Request missing posts in batches
4. Validate signatures and store locally
5. Update local vector clock
6. Propagate new posts to other peers

**Vector Clock Format**:
```python
{
    "board_id": "board_123",
    "clocks": {
        "peer_id_1": 42,  # Highest sequence number seen from peer_id_1
        "peer_id_2": 17,
        ...
    }
}
```

**Dependencies**: NetworkManager, DBManager, CryptoManager


#### 6. DBManager (`core/db_manager.py`)

**Purpose**: Database operations and ORM management

**Key Methods**:
- `initialize_database(db_path: Path)`: Creates schema if not exists
- `save_post(post: Post)`: Inserts or updates post
- `get_posts_for_thread(thread_id: str) -> List[Post]`: Retrieves posts
- `save_board(board: Board)`: Persists board metadata
- `get_all_boards() -> List[Board]`: Retrieves all boards
- `save_private_message(message: PrivateMessage)`: Stores encrypted message
- `get_private_messages(peer_id: str) -> List[PrivateMessage]`: Retrieves conversation
- `save_peer_info(peer: PeerInfo)`: Stores peer metadata
- `get_trusted_peers() -> List[str]`: Returns trust list

**Dependencies**: SQLAlchemy, SQLite

#### 7. MainWindow (`ui/main_window.py`)

**Purpose**: Primary application window with Fluent Design navigation

**Key Components**:
- `NavigationInterface`: Sidebar with Boards, Chats, Peers, Settings, About
- `StackedWidget`: Content area displaying current page
- `InfoBarManager`: Toast notifications for events

**Key Methods**:
- `setup_navigation()`: Configures navigation items and routing
- `switch_to_board(board_id: str)`: Displays board content
- `switch_to_chat(peer_id: str)`: Opens private chat
- `show_notification(message: str, type: InfoBarType)`: Displays toast
- `apply_theme(theme: Theme)`: Switches between light/dark mode

**Signal/Slot Integration**:
- Connects UI events to application logic layer
- Receives updates from async tasks via Qt signals
- Uses `asyncio.create_task()` for non-blocking operations

**Dependencies**: PySide6, QFluentWidgets, Application Logic Layer

#### 8. Application Logic Components

**BoardManager** (`logic/board_manager.py`):
- `create_board(name: str, description: str) -> Board`
- `join_board(board_id: str)`
- `get_board_threads(board_id: str) -> List[Thread]`

**ThreadManager** (`logic/thread_manager.py`):
- `create_thread(board_id: str, title: str, initial_post: str) -> Thread`
- `add_post_to_thread(thread_id: str, content: str) -> Post`
- `get_thread_posts(thread_id: str) -> List[Post]`

**ChatManager** (`logic/chat_manager.py`):
- `send_private_message(recipient_id: str, content: str)`
- `get_conversation(peer_id: str) -> List[PrivateMessage]`
- `mark_as_read(message_id: str)`

**ModerationManager** (`logic/moderation_manager.py`):
- `delete_post(post_id: str, reason: str) -> ModerationAction`
- `ban_peer(peer_id: str, reason: str) -> ModerationAction`
- `trust_peer(peer_id: str)`
- `is_peer_banned(peer_id: str) -> bool`

## Data Models

### Identity

```python
@dataclass
class Identity:
    signing_private_key: Ed25519PrivateKey
    signing_public_key: Ed25519PublicKey
    encryption_private_key: X25519PrivateKey
    encryption_public_key: X25519PublicKey
    peer_id: str  # Derived from signing_public_key
    created_at: datetime
```

### Board

```python
class Board(Base):
    __tablename__ = 'boards'
    
    id: str = Column(String, primary_key=True)  # UUID
    name: str = Column(String, nullable=False)
    description: str = Column(String)
    creator_peer_id: str = Column(String, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False)
    signature: bytes = Column(LargeBinary, nullable=False)
    
    threads: List[Thread] = relationship("Thread", back_populates="board")
```

### Thread

```python
class Thread(Base):
    __tablename__ = 'threads'
    
    id: str = Column(String, primary_key=True)  # UUID
    board_id: str = Column(String, ForeignKey('boards.id'), nullable=False)
    title: str = Column(String, nullable=False)
    creator_peer_id: str = Column(String, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False)
    last_activity: datetime = Column(DateTime, nullable=False)
    signature: bytes = Column(LargeBinary, nullable=False)
    
    board: Board = relationship("Board", back_populates="threads")
    posts: List[Post] = relationship("Post", back_populates="thread")
```

### Post

```python
class Post(Base):
    __tablename__ = 'posts'
    
    id: str = Column(String, primary_key=True)  # UUID
    thread_id: str = Column(String, ForeignKey('threads.id'), nullable=False)
    author_peer_id: str = Column(String, nullable=False)
    content: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False)
    sequence_number: int = Column(Integer, nullable=False)  # For vector clock
    signature: bytes = Column(LargeBinary, nullable=False)
    parent_post_id: str = Column(String, ForeignKey('posts.id'), nullable=True)  # For replies
    
    thread: Thread = relationship("Thread", back_populates="posts")
    attachments: List[Attachment] = relationship("Attachment", back_populates="post")
```

### PrivateMessage

```python
class PrivateMessage(Base):
    __tablename__ = 'private_messages'
    
    id: str = Column(String, primary_key=True)  # UUID
    sender_peer_id: str = Column(String, nullable=False)
    recipient_peer_id: str = Column(String, nullable=False)
    encrypted_content: bytes = Column(LargeBinary, nullable=False)  # Sealed box
    created_at: datetime = Column(DateTime, nullable=False)
    read_at: datetime = Column(DateTime, nullable=True)
```

### Attachment

```python
class Attachment(Base):
    __tablename__ = 'attachments'
    
    id: str = Column(String, primary_key=True)  # UUID
    post_id: str = Column(String, ForeignKey('posts.id'), nullable=True)
    message_id: str = Column(String, ForeignKey('private_messages.id'), nullable=True)
    filename: str = Column(String, nullable=False)
    file_hash: str = Column(String, nullable=False)  # SHA-256
    file_size: int = Column(Integer, nullable=False)
    mime_type: str = Column(String, nullable=False)
    encrypted_data: bytes = Column(LargeBinary, nullable=False)
    
    post: Post = relationship("Post", back_populates="attachments")
```

### PeerInfo

```python
class PeerInfo(Base):
    __tablename__ = 'peers'
    
    peer_id: str = Column(String, primary_key=True)
    public_key: bytes = Column(LargeBinary, nullable=False)
    last_seen: datetime = Column(DateTime, nullable=False)
    address: str = Column(String, nullable=True)
    port: int = Column(Integer, nullable=True)
    is_trusted: bool = Column(Boolean, default=False)
    is_banned: bool = Column(Boolean, default=False)
    reputation_score: int = Column(Integer, default=0)
```

### ModerationAction

```python
class ModerationAction(Base):
    __tablename__ = 'moderation_actions'
    
    id: str = Column(String, primary_key=True)  # UUID
    moderator_peer_id: str = Column(String, nullable=False)
    action_type: str = Column(String, nullable=False)  # 'delete', 'ban', 'trust'
    target_id: str = Column(String, nullable=False)  # post_id or peer_id
    reason: str = Column(String, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False)
    signature: bytes = Column(LargeBinary, nullable=False)
```


## Error Handling

### Error Categories and Strategies

#### 1. Cryptographic Errors

**Scenarios**:
- Signature verification failure
- Decryption failure
- Invalid key format
- Keystore corruption

**Handling Strategy**:
- Log security event with details (peer_id, operation, timestamp)
- Reject invalid data immediately
- Display user-friendly error message
- For keystore corruption: offer recovery from backup or create new identity
- Never expose cryptographic details in UI messages

**Example**:
```python
try:
    crypto_manager.verify_signature(data, signature, public_key)
except SignatureVerificationError as e:
    logger.warning(f"Signature verification failed for peer {peer_id}: {e}")
    peer_manager.mark_suspicious(peer_id)
    raise InvalidMessageError("Message authentication failed")
```

#### 2. Network Errors

**Scenarios**:
- Connection timeout
- Peer disconnection
- Network unreachable
- Protocol version mismatch
- Malformed messages

**Handling Strategy**:
- Implement exponential backoff for reconnection (1s, 2s, 4s, 8s, max 60s)
- Queue messages for offline peers (max 100 messages per peer)
- Display connection status in UI with visual indicators
- Gracefully degrade: continue with available peers
- Log network events for diagnostics

**Example**:
```python
async def connect_with_retry(address: str, port: int, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(
                connect_to_peer(address, port),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise ConnectionError(f"Failed to connect after {max_retries} attempts")
```

#### 3. Data Validation Errors

**Scenarios**:
- Invalid post content (empty, too long)
- Missing required fields
- Invalid timestamps (future dates)
- Duplicate message IDs

**Handling Strategy**:
- Validate all user input before processing
- Provide immediate feedback in UI
- Sanitize content to prevent injection attacks
- Reject invalid data from peers silently (log only)

**Validation Rules**:
- Post content: 1-10000 characters
- Board name: 3-50 characters, alphanumeric + spaces
- Thread title: 3-200 characters
- File attachments: max 50MB
- Timestamps: must be within ±5 minutes of current time (clock skew tolerance)

#### 4. Storage Errors

**Scenarios**:
- Disk full
- Database corruption
- Permission denied
- Concurrent access conflicts

**Handling Strategy**:
- Check available disk space before large operations
- Use SQLAlchemy transactions with rollback on error
- Implement database backup before schema migrations
- Display storage status in settings panel
- Offer database repair tool for corruption

**Example**:
```python
try:
    with db_session() as session:
        session.add(post)
        session.commit()
except IntegrityError as e:
    session.rollback()
    logger.error(f"Database integrity error: {e}")
    raise DuplicatePostError("Post already exists")
except OperationalError as e:
    session.rollback()
    logger.critical(f"Database operational error: {e}")
    raise StorageError("Database operation failed")
```

#### 5. UI Errors

**Scenarios**:
- Widget initialization failure
- Theme loading error
- Resource not found (icons, fonts)
- Qt event loop conflicts

**Handling Strategy**:
- Fallback to default theme if custom theme fails
- Use embedded resources to avoid missing files
- Catch exceptions in slot handlers to prevent crashes
- Display error dialog for critical UI failures

### Global Error Handler

```python
class ErrorHandler:
    def __init__(self, ui_manager):
        self.ui_manager = ui_manager
        
    def handle_error(self, error: Exception, context: str):
        if isinstance(error, CryptoError):
            self._handle_crypto_error(error, context)
        elif isinstance(error, NetworkError):
            self._handle_network_error(error, context)
        elif isinstance(error, StorageError):
            self._handle_storage_error(error, context)
        else:
            self._handle_unknown_error(error, context)
    
    def _handle_crypto_error(self, error: CryptoError, context: str):
        logger.error(f"Crypto error in {context}: {error}")
        self.ui_manager.show_error("Security Error", 
                                   "A security validation failed. The operation was rejected.")
    
    # ... other handlers
```

## Testing Strategy

### Unit Tests

**Crypto Module Tests** (`tests/test_crypto.py`):
- Test key generation produces valid Ed25519 and X25519 keypairs
- Test signing and verification with valid and invalid signatures
- Test encryption and decryption with sealed boxes
- Test session key derivation produces consistent results
- Test keystore encryption and decryption with correct and incorrect passwords
- Test AEAD encryption with authentication tag verification

**Message Serialization Tests** (`tests/test_serialization.py`):
- Test CBOR encoding and decoding of all message types
- Test handling of malformed messages
- Test size limits and truncation
- Test unicode handling in content

**Database Tests** (`tests/test_database.py`):
- Test CRUD operations for all models
- Test foreign key constraints
- Test transaction rollback on error
- Test concurrent access handling
- Test database migration

**Vector Clock Tests** (`tests/test_vector_clock.py`):
- Test clock increment and comparison
- Test merge operation with concurrent updates
- Test conflict detection
- Test causality preservation

### Integration Tests

**Peer Discovery Test** (`tests/test_discovery.py`):
- Start two instances with mDNS enabled
- Verify each discovers the other within 5 seconds
- Verify service records contain valid signatures
- Test discovery after peer restart

**Handshake Test** (`tests/test_handshake.py`):
- Establish connection between two peers
- Verify HELLO message exchange
- Verify session key derivation matches on both sides
- Verify CAPS message exchange
- Test handshake failure scenarios (invalid signature, timeout)

**Message Sync Test** (`tests/test_sync.py`):
- Create post on peer A
- Verify post appears on peer B within 2 seconds
- Create posts on both peers simultaneously
- Verify both peers converge to same state
- Test sync after network partition and reconnection

**File Transfer Test** (`tests/test_file_transfer.py`):
- Attach 1MB file to post
- Verify file transfers completely
- Verify hash matches on recipient
- Test chunked transfer with simulated packet loss

### UI Tests

**Smoke Test** (`tests/test_ui_launch.py`):
- Launch main window
- Verify all navigation items present
- Verify no exceptions during initialization
- Verify theme applies correctly

**Interaction Test** (`tests/test_ui_interaction.py`):
- Simulate creating a board
- Simulate creating a thread
- Simulate posting a message
- Verify UI updates reflect changes

### Performance Tests

**Load Test** (`tests/test_performance.py`):
- Create 1000 posts in a thread
- Measure UI rendering time (target: <100ms)
- Measure database query time (target: <50ms)
- Test with 50 concurrent peer connections
- Measure memory usage (target: <500MB)

### Test Execution

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=core --cov=ui --cov=logic tests/

# Run specific test category
pytest tests/test_crypto.py -v

# Run integration tests only
pytest tests/ -m integration

# Run async tests
pytest tests/ --asyncio-mode=auto
```

### Continuous Integration

**GitHub Actions Workflow** (`.github/workflows/test.yml`):
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio pytest-cov
      - run: pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```


## Security Architecture

### Threat Model Summary

**Adversaries**:
1. **Passive Network Observer**: Can intercept network traffic but not modify it
2. **Active Network Attacker**: Can intercept, modify, and inject network traffic
3. **Malicious Peer**: Runs modified client to spam, impersonate, or disrupt
4. **Local Attacker**: Has access to user's device and file system

**Assets to Protect**:
- User's private keys
- Private message content
- User's identity and reputation
- Data integrity (posts cannot be forged or modified)
- Availability (system remains functional under attack)

### Security Mechanisms

#### 1. Cryptographic Identity

**Mechanism**: Each user has Ed25519 signing keypair and X25519 encryption keypair
**Protects Against**: Impersonation, message forgery
**Implementation**:
- Peer ID derived from signing public key (SHA-256 hash)
- All posts and moderation actions signed with Ed25519
- Signatures verified before accepting any data from peers

#### 2. Forward Secrecy

**Mechanism**: Ephemeral X25519 keypairs for each connection
**Protects Against**: Compromise of long-term keys revealing past communications
**Implementation**:
- Generate new ephemeral keypair for each peer connection
- Derive session key via ECDH(local_ephemeral, remote_ephemeral)
- Session keys never stored, only kept in memory during connection
- New handshake required after disconnection

#### 3. Authenticated Encryption

**Mechanism**: ChaCha20-Poly1305 AEAD for all peer-to-peer messages
**Protects Against**: Message tampering, injection, replay attacks
**Implementation**:
- Each message encrypted with session key and unique nonce
- Nonce incremented for each message (prevents replay)
- Authentication tag verified before decryption
- Failed authentication results in immediate connection termination

#### 4. End-to-End Encryption for Private Messages

**Mechanism**: X25519 sealed box encryption
**Protects Against**: Passive and active network observers
**Implementation**:
- Private messages encrypted with recipient's public key
- Only recipient's private key can decrypt
- Encrypted messages stored in database (at-rest encryption)

#### 5. Keystore Protection

**Mechanism**: Argon2id + AES-GCM encryption
**Protects Against**: Local attacker accessing keystore file
**Implementation**:
- User password hashed with Argon2id (memory-hard, GPU-resistant)
- Derived key used to encrypt private keys with AES-GCM
- Keystore file useless without password
- Optional: integrate with OS keychain (Windows Credential Manager, macOS Keychain, Linux Secret Service)

#### 6. Signature Verification

**Mechanism**: Verify Ed25519 signatures on all received data
**Protects Against**: Forged posts, impersonation, unauthorized moderation
**Implementation**:
- Posts include author's peer ID and signature
- Moderation actions include moderator's signature
- Signatures verified before storing or displaying data
- Invalid signatures logged as security events

#### 7. Spam Prevention (Optional)

**Mechanism**: Proof-of-work requirement for posts
**Protects Against**: Spam flooding
**Implementation** (TODO for future version):
- Require SHA-256 hash of post with N leading zeros
- Difficulty adjustable per board
- Verified before accepting post

### Security Best Practices

**Key Management**:
- Private keys never logged or transmitted
- Secure memory wiping when keys no longer needed (use `cryptography` library's secure memory)
- Keystore backup encrypted with same mechanism

**Network Security**:
- TLS optional for bootstrap node connections (TODO)
- Peer certificate pinning for known peers (TODO)
- Rate limiting on incoming connections (max 100 peers)
- Connection timeout to prevent resource exhaustion

**Input Validation**:
- Sanitize all user input before display (prevent XSS in rich text)
- Validate message sizes (reject >1MB messages)
- Validate timestamps (reject messages with timestamp >5 minutes in future)
- Validate peer IDs match public key hashes

**Data Integrity**:
- All posts immutable once created (append-only log)
- Moderation actions don't delete data, only hide from UI
- Database integrity constraints prevent orphaned records
- Regular database integrity checks

## Deployment Architecture

### Directory Structure

```
~/.bbs_p2p/                    # User data directory
├── config/
│   └── settings.yaml          # User configuration
├── keys/
│   └── keystore.enc           # Encrypted private keys
├── data/
│   └── bbs.db                 # SQLite database
├── logs/
│   ├── app.log                # Application logs
│   └── security.log           # Security events
└── cache/
    └── attachments/           # Cached file attachments
```

### Configuration Management

**Default Configuration** (`config/settings.yaml`):
```yaml
network:
  listen_port: 9000
  enable_mdns: true
  enable_dht: true
  bootstrap_nodes:
    - "bootstrap1.bbs-p2p.example.com:8468"
    - "bootstrap2.bbs-p2p.example.com:8468"
  max_peers: 100
  connection_timeout: 30

ui:
  theme: "dark"
  enable_acrylic: true
  font_size: 12
  language: "en"

security:
  key_store_path: "~/.bbs_p2p/keys/keystore.enc"
  encryption_algorithm: "chacha20poly1305"
  require_signature_verification: true

storage:
  db_path: "~/.bbs_p2p/data/bbs.db"
  max_attachment_size: 52428800  # 50 MB
  cache_size: 1073741824  # 1 GB

sync:
  interval: 30
  batch_size: 50
  max_retries: 3

logging:
  level: "INFO"
  log_path: "~/.bbs_p2p/logs/app.log"
  max_log_size: 10485760  # 10 MB
  backup_count: 5
```

### Packaging with PyInstaller

**Build Script** (`build.py`):
```python
import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--name=BBS-P2P',
    '--windowed',
    '--onefile',
    '--icon=resources/icon.ico',
    '--add-data=resources:resources',
    '--add-data=config/settings.yaml:config',
    '--hidden-import=PySide6',
    '--hidden-import=qfluentwidgets',
    '--hidden-import=cryptography',
    '--hidden-import=zeroconf',
    '--collect-all=qfluentwidgets',
])
```

**Platform-Specific Notes**:
- **Windows**: Include Visual C++ Redistributable
- **macOS**: Code sign and notarize for Gatekeeper
- **Linux**: Create AppImage or Flatpak for distribution

### Asyncio Integration with Qt

**Event Loop Bridge** (`core/qt_asyncio.py`):
```python
import asyncio
from PySide6.QtCore import QTimer

class QtAsyncioEventLoop:
    def __init__(self, app):
        self.app = app
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Integrate asyncio with Qt event loop
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_events)
        self.timer.start(10)  # Process every 10ms
    
    def _process_events(self):
        self.loop.stop()
        self.loop.run_forever()
    
    def run_coroutine(self, coro):
        return asyncio.ensure_future(coro, loop=self.loop)
```

**Usage in UI**:
```python
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.event_loop = QtAsyncioEventLoop(QApplication.instance())
    
    def on_send_message_clicked(self):
        content = self.message_input.text()
        # Run async operation without blocking UI
        self.event_loop.run_coroutine(
            self.send_message_async(content)
        )
    
    async def send_message_async(self, content: str):
        try:
            await self.chat_manager.send_message(content)
            self.message_sent.emit()  # Qt signal
        except Exception as e:
            self.error_occurred.emit(str(e))
```

## Future Enhancements

### Phase 2 Features (Post-MVP)

1. **NAT Traversal**
   - Implement STUN for public IP discovery
   - UDP hole punching for direct peer connections
   - TURN relay as fallback for symmetric NATs

2. **DHT Implementation**
   - Full Kademlia DHT implementation
   - Distributed peer discovery without bootstrap servers
   - Board metadata replication in DHT

3. **Advanced Moderation**
   - Web of trust reputation system
   - Delegated moderation (moderator hierarchies)
   - Content filtering based on trust scores

4. **Rich Media Support**
   - Inline image display
   - Video/audio playback
   - Markdown rendering with syntax highlighting

5. **Mobile Clients**
   - Android app using Kivy or React Native
   - iOS app using React Native
   - Sync with desktop via encrypted cloud backup

6. **Performance Optimizations**
   - Message compression (zstd)
   - Incremental sync (only fetch new posts)
   - Database indexing for large boards
   - Lazy loading for UI components

7. **Privacy Enhancements**
   - Tor integration for anonymous connections
   - Onion routing for metadata protection
   - Disposable identities for anonymous posting

### Known Limitations

1. **Bootstrap Dependency**: Initial DHT connection requires at least one reachable bootstrap node
2. **Clock Skew**: Vector clocks assume reasonable time synchronization (±5 minutes)
3. **Sybil Attacks**: No built-in protection against single attacker creating many identities
4. **Storage Growth**: Append-only logs grow indefinitely (need pruning strategy)
5. **Network Partitions**: Extended partitions may cause significant sync overhead on reconnection

### Mitigation Strategies

1. **Bootstrap**: Provide multiple bootstrap nodes, allow user-configured nodes, fallback to mDNS-only mode
2. **Clock Skew**: Implement NTP client for time synchronization, reject messages with excessive skew
3. **Sybil**: Implement proof-of-work or proof-of-stake for identity creation (future)
4. **Storage**: Implement configurable retention policies, archive old posts to separate database
5. **Partitions**: Implement efficient delta sync, compress sync payloads, prioritize recent posts

## Development Roadmap

### Milestone 1: Core Infrastructure (Weeks 1-2)
- Crypto module with key generation, signing, encryption
- Database schema and ORM models
- Basic network manager with TCP server/client
- Configuration management

### Milestone 2: Peer Discovery (Weeks 3-4)
- mDNS service implementation
- Handshake protocol
- Peer connection management
- Basic message exchange

### Milestone 3: Data Sync (Weeks 5-6)
- Vector clock implementation
- Sync manager with conflict resolution
- Post replication
- Message deduplication

### Milestone 4: UI Foundation (Weeks 7-8)
- Main window with QFluentWidgets
- Navigation interface
- Board list view
- Thread list view
- Post display

### Milestone 5: Core Features (Weeks 9-10)
- Post creation and signing
- Private messaging
- File attachments
- Settings panel

### Milestone 6: Polish & Testing (Weeks 11-12)
- Comprehensive test suite
- Error handling improvements
- Performance optimization
- Documentation
- Packaging for distribution

**Total Estimated Timeline**: 12 weeks for MVP
