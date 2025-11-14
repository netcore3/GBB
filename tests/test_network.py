"""
Tests for NetworkManager - encrypted message transport.

Tests the core functionality of sending and receiving encrypted messages
with CBOR encoding, AEAD encryption, nonce management, and error handling.
"""

import pytest
import asyncio
from core.network_manager import NetworkManager, Message, NetworkError, MessageError
from core.crypto_manager import CryptoManager


@pytest.fixture
def crypto_manager():
    """Create a CryptoManager instance."""
    return CryptoManager()


@pytest.fixture
def identity1(crypto_manager):
    """Create first test identity."""
    return crypto_manager.generate_identity()


@pytest.fixture
def identity2(crypto_manager):
    """Create second test identity."""
    return crypto_manager.generate_identity()


@pytest.fixture
def network_manager1(identity1, crypto_manager):
    """Create first NetworkManager instance."""
    return NetworkManager(identity1, crypto_manager)


@pytest.fixture
def network_manager2(identity2, crypto_manager):
    """Create second NetworkManager instance."""
    return NetworkManager(identity2, crypto_manager)


@pytest.mark.asyncio
async def test_send_receive_encrypted_message(network_manager1, network_manager2):
    """Test sending and receiving encrypted messages between two peers."""
    # Start server on peer 2
    await network_manager2.start(port=9001, host='127.0.0.1')
    
    try:
        # Connect peer 1 to peer 2
        peer_id = await network_manager1.connect_to_peer('127.0.0.1', 9001)
        
        # Wait a moment for connection to stabilize
        await asyncio.sleep(0.1)
        
        # Create test message
        test_message = Message(
            msg_type="TEST",
            payload={"content": "Hello, encrypted world!", "number": 42}
        )
        
        # Set up message receiver
        received_messages = []
        
        def on_message(peer_id: str, message: Message):
            received_messages.append((peer_id, message))
        
        network_manager2.on_message_received = on_message
        
        # Send message from peer 1 to peer 2
        await network_manager1.send_message(peer_id, test_message)
        
        # Wait for message to be received
        await asyncio.sleep(0.2)
        
        # Verify message was received
        assert len(received_messages) == 1
        recv_peer_id, recv_message = received_messages[0]
        
        assert recv_message.msg_type == "TEST"
        assert recv_message.payload["content"] == "Hello, encrypted world!"
        assert recv_message.payload["number"] == 42
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_nonce_increment(network_manager1, network_manager2):
    """Test that nonces increment correctly for each message."""
    await network_manager2.start(port=9002, host='127.0.0.1')
    
    try:
        peer_id = await network_manager1.connect_to_peer('127.0.0.1', 9002)
        await asyncio.sleep(0.1)
        
        # Get peer connection
        peer = network_manager1.peers[peer_id]
        initial_send_nonce = peer.send_nonce
        
        # Send multiple messages
        for i in range(5):
            msg = Message(msg_type="TEST", payload={"seq": i})
            await network_manager1.send_message(peer_id, msg)
        
        # Verify nonce incremented
        assert peer.send_nonce == initial_send_nonce + 5
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_bidirectional_communication(network_manager1, network_manager2):
    """Test bidirectional encrypted message exchange."""
    await network_manager2.start(port=9003, host='127.0.0.1')
    
    try:
        # Connect peer 1 to peer 2
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9003)
        await asyncio.sleep(0.1)
        
        # Get peer 1's ID from peer 2's perspective
        peer1_id = list(network_manager2.peers.keys())[0]
        
        # Set up message receivers
        messages_at_peer1 = []
        messages_at_peer2 = []
        
        network_manager1.on_message_received = lambda pid, msg: messages_at_peer1.append(msg)
        network_manager2.on_message_received = lambda pid, msg: messages_at_peer2.append(msg)
        
        # Send message from peer 1 to peer 2
        msg1 = Message(msg_type="PING", payload={"from": "peer1"})
        await network_manager1.send_message(peer2_id, msg1)
        
        await asyncio.sleep(0.1)
        
        # Send message from peer 2 to peer 1
        msg2 = Message(msg_type="PONG", payload={"from": "peer2"})
        await network_manager2.send_message(peer1_id, msg2)
        
        await asyncio.sleep(0.1)
        
        # Verify both messages received
        assert len(messages_at_peer2) == 1
        assert messages_at_peer2[0].msg_type == "PING"
        
        assert len(messages_at_peer1) == 1
        assert messages_at_peer1[0].msg_type == "PONG"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_send_to_disconnected_peer(network_manager1):
    """Test error handling when sending to disconnected peer."""
    # Try to send to non-existent peer
    msg = Message(msg_type="TEST", payload={})
    
    with pytest.raises(NetworkError, match="not connected"):
        await network_manager1.send_message("fake_peer_id", msg)


@pytest.mark.asyncio
async def test_large_message_payload(network_manager1, network_manager2):
    """Test sending large message payloads."""
    await network_manager2.start(port=9004, host='127.0.0.1')
    
    try:
        peer_id = await network_manager1.connect_to_peer('127.0.0.1', 9004)
        await asyncio.sleep(0.1)
        
        received_messages = []
        network_manager2.on_message_received = lambda pid, msg: received_messages.append(msg)
        
        # Create large payload (1 MB of text)
        large_content = "x" * (1024 * 1024)
        msg = Message(msg_type="LARGE", payload={"data": large_content})
        
        await network_manager1.send_message(peer_id, msg)
        await asyncio.sleep(0.5)
        
        assert len(received_messages) == 1
        assert len(received_messages[0].payload["data"]) == 1024 * 1024
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_peer_connection_tracking(network_manager1, network_manager2):
    """Test peer connection state tracking."""
    await network_manager2.start(port=9005, host='127.0.0.1')
    
    try:
        # Initially no peers
        assert network_manager1.get_connection_count() == 0
        assert len(network_manager1.get_connected_peers()) == 0
        
        # Connect to peer
        peer_id = await network_manager1.connect_to_peer('127.0.0.1', 9005)
        await asyncio.sleep(0.1)
        
        # Verify peer is tracked
        assert network_manager1.get_connection_count() == 1
        assert network_manager1.is_peer_connected(peer_id)
        assert peer_id in network_manager1.get_connected_peers()
        
        # Get peer info
        peer_info = network_manager1.get_peer_info(peer_id)
        assert peer_info is not None
        assert peer_info["peer_id"] == peer_id
        assert peer_info["state"] == "connected"
        assert peer_info["address"] == "127.0.0.1"
        assert peer_info["port"] == 9005
        
        # Disconnect peer
        await network_manager1.disconnect_peer(peer_id)
        await asyncio.sleep(0.1)
        
        # Verify peer is removed
        assert network_manager1.get_connection_count() == 0
        assert not network_manager1.is_peer_connected(peer_id)
        assert peer_id not in network_manager1.get_connected_peers()
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_disconnect_peer_cleanup(network_manager1, network_manager2):
    """Test that disconnect_peer properly cleans up resources."""
    await network_manager2.start(port=9006, host='127.0.0.1')
    
    try:
        # Track connection events
        connected_peers = []
        disconnected_peers = []
        
        network_manager1.on_peer_connected = lambda pid: connected_peers.append(pid)
        network_manager1.on_peer_disconnected = lambda pid: disconnected_peers.append(pid)
        
        # Connect
        peer_id = await network_manager1.connect_to_peer('127.0.0.1', 9006)
        await asyncio.sleep(0.1)
        
        assert len(connected_peers) == 1
        assert peer_id in network_manager1.peers
        
        # Disconnect
        await network_manager1.disconnect_peer(peer_id)
        await asyncio.sleep(0.1)
        
        # Verify cleanup
        assert len(disconnected_peers) == 1
        assert peer_id not in network_manager1.peers
        
        # Try to disconnect again (should not raise error)
        await network_manager1.disconnect_peer(peer_id)
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_broadcast_to_board(network_manager1, network_manager2, crypto_manager):
    """Test broadcasting messages to peers subscribed to a board."""
    # Create a third peer
    identity3 = crypto_manager.generate_identity()
    network_manager3 = NetworkManager(identity3, crypto_manager)
    
    await network_manager1.start(port=9007, host='127.0.0.1')
    
    try:
        # Connect peer 2 and peer 3 to peer 1
        peer1_id_from_2 = await network_manager2.connect_to_peer('127.0.0.1', 9007)
        await asyncio.sleep(0.1)
        
        peer1_id_from_3 = await network_manager3.connect_to_peer('127.0.0.1', 9007)
        await asyncio.sleep(0.1)
        
        # Get peer IDs from peer 1's perspective
        peer2_id = list(network_manager1.peers.keys())[0]
        peer3_id = list(network_manager1.peers.keys())[1]
        
        # Subscribe peers to boards
        board_id_a = "board_a"
        board_id_b = "board_b"
        
        network_manager1.peers[peer2_id].board_subscriptions = [board_id_a]
        network_manager1.peers[peer3_id].board_subscriptions = [board_id_a, board_id_b]
        
        # Set up message receivers
        messages_at_peer2 = []
        messages_at_peer3 = []
        
        network_manager2.on_message_received = lambda pid, msg: messages_at_peer2.append(msg)
        network_manager3.on_message_received = lambda pid, msg: messages_at_peer3.append(msg)
        
        # Broadcast to board_a
        msg = Message(msg_type="POST", payload={"board": "board_a", "content": "Hello board A"})
        await network_manager1.broadcast_to_board(board_id_a, msg)
        await asyncio.sleep(0.2)
        
        # Both peers should receive the message
        assert len(messages_at_peer2) == 1
        assert len(messages_at_peer3) == 1
        assert messages_at_peer2[0].payload["board"] == "board_a"
        assert messages_at_peer3[0].payload["board"] == "board_a"
        
        # Broadcast to board_b
        msg2 = Message(msg_type="POST", payload={"board": "board_b", "content": "Hello board B"})
        await network_manager1.broadcast_to_board(board_id_b, msg2)
        await asyncio.sleep(0.2)
        
        # Only peer 3 should receive this message
        assert len(messages_at_peer2) == 1  # Still 1
        assert len(messages_at_peer3) == 2  # Now 2
        assert messages_at_peer3[1].payload["board"] == "board_b"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()
        await network_manager3.stop()


@pytest.mark.asyncio
async def test_get_peers_for_board(network_manager1, network_manager2, crypto_manager):
    """Test getting peers subscribed to a specific board."""
    identity3 = crypto_manager.generate_identity()
    network_manager3 = NetworkManager(identity3, crypto_manager)
    
    await network_manager1.start(port=9008, host='127.0.0.1')
    
    try:
        # Connect peers
        await network_manager2.connect_to_peer('127.0.0.1', 9008)
        await asyncio.sleep(0.1)
        await network_manager3.connect_to_peer('127.0.0.1', 9008)
        await asyncio.sleep(0.1)
        
        # Get peer IDs
        peer_ids = list(network_manager1.peers.keys())
        peer2_id = peer_ids[0]
        peer3_id = peer_ids[1]
        
        # Subscribe peers to boards
        board_id = "test_board"
        network_manager1.peers[peer2_id].board_subscriptions = [board_id]
        network_manager1.peers[peer3_id].board_subscriptions = ["other_board"]
        
        # Get peers for board
        board_peers = network_manager1.get_peers_for_board(board_id)
        
        # Only peer2 should be in the list
        assert len(board_peers) == 1
        assert peer2_id in board_peers
        assert peer3_id not in board_peers
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()
        await network_manager3.stop()
