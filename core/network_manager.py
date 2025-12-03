"""
Network Manager for P2P Encrypted BBS

Handles peer connections, handshakes, and encrypted message transport.
Implements TCP server/client, handshake protocol, and AEAD encryption.
"""

import asyncio
import logging
import struct
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization

try:
    import cbor2
except ImportError:
    raise ImportError("cbor2 is required. Install with: pip install cbor2")

from core.crypto_manager import CryptoManager, Identity, CryptoError, SignatureVerificationError
from core.mdns_service import mDNSService, mDNSError


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class NetworkError(Exception):
    """Base exception for network errors."""
    pass


class HandshakeError(NetworkError):
    """Raised when handshake fails."""
    pass


class MessageError(NetworkError):
    """Raised when message processing fails."""
    pass


@dataclass
class PeerConnection:
    """Represents a connection to a peer."""
    peer_id: str
    address: str
    port: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    session_key: bytes
    send_nonce: int = 0
    recv_nonce: int = 0
    state: ConnectionState = ConnectionState.CONNECTING
    identity_public_key: Optional[ed25519.Ed25519PublicKey] = None
    encryption_public_key: Optional[x25519.X25519PublicKey] = None
    board_subscriptions: List[str] = field(default_factory=list)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    receive_task: Optional[asyncio.Task] = None


@dataclass
class Message:
    """Represents a protocol message."""
    msg_type: str
    payload: Dict[str, Any]


class NetworkManager:
    """
    Manages peer connections, handshakes, and encrypted transport.
    
    Responsibilities:
    - TCP server for accepting incoming connections
    - TCP client for initiating outgoing connections
    - Handshake protocol (HELLO/CAPS exchange)
    - Encrypted message transport with AEAD
    - Peer connection management
    """
    
    def __init__(self, identity: Identity, crypto_manager: CryptoManager, enable_mdns: bool = True):
        """
        Initialize NetworkManager.
        
        Args:
            identity: Local peer identity
            crypto_manager: CryptoManager instance for cryptographic operations
            enable_mdns: Whether to enable mDNS peer discovery (default: True)
        """
        self.identity = identity
        self.crypto = crypto_manager
        self.peers: Dict[str, PeerConnection] = {}
        self.server: Optional[asyncio.Server] = None
        self.running = False
        self.enable_mdns = enable_mdns
        
        # mDNS service for peer discovery
        self.mdns: Optional[mDNSService] = None
        if enable_mdns:
            self.mdns = mDNSService(
                peer_id=identity.peer_id,
                signing_public_key=identity.signing_public_key,
                signing_private_key=identity.signing_private_key,
                crypto_manager=crypto_manager
            )
            # Set up mDNS callbacks
            self.mdns.on_peer_discovered = self._on_mdns_peer_discovered
            self.mdns.on_peer_removed = self._on_mdns_peer_removed
        
        # Track available peers (discovered but not yet connected)
        self.available_peers: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks for events
        self.on_peer_connected: Optional[Callable[[str], None]] = None
        self.on_peer_disconnected: Optional[Callable[[str], None]] = None
        self.on_message_received: Optional[Callable[[str, Message], None]] = None
        self.on_peer_discovered: Optional[Callable[[str, str, int], None]] = None
        self.on_peer_lost: Optional[Callable[[str], None]] = None
    
    async def start(self, port: int, host: str = '0.0.0.0') -> None:
        """
        Start TCP server and begin listening for connections.
        Also starts mDNS advertising and browsing if enabled.
        
        Args:
            port: Port to listen on
            host: Host address to bind to (default: 0.0.0.0 for all interfaces)
            
        Raises:
            NetworkError: If server fails to start
        """
        try:
            self.server = await asyncio.start_server(
                self._handle_incoming_connection,
                host,
                port
            )
            self.running = True
            
            addr = self.server.sockets[0].getsockname()
            logger.info(f"Network server started on {addr[0]}:{addr[1]}")
            
            # Start mDNS service if enabled
            if self.mdns:
                try:
                    await self.mdns.start_advertising(port)
                    self.mdns.start_browsing()
                    logger.info("mDNS service started")
                except mDNSError as e:
                    logger.error(f"Failed to start mDNS service: {e}")
                    # Continue without mDNS
            
        except Exception as e:
            raise NetworkError(f"Failed to start server: {e}")
    
    async def stop(self) -> None:
        """Stop the server, close all connections, and stop mDNS service."""
        self.running = False
        
        # Stop mDNS service
        if self.mdns:
            try:
                await self.mdns.stop()
                logger.info("mDNS service stopped")
            except Exception as e:
                logger.error(f"Error stopping mDNS service: {e}")
        
        # Close all peer connections
        peer_ids = list(self.peers.keys())
        for peer_id in peer_ids:
            await self.disconnect_peer(peer_id)
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Network server stopped")
        
        # Clear available peers
        self.available_peers.clear()
    
    async def _handle_incoming_connection(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle incoming peer connection.
        
        Args:
            reader: Stream reader for receiving data
            writer: Stream writer for sending data
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"Incoming connection from {addr}")
        
        try:
            # Perform handshake
            peer = await self._perform_handshake(reader, writer, is_initiator=False)
            
            # Store peer connection
            self.peers[peer.peer_id] = peer
            peer.state = ConnectionState.CONNECTED
            
            logger.info(f"Peer {peer.peer_id[:8]} connected from {addr}")
            
            # Notify callback
            if self.on_peer_connected:
                self.on_peer_connected(peer.peer_id)
            
            # Start message receive loop as a background task
            peer.receive_task = asyncio.create_task(self._receive_loop(peer))
            
        except Exception as e:
            logger.error(f"Error handling incoming connection from {addr}: {e}")
            writer.close()
            await writer.wait_closed()
    
    async def connect_to_peer(
        self, 
        address: str, 
        port: int, 
        timeout: float = 30.0
    ) -> str:
        """
        Initiate connection to a peer.
        
        Args:
            address: Peer IP address or hostname
            port: Peer port
            timeout: Connection timeout in seconds
            
        Returns:
            str: Peer ID of connected peer
            
        Raises:
            NetworkError: If connection fails
            asyncio.TimeoutError: If connection times out
        """
        try:
            # Ensure running flag is set for client connections
            if not self.running:
                self.running = True
            
            # Open TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, port),
                timeout=timeout
            )
            
            logger.info(f"Connected to {address}:{port}")
            
            # Perform handshake
            peer = await self._perform_handshake(reader, writer, is_initiator=True)
            
            # Store peer connection
            self.peers[peer.peer_id] = peer
            peer.state = ConnectionState.CONNECTED
            
            logger.info(f"Peer {peer.peer_id[:8]} connected at {address}:{port}")
            
            # Notify callback
            if self.on_peer_connected:
                self.on_peer_connected(peer.peer_id)
            
            # Start message receive loop in background
            peer.receive_task = asyncio.create_task(self._receive_loop(peer))
            
            return peer.peer_id
            
        except asyncio.TimeoutError:
            logger.error(f"Connection to {address}:{port} timed out")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to {address}:{port}: {e}")
            raise NetworkError(f"Connection failed: {e}")
    
    async def disconnect_peer(self, peer_id: str) -> None:
        """
        Disconnect from a peer and clean up resources.
        
        Args:
            peer_id: ID of peer to disconnect
        """
        if peer_id not in self.peers:
            logger.warning(f"Attempted to disconnect unknown peer {peer_id[:8]}")
            return
        
        peer = self.peers[peer_id]
        peer.state = ConnectionState.DISCONNECTED
        
        # Cancel receive task if it exists
        if peer.receive_task and not peer.receive_task.done():
            peer.receive_task.cancel()
            try:
                await asyncio.wait_for(peer.receive_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.debug(f"Error waiting for receive task to complete: {e}")
        
        # Close writer
        try:
            peer.writer.close()
            await peer.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing connection to peer {peer_id[:8]}: {e}")
        
        # Remove from peers dictionary
        del self.peers[peer_id]
        
        logger.info(f"Disconnected from peer {peer_id[:8]}")
        
        # Notify callback
        if self.on_peer_disconnected:
            self.on_peer_disconnected(peer_id)

    async def _perform_handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_initiator: bool
    ) -> PeerConnection:
        """
        Perform handshake protocol with a peer.
        
        Handshake steps:
        1. Generate ephemeral X25519 keypair
        2. Exchange HELLO messages (ephemeral public key + identity public key + signature)
        3. Verify signatures
        4. Derive session key via ECDH
        5. Exchange CAPS messages (encrypted with session key)
        
        Args:
            reader: Stream reader
            writer: Stream writer
            is_initiator: True if we initiated the connection
            
        Returns:
            PeerConnection: Established peer connection
            
        Raises:
            HandshakeError: If handshake fails
        """
        try:
            # Step 1: Generate ephemeral keypair for this connection
            ephemeral_private_key = x25519.X25519PrivateKey.generate()
            ephemeral_public_key = ephemeral_private_key.public_key()
            
            # Step 2: Prepare HELLO message
            hello_msg = self._create_hello_message(ephemeral_public_key)
            
            # Exchange HELLO messages
            if is_initiator:
                # Initiator sends first
                await self._send_raw_message(writer, hello_msg)
                remote_hello = await self._receive_raw_message(reader)
            else:
                # Responder receives first
                remote_hello = await self._receive_raw_message(reader)
                await self._send_raw_message(writer, hello_msg)
            
            # Step 3: Parse and verify remote HELLO
            remote_ephemeral_public_key, remote_identity_public_key, remote_peer_id = \
                self._verify_hello_message(remote_hello)
            
            # Step 4: Derive session key using ECDH
            session_key = self.crypto.derive_session_key(
                ephemeral_private_key,
                remote_ephemeral_public_key
            )
            
            # Step 5: Create peer connection object
            addr = writer.get_extra_info('peername')
            peer = PeerConnection(
                peer_id=remote_peer_id,
                address=addr[0] if addr else "unknown",
                port=addr[1] if addr else 0,
                reader=reader,
                writer=writer,
                session_key=session_key,
                identity_public_key=remote_identity_public_key,
                encryption_public_key=remote_ephemeral_public_key,
                state=ConnectionState.CONNECTING
            )
            
            # Step 6: Exchange CAPS messages (encrypted)
            caps_msg = self._create_caps_message()
            await self._send_encrypted_message(peer, caps_msg)
            
            remote_caps = await self._receive_encrypted_message(peer)
            self._process_caps_message(peer, remote_caps)
            
            logger.info(f"Handshake completed with peer {peer.peer_id[:8]}")
            
            return peer
            
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            raise HandshakeError(f"Handshake failed: {e}")
    
    def _create_hello_message(self, ephemeral_public_key: x25519.X25519PublicKey) -> bytes:
        """
        Create HELLO message for handshake.
        
        HELLO message format (CBOR-encoded):
        {
            "type": "HELLO",
            "ephemeral_public_key": bytes,
            "identity_public_key": bytes,
            "peer_id": str,
            "signature": bytes
        }
        
        Args:
            ephemeral_public_key: Ephemeral X25519 public key for this connection
            
        Returns:
            bytes: CBOR-encoded HELLO message
        """
        # Serialize keys
        ephemeral_key_bytes = ephemeral_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        identity_key_bytes = self.identity.signing_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Create message to sign (ephemeral key + identity key)
        message_to_sign = ephemeral_key_bytes + identity_key_bytes
        
        # Sign with identity private key
        signature = self.crypto.sign_data(
            message_to_sign,
            self.identity.signing_private_key
        )
        
        # Create HELLO message
        hello = {
            "type": "HELLO",
            "ephemeral_public_key": ephemeral_key_bytes,
            "identity_public_key": identity_key_bytes,
            "peer_id": self.identity.peer_id,
            "signature": signature
        }
        
        return cbor2.dumps(hello)
    
    def _verify_hello_message(
        self, 
        hello_bytes: bytes
    ) -> tuple[x25519.X25519PublicKey, ed25519.Ed25519PublicKey, str]:
        """
        Verify HELLO message from peer.
        
        Args:
            hello_bytes: CBOR-encoded HELLO message
            
        Returns:
            Tuple of (ephemeral_public_key, identity_public_key, peer_id)
            
        Raises:
            HandshakeError: If verification fails
        """
        try:
            hello = cbor2.loads(hello_bytes)
            
            if hello.get("type") != "HELLO":
                raise HandshakeError("Invalid message type")
            
            # Extract fields
            ephemeral_key_bytes = hello["ephemeral_public_key"]
            identity_key_bytes = hello["identity_public_key"]
            peer_id = hello["peer_id"]
            signature = hello["signature"]
            
            # Reconstruct public keys
            ephemeral_public_key = x25519.X25519PublicKey.from_public_bytes(
                ephemeral_key_bytes
            )
            
            identity_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                identity_key_bytes
            )
            
            # Verify signature
            message_to_verify = ephemeral_key_bytes + identity_key_bytes
            
            try:
                self.crypto.verify_signature(
                    message_to_verify,
                    signature,
                    identity_public_key
                )
            except SignatureVerificationError as e:
                raise HandshakeError(f"Signature verification failed: {e}")
            
            # Verify peer_id matches identity public key
            expected_peer_id = self.crypto._derive_peer_id(identity_public_key)
            if peer_id != expected_peer_id:
                raise HandshakeError("Peer ID does not match identity public key")
            
            return ephemeral_public_key, identity_public_key, peer_id
            
        except KeyError as e:
            raise HandshakeError(f"Missing field in HELLO message: {e}")
        except Exception as e:
            raise HandshakeError(f"Failed to verify HELLO message: {e}")
    
    def _create_caps_message(self) -> Message:
        """
        Create CAPS (capabilities) message.
        
        CAPS message contains:
        - Protocol version
        - Supported features
        - Board subscriptions
        
        Returns:
            Message: CAPS message
        """
        return Message(
            msg_type="CAPS",
            payload={
                "version": "1.0",
                "features": ["posts", "private_messages", "file_attachments"],
                "board_subscriptions": []  # Will be populated later
            }
        )
    
    def _process_caps_message(self, peer: PeerConnection, message: Message) -> None:
        """
        Process CAPS message from peer.
        
        Args:
            peer: Peer connection
            message: CAPS message
        """
        if message.msg_type != "CAPS":
            logger.warning(f"Expected CAPS message, got {message.msg_type}")
            return
        
        payload = message.payload
        peer.board_subscriptions = payload.get("board_subscriptions", [])
        
        logger.debug(
            f"Peer {peer.peer_id[:8]} capabilities: "
            f"version={payload.get('version')}, "
            f"features={payload.get('features')}"
        )

    async def send_message(self, peer_id: str, message: Message) -> None:
        """
        Send encrypted message to a peer.
        
        Args:
            peer_id: ID of peer to send to
            message: Message to send
            
        Raises:
            NetworkError: If peer not found or send fails
        """
        if peer_id not in self.peers:
            raise NetworkError(f"Peer {peer_id[:8]} not connected")
        
        peer = self.peers[peer_id]
        
        if peer.state != ConnectionState.CONNECTED:
            raise NetworkError(f"Peer {peer_id[:8]} not in connected state")
        
        try:
            await self._send_encrypted_message(peer, message)
        except Exception as e:
            logger.error(f"Failed to send message to peer {peer_id[:8]}: {e}")
            raise NetworkError(f"Send failed: {e}")
    
    async def _send_encrypted_message(self, peer: PeerConnection, message: Message) -> None:
        """
        Send encrypted message to peer using AEAD encryption.
        
        Message format:
        - 4 bytes: message length (big-endian)
        - 12 bytes: nonce
        - N bytes: CBOR-encoded message + authentication tag
        
        Args:
            peer: Peer connection
            message: Message to send
        """
        try:
            # Serialize message to CBOR
            message_dict = {
                "type": message.msg_type,
                "payload": message.payload
            }
            plaintext = cbor2.dumps(message_dict)
            
            # Generate nonce (12 bytes)
            nonce = peer.send_nonce.to_bytes(12, byteorder='big')
            peer.send_nonce += 1
            
            # Encrypt with session key
            ciphertext = self.crypto.encrypt_with_session_key(
                plaintext,
                peer.session_key,
                nonce
            )
            
            # Prepare frame: length + nonce + ciphertext
            frame = struct.pack('!I', len(nonce) + len(ciphertext)) + nonce + ciphertext
            
            # Send
            peer.writer.write(frame)
            await peer.writer.drain()
            
            logger.debug(f"Sent {message.msg_type} message to peer {peer.peer_id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to send encrypted message: {e}")
            raise
    
    async def _receive_encrypted_message(self, peer: PeerConnection) -> Message:
        """
        Receive and decrypt message from peer.
        
        Args:
            peer: Peer connection
            
        Returns:
            Message: Decrypted message
            
        Raises:
            MessageError: If receive or decryption fails
            asyncio.IncompleteReadError: If connection is closed
        """
        try:
            # Read message length (4 bytes)
            length_bytes = await peer.reader.readexactly(4)
            message_length = struct.unpack('!I', length_bytes)[0]
            
            # Validate message length
            if message_length > 10 * 1024 * 1024:  # 10 MB max
                raise MessageError(f"Message too large: {message_length} bytes")
            
            # Read nonce (12 bytes)
            nonce = await peer.reader.readexactly(12)
            
            # Read ciphertext
            ciphertext = await peer.reader.readexactly(message_length - 12)
            
            # Verify nonce is expected value (prevents replay attacks)
            expected_nonce = peer.recv_nonce.to_bytes(12, byteorder='big')
            if nonce != expected_nonce:
                raise MessageError(
                    f"Nonce mismatch: expected {peer.recv_nonce}, "
                    f"got {int.from_bytes(nonce, byteorder='big')}"
                )
            peer.recv_nonce += 1
            
            # Decrypt
            plaintext = self.crypto.decrypt_with_session_key(
                ciphertext,
                peer.session_key,
                nonce
            )
            
            # Deserialize CBOR
            message_dict = cbor2.loads(plaintext)
            
            message = Message(
                msg_type=message_dict["type"],
                payload=message_dict["payload"]
            )
            
            logger.debug(f"Received {message.msg_type} message from peer {peer.peer_id[:8]}")
            
            return message
            
        except asyncio.IncompleteReadError:
            # Re-raise to be handled by receive loop
            raise
        except Exception as e:
            logger.error(f"Failed to receive encrypted message: {e}")
            raise MessageError(f"Receive failed: {e}")
    
    async def _send_raw_message(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        """
        Send raw (unencrypted) message. Used during handshake.
        
        Args:
            writer: Stream writer
            data: Raw data to send
        """
        # Send length prefix + data
        frame = struct.pack('!I', len(data)) + data
        writer.write(frame)
        await writer.drain()
    
    async def _receive_raw_message(self, reader: asyncio.StreamReader) -> bytes:
        """
        Receive raw (unencrypted) message. Used during handshake.
        
        Args:
            reader: Stream reader
            
        Returns:
            bytes: Received data
        """
        # Read length prefix
        length_bytes = await reader.readexactly(4)
        message_length = struct.unpack('!I', length_bytes)[0]
        
        # Validate length
        if message_length > 10 * 1024 * 1024:  # 10 MB max
            raise MessageError(f"Message too large: {message_length} bytes")
        
        # Read data
        data = await reader.readexactly(message_length)
        return data
    
    async def _receive_loop(self, peer: PeerConnection) -> None:
        """
        Continuously receive messages from peer.
        
        Args:
            peer: Peer connection
        """
        logger.debug(f"Starting receive loop for peer {peer.peer_id[:8]}, state={peer.state}, running={self.running}")
        try:
            while peer.state == ConnectionState.CONNECTED and self.running:
                try:
                    logger.debug(f"Waiting for message from peer {peer.peer_id[:8]}")
                    message = await self._receive_encrypted_message(peer)
                    logger.debug(f"Received {message.msg_type} from peer {peer.peer_id[:8]}")
                    
                    # Notify callback
                    if self.on_message_received:
                        self.on_message_received(peer.peer_id, message)
                except asyncio.IncompleteReadError as e:
                    # Connection closed by peer
                    logger.debug(f"Peer {peer.peer_id[:8]} closed connection: {e}")
                    break
                except MessageError as e:
                    logger.error(f"Message error from peer {peer.peer_id[:8]}: {e}")
                    break
            
            logger.debug(f"Exited receive loop for peer {peer.peer_id[:8]}, state={peer.state}, running={self.running}")
                    
        except asyncio.CancelledError:
            logger.debug(f"Receive loop cancelled for peer {peer.peer_id[:8]}")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            logger.error(f"Error in receive loop for peer {peer.peer_id[:8]}: {e}")
        finally:
            # Disconnect peer on error or completion, but only if still in peers dict
            # (avoid double-disconnect if already cleaned up)
            if peer.peer_id in self.peers and peer.state == ConnectionState.CONNECTED:
                logger.debug(f"Receive loop ended for peer {peer.peer_id[:8]}, disconnecting")
                await self.disconnect_peer(peer.peer_id)
            else:
                logger.debug(f"Receive loop ended for peer {peer.peer_id[:8]}, already disconnected")
    
    async def broadcast_to_board(self, board_id: str, message: Message) -> None:
        """
        Broadcast message to all peers subscribed to a board.
        
        Args:
            board_id: Board identifier
            message: Message to broadcast
        """
        sent_count = 0
        
        for peer_id, peer in list(self.peers.items()):
            if board_id in peer.board_subscriptions:
                try:
                    await self.send_message(peer_id, message)
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to broadcast to peer {peer_id[:8]}: {e}"
                    )
        
        logger.info(
            f"Broadcast {message.msg_type} to {sent_count} peers on board {board_id[:8]}"
        )
    
    def get_connected_peers(self) -> List[str]:
        """
        Get list of connected peer IDs.
        
        Returns:
            List of peer IDs
        """
        return [
            peer_id for peer_id, peer in self.peers.items()
            if peer.state == ConnectionState.CONNECTED
        ]
    
    def get_peer_info(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a peer.
        
        Args:
            peer_id: Peer ID
            
        Returns:
            Dictionary with peer information or None if not found
        """
        if peer_id not in self.peers:
            return None
        
        peer = self.peers[peer_id]
        
        return {
            "peer_id": peer.peer_id,
            "address": peer.address,
            "port": peer.port,
            "state": peer.state.value,
            "board_subscriptions": peer.board_subscriptions,
            "connected_at": peer.connected_at.isoformat()
        }
    
    def get_peers_by_state(self, state: ConnectionState) -> List[str]:
        """
        Get list of peer IDs in a specific connection state.
        
        Args:
            state: Connection state to filter by
            
        Returns:
            List of peer IDs in the specified state
        """
        return [
            peer_id for peer_id, peer in self.peers.items()
            if peer.state == state
        ]
    
    def get_peers_for_board(self, board_id: str) -> List[str]:
        """
        Get list of peer IDs subscribed to a specific board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            List of peer IDs subscribed to the board
        """
        return [
            peer_id for peer_id, peer in self.peers.items()
            if board_id in peer.board_subscriptions and peer.state == ConnectionState.CONNECTED
        ]
    
    def is_peer_connected(self, peer_id: str) -> bool:
        """
        Check if a peer is currently connected.
        
        Args:
            peer_id: Peer ID to check
            
        Returns:
            True if peer is connected, False otherwise
        """
        return (
            peer_id in self.peers and 
            self.peers[peer_id].state == ConnectionState.CONNECTED
        )
    
    def get_connection_count(self) -> int:
        """
        Get the number of currently connected peers.
        
        Returns:
            Number of connected peers
        """
        return len([
            peer for peer in self.peers.values()
            if peer.state == ConnectionState.CONNECTED
        ])
    
    def _on_mdns_peer_discovered(
        self,
        peer_id: str,
        address: str,
        port: int,
        peer_info: Dict[str, Any]
    ) -> None:
        """
        Handle mDNS peer discovery event.
        
        Args:
            peer_id: Discovered peer ID
            address: Peer IP address
            port: Peer port
            peer_info: Additional peer information from mDNS
        """
        # Store in available peers
        self.available_peers[peer_id] = {
            'address': address,
            'port': port,
            'discovered_via': 'mdns',
            'peer_info': peer_info
        }
        
        logger.info(f"Added peer {peer_id[:8]} to available peers list")
        
        # Notify callback
        if self.on_peer_discovered:
            self.on_peer_discovered(peer_id, address, port)
    
    def _on_mdns_peer_removed(self, peer_id: str) -> None:
        """
        Handle mDNS peer removal event.
        
        Args:
            peer_id: Removed peer ID
        """
        # Remove from available peers
        if peer_id in self.available_peers:
            del self.available_peers[peer_id]
            logger.info(f"Removed peer {peer_id[:8]} from available peers list")
        
        # Notify callback
        if self.on_peer_lost:
            self.on_peer_lost(peer_id)
    
    def get_available_peers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get dictionary of available (discovered but not connected) peers.
        
        Returns:
            Dictionary mapping peer_id to peer information
        """
        return self.available_peers.copy()
    
    def is_peer_available(self, peer_id: str) -> bool:
        """
        Check if a peer is available (discovered via mDNS).
        
        Args:
            peer_id: Peer ID to check
            
        Returns:
            True if peer is available, False otherwise
        """
        return peer_id in self.available_peers
    
    async def connect_to_available_peer(self, peer_id: str, timeout: float = 30.0) -> str:
        """
        Connect to a peer that was discovered via mDNS.
        
        Args:
            peer_id: ID of peer to connect to
            timeout: Connection timeout in seconds
            
        Returns:
            str: Peer ID of connected peer
            
        Raises:
            NetworkError: If peer not available or connection fails
        """
        if peer_id not in self.available_peers:
            raise NetworkError(f"Peer {peer_id[:8]} not in available peers list")
        
        peer_info = self.available_peers[peer_id]
        address = peer_info['address']
        port = peer_info['port']
        
        logger.info(f"Connecting to available peer {peer_id[:8]} at {address}:{port}")
        
        return await self.connect_to_peer(address, port, timeout)
