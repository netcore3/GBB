"""
Integration tests for file transfer functionality

Tests cover:
- 1MB file attachment and transfer between peers
- Hash verification on recipient
- Chunked transfer with simulated packet loss
"""

import asyncio
import tempfile
import random
from pathlib import Path
from unittest.mock import patch

import pytest

from core.crypto_manager import CryptoManager
from core.network_manager import NetworkManager, Message
from core.file_manager import FileManager, FileAttachment, FileVerificationError


@pytest.fixture
def crypto_manager():
    """Fixture providing a CryptoManager instance"""
    return CryptoManager()


@pytest.fixture
def identity_a(crypto_manager):
    """Fixture providing identity for peer A"""
    return crypto_manager.generate_identity()


@pytest.fixture
def identity_b(crypto_manager):
    """Fixture providing identity for peer B"""
    return crypto_manager.generate_identity()


@pytest.fixture
def network_manager_a(identity_a, crypto_manager):
    """Fixture providing NetworkManager for peer A"""
    return NetworkManager(identity_a, crypto_manager, enable_mdns=False)


@pytest.fixture
def network_manager_b(identity_b, crypto_manager):
    """Fixture providing NetworkManager for peer B"""
    return NetworkManager(identity_b, crypto_manager, enable_mdns=False)


@pytest.fixture
def file_manager_a(crypto_manager, network_manager_a):
    """Fixture providing FileManager for peer A"""
    return FileManager(crypto_manager, network_manager_a)


@pytest.fixture
def file_manager_b(crypto_manager, network_manager_b):
    """Fixture providing FileManager for peer B"""
    return FileManager(crypto_manager, network_manager_b)


@pytest.fixture
def large_test_file():
    """Fixture providing a 1MB test file"""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        # Create 1MB file with random data
        test_data = bytes([random.randint(0, 255) for _ in range(1024 * 1024)])
        f.write(test_data)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestFileTransferIntegration:
    """Integration tests for file transfer between peers"""
    
    @pytest.mark.asyncio
    async def test_1mb_file_transfer(
        self,
        network_manager_a,
        network_manager_b,
        file_manager_a,
        file_manager_b,
        large_test_file
    ):
        """Test transferring a 1MB file between two peers"""
        # Track received file
        received_attachment = None
        
        def on_file_received(attachment: FileAttachment):
            nonlocal received_attachment
            received_attachment = attachment
        
        file_manager_b.on_file_received = on_file_received
        
        # Wire up message handlers for file transfer
        def on_message_received_b(peer_id: str, message: Message):
            if message.msg_type == "FILE_METADATA":
                file_manager_b.handle_file_metadata(peer_id, message)
            elif message.msg_type == "FILE_CHUNK":
                file_manager_b.handle_file_chunk(peer_id, message)
        
        network_manager_b.on_message_received = on_message_received_b
        
        # Start network managers
        await network_manager_b.start(port=9001)
        await network_manager_a.start(port=9002)
        
        try:
            # Connect peer A to peer B
            await network_manager_a.connect_to_peer('127.0.0.1', 9001)
            
            # Wait for connection to establish
            await asyncio.sleep(0.5)
            
            # Verify peers are connected
            assert network_manager_a.is_peer_connected(network_manager_b.identity.peer_id)
            assert network_manager_b.is_peer_connected(network_manager_a.identity.peer_id)
            
            # Attach file on peer A
            attachment = file_manager_a.attach_file_to_post(
                large_test_file,
                post_id="test_post_123",
                mime_type="application/octet-stream"
            )
            
            # Verify attachment properties
            assert attachment.file_size == 1024 * 1024  # 1MB
            assert len(attachment.file_hash) == 64  # SHA-256 hex
            
            # Send file from peer A to peer B
            await file_manager_a.send_file_chunks(
                network_manager_b.identity.peer_id,
                attachment
            )
            
            # Wait for transfer to complete
            await asyncio.sleep(2.0)
            
            # Verify file was received
            assert received_attachment is not None
            assert received_attachment.filename == large_test_file.name
            assert received_attachment.file_size == 1024 * 1024
            assert received_attachment.file_hash == attachment.file_hash
            assert received_attachment.post_id == "test_post_123"
            
            # Save received file and verify content
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "received_file.bin"
                file_manager_b.save_attachment_to_file(received_attachment, output_path)
                
                # Read both files and compare
                with open(large_test_file, 'rb') as f:
                    original_data = f.read()
                
                with open(output_path, 'rb') as f:
                    received_data = f.read()
                
                assert received_data == original_data
        
        finally:
            # Cleanup
            await network_manager_a.stop()
            await network_manager_b.stop()
    
    @pytest.mark.asyncio
    async def test_hash_verification_on_recipient(
        self,
        network_manager_a,
        network_manager_b,
        file_manager_a,
        file_manager_b,
        large_test_file
    ):
        """Test that hash verification works correctly on the recipient"""
        # Track received file
        received_attachment = None
        verification_error = None
        
        def on_file_received(attachment: FileAttachment):
            nonlocal received_attachment
            received_attachment = attachment
        
        file_manager_b.on_file_received = on_file_received
        
        # Wire up message handlers for file transfer
        def on_message_received_b(peer_id: str, message: Message):
            if message.msg_type == "FILE_METADATA":
                file_manager_b.handle_file_metadata(peer_id, message)
            elif message.msg_type == "FILE_CHUNK":
                file_manager_b.handle_file_chunk(peer_id, message)
        
        network_manager_b.on_message_received = on_message_received_b
        
        # Start network managers
        await network_manager_b.start(port=9003)
        await network_manager_a.start(port=9004)
        
        try:
            # Connect peer A to peer B
            await network_manager_a.connect_to_peer('127.0.0.1', 9003)
            
            # Wait for connection to establish
            await asyncio.sleep(0.5)
            
            # Attach file on peer A
            attachment = file_manager_a.attach_file_to_post(
                large_test_file,
                post_id="test_post_456"
            )
            
            original_hash = attachment.file_hash
            
            # Send file from peer A to peer B
            await file_manager_a.send_file_chunks(
                network_manager_b.identity.peer_id,
                attachment
            )
            
            # Wait for transfer to complete
            await asyncio.sleep(2.0)
            
            # Verify file was received with correct hash
            assert received_attachment is not None
            assert received_attachment.file_hash == original_hash
            
            # Verify that saving the file works (hash is verified during save)
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "verified_file.bin"
                
                # This should succeed because hash is correct
                file_manager_b.save_attachment_to_file(received_attachment, output_path)
                assert output_path.exists()
                
                # Now corrupt the attachment and verify it fails
                corrupted_attachment = FileAttachment(
                    id=received_attachment.id,
                    filename=received_attachment.filename,
                    file_size=received_attachment.file_size,
                    mime_type=received_attachment.mime_type,
                    file_hash="0" * 64,  # Wrong hash
                    encrypted_data=received_attachment.encrypted_data,
                    post_id=received_attachment.post_id
                )
                
                output_path_2 = Path(tmpdir) / "corrupted_file.bin"
                
                # This should fail due to hash mismatch
                with pytest.raises(FileVerificationError, match="Hash mismatch"):
                    file_manager_b.save_attachment_to_file(corrupted_attachment, output_path_2)
        
        finally:
            # Cleanup
            await network_manager_a.stop()
            await network_manager_b.stop()
    
    @pytest.mark.asyncio
    async def test_chunked_transfer_with_packet_loss(
        self,
        network_manager_a,
        network_manager_b,
        file_manager_a,
        file_manager_b,
        large_test_file
    ):
        """Test file transfer with simulated packet loss"""
        # Track received file
        received_attachment = None
        dropped_chunks = []
        
        def on_file_received(attachment: FileAttachment):
            nonlocal received_attachment
            received_attachment = attachment
        
        file_manager_b.on_file_received = on_file_received
        
        # Wire up message handlers for file transfer
        def on_message_received_b(peer_id: str, message: Message):
            if message.msg_type == "FILE_METADATA":
                file_manager_b.handle_file_metadata(peer_id, message)
            elif message.msg_type == "FILE_CHUNK":
                file_manager_b.handle_file_chunk(peer_id, message)
        
        network_manager_b.on_message_received = on_message_received_b
        
        # Start network managers
        await network_manager_b.start(port=9005)
        await network_manager_a.start(port=9006)
        
        try:
            # Connect peer A to peer B
            await network_manager_a.connect_to_peer('127.0.0.1', 9005)
            
            # Wait for connection to establish
            await asyncio.sleep(0.5)
            
            # Attach file on peer A
            attachment = file_manager_a.attach_file_to_post(
                large_test_file,
                post_id="test_post_789"
            )
            
            # Patch the send_message method to simulate packet loss
            original_send = network_manager_a.send_message
            
            async def send_with_packet_loss(peer_id, message):
                # Drop 10% of FILE_CHUNK messages randomly
                if message.msg_type == "FILE_CHUNK" and random.random() < 0.10:
                    chunk_index = message.payload.get("chunk_index", -1)
                    dropped_chunks.append(chunk_index)
                    # Don't send this chunk
                    return
                # Send other messages normally
                await original_send(peer_id, message)
            
            network_manager_a.send_message = send_with_packet_loss
            
            # Send file from peer A to peer B
            await file_manager_a.send_file_chunks(
                network_manager_b.identity.peer_id,
                attachment
            )
            
            # Wait for initial transfer attempt
            await asyncio.sleep(2.0)
            
            # Check if any chunks were dropped
            if dropped_chunks:
                # File should not be complete yet
                assert received_attachment is None
                
                # Verify that the transfer is still active
                active_transfers = file_manager_b.get_active_transfers()
                assert len(active_transfers) == 1
                
                # Verify progress is less than 100%
                assert active_transfers[0]["progress"] < 1.0
                
                # Resend the dropped chunks
                chunks = file_manager_a.split_file_into_chunks(attachment)
                for chunk_index in dropped_chunks:
                    chunk = chunks[chunk_index]
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
                    # Send without packet loss
                    await original_send(network_manager_b.identity.peer_id, chunk_msg)
                
                # Wait for transfer to complete
                await asyncio.sleep(1.0)
            else:
                # No chunks were dropped, transfer should be complete
                pass
            
            # Verify file was eventually received
            assert received_attachment is not None
            assert received_attachment.file_hash == attachment.file_hash
            
            # Verify no active transfers remain
            active_transfers = file_manager_b.get_active_transfers()
            assert len(active_transfers) == 0
            
            # Verify file content is correct
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "recovered_file.bin"
                file_manager_b.save_attachment_to_file(received_attachment, output_path)
                
                with open(large_test_file, 'rb') as f:
                    original_data = f.read()
                
                with open(output_path, 'rb') as f:
                    received_data = f.read()
                
                assert received_data == original_data
        
        finally:
            # Cleanup
            await network_manager_a.stop()
            await network_manager_b.stop()
