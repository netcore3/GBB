"""
Unit tests for database operations.

Tests CRUD operations for all models, foreign key constraints,
and transaction rollback behavior.
"""

import pytest
import uuid
from pathlib import Path
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from core.db_manager import DBManager
from models.database import Board, Thread, Post, PrivateMessage, Attachment, PeerInfo, ModerationAction


@pytest.fixture
def db_manager(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    manager = DBManager(db_path)
    manager.initialize_database()
    return manager


@pytest.fixture
def sample_board():
    """Create a sample board for testing."""
    board_id = str(uuid.uuid4())
    board = Board(
        id=board_id,
        name="Test Board",
        description="A test board",
        creator_peer_id="peer_123",
        created_at=datetime.now(),
        signature=b"test_signature"
    )
    # Store ID as attribute for easy access
    board._test_id = board_id
    return board


@pytest.fixture
def sample_thread(sample_board):
    """Create a sample thread for testing."""
    thread_id = str(uuid.uuid4())
    # Use stored ID to avoid accessing detached instance
    board_id = sample_board._test_id if hasattr(sample_board, '_test_id') else sample_board.id
    thread = Thread(
        id=thread_id,
        board_id=board_id,
        title="Test Thread",
        creator_peer_id="peer_123",
        created_at=datetime.now(),
        last_activity=datetime.now(),
        signature=b"test_signature"
    )
    thread._test_id = thread_id
    thread._test_board_id = board_id
    return thread


@pytest.fixture
def sample_post(sample_thread):
    """Create a sample post for testing."""
    post_id = str(uuid.uuid4())
    thread_id = sample_thread._test_id if hasattr(sample_thread, '_test_id') else sample_thread.id
    post = Post(
        id=post_id,
        thread_id=thread_id,
        author_peer_id="peer_123",
        content="Test post content",
        created_at=datetime.now(),
        sequence_number=1,
        signature=b"test_signature"
    )
    post._test_id = post_id
    return post


class TestBoardOperations:
    """Test CRUD operations for Board model."""
    
    def test_save_board(self, db_manager, sample_board):
        """Test saving a board to the database."""
        board_id = sample_board._test_id
        db_manager.save_board(sample_board)
        
        retrieved = db_manager.get_board_by_id(board_id)
        assert retrieved is not None
        assert retrieved.name == "Test Board"
        assert retrieved.description == "A test board"
    
    def test_get_all_boards(self, db_manager):
        """Test retrieving all boards."""
        board1 = Board(
            id=str(uuid.uuid4()),
            name="Board 1",
            description="First board",
            creator_peer_id="peer_1",
            signature=b"sig1"
        )
        board2 = Board(
            id=str(uuid.uuid4()),
            name="Board 2",
            description="Second board",
            creator_peer_id="peer_2",
            signature=b"sig2"
        )
        
        db_manager.save_board(board1)
        db_manager.save_board(board2)
        
        boards = db_manager.get_all_boards()
        assert len(boards) == 2
        assert any(b.name == "Board 1" for b in boards)
        assert any(b.name == "Board 2" for b in boards)
    
    def test_duplicate_board_id(self, db_manager, sample_board):
        """Test that duplicate board IDs raise IntegrityError."""
        board_id = sample_board._test_id
        db_manager.save_board(sample_board)
        
        duplicate = Board(
            id=board_id,
            name="Duplicate",
            description="Should fail",
            creator_peer_id="peer_456",
            signature=b"sig"
        )
        
        with pytest.raises(IntegrityError):
            db_manager.save_board(duplicate)


class TestThreadOperations:
    """Test CRUD operations for Thread model."""
    
    def test_save_thread(self, db_manager, sample_board, sample_thread):
        """Test saving a thread to the database."""
        board_id = sample_board._test_id
        db_manager.save_board(sample_board)
        db_manager.save_thread(sample_thread)
        
        threads = db_manager.get_threads_for_board(board_id)
        assert len(threads) == 1
        assert threads[0].title == "Test Thread"
    
    def test_get_threads_ordered_by_activity(self, db_manager, sample_board):
        """Test that threads are ordered by last activity."""
        board_id = sample_board._test_id
        db_manager.save_board(sample_board)
        
        thread1 = Thread(
            id=str(uuid.uuid4()),
            board_id=board_id,
            title="Old Thread",
            creator_peer_id="peer_1",
            created_at=datetime(2023, 1, 1),
            last_activity=datetime(2023, 1, 1),
            signature=b"sig1"
        )
        thread2 = Thread(
            id=str(uuid.uuid4()),
            board_id=board_id,
            title="New Thread",
            creator_peer_id="peer_2",
            created_at=datetime(2023, 1, 2),
            last_activity=datetime(2023, 1, 2),
            signature=b"sig2"
        )
        
        db_manager.save_thread(thread1)
        db_manager.save_thread(thread2)
        
        threads = db_manager.get_threads_for_board(board_id)
        assert threads[0].title == "New Thread"
        assert threads[1].title == "Old Thread"


class TestPostOperations:
    """Test CRUD operations for Post model."""
    
    def test_save_post(self, db_manager, sample_board, sample_thread, sample_post):
        """Test saving a post to the database."""
        thread_id = sample_thread._test_id
        db_manager.save_board(sample_board)
        db_manager.save_thread(sample_thread)
        db_manager.save_post(sample_post)
        
        posts = db_manager.get_posts_for_thread(thread_id)
        assert len(posts) == 1
        assert posts[0].content == "Test post content"
    
    def test_get_posts_ordered_by_time(self, db_manager, sample_board, sample_thread):
        """Test that posts are ordered by creation time."""
        thread_id = sample_thread._test_id
        db_manager.save_board(sample_board)
        db_manager.save_thread(sample_thread)
        
        post1 = Post(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            author_peer_id="peer_1",
            content="First post",
            created_at=datetime(2023, 1, 1, 10, 0),
            sequence_number=1,
            signature=b"sig1"
        )
        post2 = Post(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            author_peer_id="peer_2",
            content="Second post",
            created_at=datetime(2023, 1, 1, 11, 0),
            sequence_number=2,
            signature=b"sig2"
        )
        
        db_manager.save_post(post1)
        db_manager.save_post(post2)
        
        posts = db_manager.get_posts_for_thread(thread_id)
        assert posts[0].content == "First post"
        assert posts[1].content == "Second post"
    
    def test_post_with_parent(self, db_manager, sample_board, sample_thread):
        """Test creating a reply post with parent_post_id."""
        thread_id = sample_thread._test_id
        db_manager.save_board(sample_board)
        db_manager.save_thread(sample_thread)
        
        parent_post_id = str(uuid.uuid4())
        parent_post = Post(
            id=parent_post_id,
            thread_id=thread_id,
            author_peer_id="peer_1",
            content="Parent post",
            created_at=datetime.now(),
            sequence_number=1,
            signature=b"sig1"
        )
        db_manager.save_post(parent_post)
        
        reply_post_id = str(uuid.uuid4())
        reply_post = Post(
            id=reply_post_id,
            thread_id=thread_id,
            author_peer_id="peer_2",
            content="Reply post",
            created_at=datetime.now(),
            sequence_number=2,
            signature=b"sig2",
            parent_post_id=parent_post_id
        )
        db_manager.save_post(reply_post)
        
        retrieved = db_manager.get_post_by_id(reply_post_id)
        assert retrieved.parent_post_id == parent_post_id


class TestPrivateMessageOperations:
    """Test CRUD operations for PrivateMessage model."""
    
    def test_save_private_message(self, db_manager):
        """Test saving a private message."""
        message = PrivateMessage(
            id=str(uuid.uuid4()),
            sender_peer_id="peer_1",
            recipient_peer_id="peer_2",
            encrypted_content=b"encrypted_data",
            created_at=datetime.now()
        )
        
        db_manager.save_private_message(message)
        
        messages = db_manager.get_private_messages("peer_1", "peer_2")
        assert len(messages) == 1
        assert messages[0].sender_peer_id == "peer_1"
    
    def test_get_conversation_bidirectional(self, db_manager):
        """Test retrieving messages in both directions."""
        msg1 = PrivateMessage(
            id=str(uuid.uuid4()),
            sender_peer_id="peer_1",
            recipient_peer_id="peer_2",
            encrypted_content=b"msg1",
            created_at=datetime(2023, 1, 1, 10, 0)
        )
        msg2 = PrivateMessage(
            id=str(uuid.uuid4()),
            sender_peer_id="peer_2",
            recipient_peer_id="peer_1",
            encrypted_content=b"msg2",
            created_at=datetime(2023, 1, 1, 11, 0)
        )
        
        db_manager.save_private_message(msg1)
        db_manager.save_private_message(msg2)
        
        messages = db_manager.get_private_messages("peer_1", "peer_2")
        assert len(messages) == 2


class TestPeerOperations:
    """Test CRUD operations for PeerInfo model."""
    
    def test_save_peer_info(self, db_manager):
        """Test saving peer information."""
        peer = PeerInfo(
            peer_id="peer_123",
            public_key=b"public_key_data",
            last_seen=datetime.now(),
            address="192.168.1.100",
            port=9000,
            is_trusted=False,
            is_banned=False,
            reputation_score=0
        )
        
        db_manager.save_peer_info(peer)
        
        retrieved = db_manager.get_peer_info("peer_123")
        assert retrieved is not None
        assert retrieved.address == "192.168.1.100"
    
    def test_update_peer_info(self, db_manager):
        """Test updating existing peer information."""
        peer = PeerInfo(
            peer_id="peer_123",
            public_key=b"public_key_data",
            last_seen=datetime.now(),
            is_trusted=False
        )
        db_manager.save_peer_info(peer)
        
        # Update peer
        peer.is_trusted = True
        peer.reputation_score = 10
        db_manager.save_peer_info(peer)
        
        retrieved = db_manager.get_peer_info("peer_123")
        assert retrieved.is_trusted is True
        assert retrieved.reputation_score == 10
    
    def test_get_trusted_peers(self, db_manager):
        """Test retrieving only trusted peers."""
        peer1 = PeerInfo(
            peer_id="peer_1",
            public_key=b"key1",
            last_seen=datetime.utcnow(),
            is_trusted=True
        )
        peer2 = PeerInfo(
            peer_id="peer_2",
            public_key=b"key2",
            last_seen=datetime.utcnow(),
            is_trusted=False
        )
        
        db_manager.save_peer_info(peer1)
        db_manager.save_peer_info(peer2)
        
        trusted = db_manager.get_trusted_peers()
        assert len(trusted) == 1
        assert trusted[0].peer_id == "peer_1"


class TestModerationOperations:
    """Test CRUD operations for ModerationAction model."""
    
    def test_save_moderation_action(self, db_manager):
        """Test saving a moderation action."""
        action = ModerationAction(
            id=str(uuid.uuid4()),
            moderator_peer_id="mod_123",
            action_type="delete",
            target_id="post_456",
            reason="Spam",
            created_at=datetime.utcnow(),
            signature=b"mod_signature"
        )
        
        db_manager.save_moderation_action(action)
        
        actions = db_manager.get_moderation_actions_for_target("post_456")
        assert len(actions) == 1
        assert actions[0].action_type == "delete"


class TestForeignKeyConstraints:
    """Test foreign key relationships and constraints."""
    
    def test_thread_requires_valid_board(self, db_manager):
        """Test that thread requires existing board."""
        thread = Thread(
            id=str(uuid.uuid4()),
            board_id="nonexistent_board",
            title="Test",
            creator_peer_id="peer_1",
            signature=b"sig"
        )
        
        with pytest.raises(IntegrityError):
            db_manager.save_thread(thread)
    
    def test_post_requires_valid_thread(self, db_manager):
        """Test that post requires existing thread."""
        post = Post(
            id=str(uuid.uuid4()),
            thread_id="nonexistent_thread",
            author_peer_id="peer_1",
            content="Test",
            sequence_number=1,
            signature=b"sig"
        )
        
        with pytest.raises(IntegrityError):
            db_manager.save_post(post)


class TestTransactionRollback:
    """Test transaction management and rollback behavior."""
    
    def test_rollback_on_error(self, db_manager, sample_board):
        """Test that failed transactions are rolled back."""
        db_manager.save_board(sample_board)
        
        # Try to save duplicate board (should fail)
        duplicate = Board(
            id=sample_board.id,
            name="Duplicate",
            description="Should fail",
            creator_peer_id="peer_456",
            signature=b"sig"
        )
        
        try:
            db_manager.save_board(duplicate)
        except IntegrityError:
            pass
        
        # Verify original board is still intact
        boards = db_manager.get_all_boards()
        assert len(boards) == 1
        assert boards[0].name == sample_board.name
