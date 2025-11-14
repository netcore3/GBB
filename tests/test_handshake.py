"""
Integration tests for handshake protocol.

Tests the complete handshake flow between two peers including:
- Successful handshake with valid signatures
- Handshake failure with invalid signatures
- Session key derivation consistency
"""

import pytest
import asyncio
from core.network_manager import NetworkManager, HandshakeError, NetworkError
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
async def test_successful_handshake(network_manager1, network_manager2):
    """
    Test two peers performing successful handshake.
    
    Verifies:
    - HELLO message exchange
    - Signature verification
    - CAPS message exchange
    - Peer connection established
    """
    # Start server on peer 2
    await network_manager2.start(port=9100, host='127.0.0.1')
    
    try:
        # Track connection events
        peer1_connected = []
        peer2_connected = []
        
        network_manager1.on_peer_connected = lambda pid: peer1_connected.append(pid)
        network_manager2.on_peer_connected = lambda pid: peer2_connected.append(pid)
        
        # Connect peer 1 to peer 2 (this performs the handshake)
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9100)
        
        # Wait for connection to stabilize
        await asyncio.sleep(0.2)
        
        # Verify peer 1 has peer 2 in its peer list
        assert peer2_id in network_manager1.peers
        assert network_manager1.is_peer_connected(peer2_id)
        
        # Verify peer 2 has peer 1 in its peer list
        peer1_id = network_manager1.identity.peer_id
        assert len(network_manager2.peers) == 1
        connected_peer_id = list(network_manager2.peers.keys())[0]
        assert connected_peer_id == peer1_id
        assert network_manager2.is_peer_connected(peer1_id)
        
        # Verify connection callbacks were triggered
        assert len(peer1_connected) == 1
        assert peer1_connected[0] == peer2_id
        assert len(peer2_connected) == 1
        assert peer2_connected[0] == peer1_id
        
        # Verify peer connection details
        peer2_info = network_manager1.get_peer_info(peer2_id)
        assert peer2_info is not None
        assert peer2_info["peer_id"] == peer2_id
        assert peer2_info["state"] == "connected"
        assert peer2_info["address"] == "127.0.0.1"
        assert peer2_info["port"] == 9100
        
        # Verify identity public keys were exchanged
        peer2_conn = network_manager1.peers[peer2_id]
        assert peer2_conn.identity_public_key is not None
        assert peer2_conn.encryption_public_key is not None
        
        peer1_conn = network_manager2.peers[peer1_id]
        assert peer1_conn.identity_public_key is not None
        assert peer1_conn.encryption_public_key is not None
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_handshake_with_invalid_signature(crypto_manager):
    """
    Test handshake failure when peer sends invalid signature.
    
    This test verifies that the handshake protocol properly rejects
    connections from peers with invalid signatures.
    """
    # Create two identities
    identity1 = crypto_manager.generate_identity()
    identity2 = crypto_manager.generate_identity()
    
    # Create network managers
    network_manager1 = NetworkManager(identity1, crypto_manager)
    network_manager2 = NetworkManager(identity2, crypto_manager)
    
    # Start server on peer 2
    await network_manager2.start(port=9101, host='127.0.0.1')
    
    try:
        # Monkey-patch peer 1's _create_hello_message to create invalid signature
        original_create_hello = network_manager1._create_hello_message
        
        def create_invalid_hello(ephemeral_public_key):
            """Create HELLO message with invalid signature."""
            import cbor2
            from cryptography.hazmat.primitives import serialization
            
            # Serialize keys
            ephemeral_key_bytes = ephemeral_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            identity_key_bytes = identity1.signing_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Create INVALID signature (just random bytes)
            import os
            invalid_signature = os.urandom(64)
            
            # Create HELLO message with invalid signature
            hello = {
                "type": "HELLO",
                "ephemeral_public_key": ephemeral_key_bytes,
                "identity_public_key": identity_key_bytes,
                "peer_id": identity1.peer_id,
                "signature": invalid_signature
            }
            
            return cbor2.dumps(hello)
        
        network_manager1._create_hello_message = create_invalid_hello
        
        # Attempt to connect - should fail with NetworkError or HandshakeError
        # (The server rejects the invalid signature and closes the connection)
        with pytest.raises((HandshakeError, NetworkError)):
            await network_manager1.connect_to_peer('127.0.0.1', 9101)
        
        # Verify no peer connection was established on client side
        assert len(network_manager1.peers) == 0
        
        # Server may have briefly created a connection before rejecting it
        # Wait a moment for cleanup
        await asyncio.sleep(0.1)
        
        # After cleanup, server should have no peers
        assert len(network_manager2.peers) == 0
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_session_key_derivation_matches(network_manager1, network_manager2):
    """
    Test that session key derivation produces matching keys on both sides.
    
    This verifies that both peers derive the same session key from the
    ECDH exchange, which is critical for encrypted communication.
    """
    # Start server on peer 2
    await network_manager2.start(port=9102, host='127.0.0.1')
    
    try:
        # Connect peer 1 to peer 2
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9102)
        
        # Wait for connection to stabilize
        await asyncio.sleep(0.2)
        
        # Get peer connections
        peer1_id = network_manager1.identity.peer_id
        peer2_conn = network_manager1.peers[peer2_id]
        peer1_conn = network_manager2.peers[peer1_id]
        
        # Both peers should have session keys
        assert peer2_conn.session_key is not None
        assert peer1_conn.session_key is not None
        
        # Session keys should be the same length
        assert len(peer2_conn.session_key) == 32
        assert len(peer1_conn.session_key) == 32
        
        # Test that encrypted communication works (proves keys match)
        from core.network_manager import Message
        
        received_messages = []
        network_manager2.on_message_received = lambda pid, msg: received_messages.append(msg)
        
        # Send a test message
        test_message = Message(
            msg_type="TEST_KEY_MATCH",
            payload={"test": "session key verification"}
        )
        
        await network_manager1.send_message(peer2_id, test_message)
        
        # Wait for message to be received
        await asyncio.sleep(0.2)
        
        # If keys didn't match, decryption would fail and message wouldn't be received
        assert len(received_messages) == 1
        assert received_messages[0].msg_type == "TEST_KEY_MATCH"
        assert received_messages[0].payload["test"] == "session key verification"
        
        # Test bidirectional communication
        received_messages_at_peer1 = []
        network_manager1.on_message_received = lambda pid, msg: received_messages_at_peer1.append(msg)
        
        response_message = Message(
            msg_type="RESPONSE",
            payload={"response": "keys match confirmed"}
        )
        
        await network_manager2.send_message(peer1_id, response_message)
        await asyncio.sleep(0.2)
        
        assert len(received_messages_at_peer1) == 1
        assert received_messages_at_peer1[0].msg_type == "RESPONSE"
        assert received_messages_at_peer1[0].payload["response"] == "keys match confirmed"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_handshake_nonce_initialization(network_manager1, network_manager2):
    """
    Test that nonces are properly initialized to 0 after handshake.
    
    This ensures that the first message uses nonce 0, which is critical
    for the AEAD encryption scheme.
    """
    # Start server on peer 2
    await network_manager2.start(port=9103, host='127.0.0.1')
    
    try:
        # Connect peer 1 to peer 2
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9103)
        
        # Wait for connection to stabilize
        await asyncio.sleep(0.2)
        
        # Get peer connections
        peer1_id = network_manager1.identity.peer_id
        peer2_conn = network_manager1.peers[peer2_id]
        peer1_conn = network_manager2.peers[peer1_id]
        
        # After handshake, nonces should be at 1 (CAPS message was exchanged)
        # The handshake includes a CAPS message exchange which uses nonce 0
        assert peer2_conn.send_nonce == 1
        assert peer2_conn.recv_nonce == 1
        assert peer1_conn.send_nonce == 1
        assert peer1_conn.recv_nonce == 1
        
        # Send a message and verify nonce increments further
        from core.network_manager import Message
        
        test_message = Message(msg_type="TEST", payload={})
        await network_manager1.send_message(peer2_id, test_message)
        
        # Wait for message to be processed
        await asyncio.sleep(0.2)
        
        # Verify send nonce incremented on peer 1 (now at 2)
        assert peer2_conn.send_nonce == 2
        
        # Verify receive nonce incremented on peer 2 (now at 2)
        assert peer1_conn.recv_nonce == 2
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_handshake_caps_exchange(network_manager1, network_manager2):
    """
    Test that CAPS messages are properly exchanged during handshake.
    
    Verifies that capabilities and board subscriptions are communicated.
    """
    # Start server on peer 2
    await network_manager2.start(port=9104, host='127.0.0.1')
    
    try:
        # Connect peer 1 to peer 2
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9104)
        
        # Wait for connection to stabilize
        await asyncio.sleep(0.2)
        
        # Get peer connections
        peer1_id = network_manager1.identity.peer_id
        peer2_conn = network_manager1.peers[peer2_id]
        peer1_conn = network_manager2.peers[peer1_id]
        
        # Verify board subscriptions were initialized (empty by default)
        assert peer2_conn.board_subscriptions == []
        assert peer1_conn.board_subscriptions == []
        
        # Verify connection is fully established
        assert peer2_conn.state.value == "connected"
        assert peer1_conn.state.value == "connected"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_multiple_handshakes(crypto_manager):
    """
    Test that multiple peers can successfully handshake with a single peer.
    
    This verifies that the handshake protocol works correctly when
    handling multiple concurrent connections.
    """
    # Create three identities
    identity1 = crypto_manager.generate_identity()
    identity2 = crypto_manager.generate_identity()
    identity3 = crypto_manager.generate_identity()
    
    # Create network managers
    network_manager1 = NetworkManager(identity1, crypto_manager)
    network_manager2 = NetworkManager(identity2, crypto_manager)
    network_manager3 = NetworkManager(identity3, crypto_manager)
    
    # Start server on peer 1
    await network_manager1.start(port=9105, host='127.0.0.1')
    
    try:
        # Connect peer 2 and peer 3 to peer 1
        peer1_id_from_2 = await network_manager2.connect_to_peer('127.0.0.1', 9105)
        await asyncio.sleep(0.1)
        
        peer1_id_from_3 = await network_manager3.connect_to_peer('127.0.0.1', 9105)
        await asyncio.sleep(0.1)
        
        # Verify peer 1 has both connections
        assert len(network_manager1.peers) == 2
        assert network_manager1.get_connection_count() == 2
        
        # Verify both peer 2 and peer 3 are connected
        peer2_id = identity2.peer_id
        peer3_id = identity3.peer_id
        
        connected_peers = network_manager1.get_connected_peers()
        assert peer2_id in connected_peers
        assert peer3_id in connected_peers
        
        # Verify each peer has correct session keys
        for peer_id in connected_peers:
            peer_conn = network_manager1.peers[peer_id]
            assert peer_conn.session_key is not None
            assert len(peer_conn.session_key) == 32
            assert peer_conn.state.value == "connected"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()
        await network_manager3.stop()
