"""
mDNS Service for P2P Encrypted BBS

Handles local network peer discovery using Zeroconf (mDNS/DNS-SD).
Broadcasts peer presence and listens for other peers on the local network.
"""

import logging
from typing import Callable, Optional, Dict, Any
from zeroconf import ServiceBrowser, ServiceInfo, ServiceStateChange
from zeroconf.asyncio import AsyncZeroconf
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import socket


logger = logging.getLogger(__name__)


class mDNSError(Exception):
    """Base exception for mDNS errors."""
    pass


class mDNSService:
    """
    Manages mDNS-based peer discovery on local networks.
    
    Responsibilities:
    - Broadcast peer presence via mDNS service "_bbs-p2p._tcp"
    - Listen for peer announcements on local network
    - Verify peer signatures from service records
    - Notify callbacks when peers are discovered or removed
    """
    
    SERVICE_TYPE = "_bbs-p2p._tcp.local."
    
    def __init__(
        self,
        peer_id: str,
        signing_public_key: ed25519.Ed25519PublicKey,
        signing_private_key: ed25519.Ed25519PrivateKey,
        crypto_manager: 'CryptoManager'
    ):
        """
        Initialize mDNS service.
        
        Args:
            peer_id: Local peer identifier
            signing_public_key: Ed25519 public key for identity
            signing_private_key: Ed25519 private key for signing
            crypto_manager: CryptoManager instance for signature operations
        """
        self.peer_id = peer_id
        self.signing_public_key = signing_public_key
        self.signing_private_key = signing_private_key
        self.crypto = crypto_manager
        
        self.zeroconf: Optional[AsyncZeroconf] = None
        self.service_info: Optional[ServiceInfo] = None
        self.browser: Optional[ServiceBrowser] = None
        
        # Callback for peer discovery events
        self.on_peer_discovered: Optional[Callable[[str, str, int, Dict[str, Any]], None]] = None
        self.on_peer_removed: Optional[Callable[[str], None]] = None
        
        # Track discovered peers
        self.discovered_peers: Dict[str, Dict[str, Any]] = {}
        
        self.running = False
    
    async def start_advertising(self, port: int, hostname: Optional[str] = None) -> None:
        """
        Start advertising peer presence on local network.
        
        Broadcasts a service record with:
        - Service type: "_bbs-p2p._tcp.local."
        - Service name: "BBS-{peer_id[:8]}"
        - Port: listening port
        - Properties: peer_id, version, signature
        
        Args:
            port: Port number the peer is listening on
            hostname: Optional hostname (defaults to local hostname)
            
        Raises:
            mDNSError: If advertising fails to start
        """
        try:
            if self.running:
                logger.warning("mDNS service already running")
                return
            
            logger.debug("Initializing AsyncZeroconf...")
            # Initialize AsyncZeroconf
            self.zeroconf = AsyncZeroconf()
            logger.debug("AsyncZeroconf initialized")
            
            # Get local hostname if not provided
            if hostname is None:
                hostname = socket.gethostname()
            logger.debug(f"Using hostname: {hostname}")
            
            # Create service name
            service_name = f"BBS-{self.peer_id[:8]}.{self.SERVICE_TYPE}"
            logger.debug(f"Service name: {service_name}")
            
            # Serialize public key for properties
            logger.debug("Serializing public key...")
            public_key_bytes = self.signing_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            logger.debug(f"Public key serialized: {len(public_key_bytes)} bytes")
            
            # Create signature for service record
            # Sign: peer_id + port + version
            logger.debug("Creating signature...")
            message_to_sign = f"{self.peer_id}:{port}:1.0".encode('utf-8')
            signature = self.crypto.sign_data(message_to_sign, self.signing_private_key)
            logger.debug(f"Signature created: {len(signature)} bytes")
            
            # Create service properties
            properties = {
                b'peer_id': self.peer_id.encode('utf-8'),
                b'version': b'1.0',
                b'public_key': public_key_bytes,
                b'signature': signature
            }
            logger.debug(f"Properties created: {len(properties)} items")
            
            # Create service info
            # Zeroconf will auto-populate addresses if we provide a server name
            logger.debug("Creating ServiceInfo...")
            self.service_info = ServiceInfo(
                type_=self.SERVICE_TYPE,
                name=service_name,
                port=port,
                properties=properties,
                server=f"{hostname}.local."
            )
            logger.debug("ServiceInfo created")
            
            # Register service
            logger.debug("Registering service...")
            await self.zeroconf.zeroconf.async_register_service(self.service_info)
            logger.debug("Service registered")
            
            self.running = True
            
            logger.info(
                f"mDNS advertising started: {service_name} on port {port}"
            )
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to start mDNS advertising: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise mDNSError(f"Failed to start advertising: {e}")
    
    def start_browsing(self) -> None:
        """
        Start listening for peer announcements on local network.
        
        Discovers peers broadcasting "_bbs-p2p._tcp" service and
        calls on_peer_discovered callback for each discovered peer.
        
        Raises:
            mDNSError: If browsing fails to start
        """
        try:
            if self.browser is not None:
                logger.warning("mDNS browser already running")
                return
            
            if self.zeroconf is None:
                self.zeroconf = AsyncZeroconf()
            
            # Create service browser with callback
            self.browser = ServiceBrowser(
                self.zeroconf.zeroconf,
                self.SERVICE_TYPE,
                handlers=[self._on_service_state_change]
            )
            
            logger.info(f"mDNS browsing started for {self.SERVICE_TYPE}")
            
        except Exception as e:
            logger.error(f"Failed to start mDNS browsing: {e}")
            raise mDNSError(f"Failed to start browsing: {e}")
    
    async def stop(self) -> None:
        """
        Stop mDNS service and clean up resources.
        
        Unregisters service advertisement and stops browsing.
        """
        self.running = False
        
        try:
            # Unregister service
            if self.service_info and self.zeroconf:
                await self.zeroconf.zeroconf.async_unregister_service(self.service_info)
                logger.info("mDNS service unregistered")
            
            # Close Zeroconf
            if self.zeroconf:
                await self.zeroconf.async_close()
                logger.info("mDNS service stopped")
            
            # Clear references
            self.service_info = None
            self.browser = None
            self.zeroconf = None
            self.discovered_peers.clear()
            
        except Exception as e:
            logger.error(f"Error stopping mDNS service: {e}")
    
    def _on_service_state_change(
        self,
        zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange
    ) -> None:
        """
        Handle service state changes (peer discovered/removed).
        
        Args:
            zeroconf: Zeroconf instance
            service_type: Service type
            name: Service name
            state_change: Type of state change (Added, Removed, Updated)
        """
        try:
            if state_change is ServiceStateChange.Added:
                self._handle_peer_added(zeroconf, service_type, name)
            elif state_change is ServiceStateChange.Removed:
                self._handle_peer_removed(name)
            elif state_change is ServiceStateChange.Updated:
                # Treat updates as re-discovery
                self._handle_peer_added(zeroconf, service_type, name)
                
        except Exception as e:
            logger.error(f"Error handling service state change for {name}: {e}")
    
    def _handle_peer_added(
        self,
        zeroconf,
        service_type: str,
        name: str
    ) -> None:
        """
        Handle peer discovery event.
        
        Args:
            zeroconf: Zeroconf instance
            service_type: Service type
            name: Service name
        """
        try:
            # Get service info (synchronous call is OK here as it's called from ServiceBrowser callback)
            # Try multiple times with increasing timeout
            info = None
            for attempt in range(3):
                info = zeroconf.get_service_info(service_type, name, timeout=5000)
                if info is not None:
                    break
                logger.debug(f"Attempt {attempt + 1}: Could not get service info for {name}, retrying...")
                import time
                time.sleep(0.5)
            
            if info is None:
                logger.warning(f"Could not get service info for {name} after 3 attempts")
                return
            
            # Extract properties
            properties = info.properties
            
            if not properties:
                logger.warning(f"Service {name} has no properties")
                return
            
            # Extract peer information
            peer_id = properties.get(b'peer_id', b'').decode('utf-8')
            version = properties.get(b'version', b'').decode('utf-8')
            public_key_bytes = properties.get(b'public_key', b'')
            signature = properties.get(b'signature', b'')
            
            # Validate required fields
            if not peer_id or not public_key_bytes or not signature:
                logger.warning(f"Service {name} missing required properties")
                return
            
            # Skip self
            if peer_id == self.peer_id:
                logger.debug(f"Ignoring own service advertisement")
                return
            
            # Verify signature
            try:
                # Reconstruct public key
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
                
                # Verify signature on peer_id:port:version
                message_to_verify = f"{peer_id}:{info.port}:{version}".encode('utf-8')
                self.crypto.verify_signature(message_to_verify, signature, public_key)
                
            except Exception as e:
                logger.warning(f"Signature verification failed for peer {peer_id[:8]}: {e}")
                return
            
            # Get peer address
            if not info.addresses:
                logger.warning(f"Service {name} has no addresses")
                return
            
            # Use first address (IPv4 preferred)
            address = None
            for addr in info.addresses:
                if len(addr) == 4:  # IPv4
                    address = socket.inet_ntoa(addr)
                    break
            
            if address is None and info.addresses:
                # Fallback to first address (might be IPv6)
                address = socket.inet_ntop(
                    socket.AF_INET6 if len(info.addresses[0]) == 16 else socket.AF_INET,
                    info.addresses[0]
                )
            
            if address is None:
                logger.warning(f"Could not determine address for {name}")
                return
            
            # Store peer information
            peer_info = {
                'peer_id': peer_id,
                'address': address,
                'port': info.port,
                'version': version,
                'public_key': public_key,
                'service_name': name
            }
            
            # Check if this is a new peer or update
            is_new = peer_id not in self.discovered_peers
            
            self.discovered_peers[peer_id] = peer_info
            
            if is_new:
                logger.info(
                    f"Discovered peer {peer_id[:8]} at {address}:{info.port} "
                    f"via mDNS (version {version})"
                )
            else:
                logger.debug(f"Updated peer {peer_id[:8]} information")
            
            # Notify callback
            if self.on_peer_discovered and is_new:
                self.on_peer_discovered(peer_id, address, info.port, peer_info)
                
        except Exception as e:
            logger.error(f"Error handling peer added for {name}: {e}")
    
    def _handle_peer_removed(self, name: str) -> None:
        """
        Handle peer removal event.
        
        Args:
            name: Service name
        """
        try:
            # Find peer by service name
            peer_id = None
            for pid, info in self.discovered_peers.items():
                if info.get('service_name') == name:
                    peer_id = pid
                    break
            
            if peer_id is None:
                logger.debug(f"Peer removal for unknown service {name}")
                return
            
            # Remove from discovered peers
            del self.discovered_peers[peer_id]
            
            logger.info(f"Peer {peer_id[:8]} removed from network")
            
            # Notify callback
            if self.on_peer_removed:
                self.on_peer_removed(peer_id)
                
        except Exception as e:
            logger.error(f"Error handling peer removed for {name}: {e}")
    
    def _get_local_addresses(self) -> list:
        """
        Get local IP addresses for service advertisement.
        
        Returns:
            List of IP addresses as bytes
        """
        addresses = []
        
        try:
            # Try to get all local addresses
            hostname = socket.gethostname()
            
            try:
                # Get all addresses for hostname
                addr_info = socket.getaddrinfo(
                    hostname,
                    None,
                    socket.AF_UNSPEC,
                    socket.SOCK_STREAM
                )
                
                # Extract unique addresses
                seen = set()
                for info in addr_info:
                    addr = info[4][0]
                    if addr not in seen and not addr.startswith('fe80'):  # Skip link-local
                        seen.add(addr)
                        # Convert to bytes
                        try:
                            if ':' in addr:  # IPv6
                                addresses.append(socket.inet_pton(socket.AF_INET6, addr))
                            else:  # IPv4
                                addresses.append(socket.inet_aton(addr))
                        except Exception as e:
                            logger.debug(f"Could not convert address {addr}: {e}")
            except Exception as e:
                logger.debug(f"Error getting addresses for hostname: {e}")
            
            # If no addresses found, add localhost
            if not addresses:
                addresses = [socket.inet_aton('127.0.0.1')]
            
        except Exception as e:
            logger.warning(f"Error getting local addresses: {e}")
            # Fallback to localhost
            addresses = [socket.inet_aton('127.0.0.1')]
        
        return addresses
    
    def get_discovered_peers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get dictionary of all discovered peers.
        
        Returns:
            Dictionary mapping peer_id to peer information
        """
        return self.discovered_peers.copy()
    
    def is_peer_discovered(self, peer_id: str) -> bool:
        """
        Check if a peer has been discovered via mDNS.
        
        Args:
            peer_id: Peer identifier
            
        Returns:
            True if peer is discovered, False otherwise
        """
        return peer_id in self.discovered_peers
    
    def get_peer_info(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a discovered peer.
        
        Args:
            peer_id: Peer identifier
            
        Returns:
            Dictionary with peer information or None if not found
        """
        return self.discovered_peers.get(peer_id)
