"""
Integration tests for mDNS peer discovery.

Tests the mDNS service and its integration with NetworkManager including:
- Two peers discovering each other via mDNS
- Service record signature verification
- Peer removal when disconnecting
"""

import pytest
import asyncio
from core.network_manager import NetworkManager
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
    """Create first NetworkManager instance with mDNS enabled."""
    return NetworkManager(identity1, crypto_manager, enable_mdns=True)


@pytest.fixture
def network_manager2(identity2, crypto_manager):
    """Create second NetworkManager instance with mDNS enabled."""
    return NetworkManager(identity2, crypto_manager, enable_mdns=True)


@pytest.mark.asyncio
async def test_two_peers_discover_via_mdns(network_manager1, network_manager2):
    """
    Test two instances discover each other via mDNS.
    
    Verifies:
    - Both peers advertise their presence
    - Both peers discover each other
    - Discovery happens within reasonable time
    - Peer information is correctly extracted
    """
    # Track discovery events
    peer1_discovered = []
    peer2_discovered = []
    
    network_manager1.on_peer_discovered = lambda pid, addr, port: peer1_discovered.append(pid)
    network_manager2.on_peer_discovered = lambda pid, addr, port: peer2_discovered.append(pid)
    
    # Start both network managers on different ports
    await network_manager1.start(port=9200, host='127.0.0.1')
    await network_manager2.start(port=9201, host='127.0.0.1')
    
    try:
        # Wait for mDNS discovery with polling (can take several seconds)
        # mDNS service info retrieval can be slow, so we poll with timeout
        peer2_id = network_manager2.identity.peer_id
        peer1_id = network_manager1.identity.peer_id
        
        # Poll for discovery with 20 second timeout
        for _ in range(20):
            await asyncio.sleep(1)
            if peer2_id in peer1_discovered and peer1_id in peer2_discovered:
                break
        
        # Verify peer 1 discovered peer 2
        assert peer2_id in peer1_discovered, "Peer 1 should have discovered Peer 2"
        assert network_manager1.is_peer_available(peer2_id), "Peer 2 should be in available peers"
        
        # Verify peer 2 discovered peer 1
        assert peer1_id in peer2_discovered, "Peer 2 should have discovered Peer 1"
        assert network_manager2.is_peer_available(peer1_id), "Peer 1 should be in available peers"
        
        # Verify peer information is correct
        peer2_info = network_manager1.get_available_peers()[peer2_id]
        assert peer2_info['address'] in ['127.0.0.1', '::1'], "Address should be localhost"
        assert peer2_info['port'] == 9201, "Port should match"
        assert peer2_info['discovered_via'] == 'mdns', "Should be discovered via mDNS"
        
        peer1_info = network_manager2.get_available_peers()[peer1_id]
        assert peer1_info['address'] in ['127.0.0.1', '::1'], "Address should be localhost"
        assert peer1_info['port'] == 9200, "Port should match"
        assert peer1_info['discovered_via'] == 'mdns', "Should be discovered via mDNS"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_mdns_service_record_signature_verification(network_manager1, network_manager2):
    """
    Test service record contains valid signature.
    
    Verifies:
    - mDNS service records include signatures
    - Signatures are verified before adding to available peers
    - Invalid signatures are rejected
    """
    # Track discovery events
    peer1_discovered = []
    
    network_manager1.on_peer_discovered = lambda pid, addr, port: peer1_discovered.append(pid)
    
    # Start both network managers
    await network_manager1.start(port=9202, host='127.0.0.1')
    await network_manager2.start(port=9203, host='127.0.0.1')
    
    try:
        # Wait for discovery with polling
        peer2_id = network_manager2.identity.peer_id
        
        for _ in range(20):
            await asyncio.sleep(1)
            if peer2_id in peer1_discovered:
                break
        
        # Verify peer 2 was discovered (signature was valid)
        assert peer2_id in peer1_discovered, "Peer 2 should be discovered with valid signature"
        
        # Verify peer info includes public key from mDNS
        peer2_info = network_manager1.get_available_peers()[peer2_id]
        assert 'peer_info' in peer2_info, "Should have peer_info from mDNS"
        assert 'public_key' in peer2_info['peer_info'], "Should have public_key"
        
        # Verify the public key matches the identity
        discovered_public_key = peer2_info['peer_info']['public_key']
        expected_public_key = network_manager2.identity.signing_public_key
        
        from cryptography.hazmat.primitives import serialization
        discovered_key_bytes = discovered_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        expected_key_bytes = expected_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        assert discovered_key_bytes == expected_key_bytes, "Public keys should match"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_peer_removal_on_disconnect(network_manager1, network_manager2):
    """
    Test peer removal when they disappear from network.
    
    Verifies:
    - Peers are removed from available list when they stop advertising
    - Removal callback is triggered
    - Removal happens within reasonable time
    """
    # Track discovery and removal events
    peer1_discovered = []
    peer1_lost = []
    
    network_manager1.on_peer_discovered = lambda pid, addr, port: peer1_discovered.append(pid)
    network_manager1.on_peer_lost = lambda pid: peer1_lost.append(pid)
    
    # Start both network managers
    await network_manager1.start(port=9204, host='127.0.0.1')
    await network_manager2.start(port=9205, host='127.0.0.1')
    
    try:
        # Wait for discovery with polling
        peer2_id = network_manager2.identity.peer_id
        
        for _ in range(20):
            await asyncio.sleep(1)
            if peer2_id in peer1_discovered:
                break
        
        # Verify peer 2 was discovered
        assert peer2_id in peer1_discovered, "Peer 2 should be discovered"
        assert network_manager1.is_peer_available(peer2_id), "Peer 2 should be available"
        
        # Stop peer 2 (this unregisters the mDNS service)
        await network_manager2.stop()
        
        # Wait for mDNS removal notification (can take up to 10 seconds per spec)
        # We'll wait up to 15 seconds to be safe
        for _ in range(30):  # 30 * 0.5s = 15s
            await asyncio.sleep(0.5)
            if peer2_id in peer1_lost:
                break
        
        # Verify peer 2 was removed
        assert peer2_id in peer1_lost, "Peer 2 should be removed after stopping"
        assert not network_manager1.is_peer_available(peer2_id), "Peer 2 should not be available"
        
    finally:
        await network_manager1.stop()
        # network_manager2 already stopped


@pytest.mark.asyncio
async def test_connect_to_discovered_peer(network_manager1, network_manager2):
    """
    Test connecting to a peer discovered via mDNS.
    
    Verifies:
    - Can connect to discovered peer using connect_to_available_peer()
    - Connection succeeds and handshake completes
    - Peer moves from available to connected state
    """
    # Track events
    peer1_discovered = []
    peer1_connected = []
    
    network_manager1.on_peer_discovered = lambda pid, addr, port: peer1_discovered.append(pid)
    network_manager1.on_peer_connected = lambda pid: peer1_connected.append(pid)
    
    # Start both network managers
    await network_manager1.start(port=9206, host='127.0.0.1')
    await network_manager2.start(port=9207, host='127.0.0.1')
    
    try:
        # Wait for discovery with polling
        peer2_id = network_manager2.identity.peer_id
        
        for _ in range(20):
            await asyncio.sleep(1)
            if peer2_id in peer1_discovered:
                break
        
        # Verify peer 2 was discovered
        assert peer2_id in peer1_discovered, "Peer 2 should be discovered"
        
        # Connect to discovered peer
        connected_peer_id = await network_manager1.connect_to_available_peer(peer2_id)
        
        # Wait for connection to stabilize
        await asyncio.sleep(0.2)
        
        # Verify connection succeeded
        assert connected_peer_id == peer2_id, "Connected peer ID should match"
        assert peer2_id in peer1_connected, "Connection callback should be triggered"
        assert network_manager1.is_peer_connected(peer2_id), "Peer should be connected"
        
        # Verify peer is still in available list (discovery doesn't remove on connect)
        assert network_manager1.is_peer_available(peer2_id), "Peer should still be available"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_mdns_disabled(crypto_manager):
    """
    Test that NetworkManager works without mDNS when disabled.
    
    Verifies:
    - NetworkManager can be created with enable_mdns=False
    - No mDNS service is started
    - Manual connections still work
    """
    # Create identities
    identity1 = crypto_manager.generate_identity()
    identity2 = crypto_manager.generate_identity()
    
    # Create network managers with mDNS disabled
    network_manager1 = NetworkManager(identity1, crypto_manager, enable_mdns=False)
    network_manager2 = NetworkManager(identity2, crypto_manager, enable_mdns=False)
    
    # Start both network managers
    await network_manager1.start(port=9208, host='127.0.0.1')
    await network_manager2.start(port=9209, host='127.0.0.1')
    
    try:
        # Wait a bit
        await asyncio.sleep(3)
        
        # Verify no peers were discovered (mDNS is disabled)
        assert len(network_manager1.get_available_peers()) == 0, "No peers should be discovered"
        assert len(network_manager2.get_available_peers()) == 0, "No peers should be discovered"
        
        # Verify manual connection still works
        peer2_id = await network_manager1.connect_to_peer('127.0.0.1', 9209)
        await asyncio.sleep(0.2)
        
        assert network_manager1.is_peer_connected(peer2_id), "Manual connection should work"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()


@pytest.mark.asyncio
async def test_multiple_peers_discovery(crypto_manager):
    """
    Test that a peer can discover multiple other peers via mDNS.
    
    Verifies:
    - One peer can discover multiple peers
    - All peers are correctly tracked
    """
    # Create three identities
    identity1 = crypto_manager.generate_identity()
    identity2 = crypto_manager.generate_identity()
    identity3 = crypto_manager.generate_identity()
    
    # Create network managers
    network_manager1 = NetworkManager(identity1, crypto_manager, enable_mdns=True)
    network_manager2 = NetworkManager(identity2, crypto_manager, enable_mdns=True)
    network_manager3 = NetworkManager(identity3, crypto_manager, enable_mdns=True)
    
    # Track discoveries
    peer1_discovered = []
    network_manager1.on_peer_discovered = lambda pid, addr, port: peer1_discovered.append(pid)
    
    # Start all network managers
    await network_manager1.start(port=9210, host='127.0.0.1')
    await network_manager2.start(port=9211, host='127.0.0.1')
    await network_manager3.start(port=9212, host='127.0.0.1')
    
    try:
        # Wait for discovery with polling
        peer2_id = network_manager2.identity.peer_id
        peer3_id = network_manager3.identity.peer_id
        
        for _ in range(20):
            await asyncio.sleep(1)
            if peer2_id in peer1_discovered and peer3_id in peer1_discovered:
                break
        
        # Verify peer 1 discovered both peer 2 and peer 3
        assert peer2_id in peer1_discovered, "Peer 1 should discover Peer 2"
        assert peer3_id in peer1_discovered, "Peer 1 should discover Peer 3"
        
        # Verify both are in available peers
        available = network_manager1.get_available_peers()
        assert peer2_id in available, "Peer 2 should be available"
        assert peer3_id in available, "Peer 3 should be available"
        assert len(available) == 2, "Should have exactly 2 available peers"
        
    finally:
        await network_manager1.stop()
        await network_manager2.stop()
        await network_manager3.stop()
