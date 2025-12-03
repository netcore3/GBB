"""
Unit tests for FileManager

Tests cover:
- File attachment to posts and messages
- SHA-256 hash computation
- File encryption/decryption
- File chunking
- File transfer (send/receive)
- Hash verification
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from core.crypto_manager import CryptoManager
from core.network_manager import NetworkManager, Message
from core.file_manager import (
    FileManager,
    FileAttachment,
    FileChunk,
    FileError,
    FileTooLargeError,
    FileVerificationError,
    CHUNK_SIZE,
    MAX_FILE_SIZE
)


@pytest.fixture
def crypto_manager():
    """Fixture providing a CryptoManager instance"""
    return CryptoManager()


@pytest.fixture
def identity(crypto_manager):
    """Fixture providing a generated identity"""
    return crypto_manager.generate_identity()


@pytest.fixture
def network_manager(identity, crypto_manager):
    """Fixture providing a NetworkManager instance"""
    return NetworkManager(identity, crypto_manager, enable_mdns=False)


@pytest.fixture
def file_manager(crypto_manager, network_manager):
    """Fixture providing a FileManager instance"""
    return FileManager(crypto_manager, network_manager)


@pytest.fixture
def temp_file():
    """Fixture providing a temporary test file"""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        test_data = b"This is test file content for BBS file attachment testing.\n" * 100
        f.write(test_data)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def large_temp_file():
    """Fixture providing a large temporary test file (1MB)"""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        # Create 1MB file
        test_data = b"X" * (1024 * 1024)
        f.write(test_data)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestFileAttachment:
    """Tests for file attachment operations"""
    
    def test_attach_file_to_post(self, file_manager, temp_file):
        """Test attaching a file to a post"""
        post_id = "test_post_123"
        
        attachment = file_manager.attach_file_to_post(
            temp_file,
            post_id,
            mime_type="text/plain"
        )
        
        assert attachment.filename == temp_file.name
        assert attachment.post_id == post_id
        assert attachment.message_id is None
        assert attachment.mime_type == "text/plain"
        assert attachment.file_size > 0
        assert len(attachment.file_hash) == 64  # SHA-256 hex length
        assert len(attachment.encrypted_data) > 0
    
    def test_attach_file_to_message(self, file_manager, temp_file):
        """Test attaching a file to a private message"""
        message_id = "test_message_456"
        
        attachment = file_manager.attach_file_to_message(
            temp_file,
            message_id,
            mime_type="text/plain"
        )
        
        assert attachment.filename == temp_file.name
        assert attachment.message_id == message_id
        assert attachment.post_id is None
        assert attachment.mime_type == "text/plain"
        assert attachment.file_size > 0
        assert len(attachment.file_hash) == 64
        assert len(attachment.encrypted_data) > 0
    
    def test_attach_nonexistent_file(self, file_manager):
        """Test attaching a file that doesn't exist"""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(FileError, match="File not found"):
            file_manager.attach_file_to_post(nonexistent_path, "post_123")
    
    def test_attach_file_too_large(self, file_manager):
        """Test attaching a file that exceeds maximum size"""
        # Create a temporary file larger than MAX_FILE_SIZE
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write just enough to exceed the limit
            f.write(b"X" * (MAX_FILE_SIZE + 1))
            large_file = Path(f.name)
        
        try:
            with pytest.raises(FileTooLargeError, match="exceeds maximum"):
                file_manager.attach_file_to_post(large_file, "post_123")
        finally:
            if large_file.exists():
                large_file.unlink()
    
    def test_mime_type_detection(self, file_manager):
        """Test automatic MIME type detection"""
        # Create a temporary .json file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{"test": "data"}')
            json_file = Path(f.name)
        
        try:
            attachment = file_manager.attach_file_to_post(json_file, "post_123")
            # MIME type should be detected as application/json or text/json
            assert 'json' in attachment.mime_type.lower()
        finally:
            if json_file.exists():
                json_file.unlink()


class TestFileChunking:
    """Tests for file chunking operations"""
    
    def test_split_file_into_chunks(self, file_manager, temp_file):
        """Test splitting a file into chunks"""
        attachment = file_manager.attach_file_to_post(temp_file, "post_123")
        
        chunks = file_manager.split_file_into_chunks(attachment)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, FileChunk) for chunk in chunks)
        assert all(chunk.file_id == attachment.id for chunk in chunks)
        assert all(chunk.file_hash == attachment.file_hash for chunk in chunks)
        
        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)
    
    def test_chunk_size(self, file_manager, large_temp_file):
        """Test that chunks are properly sized"""
        attachment = file_manager.attach_file_to_post(large_temp_file, "post_123")
        
        chunks = file_manager.split_file_into_chunks(attachment)
        
        # All chunks except possibly the last should be CHUNK_SIZE
        for i, chunk in enumerate(chunks[:-1]):
            assert len(chunk.data) == CHUNK_SIZE
        
        # Last chunk can be smaller or equal to CHUNK_SIZE
        assert len(chunks[-1].data) <= CHUNK_SIZE
    
    def test_reassemble_chunks(self, file_manager, temp_file):
        """Test reassembling file from chunks"""
        # Read original file data
        with open(temp_file, 'rb') as f:
            original_data = f.read()
        
        # Attach and chunk the file
        attachment = file_manager.attach_file_to_post(temp_file, "post_123")
        chunks = file_manager.split_file_into_chunks(attachment)
        
        # Create a mock transfer object
        from core.file_manager import FileTransfer
        transfer = FileTransfer(
            file_id=attachment.id,
            filename=attachment.filename,
            file_size=attachment.file_size,
            file_hash=attachment.file_hash,
            mime_type=attachment.mime_type,
            total_chunks=len(chunks)
        )
        
        # Add all chunks
        for chunk in chunks:
            transfer.received_chunks[chunk.chunk_index] = chunk.data
        
        # Reassemble
        reassembled_data = file_manager._reassemble_chunks(transfer)
        
        # Verify reassembled data matches original
        assert reassembled_data == original_data


class TestHashVerification:
    """Tests for hash computation and verification"""
    
    def test_hash_computation(self, file_manager, temp_file):
        """Test SHA-256 hash computation"""
        # Read file data
        with open(temp_file, 'rb') as f:
            file_data = f.read()
        
        # Compute hash using file manager
        computed_hash = file_manager._compute_hash(file_data)
        
        # Verify hash format (64 hex characters)
        assert len(computed_hash) == 64
        assert all(c in '0123456789abcdef' for c in computed_hash)
        
        # Compute hash independently
        import hashlib
        expected_hash = hashlib.sha256(file_data).hexdigest()
        
        assert computed_hash == expected_hash
    
    def test_hash_verification_success(self, file_manager, temp_file):
        """Test successful hash verification"""
        attachment = file_manager.attach_file_to_post(temp_file, "post_123")
        
        # Save and reload - should verify hash successfully
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.txt"
            file_manager.save_attachment_to_file(attachment, output_path)
            
            assert output_path.exists()
    
    def test_hash_verification_failure(self, file_manager, temp_file):
        """Test hash verification failure with corrupted data"""
        attachment = file_manager.attach_file_to_post(temp_file, "post_123")
        
        # Corrupt the encrypted data
        corrupted_data = bytearray(attachment.encrypted_data)
        corrupted_data[-1] ^= 0xFF  # Flip bits in last byte
        attachment.encrypted_data = bytes(corrupted_data)
        
        # Attempt to save - should fail hash verification
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.txt"
            
            # This should raise an error during decryption or hash verification
            with pytest.raises((FileVerificationError, Exception)):
                file_manager.save_attachment_to_file(attachment, output_path)


class TestFileEncryption:
    """Tests for file encryption and decryption"""
    
    def test_encrypt_decrypt_roundtrip(self, file_manager):
        """Test encryption and decryption round-trip"""
        original_data = b"Test file content for encryption"
        
        # Encrypt
        encrypted_data = file_manager._encrypt_file_data(original_data)
        
        # Verify encrypted data is different and longer (includes key + nonce + tag)
        assert encrypted_data != original_data
        assert len(encrypted_data) > len(original_data)
        
        # Decrypt
        decrypted_data = file_manager._decrypt_file_data(encrypted_data)
        
        # Verify decrypted data matches original
        assert decrypted_data == original_data
    
    def test_save_and_load_attachment(self, file_manager, temp_file):
        """Test saving attachment to disk and loading it back"""
        # Read original file
        with open(temp_file, 'rb') as f:
            original_data = f.read()
        
        # Create attachment
        attachment = file_manager.attach_file_to_post(temp_file, "post_123")
        
        # Save to new location
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "saved_file.txt"
            file_manager.save_attachment_to_file(attachment, output_path)
            
            # Read saved file
            with open(output_path, 'rb') as f:
                saved_data = f.read()
            
            # Verify data matches original
            assert saved_data == original_data


class TestFileTransferTracking:
    """Tests for file transfer tracking"""
    
    def test_handle_file_metadata(self, file_manager):
        """Test handling incoming file metadata"""
        metadata_msg = Message(
            msg_type="FILE_METADATA",
            payload={
                "file_id": "file_123",
                "filename": "test.txt",
                "file_size": 1024,
                "file_hash": "a" * 64,
                "mime_type": "text/plain",
                "total_chunks": 2,
                "post_id": "post_123",
                "message_id": None
            }
        )
        
        file_manager.handle_file_metadata("peer_123", metadata_msg)
        
        # Verify transfer was created
        assert "file_123" in file_manager.active_transfers
        transfer = file_manager.active_transfers["file_123"]
        assert transfer.filename == "test.txt"
        assert transfer.file_size == 1024
        assert transfer.total_chunks == 2
    
    def test_get_active_transfers(self, file_manager):
        """Test getting list of active transfers"""
        # Create a mock transfer
        metadata_msg = Message(
            msg_type="FILE_METADATA",
            payload={
                "file_id": "file_123",
                "filename": "test.txt",
                "file_size": 1024,
                "file_hash": "a" * 64,
                "mime_type": "text/plain",
                "total_chunks": 2,
                "post_id": "post_123",
                "message_id": None
            }
        )
        
        file_manager.handle_file_metadata("peer_123", metadata_msg)
        
        # Get active transfers
        transfers = file_manager.get_active_transfers()
        
        assert len(transfers) == 1
        assert transfers[0]["file_id"] == "file_123"
        assert transfers[0]["filename"] == "test.txt"
        assert transfers[0]["progress"] == 0.0
    
    def test_cancel_transfer(self, file_manager):
        """Test cancelling an active transfer"""
        # Create a mock transfer
        metadata_msg = Message(
            msg_type="FILE_METADATA",
            payload={
                "file_id": "file_123",
                "filename": "test.txt",
                "file_size": 1024,
                "file_hash": "a" * 64,
                "mime_type": "text/plain",
                "total_chunks": 2,
                "post_id": "post_123",
                "message_id": None
            }
        )
        
        file_manager.handle_file_metadata("peer_123", metadata_msg)
        
        # Cancel transfer
        file_manager.cancel_transfer("file_123")
        
        # Verify transfer was removed
        assert "file_123" not in file_manager.active_transfers
