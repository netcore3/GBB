"""
Board Manager for P2P Encrypted BBS

Manages board creation, joining, and thread retrieval.
Handles board announcements to connected peers.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from cryptography.hazmat.primitives import serialization

from core.crypto_manager import CryptoManager, Identity, CryptoError
from core.db_manager import DBManager
from core.network_manager import NetworkManager, Message
from models.database import Board, Thread


logger = logging.getLogger(__name__)


class BoardManagerError(Exception):
    """Base exception for BoardManager errors."""
    pass


class BoardManager:
    """
    Manages board operations including creation, joining, and thread retrieval.
    
    Responsibilities:
    - Create new boards with unique IDs and signatures
    - Join existing boards and request synchronization
    - Retrieve threads for boards from database
    - Announce new boards to connected peers
    """
    
    def __init__(
        self,
        identity: Identity,
        crypto_manager: CryptoManager,
        db_manager: DBManager,
        network_manager: NetworkManager
    ):
        """
        Initialize BoardManager.
        
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
        
        # Track subscribed boards
        self.subscribed_boards: set[str] = set()
    
    def create_board(self, name: str, description: str = "", welcome_message: str = "", image_path: str = "", is_private: bool = False) -> Board:
        """
        Create a new board with unique ID and signature.

        The board is signed by the creator to ensure authenticity and prevent
        tampering. The signature covers the board ID, name, description, creator
        peer ID, and creation timestamp.

        Args:
            name: Board name (3-50 characters)
            description: Board description (optional)
            welcome_message: Welcome message shown on board entry (optional)
            image_path: Path to board image (optional)
            is_private: Whether the board is private/invite-only (default: False)

        Returns:
            Board: Created board object

        Raises:
            BoardManagerError: If board creation fails
            ValueError: If name is invalid
        """
        # Validate input
        if not name or len(name) < 3 or len(name) > 50:
            raise ValueError("Board name must be 3-50 characters")

        try:
            # Generate unique board ID
            board_id = str(uuid.uuid4())
            created_at = datetime.utcnow()

            # Create message to sign (include welcome_message, image_path, and is_private for integrity)
            message_to_sign = (
                f"{board_id}|{name}|{description}|{welcome_message}|{image_path}|{is_private}|"
                f"{self.identity.peer_id}|{created_at.isoformat()}"
            ).encode('utf-8')

            # Sign the board
            signature = self.crypto.sign_data(
                message_to_sign,
                self.identity.signing_private_key
            )

            # Create board object
            board = Board(
                id=board_id,
                name=name,
                description=description,
                welcome_message=welcome_message,
                image_path=image_path,
                is_private=is_private,
                creator_peer_id=self.identity.peer_id,
                created_at=created_at,
                signature=signature
            )
            
            # Save to database
            self.db.save_board(board)
            
            # Subscribe to the board
            self.subscribed_boards.add(board_id)
            
            logger.info(f"Created board '{name}' with ID {board_id[:8]}")
            
            # Announce to connected peers
            self._announce_board(board)
            
            return board
            
        except Exception as e:
            logger.error(f"Failed to create board: {e}")
            raise BoardManagerError(f"Board creation failed: {e}")
    
    def join_board(self, board_id: str) -> None:
        """
        Subscribe to a board and request synchronization from peers.
        
        When joining a board, the manager subscribes to updates and requests
        the complete thread and post history from connected peers.
        
        Args:
            board_id: Board identifier to join
            
        Raises:
            BoardManagerError: If board doesn't exist or join fails
        """
        try:
            # Verify board exists in database
            board = self.db.get_board_by_id(board_id)
            if not board:
                raise BoardManagerError(f"Board {board_id[:8]} not found")
            
            # Add to subscribed boards
            self.subscribed_boards.add(board_id)
            
            logger.info(f"Joined board '{board.name}' ({board_id[:8]})")
            
            # Request sync from connected peers
            self._request_board_sync(board_id)
            
        except Exception as e:
            logger.error(f"Failed to join board {board_id[:8]}: {e}")
            raise BoardManagerError(f"Join board failed: {e}")
    
    def get_board_threads(self, board_id: str) -> List[Thread]:
        """
        Retrieve all threads for a specific board from the database.
        
        Threads are returned ordered by last activity (most recent first).
        
        Args:
            board_id: Board identifier
            
        Returns:
            List of Thread objects for the board
            
        Raises:
            BoardManagerError: If retrieval fails
        """
        try:
            threads = self.db.get_threads_for_board(board_id)
            logger.debug(f"Retrieved {len(threads)} threads for board {board_id[:8]}")
            return threads
            
        except Exception as e:
            logger.error(f"Failed to get threads for board {board_id[:8]}: {e}")
            raise BoardManagerError(f"Get threads failed: {e}")
    
    def get_all_boards(self) -> List[Board]:
        """
        Retrieve all boards from the database.
        
        Returns:
            List of all Board objects
            
        Raises:
            BoardManagerError: If retrieval fails
        """
        try:
            boards = self.db.get_all_boards()
            logger.debug(f"Retrieved {len(boards)} boards")
            return boards
            
        except Exception as e:
            logger.error(f"Failed to get all boards: {e}")
            raise BoardManagerError(f"Get boards failed: {e}")
    
    def get_board_by_id(self, board_id: str) -> Optional[Board]:
        """
        Retrieve a specific board by ID.
        
        Args:
            board_id: Board identifier
            
        Returns:
            Board object if found, None otherwise
            
        Raises:
            BoardManagerError: If retrieval fails
        """
        try:
            board = self.db.get_board_by_id(board_id)
            return board
            
        except Exception as e:
            logger.error(f"Failed to get board {board_id[:8]}: {e}")
            raise BoardManagerError(f"Get board failed: {e}")
    
    def is_subscribed(self, board_id: str) -> bool:
        """
        Check if currently subscribed to a board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            True if subscribed, False otherwise
        """
        return board_id in self.subscribed_boards
    
    def get_subscribed_boards(self) -> List[str]:
        """
        Get list of subscribed board IDs.
        
        Returns:
            List of board IDs
        """
        return list(self.subscribed_boards)
    
    def _announce_board(self, board: Board) -> None:
        """
        Announce new board to all connected peers.
        
        Args:
            board: Board to announce
        """
        try:
            # Create announcement message
            message = Message(
                msg_type="BOARD_ANNOUNCE",
                payload={
                    "board_id": board.id,
                    "name": board.name,
                    "description": board.description,
                    "welcome_message": getattr(board, 'welcome_message', None),
                    "image_path": getattr(board, 'image_path', None),
                    "creator_peer_id": board.creator_peer_id,
                    "created_at": board.created_at.isoformat(),
                    "signature": board.signature.hex()
                }
            )
            
            # Send to all connected peers
            connected_peers = self.network.get_connected_peers()
            for peer_id in connected_peers:
                try:
                    # Use asyncio to send message (non-blocking)
                    import asyncio
                    asyncio.create_task(
                        self.network.send_message(peer_id, message)
                    )
                except Exception as e:
                    logger.error(f"Failed to announce board to peer {peer_id[:8]}: {e}")
            
            logger.info(f"Announced board '{board.name}' to {len(connected_peers)} peers")
            
        except Exception as e:
            logger.error(f"Failed to announce board: {e}")
    
    def _request_board_sync(self, board_id: str) -> None:
        """
        Request board synchronization from connected peers.
        
        Args:
            board_id: Board identifier to sync
        """
        try:
            # Create sync request message
            message = Message(
                msg_type="BOARD_SYNC_REQUEST",
                payload={
                    "board_id": board_id,
                    "requester_peer_id": self.identity.peer_id
                }
            )
            
            # Send to all connected peers
            connected_peers = self.network.get_connected_peers()
            for peer_id in connected_peers:
                try:
                    import asyncio
                    asyncio.create_task(
                        self.network.send_message(peer_id, message)
                    )
                except Exception as e:
                    logger.error(f"Failed to request sync from peer {peer_id[:8]}: {e}")
            
            logger.info(f"Requested sync for board {board_id[:8]} from {len(connected_peers)} peers")
            
        except Exception as e:
            logger.error(f"Failed to request board sync: {e}")
    
    def verify_board_signature(self, board: Board) -> bool:
        """
        Verify the signature on a board.
        
        Args:
            board: Board to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct message that was signed
            message_to_verify = (
                f"{board.id}|{board.name}|{board.description}|"
                f"{board.creator_peer_id}|{board.created_at.isoformat()}"
            ).encode('utf-8')
            
            # Get creator's public key from database
            peer_info = self.db.get_peer_info(board.creator_peer_id)
            if not peer_info:
                logger.warning(f"Cannot verify board: creator peer {board.creator_peer_id[:8]} not found")
                return False
            
            # Reconstruct public key
            from cryptography.hazmat.primitives.asymmetric import ed25519
            creator_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                peer_info.public_key
            )
            
            # Verify signature
            return self.crypto.verify_signature(
                message_to_verify,
                board.signature,
                creator_public_key
            )
            
        except Exception as e:
            logger.error(f"Failed to verify board signature: {e}")
            return False

    def update_board(self, board_id: str, name: str, description: str, welcome_message: str = "", image_path: str = "", is_private: bool = False) -> Board:
        """
        Update an existing board's name and description. Only the original creator
        may update a board. The board will be re-signed with the creator's key.

        Args:
            board_id: ID of the board to update
            name: New name
            description: New description
            welcome_message: Welcome message shown on board entry (optional)
            image_path: Path to board image (optional)
            is_private: Whether the board is private/invite-only (default: False)

        Returns:
            Updated Board object
        """
        try:
            board = self.get_board_by_id(board_id)
            if not board:
                raise BoardManagerError("Board not found")

            if board.creator_peer_id != self.identity.peer_id:
                raise BoardManagerError("Only the creator can edit this board")

            # Update fields
            board.name = name
            board.description = description
            board.welcome_message = welcome_message
            board.image_path = image_path
            board.is_private = is_private

            # Re-sign using original created_at value and include metadata
            message_to_sign = (
                f"{board.id}|{board.name}|{board.description}|{getattr(board,'welcome_message','')}|{getattr(board,'image_path','')}|{board.is_private}|"
                f"{board.creator_peer_id}|{board.created_at.isoformat()}"
            ).encode('utf-8')

            board.signature = self.crypto.sign_data(
                message_to_sign,
                self.identity.signing_private_key
            )

            # Persist update
            self.db.update_board(board)

            # Optionally re-announce the board update to peers
            self._announce_board(board)

            logger.info(f"Updated board '{board.name}' ({board.id[:8]})")
            return board

        except BoardManagerError:
            raise
        except Exception as e:
            logger.error(f"Failed to update board: {e}")
            raise BoardManagerError(f"Update failed: {e}")
