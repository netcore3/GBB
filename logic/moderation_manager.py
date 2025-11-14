"""
Moderation Manager for P2P Encrypted BBS

Manages moderation actions including post deletion, peer banning, and trust management.
Handles action signing, verification, and broadcasting.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.crypto_manager import CryptoManager, Identity, CryptoError
from core.db_manager import DBManager
from core.network_manager import NetworkManager, Message
from models.database import ModerationAction, PeerInfo


logger = logging.getLogger(__name__)


class ModerationManagerError(Exception):
    """Base exception for ModerationManager errors."""
    pass


class ModerationManager:
    """
    Manages moderation operations.
    
    Responsibilities:
    - Create signed moderation actions (delete, ban, trust)
    - Verify moderation action signatures
    - Check peer ban status
    - Broadcast moderation actions to peers
    """
    
    def __init__(
        self,
        identity: Identity,
        crypto_manager: CryptoManager,
        db_manager: DBManager,
        network_manager: NetworkManager
    ):
        """
        Initialize ModerationManager.
        
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
    
    def delete_post(
        self,
        post_id: str,
        reason: Optional[str] = None
    ) -> ModerationAction:
        """
        Create a signed moderation action to delete a post.
        
        The moderation action is signed by the moderator to ensure authenticity.
        The signature covers the action ID, moderator peer ID, action type,
        target ID, reason, and creation timestamp.
        
        Note: This creates a moderation action but doesn't actually delete the post
        from the database. The post is hidden from the UI based on moderation actions.
        
        Args:
            post_id: Post identifier to delete
            reason: Optional reason for deletion
            
        Returns:
            ModerationAction: Created moderation action
            
        Raises:
            ModerationManagerError: If action creation fails
        """
        try:
            # Verify post exists
            post = self.db.get_post_by_id(post_id)
            if not post:
                raise ModerationManagerError(f"Post {post_id[:8]} not found")
            
            # Generate unique action ID
            action_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            action_type = "delete"
            
            # Create message to sign
            message_to_sign = (
                f"{action_id}|{self.identity.peer_id}|{action_type}|"
                f"{post_id}|{reason or ''}|{created_at.isoformat()}"
            ).encode('utf-8')
            
            # Sign the action
            signature = self.crypto.sign_data(
                message_to_sign,
                self.identity.signing_private_key
            )
            
            # Create moderation action object
            action = ModerationAction(
                id=action_id,
                moderator_peer_id=self.identity.peer_id,
                action_type=action_type,
                target_id=post_id,
                reason=reason,
                created_at=created_at,
                signature=signature
            )
            
            # Save to database
            self.db.save_moderation_action(action)
            
            logger.info(
                f"Created delete action {action_id[:8]} for post {post_id[:8]}"
            )
            
            # Broadcast to peers
            self._broadcast_moderation_action(action)
            
            return action
            
        except Exception as e:
            logger.error(f"Failed to create delete action: {e}")
            raise ModerationManagerError(f"Delete post failed: {e}")
    
    def ban_peer(
        self,
        peer_id: str,
        reason: Optional[str] = None
    ) -> ModerationAction:
        """
        Create a signed moderation action to ban a peer.
        
        Banning a peer marks them as banned in the local database and broadcasts
        the ban action to other peers. Banned peers' posts can be hidden from
        the UI based on local moderation preferences.
        
        Args:
            peer_id: Peer identifier to ban
            reason: Optional reason for ban
            
        Returns:
            ModerationAction: Created moderation action
            
        Raises:
            ModerationManagerError: If action creation fails
        """
        try:
            # Get or create peer info
            peer_info = self.db.get_peer_info(peer_id)
            if not peer_info:
                # Create minimal peer info for ban
                peer_info = PeerInfo(
                    peer_id=peer_id,
                    public_key=b'',  # Unknown public key
                    last_seen=datetime.utcnow(),
                    is_banned=True
                )
            else:
                # Update existing peer info
                peer_info.is_banned = True
            
            # Save peer info
            self.db.save_peer_info(peer_info)
            
            # Generate unique action ID
            action_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            action_type = "ban"
            
            # Create message to sign
            message_to_sign = (
                f"{action_id}|{self.identity.peer_id}|{action_type}|"
                f"{peer_id}|{reason or ''}|{created_at.isoformat()}"
            ).encode('utf-8')
            
            # Sign the action
            signature = self.crypto.sign_data(
                message_to_sign,
                self.identity.signing_private_key
            )
            
            # Create moderation action object
            action = ModerationAction(
                id=action_id,
                moderator_peer_id=self.identity.peer_id,
                action_type=action_type,
                target_id=peer_id,
                reason=reason,
                created_at=created_at,
                signature=signature
            )
            
            # Save to database
            self.db.save_moderation_action(action)
            
            logger.info(
                f"Created ban action {action_id[:8]} for peer {peer_id[:8]}"
            )
            
            # Broadcast to peers
            self._broadcast_moderation_action(action)
            
            return action
            
        except Exception as e:
            logger.error(f"Failed to create ban action: {e}")
            raise ModerationManagerError(f"Ban peer failed: {e}")
    
    def trust_peer(self, peer_id: str) -> None:
        """
        Add a peer to the local trust list.
        
        Trusted peers' moderation actions may be given higher weight or
        automatically applied based on local preferences.
        
        Args:
            peer_id: Peer identifier to trust
            
        Raises:
            ModerationManagerError: If trust operation fails
        """
        try:
            # Get or create peer info
            peer_info = self.db.get_peer_info(peer_id)
            if not peer_info:
                # Create minimal peer info for trust
                peer_info = PeerInfo(
                    peer_id=peer_id,
                    public_key=b'',  # Unknown public key
                    last_seen=datetime.utcnow(),
                    is_trusted=True
                )
            else:
                # Update existing peer info
                peer_info.is_trusted = True
            
            # Save peer info
            self.db.save_peer_info(peer_info)
            
            logger.info(f"Added peer {peer_id[:8]} to trust list")
            
            # Optionally create and broadcast a trust action
            # For now, trust is local only
            
        except Exception as e:
            logger.error(f"Failed to trust peer {peer_id[:8]}: {e}")
            raise ModerationManagerError(f"Trust peer failed: {e}")
    
    def untrust_peer(self, peer_id: str) -> None:
        """
        Remove a peer from the local trust list.
        
        Args:
            peer_id: Peer identifier to untrust
            
        Raises:
            ModerationManagerError: If untrust operation fails
        """
        try:
            # Get peer info
            peer_info = self.db.get_peer_info(peer_id)
            if peer_info:
                # Update trust status
                peer_info.is_trusted = False
                self.db.save_peer_info(peer_info)
                logger.info(f"Removed peer {peer_id[:8]} from trust list")
            else:
                logger.warning(f"Peer {peer_id[:8]} not found in database")
            
        except Exception as e:
            logger.error(f"Failed to untrust peer {peer_id[:8]}: {e}")
            raise ModerationManagerError(f"Untrust peer failed: {e}")
    
    def unban_peer(self, peer_id: str) -> None:
        """
        Remove a peer from the local ban list.
        
        Args:
            peer_id: Peer identifier to unban
            
        Raises:
            ModerationManagerError: If unban operation fails
        """
        try:
            # Get peer info
            peer_info = self.db.get_peer_info(peer_id)
            if peer_info:
                # Update ban status
                peer_info.is_banned = False
                self.db.save_peer_info(peer_info)
                logger.info(f"Removed peer {peer_id[:8]} from ban list")
            else:
                logger.warning(f"Peer {peer_id[:8]} not found in database")
            
        except Exception as e:
            logger.error(f"Failed to unban peer {peer_id[:8]}: {e}")
            raise ModerationManagerError(f"Unban peer failed: {e}")
    
    def is_peer_banned(self, peer_id: str) -> bool:
        """
        Check if a peer is banned.
        
        Args:
            peer_id: Peer identifier to check
            
        Returns:
            True if peer is banned, False otherwise
        """
        try:
            peer_info = self.db.get_peer_info(peer_id)
            if peer_info:
                return peer_info.is_banned
            return False
            
        except Exception as e:
            logger.error(f"Failed to check ban status for {peer_id[:8]}: {e}")
            return False
    
    def is_peer_trusted(self, peer_id: str) -> bool:
        """
        Check if a peer is trusted.
        
        Args:
            peer_id: Peer identifier to check
            
        Returns:
            True if peer is trusted, False otherwise
        """
        try:
            peer_info = self.db.get_peer_info(peer_id)
            if peer_info:
                return peer_info.is_trusted
            return False
            
        except Exception as e:
            logger.error(f"Failed to check trust status for {peer_id[:8]}: {e}")
            return False
    
    def get_moderation_actions_for_post(self, post_id: str) -> List[ModerationAction]:
        """
        Get all moderation actions for a specific post.
        
        Args:
            post_id: Post identifier
            
        Returns:
            List of ModerationAction objects
            
        Raises:
            ModerationManagerError: If retrieval fails
        """
        try:
            actions = self.db.get_moderation_actions_for_target(post_id)
            return actions
            
        except Exception as e:
            logger.error(f"Failed to get moderation actions for post {post_id[:8]}: {e}")
            raise ModerationManagerError(f"Get moderation actions failed: {e}")
    
    def get_moderation_actions_for_peer(self, peer_id: str) -> List[ModerationAction]:
        """
        Get all moderation actions for a specific peer.
        
        Args:
            peer_id: Peer identifier
            
        Returns:
            List of ModerationAction objects
            
        Raises:
            ModerationManagerError: If retrieval fails
        """
        try:
            actions = self.db.get_moderation_actions_for_target(peer_id)
            return actions
            
        except Exception as e:
            logger.error(f"Failed to get moderation actions for peer {peer_id[:8]}: {e}")
            raise ModerationManagerError(f"Get moderation actions failed: {e}")
    
    def is_post_deleted(self, post_id: str) -> bool:
        """
        Check if a post has been deleted by any moderation action.
        
        Args:
            post_id: Post identifier
            
        Returns:
            True if post has a delete action, False otherwise
        """
        try:
            actions = self.get_moderation_actions_for_post(post_id)
            return any(action.action_type == "delete" for action in actions)
            
        except Exception as e:
            logger.error(f"Failed to check delete status for post {post_id[:8]}: {e}")
            return False
    
    def _broadcast_moderation_action(self, action: ModerationAction) -> None:
        """
        Broadcast moderation action to all connected peers.
        
        Args:
            action: ModerationAction to broadcast
        """
        try:
            # Create moderation action message
            message = Message(
                msg_type="MODERATION_ACTION",
                payload={
                    "action_id": action.id,
                    "moderator_peer_id": action.moderator_peer_id,
                    "action_type": action.action_type,
                    "target_id": action.target_id,
                    "reason": action.reason,
                    "created_at": action.created_at.isoformat(),
                    "signature": action.signature.hex()
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
                    logger.error(
                        f"Failed to broadcast moderation action to peer {peer_id[:8]}: {e}"
                    )
            
            logger.info(
                f"Broadcast {action.action_type} action {action.id[:8]} "
                f"to {len(connected_peers)} peers"
            )
            
        except Exception as e:
            logger.error(f"Failed to broadcast moderation action: {e}")
    
    def verify_moderation_action_signature(
        self,
        action: ModerationAction
    ) -> bool:
        """
        Verify the signature on a moderation action.
        
        Args:
            action: ModerationAction to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct message that was signed
            message_to_verify = (
                f"{action.id}|{action.moderator_peer_id}|{action.action_type}|"
                f"{action.target_id}|{action.reason or ''}|{action.created_at.isoformat()}"
            ).encode('utf-8')
            
            # Get moderator's public key from database
            peer_info = self.db.get_peer_info(action.moderator_peer_id)
            if not peer_info:
                logger.warning(
                    f"Cannot verify action: moderator peer {action.moderator_peer_id[:8]} not found"
                )
                return False
            
            # Reconstruct public key
            moderator_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                peer_info.public_key
            )
            
            # Verify signature
            return self.crypto.verify_signature(
                message_to_verify,
                action.signature,
                moderator_public_key
            )
            
        except Exception as e:
            logger.error(f"Failed to verify moderation action signature: {e}")
            return False
    
    def get_trusted_peers(self) -> List[PeerInfo]:
        """
        Get list of all trusted peers.
        
        Returns:
            List of PeerInfo objects marked as trusted
            
        Raises:
            ModerationManagerError: If retrieval fails
        """
        try:
            trusted_peers = self.db.get_trusted_peers()
            return trusted_peers
            
        except Exception as e:
            logger.error(f"Failed to get trusted peers: {e}")
            raise ModerationManagerError(f"Get trusted peers failed: {e}")
