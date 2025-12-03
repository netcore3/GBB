import asyncio
import logging
from core.network_manager import NetworkManager
from core.crypto_manager import CryptoManager

logging.basicConfig(level=logging.DEBUG)

async def main():
    crypto = CryptoManager()
    identity1 = crypto.generate_identity()
    identity2 = crypto.generate_identity()
    
    nm1 = NetworkManager(identity1, crypto)
    nm2 = NetworkManager(identity2, crypto)
    
    # Start server
    await nm2.start(port=9999, host='127.0.0.1')
    print("Server started")
    
    # Connect
    peer_id = await nm1.connect_to_peer('127.0.0.1', 9999)
    print(f"Connected to peer: {peer_id[:8]}")
    
    # Wait a bit
    await asyncio.sleep(0.5)
    
    # Check connection
    print(f"Peer count in nm1: {nm1.get_connection_count()}")
    print(f"Peer count in nm2: {nm2.get_connection_count()}")
    print(f"Peers in nm1: {list(nm1.peers.keys())}")
    print(f"Peers in nm2: {list(nm2.peers.keys())}")
    
    # Cleanup
    await nm1.stop()
    await nm2.stop()
    print("Stopped")

if __name__ == "__main__":
    asyncio.run(main())
