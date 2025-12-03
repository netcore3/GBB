# File Attachment Usage Guide

This document demonstrates how to use the FileManager for handling file attachments in the P2P Encrypted BBS application.

## Overview

The FileManager provides functionality for:
- Attaching files to posts and private messages
- Computing SHA-256 hashes for integrity verification
- Encrypting files for secure storage
- Splitting files into 64KB chunks for network transmission
- Reassembling and verifying received file chunks

## Basic Usage

### 1. Initialize FileManager

```python
from pathlib import Path
from core.crypto_manager import CryptoManager
from core.network_manager import NetworkManager
from core.file_manager import FileManager
from core.db_manager import DBManager
from models.database import Attachment

# Initialize dependencies
crypto = CryptoManager()
identity = crypto.generate_identity()
network = NetworkManager(identity, crypto, enable_mdns=False)
file_manager = FileManager(crypto, network)
db_manager = DBManager(Path("data/bbs.db"))
db_manager.initialize_database()
```

### 2. Attach a File to a Post

```python
from pathlib import Path

# Attach file to post
file_path = Path("documents/report.pdf")
post_id = "post_123"

attachment = file_manager.attach_file_to_post(
    file_path=file_path,
    post_id=post_id,
    mime_type="application/pdf"  # Optional, auto-detected if not provided
)

# Save attachment to database
db_attachment = Attachment(
    id=attachment.id,
    post_id=attachment.post_id,
    message_id=attachment.message_id,
    filename=attachment.filename,
    file_hash=attachment.file_hash,
    file_size=attachment.file_size,
    mime_type=attachment.mime_type,
    encrypted_data=attachment.encrypted_data
)
db_manager.save_attachment(db_attachment)

print(f"Attached {attachment.filename} ({attachment.file_size} bytes)")
print(f"SHA-256 hash: {attachment.file_hash}")
```

### 3. Attach a File to a Private Message

```python
# Attach file to private message
file_path = Path("images/photo.jpg")
message_id = "message_456"

attachment = file_manager.attach_file_to_message(
    file_path=file_path,
    message_id=message_id,
    mime_type="image/jpeg"
)

# Save to database
db_attachment = Attachment(
    id=attachment.id,
    post_id=attachment.post_id,
    message_id=attachment.message_id,
    filename=attachment.filename,
    file_hash=attachment.file_hash,
    file_size=attachment.file_size,
    mime_type=attachment.mime_type,
    encrypted_data=attachment.encrypted_data
)
db_manager.save_attachment(db_attachment)
```

### 4. Send File to a Peer

```python
import asyncio

async def send_file_example():
    # Assume peer is already connected
    peer_id = "peer_abc123"
    
    # Attach file
    file_path = Path("documents/presentation.pptx")
    post_id = "post_789"
    attachment = file_manager.attach_file_to_post(file_path, post_id)
    
    # Send file chunks to peer
    await file_manager.send_file_chunks(peer_id, attachment)
    
    print(f"Sent {attachment.filename} to peer {peer_id[:8]}")

# Run async function
asyncio.run(send_file_example())
```

### 5. Receive File from a Peer

```python
# Set up callbacks for file reception
def on_file_received(attachment):
    """Called when a file transfer completes"""
    print(f"Received file: {attachment.filename}")
    print(f"Size: {attachment.file_size} bytes")
    print(f"Hash: {attachment.file_hash}")
    
    # Save to database
    db_attachment = Attachment(
        id=attachment.id,
        post_id=attachment.post_id,
        message_id=attachment.message_id,
        filename=attachment.filename,
        file_hash=attachment.file_hash,
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        encrypted_data=attachment.encrypted_data
    )
    db_manager.save_attachment(db_attachment)

def on_transfer_progress(file_id, received_chunks, total_chunks):
    """Called when a chunk is received"""
    progress = (received_chunks / total_chunks) * 100
    print(f"Transfer progress: {progress:.1f}% ({received_chunks}/{total_chunks} chunks)")

# Register callbacks
file_manager.on_file_received = on_file_received
file_manager.on_transfer_progress = on_transfer_progress

# Handle incoming messages from network
def on_message_received(peer_id, message):
    """Handle incoming network messages"""
    if message.msg_type == "FILE_METADATA":
        file_manager.handle_file_metadata(peer_id, message)
    elif message.msg_type == "FILE_CHUNK":
        file_manager.handle_file_chunk(peer_id, message)

# Register network callback
network.on_message_received = on_message_received
```

### 6. Save Attachment to Disk

```python
# Retrieve attachment from database
attachment_id = "attachment_123"
db_attachment = db_manager.get_attachment_by_id(attachment_id)

if db_attachment:
    # Convert database model to FileAttachment
    from core.file_manager import FileAttachment
    
    attachment = FileAttachment(
        id=db_attachment.id,
        filename=db_attachment.filename,
        file_size=db_attachment.file_size,
        mime_type=db_attachment.mime_type,
        file_hash=db_attachment.file_hash,
        encrypted_data=db_attachment.encrypted_data,
        post_id=db_attachment.post_id,
        message_id=db_attachment.message_id
    )
    
    # Save to disk
    output_path = Path("downloads") / attachment.filename
    file_manager.save_attachment_to_file(attachment, output_path)
    
    print(f"Saved attachment to {output_path}")
```

### 7. Monitor Active Transfers

```python
# Get list of active file transfers
transfers = file_manager.get_active_transfers()

for transfer in transfers:
    print(f"File: {transfer['filename']}")
    print(f"Progress: {transfer['progress'] * 100:.1f}%")
    print(f"Chunks: {transfer['received_chunks']}/{transfer['total_chunks']}")
    print()

# Cancel a transfer if needed
file_id = "file_123"
file_manager.cancel_transfer(file_id)
```

## Error Handling

```python
from core.file_manager import (
    FileError,
    FileTooLargeError,
    FileTransferError,
    FileVerificationError
)

try:
    # Attach file
    attachment = file_manager.attach_file_to_post(file_path, post_id)
    
except FileTooLargeError as e:
    print(f"File is too large: {e}")
    # Maximum file size is 50 MB
    
except FileError as e:
    print(f"File operation failed: {e}")

try:
    # Send file
    await file_manager.send_file_chunks(peer_id, attachment)
    
except FileTransferError as e:
    print(f"File transfer failed: {e}")
    
except NetworkError as e:
    print(f"Network error: {e}")
```

## Configuration

File attachment constants can be found in `core/file_manager.py`:

```python
CHUNK_SIZE = 64 * 1024  # 64 KB chunks
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB max file size
```

## Security Considerations

1. **Encryption**: All files are encrypted before storage using ChaCha20-Poly1305 AEAD
2. **Integrity**: SHA-256 hashes ensure file integrity during transfer
3. **Size Limits**: Files are limited to 50 MB to prevent resource exhaustion
4. **Chunking**: Files are split into 64 KB chunks for efficient transmission
5. **Verification**: Hash verification occurs after reassembly to detect corruption

## Integration with Network Protocol

The FileManager integrates with the NetworkManager through two message types:

1. **FILE_METADATA**: Sent before chunks to provide file information
   ```python
   {
       "type": "FILE_METADATA",
       "payload": {
           "file_id": "uuid",
           "filename": "document.pdf",
           "file_size": 1024000,
           "file_hash": "sha256_hash",
           "mime_type": "application/pdf",
           "total_chunks": 16,
           "post_id": "post_123",
           "message_id": null
       }
   }
   ```

2. **FILE_CHUNK**: Sent for each chunk of the file
   ```python
   {
       "type": "FILE_CHUNK",
       "payload": {
           "file_id": "uuid",
           "chunk_index": 0,
           "total_chunks": 16,
           "data": b"...",  # Chunk data
           "file_hash": "sha256_hash"
       }
   }
   ```

All messages are encrypted using the session key established during the handshake protocol.
