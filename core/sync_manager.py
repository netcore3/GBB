"""
Synchronization Manager for P2P Encrypted BBS

Handles replication of posts and threads across peers with conflict resolution
using vector clocks. Implements the sync protocol for exchanging missing data.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime

from core.vector_clock import VectorClock, ClockComparison
from core.network_manager import NetworkManager, Message
from core.db_manager import DBManager
from core.crypto_manager import CryptoManager, SignatureVerificationError
from models.database import Post, Thread, Board


logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Base exception for synchronization errors."""
    pass


class SyncManager:
    """
    Manages synchronization of posts and threads across peers.
    
    Responsibilities:
    - Maintain vector clocks for each board
    - Exchange vector clocks with peers to identify missing posts
    - Request and receive missing posts
    - Validate and store incoming posts
    - Propagate new posts to other peers
    - Periodic synchronization with connected peers
    """
    
    def __init__(
        self,
        network_manager: NetworkManager,
        db_manager: DBManager,
        crypto_manager: CryptoManager,
        local_peer_id: str
    ):
        """
        Initialize SyncManager.
        
        Args:
            network_manager: NetworkManager instance for peer communication
            db_manager: DBManager instance for data persistence
            crypto_manager: CryptoManager instance for signature verification
            local_peer_id: Local peer's ID
        """
        self.network = network_manager
        self.db = db_manager
        self.crypto = crypto_manager
        self.local_peer_id = local_peer_id
        
        # Vector clocks for each board (board_id -> VectorClock)
        self.board_clocks: Dict[str, VectorClock] = {}
        
        # Track sync tasks
        self.sync_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Register message handler with network manager
        self.network.on_message_received = self._handle_network_message
    
    def _get_or_create_clock(self, board_id: str) -> VectorClock:
        """
        Get or create a vector clock for a board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            VectorClock for the board
        """
        if board_id not in self.board_clocks:
            self.board_clocks[board_id] = VectorClock(self.local_peer_id)
        return self.board_clocks[board_id]
    
    async def sync_board(self, board_id: str, peer_ids: Optional[List[str]] = None) -> None:
        """
        Synchronize all threads and posts in a board with peers.
        
        Steps:
        1. Get local vector clock for the board
        2. Send SYNC_REQUEST with local clock to peers
        3. Receive SYNC_RESPONSE with peer's clock
        4. Identify missing posts by comparing clocks
        5. Request missing posts
        6. Validate and store received posts
        
        Args:
            board_id: Board identifier to synchronize
            peer_ids: Optional list of specific peer IDs to sync with.
                     If None, syncs with all connected peers.
                     
        Raises:
            SyncError: If synchronization fails
        """
        try:
            # Get peers to sync with
            if peer_ids is None:
                peer_ids = self.network.get_peers_for_board(board_id)
            
            if not peer_ids:
                logger.debug(f"No peers available for board {board_id[:8]}")
                return
            
            # Get local vector clock for this board
            local_clock = self._get_or_create_clock(board_id)
            
            logger.info(f"Starting sync for board {board_id[:8]} with {len(peer_ids)} peers")
            
            # Sync with each peer
            for peer_id in peer_ids:
                try:
                    await self._sync_with_peer(board_id, peer_id, local_clock)
                except Exception as e:
                    logger.error(f"Failed to sync board {board_id[:8]} with peer {peer_id[:8]}: {e}")
                    # Continue with other peers
            
            logger.info(f"Completed sync for board {board_id[:8]}")
            
        except Exception as e:
            logger.error(f"Error syncing board {board_id[:8]}: {e}")
            raise SyncError(f"Board sync failed: {e}")
    
    async def _sync_with_peer(
        self,
        board_id: str,
        peer_id: str,
        local_clock: VectorClock
    ) -> None:
        """
        Synchronize a board with a specific peer.
        
        Args:
            board_id: Board identifier
            peer_id: Peer ID to sync with
            local_clock: Local vector clock for the board
        """
        # Send SYNC_REQUEST with our clock
        sync_request = Message(
            msg_type="SYNC_REQUEST",
            payload={
                "board_id": board_id,
                "vector_clock": local_clock.to_dict()
            }
        )
        
        await self.network.send_message(peer_id, sync_request)
        logger.debug(f"Sent SYNC_REQUEST to peer {peer_id[:8]} for board {board_id[:8]}")
        
        # Note: SYNC_RESPONSE will be handled by _handle_network_message
    
    async def request_missing_posts(
        self,
        board_id: str,
        peer_id: str,
        missing_ids: List[str]
    ) -> None:
        """
        Request specific posts from a peer.
        
        Args:
            board_id: Board identifier
            peer_id: Peer ID to request from
            missing_ids: List of post IDs to request
        """
        if not missing_ids:
            return
        
        logger.info(f"Requesting {len(missing_ids)} missing posts from peer {peer_id[:8]}")
        
        request = Message(
            msg_type="REQ_MISSING",
            payload={
                "board_id": board_id,
                "post_ids": missing_ids
            }
        )
        
        await self.network.send_message(peer_id, request)
    
    async def handle_incoming_post(self, post_data: Dict, from_peer_id: str) -> bool:
        """
        Validate, store, and propagate an incoming post.
        
        Steps:
        1. Validate post signature
        2. Check if post already exists
        3. Store post in database
        4. Update vector clock
        5. Propagate to other peers on the same board
        
        Args:
            post_data: Dictionary containing post data
            from_peer_id: Peer ID that sent the post
            
        Returns:
            bool: True if post was successfully processed, False otherwise
        """
        try:
            # Extract post fields
            post_id = post_data.get("id")
            thread_id = post_data.get("thread_id")
            author_peer_id = post_data.get("author_peer_id")
            content = post_data.get("content")
            created_at_str = post_data.get("created_at")
            sequence_number = post_data.get("sequence_number")
            signature = bytes.fromhex(post_data.get("signature"))
            parent_post_id = post_data.get("parent_post_id")
            
            # Validate required fields
            if not all([post_id, thread_id, author_peer_id, content, created_at_str, sequence_number is not None, signature]):
                logger.warning(f"Incoming post missing required fields from peer {from_peer_id[:8]}")
                return False
            
            # Check if post already exists
            existing_post = self.db.get_post_by_id(post_id)
            if existing_post:
                logger.debug(f"Post {post_id[:8]} already exists, skipping")
                return True  # Not an error, just already have it
            
            # Verify signature
            try:
                # Reconstruct the data that was signed
                from cryptography.hazmat.primitives.asymmetric import ed25519
                from cryptography.hazmat.primitives import serialization
                
                # Get author's public key from peer info
                peer_info = self.db.get_peer_info(author_peer_id)
                if not peer_info:
                    logger.warning(f"Unknown author {author_peer_id[:8]} for post {post_id[:8]}")
                    return False
                
                author_public_key = ed25519.Ed25519PublicKey.from_public_bytes(peer_info.public_key)
                
                # Create message to verify (same format as when signing)
                message_to_verify = f"{post_id}{thread_id}{author_peer_id}{content}{created_at_str}{sequence_number}".encode('utf-8')
                
                self.crypto.verify_signature(message_to_verify, signature, author_public_key)
                
            except SignatureVerificationError as e:
                logger.error(f"Signature verification failed for post {post_id[:8]}: {e}")
                return False
            except Exception as e:
                logger.error(f"Error verifying post signature: {e}")
                return False
            
            # Parse timestamp
            created_at = datetime.fromisoformat(created_at_str)
            
            # Create Post object
            post = Post(
                id=post_id,
                thread_id=thread_id,
                author_peer_id=author_peer_id,
                content=content,
                created_at=created_at,
                sequence_number=sequence_number,
                signature=signature,
                parent_post_id=parent_post_id
            )
            
            # Store in database
            self.db.save_post(post)
            logger.info(f"Stored post {post_id[:8]} from {author_peer_id[:8]}")
            
            # Update vector clock for the board
            # First, get the board_id from the thread
            thread = self.db.get_posts_for_thread(thread_id)
            if thread:
                # Get board_id from thread (need to query thread first)
                # For now, we'll update the clock based on author and sequence
                pass
            
            # Update vector clock
            board_id = post_data.get("board_id")  # Should be included in post_data
            if board_id:
                clock = self._get_or_create_clock(board_id)
                # Update clock with author's sequence number
                current_seq = clock.get(author_peer_id)
                if sequence_number > current_seq:
                    clock.set(author_peer_id, sequence_number)
            
            # Propagate to other peers (except the one we received it from)
            if board_id:
                await self._propagate_post(board_id, post_data, exclude_peer_id=from_peer_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling incoming post: {e}")
            return False
    
    async def _propagate_post(
        self,
        board_id: str,
        post_data: Dict,
        exclude_peer_id: Optional[str] = None
    ) -> None:
        """
        Propagate a post to other peers on the same board.
        
        Args:
            board_id: Board identifier
            post_data: Post data to propagate
            exclude_peer_id: Optional peer ID to exclude from propagation
        """
        peers = self.network.get_peers_for_board(board_id)
        
        # Filter out the excluded peer
        if exclude_peer_id:
            peers = [p for p in peers if p != exclude_peer_id]
        
        if not peers:
            return
        
        message = Message(
            msg_type="POST",
            payload=post_data
        )
        
        # Send to each peer
        for peer_id in peers:
            try:
                await self.network.send_message(peer_id, message)
                logger.debug(f"Propagated post to peer {peer_id[:8]}")
            except Exception as e:
                logger.error(f"Failed to propagate post to peer {peer_id[:8]}: {e}")
    
    async def _handle_network_message(self, peer_id: str, message: Message) -> None:
        """
        Handle incoming network messages related to synchronization.
        
        Args:
            peer_id: Peer ID that sent the message
            message: Received message
        """
        try:
            if message.msg_type == "SYNC_REQUEST":
                await self._handle_sync_request(peer_id, message)
            elif message.msg_type == "SYNC_RESPONSE":
                await self._handle_sync_response(peer_id, message)
            elif message.msg_type == "REQ_MISSING":
                await self._handle_req_missing(peer_id, message)
            elif message.msg_type == "POST_BATCH":
                await self._handle_post_batch(peer_id, message)
            elif message.msg_type == "POST":
                await self._handle_single_post(peer_id, message)
            else:
                # Not a sync-related message, ignore
                pass
                
        except Exception as e:
            logger.error(f"Error handling message {message.msg_type} from peer {peer_id[:8]}: {e}")
    
    async def _handle_sync_request(self, peer_id: str, message: Message) -> None:
        """
        Handle SYNC_REQUEST from a peer.
        
        Args:
            peer_id: Peer ID that sent the request
            message: SYNC_REQUEST message
        """
        board_id = message.payload.get("board_id")
        remote_clock_dict = message.payload.get("vector_clock", {})
        remote_clock = VectorClock.from_dict(remote_clock_dict)
        
        logger.debug(f"Received SYNC_REQUEST from peer {peer_id[:8]} for board {board_id[:8]}")
        
        # Get our local clock for this board
        local_clock = self._get_or_create_clock(board_id)
        
        # Send SYNC_RESPONSE with our clock
        response = Message(
            msg_type="SYNC_RESPONSE",
            payload={
                "board_id": board_id,
                "vector_clock": local_clock.to_dict()
            }
        )
        
        await self.network.send_message(peer_id, response)
        logger.debug(f"Sent SYNC_RESPONSE to peer {peer_id[:8]} for board {board_id[:8]}")
        
        # Identify posts we have that the peer might be missing
        missing_for_peer = self._identify_missing_posts(board_id, local_clock, remote_clock)
        
        if missing_for_peer:
            # Send the missing posts to the peer
            await self._send_post_batch(peer_id, board_id, missing_for_peer)
    
    async def _handle_sync_response(self, peer_id: str, message: Message) -> None:
        """
        Handle SYNC_RESPONSE from a peer.
        
        Args:
            peer_id: Peer ID that sent the response
            message: SYNC_RESPONSE message
        """
        board_id = message.payload.get("board_id")
        remote_clock_dict = message.payload.get("vector_clock", {})
        remote_clock = VectorClock.from_dict(remote_clock_dict)
        
        logger.debug(f"Received SYNC_RESPONSE from peer {peer_id[:8]} for board {board_id[:8]}")
        
        # Get our local clock
        local_clock = self._get_or_create_clock(board_id)
        
        # Identify posts we're missing
        missing_for_us = self._identify_missing_posts(board_id, remote_clock, local_clock)
        
        if missing_for_us:
            # Request the missing posts
            await self.request_missing_posts(board_id, peer_id, missing_for_us)
    
    async def _handle_req_missing(self, peer_id: str, message: Message) -> None:
        """
        Handle REQ_MISSING request from a peer.
        
        Args:
            peer_id: Peer ID that sent the request
            message: REQ_MISSING message
        """
        board_id = message.payload.get("board_id")
        post_ids = message.payload.get("post_ids", [])
        
        logger.debug(f"Received REQ_MISSING from peer {peer_id[:8]} for {len(post_ids)} posts")
        
        # Send the requested posts
        await self._send_post_batch(peer_id, board_id, post_ids)
    
    async def _handle_post_batch(self, peer_id: str, message: Message) -> None:
        """
        Handle POST_BATCH message containing multiple posts.
        
        Args:
            peer_id: Peer ID that sent the batch
            message: POST_BATCH message
        """
        posts = message.payload.get("posts", [])
        board_id = message.payload.get("board_id")
        
        logger.info(f"Received POST_BATCH with {len(posts)} posts from peer {peer_id[:8]}")
        
        # Process each post
        for post_data in posts:
            post_data["board_id"] = board_id  # Add board_id for processing
            await self.handle_incoming_post(post_data, peer_id)
    
    async def _handle_single_post(self, peer_id: str, message: Message) -> None:
        """
        Handle a single POST message.
        
        Args:
            peer_id: Peer ID that sent the post
            message: POST message
        """
        post_data = message.payload
        await self.handle_incoming_post(post_data, peer_id)
    
    def _identify_missing_posts(
        self,
        board_id: str,
        have_clock: VectorClock,
        need_clock: VectorClock
    ) -> List[str]:
        """
        Identify post IDs that are in have_clock but not in need_clock.
        
        This is a simplified implementation that identifies posts based on
        sequence numbers. In a real implementation, we would query the database
        for actual post IDs.
        
        Args:
            board_id: Board identifier
            have_clock: Vector clock of posts we have
            need_clock: Vector clock of posts they need
            
        Returns:
            List of post IDs that are missing
        """
        missing_posts = []
        
        # For each peer in have_clock
        for peer_id, have_seq in have_clock.to_dict().items():
            need_seq = need_clock.get(peer_id)
            
            if have_seq > need_seq:
                # We have posts from this peer that they don't have
                # Query database for posts from this peer with sequence > need_seq
                # For now, we'll return an empty list as we need to implement
                # proper post querying by sequence number
                pass
        
        # TODO: Implement actual database query to get post IDs
        # For now, return empty list
        return missing_posts
    
    async def _send_post_batch(
        self,
        peer_id: str,
        board_id: str,
        post_ids: List[str]
    ) -> None:
        """
        Send a batch of posts to a peer.
        
        Args:
            peer_id: Peer ID to send to
            board_id: Board identifier
            post_ids: List of post IDs to send
        """
        if not post_ids:
            return
        
        # Retrieve posts from database
        posts_data = []
        for post_id in post_ids:
            post = self.db.get_post_by_id(post_id)
            if post:
                post_data = {
                    "id": post.id,
                    "thread_id": post.thread_id,
                    "author_peer_id": post.author_peer_id,
                    "content": post.content,
                    "created_at": post.created_at.isoformat(),
                    "sequence_number": post.sequence_number,
                    "signature": post.signature.hex(),
                    "parent_post_id": post.parent_post_id
                }
                posts_data.append(post_data)
        
        if not posts_data:
            logger.warning(f"No posts found for IDs: {post_ids}")
            return
        
        # Send POST_BATCH message
        message = Message(
            msg_type="POST_BATCH",
            payload={
                "board_id": board_id,
                "posts": posts_data
            }
        )
        
        await self.network.send_message(peer_id, message)
        logger.info(f"Sent POST_BATCH with {len(posts_data)} posts to peer {peer_id[:8]}")
    
    async def start_periodic_sync(self, interval: int = 30) -> None:
        """
        Start periodic synchronization with all connected peers.
        
        This runs as a background asyncio task that syncs all boards
        at the specified interval.
        
        Args:
            interval: Sync interval in seconds (default: 30)
        """
        if self.running:
            logger.warning("Periodic sync already running")
            return
        
        self.running = True
        self.sync_task = asyncio.create_task(self._periodic_sync_loop(interval))
        logger.info(f"Started periodic sync with interval {interval}s")
    
    async def stop_periodic_sync(self) -> None:
        """Stop periodic synchronization."""
        self.running = False
        
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped periodic sync")
    
    async def _periodic_sync_loop(self, interval: int) -> None:
        """
        Background task for periodic synchronization.
        
        Args:
            interval: Sync interval in seconds
        """
        retry_count = 0
        max_retries = 3
        base_backoff = 5  # seconds
        
        while self.running:
            try:
                # Get all boards
                boards = self.db.get_all_boards()
                
                # Sync each board
                for board in boards:
                    if not self.running:
                        break
                    
                    try:
                        await self.sync_board(board.id)
                        retry_count = 0  # Reset on success
                    except Exception as e:
                        logger.error(f"Error syncing board {board.id[:8]}: {e}")
                        retry_count += 1
                
                # Wait for next sync interval
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.debug("Periodic sync loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic sync loop: {e}")
                retry_count += 1
                
                # Exponential backoff on repeated failures
                if retry_count >= max_retries:
                    backoff = min(base_backoff * (2 ** (retry_count - max_retries)), 60)
                    logger.warning(f"Multiple sync failures, backing off for {backoff}s")
                    await asyncio.sleep(backoff)
                else:
                    await asyncio.sleep(interval)
