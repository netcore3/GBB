"""
Thread Manager for P2P Encrypted BBS

Manages thread and post creation, retrieval, and broadcasting.
Handles post signing and verification.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.crypto_manager import CryptoManager, Identity, CryptoError
from core.db_manager import DBManager
from core.network_manager import NetworkManager, Message
from models.database import Thread, Post


logger = logging.getLogger(__name__)


class ThreadManagerError(Exception):
    """Base exception for ThreadManager errors."""
    pass


class ThreadManager:
    """
    Manages thread and post operations.
    
    Responsibilities:
    - Create threads with title and initial post
    - Add signed posts to threads
    - Retrieve posts from database
    - Broadcast new threads and posts to peers
    """
    
    def __init__(
        self,
        identity: Identity,
        crypto_manager: CryptoManager,
        db_manager: DBManager,
        network_manager: NetworkManager
    ):
        """
        Initialize ThreadManager.
        
        Args:
            identity: Local peer identity
            crypto_manager: CryptoManager instance for signing
            db_manager: DBManager instance for database operations
            network_manager: NetworkManager instance for peer communication
        """
        self.identity = identity
        self.crypto = crypto_manager
        self.db = db_manager
        self.network = network_manager
        
        # Track sequence numbers for posts (for vector clock)
        self.sequence_counter = 0
    
    def create_thread(
        self,
        board_id: str,
        title: str,
        initial_post_content: str
    ) -> Thread:
        """
        Create a new thread with title and initial post.
        
        The thread and initial post are both signed by the creator. The thread
        signature covers the thread ID, board ID, title, creator peer ID, and
        creation timestamp.
        
        Args:
            board_id: Board identifier where thread will be created
            title: Thread title (3-200 characters)
            initial_post_content: Content of the first post (1-10000 characters)
            
        Returns:
            Thread: Created thread object
            
        Raises:
            ThreadManagerError: If thread creation fails
            ValueError: If title or content is invalid
        """
        # Validate input
        if not title or len(title) < 3 or len(title) > 200:
            raise ValueError("Thread title must be 3-200 characters")
        
        if not initial_post_content or len(initial_post_content) < 1 or len(initial_post_content) > 10000:
            raise ValueError("Post content must be 1-10000 characters")
        
        # Verify board exists
        board = self.db.get_board_by_id(board_id)
        if not board:
            raise ThreadManagerError(f"Board {board_id[:8]} not found")
        
        try:
            # Generate unique thread ID
            thread_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            
            # Create message to sign for thread
            thread_message_to_sign = (
                f"{thread_id}|{board_id}|{title}|"
                f"{self.identity.peer_id}|{created_at.isoformat()}"
            ).encode('utf-8')
            
            # Sign the thread
            thread_signature = self.crypto.sign_data(
                thread_message_to_sign,
                self.identity.signing_private_key
            )
            
            # Create thread object
            thread = Thread(
                id=thread_id,
                board_id=board_id,
                title=title,
                creator_peer_id=self.identity.peer_id,
                created_at=created_at,
                last_activity=created_at,
                signature=thread_signature
            )
            
            # Save thread to database
            self.db.save_thread(thread)
            
            logger.info(f"Created thread '{title}' with ID {thread_id[:8]} in board {board_id[:8]}")
            
            # Create initial post
            post = self.add_post_to_thread(
                thread_id=thread_id,
                content=initial_post_content,
                parent_post_id=None
            )
            
            # Broadcast thread to peers
            self._broadcast_thread(thread, post)
            
            return thread
            
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
            raise ThreadManagerError(f"Thread creation failed: {e}")
    
    def add_post_to_thread(
        self,
        thread_id: str,
        content: str,
        parent_post_id: Optional[str] = None
    ) -> Post:
        """
        Create a signed post and add it to a thread.
        
        The post is signed by the author to ensure authenticity. The signature
        covers the post ID, thread ID, author peer ID, content, creation timestamp,
        and sequence number.
        
        Args:
            thread_id: Thread identifier
            content: Post content (1-10000 characters)
            parent_post_id: Optional parent post ID for replies
            
        Returns:
            Post: Created post object
            
        Raises:
            ThreadManagerError: If post creation fails
            ValueError: If content is invalid
        """
        # Validate input
        if not content or len(content) < 1 or len(content) > 10000:
            raise ValueError("Post content must be 1-10000 characters")
        
        # Verify thread exists
        thread = self.db.get_posts_for_thread(thread_id)
        if thread is None:
            # Check if thread exists by trying to get it
            threads = self.db.get_threads_for_board("")
            thread_exists = any(t.id == thread_id for t in threads)
            if not thread_exists:
                raise ThreadManagerError(f"Thread {thread_id[:8]} not found")
        
        try:
            # Generate unique post ID
            post_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            
            # Increment sequence number for vector clock
            self.sequence_counter += 1
            sequence_number = self.sequence_counter
            
            # Create message to sign
            post_message_to_sign = (
                f"{post_id}|{thread_id}|{self.identity.peer_id}|"
                f"{content}|{created_at.isoformat()}|{sequence_number}"
            ).encode('utf-8')
            
            # Sign the post
            post_signature = self.crypto.sign_data(
                post_message_to_sign,
                self.identity.signing_private_key
            )
            
            # Create post object
            post = Post(
                id=post_id,
                thread_id=thread_id,
                author_peer_id=self.identity.peer_id,
                content=content,
                created_at=created_at,
                sequence_number=sequence_number,
                signature=post_signature,
                parent_post_id=parent_post_id
            )
            
            # Save post to database
            self.db.save_post(post)
            
            logger.info(f"Created post {post_id[:8]} in thread {thread_id[:8]}")
            
            # Broadcast post to peers
            self._broadcast_post(post)
            
            return post
            
        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            raise ThreadManagerError(f"Post creation failed: {e}")
    
    def get_thread_posts(self, thread_id: str) -> List[Post]:
        """
        Retrieve all posts for a specific thread from the database.
        
        Posts are returned ordered by creation time (oldest first).
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            List of Post objects for the thread
            
        Raises:
            ThreadManagerError: If retrieval fails
        """
        try:
            posts = self.db.get_posts_for_thread(thread_id)
            logger.debug(f"Retrieved {len(posts)} posts for thread {thread_id[:8]}")
            return posts
            
        except Exception as e:
            logger.error(f"Failed to get posts for thread {thread_id[:8]}: {e}")
            raise ThreadManagerError(f"Get posts failed: {e}")
    
    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """
        Retrieve a specific post by ID.
        
        Args:
            post_id: Post identifier
            
        Returns:
            Post object if found, None otherwise
            
        Raises:
            ThreadManagerError: If retrieval fails
        """
        try:
            post = self.db.get_post_by_id(post_id)
            return post
            
        except Exception as e:
            logger.error(f"Failed to get post {post_id[:8]}: {e}")
            raise ThreadManagerError(f"Get post failed: {e}")
    
    def _broadcast_thread(self, thread: Thread, initial_post: Post) -> None:
        """
        Broadcast new thread to all connected peers on the board.
        
        Args:
            thread: Thread to broadcast
            initial_post: Initial post in the thread
        """
        try:
            # Create thread announcement message
            message = Message(
                msg_type="THREAD_ANNOUNCE",
                payload={
                    "thread_id": thread.id,
                    "board_id": thread.board_id,
                    "title": thread.title,
                    "creator_peer_id": thread.creator_peer_id,
                    "created_at": thread.created_at.isoformat(),
                    "signature": thread.signature.hex(),
                    "initial_post": {
                        "post_id": initial_post.id,
                        "content": initial_post.content,
                        "created_at": initial_post.created_at.isoformat(),
                        "sequence_number": initial_post.sequence_number,
                        "signature": initial_post.signature.hex()
                    }
                }
            )
            
            # Broadcast to board
            import asyncio
            asyncio.create_task(
                self.network.broadcast_to_board(thread.board_id, message)
            )
            
            logger.info(f"Broadcast thread '{thread.title}' to board {thread.board_id[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast thread: {e}")
    
    def _broadcast_post(self, post: Post) -> None:
        """
        Broadcast new post to all connected peers on the board.
        
        Args:
            post: Post to broadcast
        """
        try:
            # Get thread to determine board
            # We need to query the database to get the thread's board_id
            # For now, we'll send to all connected peers
            # In a real implementation, we'd track which board each thread belongs to
            
            # Create post announcement message
            message = Message(
                msg_type="POST_ANNOUNCE",
                payload={
                    "post_id": post.id,
                    "thread_id": post.thread_id,
                    "author_peer_id": post.author_peer_id,
                    "content": post.content,
                    "created_at": post.created_at.isoformat(),
                    "sequence_number": post.sequence_number,
                    "signature": post.signature.hex(),
                    "parent_post_id": post.parent_post_id
                }
            )
            
            # Send to all connected peers
            # In a production system, we'd only send to peers subscribed to the board
            connected_peers = self.network.get_connected_peers()
            for peer_id in connected_peers:
                try:
                    import asyncio
                    asyncio.create_task(
                        self.network.send_message(peer_id, message)
                    )
                except Exception as e:
                    logger.error(f"Failed to broadcast post to peer {peer_id[:8]}: {e}")
            
            logger.info(f"Broadcast post {post.id[:8]} to {len(connected_peers)} peers")
            
        except Exception as e:
            logger.error(f"Failed to broadcast post: {e}")
    
    def verify_thread_signature(self, thread: Thread) -> bool:
        """
        Verify the signature on a thread.
        
        Args:
            thread: Thread to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct message that was signed
            message_to_verify = (
                f"{thread.id}|{thread.board_id}|{thread.title}|"
                f"{thread.creator_peer_id}|{thread.created_at.isoformat()}"
            ).encode('utf-8')
            
            # Get creator's public key from database
            peer_info = self.db.get_peer_info(thread.creator_peer_id)
            if not peer_info:
                logger.warning(f"Cannot verify thread: creator peer {thread.creator_peer_id[:8]} not found")
                return False
            
            # Reconstruct public key
            creator_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                peer_info.public_key
            )
            
            # Verify signature
            return self.crypto.verify_signature(
                message_to_verify,
                thread.signature,
                creator_public_key
            )
            
        except Exception as e:
            logger.error(f"Failed to verify thread signature: {e}")
            return False
    
    def verify_post_signature(self, post: Post) -> bool:
        """
        Verify the signature on a post.
        
        Args:
            post: Post to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct message that was signed
            message_to_verify = (
                f"{post.id}|{post.thread_id}|{post.author_peer_id}|"
                f"{post.content}|{post.created_at.isoformat()}|{post.sequence_number}"
            ).encode('utf-8')
            
            # Get author's public key from database
            peer_info = self.db.get_peer_info(post.author_peer_id)
            if not peer_info:
                logger.warning(f"Cannot verify post: author peer {post.author_peer_id[:8]} not found")
                return False
            
            # Reconstruct public key
            author_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                peer_info.public_key
            )
            
            # Verify signature
            return self.crypto.verify_signature(
                message_to_verify,
                post.signature,
                author_public_key
            )
            
        except Exception as e:
            logger.error(f"Failed to verify post signature: {e}")
            return False
