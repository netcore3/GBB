<p align="center">
  ![GhostBBs](GhostBBs.jpeg "GhostBBs ")
</p>


# BBS P2P - Decentralized Encrypted Bulletin Board System

A modern, peer-to-peer bulletin board system with end-to-end encryption, built with Python, Qt, and QFluentWidgets.

## Features

- 🔐 **End-to-End Encryption**: All messages encrypted with forward secrecy
- 🌐 **Decentralized**: No central servers, pure P2P architecture
- 🔍 **Auto-Discovery**: Automatic peer discovery via mDNS (LAN) and DHT (Internet)
- 💬 **Threaded Discussions**: Organize conversations in boards and threads
- 📨 **Private Messaging**: Encrypted direct messages between peers
- 📎 **File Sharing**: Attach files to posts and messages
- 🎨 **Modern UI**: Fluent Design interface with dark/light themes
- 🛡️ **Moderation**: Cryptographically signed moderation actions
- ✅ **Verified Identity**: Ed25519 signatures on all posts

## Architecture

The application is built with a clean layered architecture:

- **UI Layer**: PySide6 + QFluentWidgets (Fluent Design)
- **Application Logic**: Board, Thread, Chat, and Moderation managers
- **Networking**: Asyncio-based P2P with mDNS discovery
- **Cryptography**: Ed25519 signing + X25519 encryption
- **Storage**: SQLite + SQLAlchemy ORM
- **Sync**: Vector clock-based conflict resolution

## Requirements

- Python 3.11 or higher
- Windows, macOS, or Linux

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/bbs-p2p.git
cd bbs-p2p

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

#Windows
set PATH=%PATH%;C:\path\to\qt\bin

### Demo Mode

Test the P2P functionality locally by running multiple instances:

```bash
# Terminal 1 - First peer
python main.py --demo --port 9001

# Terminal 2 - Second peer (auto-connects to first)
python main.py --demo --port 9002 --connect localhost:9001
```

## Configuration

Configuration is stored in `~/.bbs_p2p/config/settings.yaml`. Key settings:

- **network.listen_port**: Port for P2P connections (default: 9000)
- **network.enable_mdns**: Enable local network discovery (default: true)
- **ui.theme**: UI theme - "dark" or "light" (default: "dark")
- **sync.interval**: Sync interval in seconds (default: 30)

## Security

- **Identity**: Ed25519 signing keys + X25519 encryption keys
- **Transport**: ChaCha20-Poly1305 AEAD encryption with forward secrecy
- **Private Messages**: X25519 sealed box encryption
- **Keystore**: Argon2id + AES-GCM encrypted key storage
- **Signatures**: All posts cryptographically signed and verified

See [docs/threat_model.md](docs/threat_model.md) for detailed security analysis.

## Documentation

- [Architecture](docs/architecture.md) - System design and components
- [Protocol](docs/protocol.md) - Network protocol specification
- [Threat Model](docs/threat_model.md) - Security analysis

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=ui --cov=logic

# Run specific test file
pytest tests/test_crypto.py -v
```

### Code Style

```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy core/ ui/ logic/
```

## Building Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
python build.py

# Executable will be in dist/ folder
```

## Project Status

🚧 **Alpha** - Core functionality implemented, testing in progress

### Completed
- ✅ Project structure and configuration
- ✅ Cryptography module (signing, encryption, keystore)
- ✅ Database models and ORM
- ✅ Network manager with handshake protocol
- ✅ mDNS peer discovery
- ✅ Basic UI with QFluentWidgets

### In Progress
- 🔄 Synchronization manager
- 🔄 File attachment support
- 🔄 Complete UI implementation

### Planned
- 📋 DHT implementation for global discovery
- 📋 NAT traversal (STUN/TURN)
- 📋 Mobile clients
- 📋 Advanced moderation features

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [PySide6](https://www.qt.io/qt-for-python)
- UI powered by [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- Cryptography via [cryptography](https://cryptography.io/)
- mDNS discovery using [zeroconf](https://github.com/python-zeroconf/python-zeroconf)
