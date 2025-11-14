"""
Chat Manager for P2P Encrypted BBS

Manages private messaging with sealed box encryption.
Handles message sending, retrieval, and read status tracking.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

from core.crypto_manager import CryptoManager, Identity, CryptoError, DecryptionError
from core.db_manager import DBManager
from core.network_manager import NetworkManager, Message
from models.database import PrivateMessage


logger = logging.getLogger(__name__)


class ChatManagerError(Exception):
    """Base exception for ChatManager errors."""
    pass


class ChatManager:
    """
    Manages private messaging operations.
    
    Responsibilities:
    - Send encrypted private messages using sealed box encryption
    - Retrieve conversation history from database
    - Mark messages as read
    - Send encrypted messages directly to recipient peer
    """
    
    def __init__(
        self,
        identity: Identity,
        crypto_manager: CryptoManager,
        db_manager: DBManager,
        network_manager: NetworkManager
    ):
        """
        Initialize ChatManager.
        
        Args:
            identity: Local peer identity
            crypto_manager: CryptoManager instance for encryption
            db_manager: DBManager instance for database operations
            network_manager: NetworkManager instance for peer communication
        """
        self.identity = identity
        self.crypto = crypto_manager
        self.db = db_manager
        self.network = network_manager
    
    async def send_private_message(
        self,
        recipient_peer_id: str,
        content: str
    ) -> PrivateMessage:
        """
        Send an encrypted private message to a peer using sealed box encryption.
        
        The message content is encrypted with the recipient's X25519 public key,
        ensuring only the recipient can decrypt it. The encrypted message is
        stored locally and sent to the recipient peer if connected.
        
        Args:
            recipient_peer_id: Peer ID of the recipient
            content: Message content (1-10000 characters)
            
        Returns:
            PrivateMessage: Created private message object
            
        Raises:
            ChatManagerError: If message sending fails
            ValueError: If content is invalid
        """
        # Validate input
        if not content or len(content) < 1 or len(content) > 10000:
            raise ValueError("Message content must be 1-10000 characters")
        
        try:
            # Get recipient's public key from database
            peer_info = self.db.get_peer_info(recipient_peer_id)
            if not peer_info:
                raise ChatManagerError(f"Recipient peer {recipient_peer_id[:8]} not found")
            
            # Extract recipient's encryption public key
            # Note: peer_info.public_key contains the Ed25519 signing key
            # We need to get the X25519 encryption key from the peer connection or stored separately
            # For now, we'll assume we need to request it or have it stored
            
            # In a real implementation, we'd need to store both keys separately
            # For this implementation, we'll raise an error if we can't find the encryption key
            
            # Check if peer is connected to get their encryption key
            peer_connection_info = self.network.get_peer_info(recipient_peer_id)
            if not peer_connection_info:
                raise ChatManagerError(
                    f"Cannot send message: recipient {recipient_peer_id[:8]} not connected. "
                    "Encryption key not available."
                )
            
            # Get encryption public key from peer connection
            # This is available after handshake
            recipient_encryption_key = None
            if recipient_peer_id in self.network.peers:
                peer_conn = self.network.peers[recipient_peer_id]
                recipient_encryption_key = peer_conn.encryption_public_key
            
            if not recipient_encryption_key:
                raise ChatManagerError(
                    f"Cannot send message: recipient {recipient_peer_id[:8]} encryption key not available"
                )
            
            # Encrypt message content using sealed box
            plaintext = content.encode('utf-8')
            encrypted_content = self.crypto.encrypt_message(
                plaintext,
                recipient_encryption_key
            )
            
            # Generate unique message ID
            message_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            
            # Create private message object
            private_message = PrivateMessage(
                id=message_id,
                sender_peer_id=self.identity.peer_id,
                recipient_peer_id=recipient_peer_id,
                encrypted_content=encrypted_content,
                created_at=created_at,
                read_at=None
            )
            
            # Save to database
            self.db.save_private_message(private_message)
            
            logger.info(f"Created private message {message_id[:8]} to {recipient_peer_id[:8]}")
            
            # Send to recipient if connected
            if self.network.is_peer_connected(recipient_peer_id):
                await self._send_private_message_to_peer(
                    recipient_peer_id,
                    private_message
                )
            else:
                logger.warning(
                    f"Recipient {recipient_peer_id[:8]} not connected. "
                    "Message saved but not sent."
                )
            
            return private_message
            
        except Exception as e:
            logger.error(f"Failed to send private message: {e}")
            raise ChatManagerError(f"Send private message failed: {e}")
    
    def get_conversation(
        self,
        peer_id: str
    ) -> List[PrivateMessage]:
        """
        Retrieve all private messages in a conversation with a peer.
        
        Returns messages in both directions (sent and received) ordered by
        creation time. Encrypted messages are returned as-is; decryption
        should be done separately when displaying.
        
        Args:
            peer_id: Peer ID of the conversation partner
            
        Returns:
            List of PrivateMessage objects ordered by creation time
            
        Raises:
            ChatManagerError: If retrieval fails
        """
        try:
            messages = self.db.get_private_messages(
                self.identity.peer_id,
                peer_id
            )
            logger.debug(
                f"Retrieved {len(messages)} messages in conversation with {peer_id[:8]}"
            )
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get conversation with {peer_id[:8]}: {e}")
            raise ChatManagerError(f"Get conversation failed: {e}")
    
    def decrypt_message(self, message: PrivateMessage) -> str:
        """
        Decrypt a private message using the local identity's private key.
        
        Args:
            message: PrivateMessage to decrypt
            
        Returns:
            Decrypted message content as string
            
        Raises:
            ChatManagerError: If decryption fails
        """
        try:
            # Only decrypt messages sent to us
            if message.recipient_peer_id != self.identity.peer_id:
                raise ChatManagerError("Cannot decrypt message not addressed to us")
            
            # Decrypt using our encryption private key
            plaintext = self.crypto.decrypt_message(
                message.encrypted_content,
                self.identity.encryption_private_key
            )
            
            return plaintext.decode('utf-8')
            
        except DecryptionError as e:
            logger.error(f"Failed to decrypt message {message.id[:8]}: {e}")
            raise ChatManagerError(f"Decryption failed: {e}")
        except Exception as e:
            logger.error(f"Failed to decrypt message {message.id[:8]}: {e}")
            raise ChatManagerError(f"Decryption failed: {e}")
    
    def mark_as_read(self, message_id: str) -> None:
        """
        Mark a private message as read by updating the read timestamp.
        
        Args:
            message_id: Message identifier
            
        Raises:
            ChatManagerError: If update fails
        """
        try:
            # Get message from database
            # Note: DBManager doesn't have a get_message_by_id method
            # We'll need to implement this or work around it
            
            # For now, we'll use a workaround by getting all messages and finding the one we want
            # In a production system, we'd add a get_message_by_id method to DBManager
            
            # Get all conversations and find the message
            # This is inefficient but works for the MVP
            all_peers = self.db.get_all_peers()
            message_found = False
            
            for peer in all_peers:
                messages = self.db.get_private_messages(self.identity.peer_id, peer.peer_id)
                for msg in messages:
                    if msg.id == message_id:
                        # Update read timestamp
                        msg.read_at = datetime.utcnow()
                        # Save back to database
                        self.db.save_private_message(msg)
                        message_found = True
                        logger.info(f"Marked message {message_id[:8]} as read")
                        break
                if message_found:
                    break
            
            if not message_found:
                logger.warning(f"Message {message_id[:8]} not found")
            
        except Exception as e:
            logger.error(f"Failed to mark message {message_id[:8]} as read: {e}")
            raise ChatManagerError(f"Mark as read failed: {e}")
    
    async def _send_private_message_to_peer(
        self,
        recipient_peer_id: str,
        private_message: PrivateMessage
    ) -> None:
        """
        Send encrypted private message to recipient peer over the network.
        
        Args:
            recipient_peer_id: Peer ID of the recipient
            private_message: PrivateMessage object to send
        """
        try:
            # Create message for network transport
            message = Message(
                msg_type="PRIVATE_MESSAGE",
                payload={
                    "message_id": private_message.id,
                    "sender_peer_id": private_message.sender_peer_id,
                    "encrypted_content": private_message.encrypted_content.hex(),
                    "created_at": private_message.created_at.isoformat()
                }
            )
            
            # Send to recipient
            await self.network.send_message(recipient_peer_id, message)
            
            logger.info(
                f"Sent private message {private_message.id[:8]} to {recipient_peer_id[:8]}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to send private message to peer {recipient_peer_id[:8]}: {e}"
            )
            raise
    
    def get_unread_count(self, peer_id: str) -> int:
        """
        Get the count of unread messages from a specific peer.
        
        Args:
            peer_id: Peer ID to check
            
        Returns:
            Number of unread messages from the peer
            
        Raises:
            ChatManagerError: If retrieval fails
        """
        try:
            messages = self.get_conversation(peer_id)
            
            # Count messages from peer that are unread
            unread_count = sum(
                1 for msg in messages
                if msg.sender_peer_id == peer_id and msg.read_at is None
            )
            
            return unread_count
            
        except Exception as e:
            logger.error(f"Failed to get unread count for {peer_id[:8]}: {e}")
            raise ChatManagerError(f"Get unread count failed: {e}")
    
    def get_all_conversations(self) -> List[str]:
        """
        Get list of peer IDs with whom we have conversations.
        
        Returns:
            List of peer IDs
            
        Raises:
            ChatManagerError: If retrieval fails
        """
        try:
            # Get all peers we've exchanged messages with
            all_peers = self.db.get_all_peers()
            conversation_peers = []
            
            for peer in all_peers:
                messages = self.db.get_private_messages(
                    self.identity.peer_id,
                    peer.peer_id
                )
                if messages:
                    conversation_peers.append(peer.peer_id)
            
            return conversation_peers
            
        except Exception as e:
            logger.error(f"Failed to get all conversations: {e}")
            raise ChatManagerError(f"Get all conversations failed: {e}")
