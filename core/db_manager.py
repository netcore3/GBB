"""
Database manager for the P2P Encrypted BBS Application.

This module provides the DBManager class which handles all database operations
including initialization, CRUD operations, and transaction management.
"""

from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, OperationalError

from models.database import (
    Base,
    Profile,
    Board,
    Thread,
    Post,
    PrivateMessage,
    Attachment,
    PeerInfo,
    ModerationAction,
)


class DBManager:
    """
    Manages database operations for the BBS application.
    
    Provides methods for initializing the database, saving and retrieving
    data, and managing transactions with automatic rollback on errors.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.engine = None
        self.SessionLocal = None
    
    def initialize_database(self):
        """
        Initialize the database by creating the schema if it doesn't exist.
        
        Creates all tables defined in the models and sets up the session factory.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with foreign key enforcement
        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            db_url, 
            echo=False,
            connect_args={"check_same_thread": False}
        )
        
        # Enable foreign key constraints for SQLite
        from sqlalchemy import event
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        # Create all tables
        Base.metadata.create_all(self.engine)
        # Lightweight migration: add new columns to boards table if missing
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            cur.execute("PRAGMA table_info('boards')")
            cols = [r[1] for r in cur.fetchall()]
            if 'welcome_message' not in cols:
                cur.execute("ALTER TABLE boards ADD COLUMN welcome_message TEXT")
            if 'image_path' not in cols:
                cur.execute("ALTER TABLE boards ADD COLUMN image_path TEXT")
            if 'is_private' not in cols:
                cur.execute("ALTER TABLE boards ADD COLUMN is_private INTEGER DEFAULT 0 NOT NULL")
            
            # Add display_name to peers table if missing
            cur.execute("PRAGMA table_info('peers')")
            peer_cols = [r[1] for r in cur.fetchall()]
            if 'display_name' not in peer_cols:
                cur.execute("ALTER TABLE peers ADD COLUMN display_name TEXT")
            
            conn.commit()
            conn.close()
        except Exception:
            # Non-fatal if migration fails; log via standard logging where DBManager is used
            pass
        
        # Create session factory with expire_on_commit=False to avoid detached instance errors
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------
    # Profile operations
    # ------------------------------------------------------------------

    def get_all_profiles(self) -> List[Profile]:
        """Return all local profiles ordered by last_used desc then created_at."""
        with self.get_session() as session:
            profiles = (
                session.query(Profile)
                .order_by(Profile.last_used.desc(), Profile.created_at.desc())
                .all()
            )
            session.expunge_all()
            return profiles

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Fetch a single profile by its ID."""
        with self.get_session() as session:
            profile = session.query(Profile).filter(Profile.id == profile_id).first()
            if profile:
                session.expunge(profile)
            return profile

    def get_last_used_profile(self) -> Optional[Profile]:
        """Return the most recently used profile, if any."""
        with self.get_session() as session:
            profile = (
                session.query(Profile)
                .order_by(Profile.last_used.desc())
                .first()
            )
            if profile:
                session.expunge(profile)
            return profile

    def create_profile(
        self,
        profile_id: str,
        display_name: str,
        avatar_path: Optional[str] = None,
        shared_folder: Optional[str] = None,
        peer_id: Optional[str] = None,
        keystore_path: Optional[str] = None,
    ) -> Profile:
        """Create and persist a new profile and return the detached instance."""
        with self.get_session() as session:
            profile = Profile(
                id=profile_id,
                display_name=display_name,
                avatar_path=avatar_path,
                shared_folder=shared_folder,
                peer_id=peer_id,
                keystore_path=keystore_path,
            )
            session.add(profile)
            session.flush()
            session.expunge(profile)
            return profile

    def update_profile(self, profile: Profile) -> None:
        """Persist changes to an existing profile.

        The given instance may be detached; it will be merged inside a
        transaction. Callers should update ``profile.last_used`` themselves
        when appropriate.
        """
        with self.get_session() as session:
            session.merge(profile)
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions with automatic rollback on error.
        
        Yields:
            Session: SQLAlchemy session object
            
        Example:
            with db_manager.get_session() as session:
                session.add(board)
                session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # Board operations
    
    def save_board(self, board: Board) -> None:
        """
        Save a board to the database.
        
        Args:
            board: Board object to save
            
        Raises:
            IntegrityError: If board with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(board)

    def update_board(self, board: Board) -> None:
        """
        Update an existing board in the database. Uses merge to handle detached instances.

        Args:
            board: Board object with updated fields
        """
        with self.get_session() as session:
            session.merge(board)
    
    def get_all_boards(self) -> List[Board]:
        """
        Retrieve all boards from the database.
        
        Returns:
            List of Board objects
        """
        with self.get_session() as session:
            boards = session.query(Board).all()
            # Detach from session to avoid lazy loading issues
            session.expunge_all()
            return boards
    
    def get_board_by_id(self, board_id: str) -> Optional[Board]:
        """
        Retrieve a board by its ID.
        
        Args:
            board_id: Unique board identifier
            
        Returns:
            Board object if found, None otherwise
        """
        with self.get_session() as session:
            board = session.query(Board).filter(Board.id == board_id).first()
            if board:
                session.expunge(board)
            return board
    
    def delete_board(self, board_id: str) -> None:
        """
        Delete a board from the database by its ID.
        
        Args:
            board_id: Unique board identifier
            
        Raises:
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            board = session.query(Board).filter(Board.id == board_id).first()
            if board:
                session.delete(board)
    
    # Thread operations
    
    def save_thread(self, thread: Thread) -> None:
        """
        Save a thread to the database.
        
        Args:
            thread: Thread object to save
            
        Raises:
            IntegrityError: If thread with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(thread)
    
    def get_threads_for_board(self, board_id: str) -> List[Thread]:
        """
        Retrieve all threads for a specific board.
        
        Args:
            board_id: Board identifier
            
        Returns:
            List of Thread objects ordered by last activity (most recent first)
        """
        with self.get_session() as session:
            threads = session.query(Thread).filter(
                Thread.board_id == board_id
            ).order_by(Thread.last_activity.desc()).all()
            session.expunge_all()
            return threads
    
    # Post operations
    
    def save_post(self, post: Post) -> None:
        """
        Save a post to the database.
        
        Args:
            post: Post object to save
            
        Raises:
            IntegrityError: If post with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(post)
    
    def get_posts_for_thread(self, thread_id: str) -> List[Post]:
        """
        Retrieve all posts for a specific thread.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            List of Post objects ordered by creation time (oldest first)
        """
        with self.get_session() as session:
            posts = session.query(Post).filter(
                Post.thread_id == thread_id
            ).order_by(Post.created_at.asc()).all()
            session.expunge_all()
            return posts
    
    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """
        Retrieve a post by its ID.
        
        Args:
            post_id: Unique post identifier
            
        Returns:
            Post object if found, None otherwise
        """
        with self.get_session() as session:
            post = session.query(Post).filter(Post.id == post_id).first()
            if post:
                session.expunge(post)
            return post
    
    # Private message operations
    
    def save_private_message(self, message: PrivateMessage) -> None:
        """
        Save a private message to the database.
        
        Args:
            message: PrivateMessage object to save
            
        Raises:
            IntegrityError: If message with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(message)
    
    def get_private_messages(self, peer_id: str, other_peer_id: str) -> List[PrivateMessage]:
        """
        Retrieve private messages between two peers.
        
        Args:
            peer_id: Current user's peer ID
            other_peer_id: Other peer's ID
            
        Returns:
            List of PrivateMessage objects ordered by creation time
        """
        with self.get_session() as session:
            messages = session.query(PrivateMessage).filter(
                ((PrivateMessage.sender_peer_id == peer_id) & 
                 (PrivateMessage.recipient_peer_id == other_peer_id)) |
                ((PrivateMessage.sender_peer_id == other_peer_id) & 
                 (PrivateMessage.recipient_peer_id == peer_id))
            ).order_by(PrivateMessage.created_at.asc()).all()
            session.expunge_all()
            return messages
    
    # Peer operations
    
    def save_peer_info(self, peer: PeerInfo) -> None:
        """
        Save or update peer information.
        
        Args:
            peer: PeerInfo object to save
            
        Raises:
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            # Use merge to handle both insert and update
            session.merge(peer)
    
    def get_peer_info(self, peer_id: str) -> Optional[PeerInfo]:
        """
        Retrieve peer information by peer ID.
        
        Args:
            peer_id: Peer identifier
            
        Returns:
            PeerInfo object if found, None otherwise
        """
        with self.get_session() as session:
            peer = session.query(PeerInfo).filter(PeerInfo.peer_id == peer_id).first()
            if peer:
                session.expunge(peer)
            return peer
    
    def get_trusted_peers(self) -> List[PeerInfo]:
        """
        Retrieve all trusted peers.
        
        Returns:
            List of PeerInfo objects marked as trusted
        """
        with self.get_session() as session:
            peers = session.query(PeerInfo).filter(PeerInfo.is_trusted == True).all()
            session.expunge_all()
            return peers
    
    def get_all_peers(self) -> List[PeerInfo]:
        """
        Retrieve all known peers.
        
        Returns:
            List of all PeerInfo objects
        """
        with self.get_session() as session:
            peers = session.query(PeerInfo).all()
            session.expunge_all()
            return peers
    
    # Moderation operations
    
    def save_moderation_action(self, action: ModerationAction) -> None:
        """
        Save a moderation action to the database.
        
        Args:
            action: ModerationAction object to save
            
        Raises:
            IntegrityError: If action with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(action)
    
    def get_moderation_actions_for_target(self, target_id: str) -> List[ModerationAction]:
        """
        Retrieve all moderation actions for a specific target.
        
        Args:
            target_id: Target post ID or peer ID
            
        Returns:
            List of ModerationAction objects
        """
        with self.get_session() as session:
            actions = session.query(ModerationAction).filter(
                ModerationAction.target_id == target_id
            ).order_by(ModerationAction.created_at.desc()).all()
            session.expunge_all()
            return actions
    
    # Attachment operations
    
    def save_attachment(self, attachment: Attachment) -> None:
        """
        Save an attachment to the database.
        
        Args:
            attachment: Attachment object to save
            
        Raises:
            IntegrityError: If attachment with same ID already exists
            OperationalError: If database operation fails
        """
        with self.get_session() as session:
            session.add(attachment)
    
    def get_attachments_for_post(self, post_id: str) -> List[Attachment]:
        """
        Retrieve all attachments for a specific post.
        
        Args:
            post_id: Post identifier
            
        Returns:
            List of Attachment objects
        """
        with self.get_session() as session:
            attachments = session.query(Attachment).filter(
                Attachment.post_id == post_id
            ).all()
            session.expunge_all()
            return attachments
    
    def get_attachments_for_message(self, message_id: str) -> List[Attachment]:
        """
        Retrieve all attachments for a specific private message.
        
        Args:
            message_id: Private message identifier
            
        Returns:
            List of Attachment objects
        """
        with self.get_session() as session:
            attachments = session.query(Attachment).filter(
                Attachment.message_id == message_id
            ).all()
            session.expunge_all()
            return attachments
    
    def get_attachment_by_id(self, attachment_id: str) -> Optional[Attachment]:
        """
        Retrieve an attachment by its ID.
        
        Args:
            attachment_id: Unique attachment identifier
            
        Returns:
            Attachment object if found, None otherwise
        """
        with self.get_session() as session:
            attachment = session.query(Attachment).filter(
                Attachment.id == attachment_id
            ).first()
            if attachment:
                session.expunge(attachment)
            return attachment
