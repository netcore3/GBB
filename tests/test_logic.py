"""
Tests for Application Logic Layer

Tests the BoardManager, ThreadManager, ChatManager, and ModerationManager.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from core.crypto_manager import CryptoManager
from core.db_manager import DBManager
from core.network_manager import NetworkManager
from logic.board_manager import BoardManager, BoardManagerError
from logic.thread_manager import ThreadManager, ThreadManagerError
from logic.chat_manager import ChatManager, ChatManagerError
from logic.moderation_manager import ModerationManager, ModerationManagerError
from models.database import PeerInfo


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def crypto_manager():
    """Create a CryptoManager instance."""
    return CryptoManager()


@pytest.fixture
def identity(crypto_manager):
    """Create a test identity."""
    return crypto_manager.generate_identity()


@pytest.fixture
def db_manager(temp_db):
    """Create and initialize a DBManager instance."""
    db = DBManager(temp_db)
    db.initialize_database()
    return db


@pytest.fixture
def network_manager(identity, crypto_manager):
    """Create a NetworkManager instance."""
    return NetworkManager(identity, crypto_manager, enable_mdns=False)


@pytest.fixture
def board_manager(identity, crypto_manager, db_manager, network_manager):
    """Create a BoardManager instance."""
    return BoardManager(identity, crypto_manager, db_manager, network_manager)


@pytest.fixture
def thread_manager(identity, crypto_manager, db_manager, network_manager):
    """Create a ThreadManager instance."""
    return ThreadManager(identity, crypto_manager, db_manager, network_manager)


@pytest.fixture
def chat_manager(identity, crypto_manager, db_manager, network_manager):
    """Create a ChatManager instance."""
    return ChatManager(identity, crypto_manager, db_manager, network_manager)


@pytest.fixture
def moderation_manager(identity, crypto_manager, db_manager, network_manager):
    """Create a ModerationManager instance."""
    return ModerationManager(identity, crypto_manager, db_manager, network_manager)


class TestBoardManager:
    """Tests for BoardManager."""
    
    def test_create_board(self, board_manager):
        """Test creating a board."""
        board = board_manager.create_board("Test Board", "A test board")
        
        assert board.name == "Test Board"
        assert board.description == "A test board"
        assert board.creator_peer_id == board_manager.identity.peer_id
        assert board.signature is not None
        assert len(board.id) == 36  # UUID length
    
    def test_create_board_invalid_name(self, board_manager):
        """Test creating a board with invalid name."""
        with pytest.raises(ValueError):
            board_manager.create_board("AB")  # Too short
        
        with pytest.raises(ValueError):
            board_manager.create_board("A" * 51)  # Too long
    
    def test_join_board(self, board_manager):
        """Test joining a board."""
        board = board_manager.create_board("Test Board", "A test board")
        
        # Should already be subscribed after creation
        assert board_manager.is_subscribed(board.id)
        
        # Unsubscribe and rejoin
        board_manager.subscribed_boards.remove(board.id)
        assert not board_manager.is_subscribed(board.id)
        
        board_manager.join_board(board.id)
        assert board_manager.is_subscribed(board.id)
    
    def test_get_all_boards(self, board_manager):
        """Test retrieving all boards."""
        board1 = board_manager.create_board("Board 1", "First board")
        board2 = board_manager.create_board("Board 2", "Second board")
        
        boards = board_manager.get_all_boards()
        assert len(boards) == 2
        assert any(b.id == board1.id for b in boards)
        assert any(b.id == board2.id for b in boards)
    
    def test_get_board_by_id(self, board_manager):
        """Test retrieving a board by ID."""
        board = board_manager.create_board("Test Board", "A test board")
        
        retrieved = board_manager.get_board_by_id(board.id)
        assert retrieved is not None
        assert retrieved.id == board.id
        assert retrieved.name == board.name


class TestThreadManager:
    """Tests for ThreadManager."""
    
    def test_create_thread(self, board_manager, thread_manager):
        """Test creating a thread."""
        board = board_manager.create_board("Test Board", "A test board")
        
        thread = thread_manager.create_thread(
            board.id,
            "Test Thread",
            "This is the first post"
        )
        
        assert thread.title == "Test Thread"
        assert thread.board_id == board.id
        assert thread.creator_peer_id == thread_manager.identity.peer_id
        assert thread.signature is not None
    
    def test_create_thread_invalid_title(self, board_manager, thread_manager):
        """Test creating a thread with invalid title."""
        board = board_manager.create_board("Test Board", "A test board")
        
        with pytest.raises(ValueError):
            thread_manager.create_thread(board.id, "AB", "Content")  # Too short
        
        with pytest.raises(ValueError):
            thread_manager.create_thread(board.id, "A" * 201, "Content")  # Too long
    
    def test_add_post_to_thread(self, board_manager, thread_manager):
        """Test adding a post to a thread."""
        board = board_manager.create_board("Test Board", "A test board")
        thread = thread_manager.create_thread(
            board.id,
            "Test Thread",
            "First post"
        )
        
        post = thread_manager.add_post_to_thread(
            thread.id,
            "Second post content"
        )
        
        assert post.content == "Second post content"
        assert post.thread_id == thread.id
        assert post.author_peer_id == thread_manager.identity.peer_id
        assert post.signature is not None
        assert post.sequence_number > 0
    
    def test_get_thread_posts(self, board_manager, thread_manager):
        """Test retrieving posts for a thread."""
        board = board_manager.create_board("Test Board", "A test board")
        thread = thread_manager.create_thread(
            board.id,
            "Test Thread",
            "First post"
        )
        
        # Add more posts
        thread_manager.add_post_to_thread(thread.id, "Second post")
        thread_manager.add_post_to_thread(thread.id, "Third post")
        
        posts = thread_manager.get_thread_posts(thread.id)
        assert len(posts) == 3  # Initial post + 2 additional
        assert posts[0].content == "First post"
        assert posts[1].content == "Second post"
        assert posts[2].content == "Third post"


class TestChatManager:
    """Tests for ChatManager."""
    
    def test_get_conversation_empty(self, chat_manager):
        """Test getting an empty conversation."""
        messages = chat_manager.get_conversation("peer123")
        assert len(messages) == 0
    
    def test_get_unread_count(self, chat_manager):
        """Test getting unread message count."""
        count = chat_manager.get_unread_count("peer123")
        assert count == 0
    
    def test_get_all_conversations(self, chat_manager):
        """Test getting all conversations."""
        conversations = chat_manager.get_all_conversations()
        assert len(conversations) == 0


class TestModerationManager:
    """Tests for ModerationManager."""
    
    def test_trust_peer(self, moderation_manager, db_manager):
        """Test trusting a peer."""
        peer_id = "test_peer_123"
        
        # Trust the peer
        moderation_manager.trust_peer(peer_id)
        
        # Verify trust status
        assert moderation_manager.is_peer_trusted(peer_id)
        assert not moderation_manager.is_peer_banned(peer_id)
    
    def test_ban_peer(self, moderation_manager):
        """Test banning a peer."""
        peer_id = "test_peer_456"
        
        # Ban the peer
        action = moderation_manager.ban_peer(peer_id, "Spam")
        
        assert action.action_type == "ban"
        assert action.target_id == peer_id
        assert action.reason == "Spam"
        assert action.moderator_peer_id == moderation_manager.identity.peer_id
        
        # Verify ban status
        assert moderation_manager.is_peer_banned(peer_id)
    
    def test_delete_post(self, board_manager, thread_manager, moderation_manager):
        """Test deleting a post."""
        board = board_manager.create_board("Test Board", "A test board")
        thread = thread_manager.create_thread(
            board.id,
            "Test Thread",
            "First post"
        )
        
        posts = thread_manager.get_thread_posts(thread.id)
        post_id = posts[0].id
        
        # Delete the post
        action = moderation_manager.delete_post(post_id, "Inappropriate")
        
        assert action.action_type == "delete"
        assert action.target_id == post_id
        assert action.reason == "Inappropriate"
        
        # Verify delete status
        assert moderation_manager.is_post_deleted(post_id)
    
    def test_untrust_peer(self, moderation_manager):
        """Test untrusting a peer."""
        peer_id = "test_peer_789"
        
        # Trust then untrust
        moderation_manager.trust_peer(peer_id)
        assert moderation_manager.is_peer_trusted(peer_id)
        
        moderation_manager.untrust_peer(peer_id)
        assert not moderation_manager.is_peer_trusted(peer_id)
    
    def test_unban_peer(self, moderation_manager):
        """Test unbanning a peer."""
        peer_id = "test_peer_101"
        
        # Ban then unban
        moderation_manager.ban_peer(peer_id)
        assert moderation_manager.is_peer_banned(peer_id)
        
        moderation_manager.unban_peer(peer_id)
        assert not moderation_manager.is_peer_banned(peer_id)
    
    def test_get_trusted_peers(self, moderation_manager):
        """Test getting list of trusted peers."""
        # Trust some peers
        moderation_manager.trust_peer("peer1")
        moderation_manager.trust_peer("peer2")
        
        trusted = moderation_manager.get_trusted_peers()
        assert len(trusted) == 2
        assert any(p.peer_id == "peer1" for p in trusted)
        assert any(p.peer_id == "peer2" for p in trusted)
