"""
SQLAlchemy database models for the P2P Encrypted BBS Application.

This module defines all database models including Board, Thread, Post,
PrivateMessage, Attachment, PeerInfo, and ModerationAction.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, LargeBinary, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Profile(Base):
    """Represents a local user profile on this device.

    Profiles are *not* network identities; they are local personas that can
    have their own display name, avatar, and shared folder. A single peer
    identity/keystore can be associated with one or more profiles via the
    ``peer_id`` and optional ``keystore_path`` fields.
    """

    __tablename__ = "profiles"

    id = Column(String, primary_key=True)  # UUID
    display_name = Column(String, nullable=False)
    avatar_path = Column(String, nullable=True)
    shared_folder = Column(String, nullable=True)
    peer_id = Column(String, nullable=True)  # linked crypto identity (optional)
    keystore_path = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=False, default=datetime.utcnow)


class Board(Base):
    """
    Represents a discussion board.

    A board is a container for threads and is identified by a unique ID.
    Each board is created by a peer and signed to ensure authenticity.
    Boards can be public (visible to all peers) or private (invite-only).
    """
    __tablename__ = 'boards'

    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)
    description = Column(String)
    creator_peer_id = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    signature = Column(LargeBinary, nullable=False)
    welcome_message = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)

    # Relationships
    threads = relationship("Thread", back_populates="board", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Board(id={self.id}, name={self.name})>"


class Thread(Base):
    """
    Represents a discussion thread within a board.
    
    A thread contains multiple posts and tracks the last activity timestamp
    for sorting and display purposes.
    """
    __tablename__ = 'threads'
    
    id = Column(String, primary_key=True)  # UUID
    board_id = Column(String, ForeignKey('boards.id'), nullable=False)
    title = Column(String, nullable=False)
    creator_peer_id = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity = Column(DateTime, nullable=False, default=datetime.utcnow)
    signature = Column(LargeBinary, nullable=False)
    
    # Relationships
    board = relationship("Board", back_populates="threads")
    posts = relationship("Post", back_populates="thread", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Thread(id={self.id}, title={self.title})>"


class Post(Base):
    """
    Represents a single post within a thread.
    
    Posts are signed by their authors and include a sequence number for
    vector clock synchronization. Posts can optionally reply to other posts.
    """
    __tablename__ = 'posts'
    
    id = Column(String, primary_key=True)  # UUID
    thread_id = Column(String, ForeignKey('threads.id'), nullable=False)
    author_peer_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sequence_number = Column(Integer, nullable=False)  # For vector clock
    signature = Column(LargeBinary, nullable=False)
    parent_post_id = Column(String, ForeignKey('posts.id'), nullable=True)  # For replies
    
    # Relationships
    thread = relationship("Thread", back_populates="posts")
    attachments = relationship("Attachment", back_populates="post", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Post(id={self.id}, author={self.author_peer_id})>"


class PrivateMessage(Base):
    """
    Represents an encrypted private message between two peers.
    
    The content is encrypted using sealed box encryption with the recipient's
    public key, ensuring only the recipient can decrypt it.
    """
    __tablename__ = 'private_messages'
    
    id = Column(String, primary_key=True)  # UUID
    sender_peer_id = Column(String, nullable=False)
    recipient_peer_id = Column(String, nullable=False)
    encrypted_content = Column(LargeBinary, nullable=False)  # Sealed box encrypted
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<PrivateMessage(id={self.id}, from={self.sender_peer_id}, to={self.recipient_peer_id})>"


class Attachment(Base):
    """
    Represents a file attachment for a post or private message.
    
    Files are encrypted and stored with their hash for integrity verification.
    Attachments can be associated with either posts or private messages.
    """
    __tablename__ = 'attachments'
    
    id = Column(String, primary_key=True)  # UUID
    post_id = Column(String, ForeignKey('posts.id'), nullable=True)
    message_id = Column(String, ForeignKey('private_messages.id'), nullable=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)  # SHA-256
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    encrypted_data = Column(LargeBinary, nullable=False)
    
    # Relationships
    post = relationship("Post", back_populates="attachments")
    
    def __repr__(self):
        return f"<Attachment(id={self.id}, filename={self.filename})>"


class PeerInfo(Base):
    """
    Represents information about a discovered peer.
    
    Stores peer metadata including connection information, trust status,
    and reputation score for moderation purposes.
    """
    __tablename__ = 'peers'
    
    peer_id = Column(String, primary_key=True)
    public_key = Column(LargeBinary, nullable=False)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    address = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    is_trusted = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    reputation_score = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<PeerInfo(peer_id={self.peer_id}, trusted={self.is_trusted})>"


class ModerationAction(Base):
    """
    Represents a moderation action taken by a moderator.
    
    Moderation actions are signed and can delete posts, ban peers, or
    establish trust relationships. Actions are verified before application.
    """
    __tablename__ = 'moderation_actions'
    
    id = Column(String, primary_key=True)  # UUID
    moderator_peer_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # 'delete', 'ban', 'trust'
    target_id = Column(String, nullable=False)  # post_id or peer_id
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    signature = Column(LargeBinary, nullable=False)
    
    def __repr__(self):
        return f"<ModerationAction(id={self.id}, type={self.action_type}, target={self.target_id})>"
