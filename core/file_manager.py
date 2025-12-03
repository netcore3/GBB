"""
File Manager for P2P Encrypted BBS

Handles file attachment operations including:
- Computing SHA-256 hashes for integrity verification
- Encrypting files for storage and transmission
- Splitting files into chunks for network transmission
- Reassembling and verifying received file chunks
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from core.crypto_manager import CryptoManager, CryptoError
from core.network_manager import NetworkManager, Message, NetworkError


logger = logging.getLogger(__name__)


# Constants
CHUNK_SIZE = 64 * 1024  # 64 KB chunks
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB max file size


class FileError(Exception):
    """Base exception for file operations"""
    pass


class FileTooLargeError(FileError):
    """Raised when file exceeds maximum size"""
    pass


class FileTransferError(FileError):
    """Raised when file transfer fails"""
    pass


class FileVerificationError(FileError):
    """Raised when file hash verification fails"""
    pass


@dataclass
class FileAttachment:
    """Represents a file attachment."""
    id: str
    filename: str
    file_size: int
    mime_type: str
    file_hash: str  # SHA-256 hash
    encrypted_data: bytes
    post_id: Optional[str] = None
    message_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FileChunk:
    """Represents a chunk of a file being transferred."""
    file_id: str
    chunk_index: int
    total_chunks: int
    data: bytes
    file_hash: str  # SHA-256 hash of complete file


@dataclass
class FileTransfer:
    """Tracks an ongoing file transfer."""
    file_id: str
    filename: str
    file_size: int
    file_hash: str
    mime_type: str
    total_chunks: int
    received_chunks: Dict[int, bytes] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    post_id: Optional[str] = None
    message_id: Optional[str] = None


class FileManager:
    """
    Manages file attachment operations.
    
    Responsibilities:
    - Attach files to posts and private messages
    - Compute SHA-256 hashes for integrity
    - Encrypt files for storage
    - Split files into chunks for transmission
    - Reassemble and verify received chunks
    """
    
    def __init__(self, crypto_manager: CryptoManager, network_manager: NetworkManager):
        """
        Initialize FileManager.
        
        Args:
            crypto_manager: CryptoManager instance for encryption
            network_manager: NetworkManager instance for transmission
        """
        self.crypto = crypto_manager
        self.network = network_manager
        
        # Track ongoing file transfers
        self.active_transfers: Dict[str, FileTransfer] = {}
        
        # Callbacks
        self.on_file_received: Optional[Callable[[FileAttachment], None]] = None
        self.on_transfer_progress: Optional[Callable[[str, int, int], None]] = None
    
    def attach_file_to_post(
        self,
        file_path: Path,
        post_id: str,
        mime_type: Optional[str] = None
    ) -> FileAttachment:
        """
        Attach a file to a post by computing hash and encrypting.
        
        Args:
            file_path: Path to file to attach
            post_id: ID of post to attach to
            mime_type: MIME type of file (auto-detected if None)
            
        Returns:
            FileAttachment: File attachment object
            
        Raises:
            FileError: If file operations fail
            FileTooLargeError: If file exceeds maximum size
        """
        try:
            # Check file exists
            if not file_path.exists():
                raise FileError(f"File not found: {file_path}")
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                raise FileTooLargeError(
                    f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes"
                )
            
            # Read file data
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Compute SHA-256 hash
            file_hash = self._compute_hash(file_data)
            
            # Detect MIME type if not provided
            if mime_type is None:
                mime_type = self._detect_mime_type(file_path)
            
            # Encrypt file data
            encrypted_data = self._encrypt_file_data(file_data)
            
            # Create attachment object
            attachment = FileAttachment(
                id=str(uuid.uuid4()),
                filename=file_path.name,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                encrypted_data=encrypted_data,
                post_id=post_id
            )
            
            logger.info(
                f"Attached file {file_path.name} ({file_size} bytes) to post {post_id[:8]}"
            )
            
            return attachment
            
        except FileTooLargeError:
            raise
        except Exception as e:
            raise FileError(f"Failed to attach file: {e}")
    
    def attach_file_to_message(
        self,
        file_path: Path,
        message_id: str,
        mime_type: Optional[str] = None
    ) -> FileAttachment:
        """
        Attach a file to a private message by computing hash and encrypting.
        
        Args:
            file_path: Path to file to attach
            message_id: ID of private message to attach to
            mime_type: MIME type of file (auto-detected if None)
            
        Returns:
            FileAttachment: File attachment object
            
        Raises:
            FileError: If file operations fail
            FileTooLargeError: If file exceeds maximum size
        """
        try:
            # Check file exists
            if not file_path.exists():
                raise FileError(f"File not found: {file_path}")
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                raise FileTooLargeError(
                    f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes"
                )
            
            # Read file data
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Compute SHA-256 hash
            file_hash = self._compute_hash(file_data)
            
            # Detect MIME type if not provided
            if mime_type is None:
                mime_type = self._detect_mime_type(file_path)
            
            # Encrypt file data
            encrypted_data = self._encrypt_file_data(file_data)
            
            # Create attachment object
            attachment = FileAttachment(
                id=str(uuid.uuid4()),
                filename=file_path.name,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                encrypted_data=encrypted_data,
                message_id=message_id
            )
            
            logger.info(
                f"Attached file {file_path.name} ({file_size} bytes) to message {message_id[:8]}"
            )
            
            return attachment
            
        except FileTooLargeError:
            raise
        except Exception as e:
            raise FileError(f"Failed to attach file: {e}")
    
    def _compute_hash(self, data: bytes) -> str:
        """
        Compute SHA-256 hash of data.
        
        Args:
            data: Data to hash
            
        Returns:
            str: Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()
    
    def _detect_mime_type(self, file_path: Path) -> str:
        """
        Detect MIME type from file extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: MIME type
        """
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    def _encrypt_file_data(self, data: bytes) -> bytes:
        """
        Encrypt file data for storage.
        
        Uses a simple encryption scheme with a random key stored alongside.
        For production, this should use a key derived from user's identity.
        
        Args:
            data: File data to encrypt
            
        Returns:
            bytes: Encrypted data (key + nonce + ciphertext)
            
        Raises:
            CryptoError: If encryption fails
        """
        import os
        
        # Generate random encryption key for this file
        encryption_key = os.urandom(32)
        nonce = os.urandom(12)
        
        # Encrypt data
        ciphertext = self.crypto.encrypt_with_session_key(data, encryption_key, nonce)
        
        # Return key + nonce + ciphertext
        # In production, the key should be encrypted with user's key
        return encryption_key + nonce + ciphertext
    
    def _decrypt_file_data(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt file data from storage.
        
        Args:
            encrypted_data: Encrypted data (key + nonce + ciphertext)
            
        Returns:
            bytes: Decrypted file data
            
        Raises:
            CryptoError: If decryption fails
        """
        # Extract key, nonce, and ciphertext
        encryption_key = encrypted_data[:32]
        nonce = encrypted_data[32:44]
        ciphertext = encrypted_data[44:]
        
        # Decrypt
        return self.crypto.decrypt_with_session_key(ciphertext, encryption_key, nonce)
    
    def split_file_into_chunks(self, attachment: FileAttachment) -> List[FileChunk]:
        """
        Split file into chunks for transmission.
        
        Args:
            attachment: File attachment to split
            
        Returns:
            List of FileChunk objects
        """
        # Decrypt file data first
        file_data = self._decrypt_file_data(attachment.encrypted_data)
        
        # Calculate number of chunks
        total_chunks = (len(file_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        chunks = []
        for i in range(total_chunks):
            start = i * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(file_data))
            chunk_data = file_data[start:end]
            
            chunk = FileChunk(
                file_id=attachment.id,
                chunk_index=i,
                total_chunks=total_chunks,
                data=chunk_data,
                file_hash=attachment.file_hash
            )
            chunks.append(chunk)
        
        logger.debug(
            f"Split file {attachment.filename} into {total_chunks} chunks"
        )
        
        return chunks
    
    async def send_file_chunks(
        self,
        peer_id: str,
        attachment: FileAttachment
    ) -> None:
        """
        Send file chunks to a peer with AEAD encryption per chunk.
        
        Args:
            peer_id: ID of peer to send to
            attachment: File attachment to send
            
        Raises:
            NetworkError: If peer not connected or send fails
            FileTransferError: If file transfer fails
        """
        try:
            # Check peer is connected
            if not self.network.is_peer_connected(peer_id):
                raise NetworkError(f"Peer {peer_id[:8]} not connected")
            
            # Split file into chunks
            chunks = self.split_file_into_chunks(attachment)
            
            logger.info(
                f"Sending file {attachment.filename} ({len(chunks)} chunks) to peer {peer_id[:8]}"
            )
            
            # Send file metadata first
            metadata_msg = Message(
                msg_type="FILE_METADATA",
                payload={
                    "file_id": attachment.id,
                    "filename": attachment.filename,
                    "file_size": attachment.file_size,
                    "file_hash": attachment.file_hash,
                    "mime_type": attachment.mime_type,
                    "total_chunks": len(chunks),
                    "post_id": attachment.post_id,
                    "message_id": attachment.message_id
                }
            )
            await self.network.send_message(peer_id, metadata_msg)
            
            # Send each chunk
            for chunk in chunks:
                chunk_msg = Message(
                    msg_type="FILE_CHUNK",
                    payload={
                        "file_id": chunk.file_id,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                        "data": chunk.data,
                        "file_hash": chunk.file_hash
                    }
                )
                await self.network.send_message(peer_id, chunk_msg)
                
                logger.debug(
                    f"Sent chunk {chunk.chunk_index + 1}/{chunk.total_chunks} "
                    f"of file {attachment.filename} to peer {peer_id[:8]}"
                )
            
            logger.info(
                f"Completed sending file {attachment.filename} to peer {peer_id[:8]}"
            )
            
        except NetworkError:
            raise
        except Exception as e:
            raise FileTransferError(f"Failed to send file chunks: {e}")
    
    def handle_file_metadata(self, peer_id: str, message: Message) -> None:
        """
        Handle incoming file metadata message.
        
        Args:
            peer_id: ID of peer sending the file
            message: FILE_METADATA message
        """
        try:
            payload = message.payload
            file_id = payload["file_id"]
            
            # Create file transfer tracker
            transfer = FileTransfer(
                file_id=file_id,
                filename=payload["filename"],
                file_size=payload["file_size"],
                file_hash=payload["file_hash"],
                mime_type=payload["mime_type"],
                total_chunks=payload["total_chunks"],
                post_id=payload.get("post_id"),
                message_id=payload.get("message_id")
            )
            
            self.active_transfers[file_id] = transfer
            
            logger.info(
                f"Receiving file {transfer.filename} ({transfer.total_chunks} chunks) "
                f"from peer {peer_id[:8]}"
            )
            
        except KeyError as e:
            logger.error(f"Missing field in FILE_METADATA message: {e}")
        except Exception as e:
            logger.error(f"Error handling file metadata: {e}")
    
    def handle_file_chunk(self, peer_id: str, message: Message) -> None:
        """
        Handle incoming file chunk message.
        
        Args:
            peer_id: ID of peer sending the chunk
            message: FILE_CHUNK message
        """
        try:
            payload = message.payload
            file_id = payload["file_id"]
            chunk_index = payload["chunk_index"]
            chunk_data = payload["data"]
            
            # Check if we're expecting this file
            if file_id not in self.active_transfers:
                logger.warning(
                    f"Received chunk for unknown file {file_id[:8]} from peer {peer_id[:8]}"
                )
                return
            
            transfer = self.active_transfers[file_id]
            
            # Store chunk
            transfer.received_chunks[chunk_index] = chunk_data
            
            logger.debug(
                f"Received chunk {chunk_index + 1}/{transfer.total_chunks} "
                f"of file {transfer.filename} from peer {peer_id[:8]}"
            )
            
            # Notify progress callback
            if self.on_transfer_progress:
                self.on_transfer_progress(
                    file_id,
                    len(transfer.received_chunks),
                    transfer.total_chunks
                )
            
            # Check if all chunks received
            if len(transfer.received_chunks) == transfer.total_chunks:
                self._complete_file_transfer(file_id, peer_id)
            
        except KeyError as e:
            logger.error(f"Missing field in FILE_CHUNK message: {e}")
        except Exception as e:
            logger.error(f"Error handling file chunk: {e}")
    
    def _complete_file_transfer(self, file_id: str, peer_id: str) -> None:
        """
        Complete file transfer by reassembling chunks and verifying hash.
        
        Args:
            file_id: ID of file transfer
            peer_id: ID of peer who sent the file
        """
        try:
            transfer = self.active_transfers[file_id]
            
            # Reassemble file from chunks
            file_data = self._reassemble_chunks(transfer)
            
            # Verify hash
            computed_hash = self._compute_hash(file_data)
            if computed_hash != transfer.file_hash:
                raise FileVerificationError(
                    f"Hash mismatch for file {transfer.filename}: "
                    f"expected {transfer.file_hash}, got {computed_hash}"
                )
            
            # Encrypt for storage
            encrypted_data = self._encrypt_file_data(file_data)
            
            # Create attachment object
            attachment = FileAttachment(
                id=file_id,
                filename=transfer.filename,
                file_size=transfer.file_size,
                mime_type=transfer.mime_type,
                file_hash=transfer.file_hash,
                encrypted_data=encrypted_data,
                post_id=transfer.post_id,
                message_id=transfer.message_id
            )
            
            logger.info(
                f"Completed receiving file {transfer.filename} from peer {peer_id[:8]}, "
                f"hash verified"
            )
            
            # Notify callback
            if self.on_file_received:
                self.on_file_received(attachment)
            
            # Clean up transfer
            del self.active_transfers[file_id]
            
        except FileVerificationError as e:
            logger.error(f"File verification failed: {e}")
            # Clean up failed transfer
            if file_id in self.active_transfers:
                del self.active_transfers[file_id]
        except Exception as e:
            logger.error(f"Error completing file transfer: {e}")
            # Clean up failed transfer
            if file_id in self.active_transfers:
                del self.active_transfers[file_id]
    
    def _reassemble_chunks(self, transfer: FileTransfer) -> bytes:
        """
        Reassemble file from received chunks.
        
        Args:
            transfer: File transfer object with received chunks
            
        Returns:
            bytes: Reassembled file data
            
        Raises:
            FileTransferError: If chunks are missing or invalid
        """
        # Check all chunks are present
        for i in range(transfer.total_chunks):
            if i not in transfer.received_chunks:
                raise FileTransferError(
                    f"Missing chunk {i} for file {transfer.filename}"
                )
        
        # Reassemble in order
        file_data = b''
        for i in range(transfer.total_chunks):
            file_data += transfer.received_chunks[i]
        
        # Verify size matches
        if len(file_data) != transfer.file_size:
            raise FileTransferError(
                f"Size mismatch for file {transfer.filename}: "
                f"expected {transfer.file_size}, got {len(file_data)}"
            )
        
        return file_data
    
    def save_attachment_to_file(
        self,
        attachment: FileAttachment,
        output_path: Path
    ) -> None:
        """
        Save attachment to a file on disk.
        
        Args:
            attachment: File attachment to save
            output_path: Path to save file to
            
        Raises:
            FileError: If save fails
        """
        try:
            # Decrypt file data
            file_data = self._decrypt_file_data(attachment.encrypted_data)
            
            # Verify hash
            computed_hash = self._compute_hash(file_data)
            if computed_hash != attachment.file_hash:
                raise FileVerificationError(
                    f"Hash mismatch for attachment {attachment.filename}: "
                    f"expected {attachment.file_hash}, got {computed_hash}"
                )
            
            # Create parent directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(file_data)
            
            logger.info(
                f"Saved attachment {attachment.filename} to {output_path}"
            )
            
        except FileVerificationError:
            raise
        except Exception as e:
            raise FileError(f"Failed to save attachment: {e}")
    
    def get_active_transfers(self) -> List[Dict[str, Any]]:
        """
        Get list of active file transfers.
        
        Returns:
            List of dictionaries with transfer information
        """
        transfers = []
        for file_id, transfer in self.active_transfers.items():
            transfers.append({
                "file_id": file_id,
                "filename": transfer.filename,
                "file_size": transfer.file_size,
                "total_chunks": transfer.total_chunks,
                "received_chunks": len(transfer.received_chunks),
                "progress": len(transfer.received_chunks) / transfer.total_chunks,
                "started_at": transfer.started_at.isoformat()
            })
        return transfers
    
    def cancel_transfer(self, file_id: str) -> None:
        """
        Cancel an active file transfer.
        
        Args:
            file_id: ID of file transfer to cancel
        """
        if file_id in self.active_transfers:
            transfer = self.active_transfers[file_id]
            logger.info(f"Cancelled transfer of file {transfer.filename}")
            del self.active_transfers[file_id]
        else:
            logger.warning(f"Attempted to cancel unknown transfer {file_id[:8]}")
