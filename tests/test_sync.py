"""
Tests for synchronization components (VectorClock and SyncManager).
"""

import pytest
import asyncio
from cryptography.hazmat.primitives import serialization
from core.vector_clock import VectorClock, ClockComparison


class TestVectorClock:
    """Tests for VectorClock class."""
    
    def test_initialization(self):
        """Test vector clock initialization."""
        # Empty clock
        clock = VectorClock()
        assert clock.clocks == {}
        
        # Clock with peer_id
        clock = VectorClock("peer1")
        assert clock.clocks == {"peer1": 0}
    
    def test_increment(self):
        """Test incrementing sequence numbers."""
        clock = VectorClock()
        
        # Increment new peer
        clock.increment("peer1")
        assert clock.get("peer1") == 1
        
        # Increment existing peer
        clock.increment("peer1")
        assert clock.get("peer1") == 2
        
        # Increment different peer
        clock.increment("peer2")
        assert clock.get("peer2") == 1
        assert clock.get("peer1") == 2
    
    def test_merge(self):
        """Test merging two vector clocks."""
        clock1 = VectorClock()
        clock1.set("peer1", 5)
        clock1.set("peer2", 3)
        
        clock2 = VectorClock()
        clock2.set("peer1", 3)
        clock2.set("peer2", 7)
        clock2.set("peer3", 2)
        
        # Merge clock2 into clock1
        clock1.merge(clock2)
        
        # Should take maximum for each peer
        assert clock1.get("peer1") == 5  # max(5, 3)
        assert clock1.get("peer2") == 7  # max(3, 7)
        assert clock1.get("peer3") == 2  # new peer
    
    def test_compare_equal(self):
        """Test comparing equal clocks."""
        clock1 = VectorClock()
        clock1.set("peer1", 5)
        clock1.set("peer2", 3)
        
        clock2 = VectorClock()
        clock2.set("peer1", 5)
        clock2.set("peer2", 3)
        
        assert clock1.compare(clock2) == ClockComparison.EQUAL
        assert clock2.compare(clock1) == ClockComparison.EQUAL
    
    def test_compare_before(self):
        """Test comparing when one clock is before another."""
        clock1 = VectorClock()
        clock1.set("peer1", 3)
        clock1.set("peer2", 2)
        
        clock2 = VectorClock()
        clock2.set("peer1", 5)
        clock2.set("peer2", 4)
        
        assert clock1.compare(clock2) == ClockComparison.BEFORE
        assert clock2.compare(clock1) == ClockComparison.AFTER
    
    def test_compare_concurrent(self):
        """Test comparing concurrent clocks."""
        clock1 = VectorClock()
        clock1.set("peer1", 5)
        clock1.set("peer2", 2)
        
        clock2 = VectorClock()
        clock2.set("peer1", 3)
        clock2.set("peer2", 4)
        
        # clock1 has higher peer1, clock2 has higher peer2 -> concurrent
        assert clock1.compare(clock2) == ClockComparison.CONCURRENT
        assert clock2.compare(clock1) == ClockComparison.CONCURRENT
    
    def test_copy(self):
        """Test copying a vector clock."""
        clock1 = VectorClock()
        clock1.set("peer1", 5)
        clock1.set("peer2", 3)
        
        clock2 = clock1.copy()
        
        # Should be equal but independent
        assert clock1 == clock2
        assert clock1.clocks == clock2.clocks
        
        # Modifying one shouldn't affect the other
        clock2.increment("peer1")
        assert clock1.get("peer1") == 5
        assert clock2.get("peer1") == 6
    
    def test_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        clock1 = VectorClock()
        clock1.set("peer1", 5)
        clock1.set("peer2", 3)
        
        # Serialize
        data = clock1.to_dict()
        assert data == {"peer1": 5, "peer2": 3}
        
        # Deserialize
        clock2 = VectorClock.from_dict(data)
        assert clock1 == clock2
    
    def test_get_nonexistent_peer(self):
        """Test getting sequence number for nonexistent peer."""
        clock = VectorClock()
        clock.set("peer1", 5)
        
        # Should return 0 for unknown peer
        assert clock.get("peer2") == 0
    
    def test_set(self):
        """Test setting sequence numbers."""
        clock = VectorClock()
        
        clock.set("peer1", 10)
        assert clock.get("peer1") == 10
        
        # Overwrite existing value
        clock.set("peer1", 20)
        assert clock.get("peer1") == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestSyncManager:
    """Tests for SyncManager class."""
    
    def test_initialization(self):
        """Test SyncManager initialization."""
        from core.sync_manager import SyncManager
        from core.network_manager import NetworkManager
        from core.db_manager import DBManager
        from core.crypto_manager import CryptoManager
        from pathlib import Path
        import tempfile
        
        # Create temporary database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Initialize components
            crypto = CryptoManager()
            identity = crypto.generate_identity()
            db = DBManager(db_path)
            db.initialize_database()
            network = NetworkManager(identity, crypto, enable_mdns=False)
            
            # Create SyncManager
            sync = SyncManager(network, db, crypto, identity.peer_id)
            
            # Verify initialization
            assert sync.local_peer_id == identity.peer_id
            assert sync.board_clocks == {}
            assert sync.running is False
            assert sync.sync_task is None
            
            # Close database connection to release file lock
            if db.engine:
                db.engine.dispose()
    
    def test_get_or_create_clock(self):
        """Test getting or creating board clocks."""
        from core.sync_manager import SyncManager
        from core.network_manager import NetworkManager
        from core.db_manager import DBManager
        from core.crypto_manager import CryptoManager
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            crypto = CryptoManager()
            identity = crypto.generate_identity()
            db = DBManager(db_path)
            db.initialize_database()
            network = NetworkManager(identity, crypto, enable_mdns=False)
            sync = SyncManager(network, db, crypto, identity.peer_id)
            
            # Get clock for new board
            board_id = "board123"
            clock = sync._get_or_create_clock(board_id)
            
            # Should be initialized with local peer
            assert board_id in sync.board_clocks
            assert clock.get(identity.peer_id) == 0
            
            # Getting again should return same clock
            clock2 = sync._get_or_create_clock(board_id)
            assert clock is clock2
            
            # Close database connection to release file lock
            if db.engine:
                db.engine.dispose()



# Integration Tests for Synchronization

@pytest.mark.asyncio
async def test_post_sync_between_peers():
    """
    Integration test: Post created on peer A appears on peer B.
    
    This test verifies the complete synchronization flow:
    1. Two peers establish connection
    2. Peer A creates a post
    3. Post is synchronized to peer B
    4. Peer B can retrieve the post from its database
    """
    from core.sync_manager import SyncManager
    from core.network_manager import NetworkManager
    from core.db_manager import DBManager
    from core.crypto_manager import CryptoManager
    from models.database import Post, Thread, Board
    from pathlib import Path
    import tempfile
    import uuid
    from datetime import datetime
    
    # Create temporary directories for each peer
    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        db_path1 = Path(tmpdir1) / "peer1.db"
        db_path2 = Path(tmpdir2) / "peer2.db"
        
        # Initialize components for peer 1
        crypto1 = CryptoManager()
        identity1 = crypto1.generate_identity()
        db1 = DBManager(db_path1)
        db1.initialize_database()
        network1 = NetworkManager(identity1, crypto1, enable_mdns=False)
        sync1 = SyncManager(network1, db1, crypto1, identity1.peer_id)
        
        # Initialize components for peer 2
        crypto2 = CryptoManager()
        identity2 = crypto2.generate_identity()
        db2 = DBManager(db_path2)
        db2.initialize_database()
        network2 = NetworkManager(identity2, crypto2, enable_mdns=False)
        sync2 = SyncManager(network2, db2, crypto2, identity2.peer_id)
        
        try:
            # Start network manager for peer 2 (server)
            await network2.start(port=9200, host='127.0.0.1')
            
            # Connect peer 1 to peer 2
            peer2_id = await network1.connect_to_peer('127.0.0.1', 9200)
            await asyncio.sleep(0.2)
            
            # Create a board on peer 1
            board_id = str(uuid.uuid4())
            board1 = Board(
                id=board_id,
                name="Test Board",
                description="Test board for sync",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            db1.save_board(board1)
            
            # Create a thread on peer 1
            thread_id = str(uuid.uuid4())
            thread1 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Test Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            db1.save_thread(thread1)
            
            # Create a post on peer 1
            post_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            content = "Hello from peer 1!"
            sequence_number = 1
            
            # Sign the post
            message_to_sign = f"{post_id}{thread_id}{identity1.peer_id}{content}{created_at.isoformat()}{sequence_number}".encode('utf-8')
            signature = crypto1.sign_data(message_to_sign, identity1.signing_private_key)
            
            post = Post(
                id=post_id,
                thread_id=thread_id,
                author_peer_id=identity1.peer_id,
                content=content,
                created_at=created_at,
                sequence_number=sequence_number,
                signature=signature,
                parent_post_id=None
            )
            db1.save_post(post)
            
            # Update vector clock on peer 1
            clock1 = sync1._get_or_create_clock(board_id)
            clock1.increment(identity1.peer_id)
            
            # Save peer info for peer 1 in peer 2's database (needed for signature verification)
            from models.database import PeerInfo
            peer1_info = PeerInfo(
                peer_id=identity1.peer_id,
                public_key=identity1.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ),
                last_seen=datetime.utcnow(),
                address="127.0.0.1",
                port=9200,
                is_trusted=False,
                is_banned=False,
                reputation_score=0
            )
            db2.save_peer_info(peer1_info)
            
            # Also save board and thread on peer 2 (needed for post storage)
            # Create separate objects to avoid SQLAlchemy session issues
            board2 = Board(
                id=board_id,
                name="Test Board",
                description="Test board for sync",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            thread2 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Test Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            db2.save_board(board2)
            db2.save_thread(thread2)
            
            # Manually send post from peer 1 to peer 2 (simulating sync)
            post_data = {
                "id": post.id,
                "thread_id": post.thread_id,
                "author_peer_id": post.author_peer_id,
                "content": post.content,
                "created_at": post.created_at.isoformat(),
                "sequence_number": post.sequence_number,
                "signature": post.signature.hex(),
                "parent_post_id": post.parent_post_id,
                "board_id": board_id
            }
            
            # Process the post on peer 2
            result = await sync2.handle_incoming_post(post_data, identity1.peer_id)
            assert result is True, "Post should be successfully processed"
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Verify post exists on peer 2
            posts_on_peer2 = db2.get_posts_for_thread(thread_id)
            assert len(posts_on_peer2) == 1, "Peer 2 should have the post"
            
            synced_post = posts_on_peer2[0]
            assert synced_post.id == post_id
            assert synced_post.content == content
            assert synced_post.author_peer_id == identity1.peer_id
            assert synced_post.sequence_number == sequence_number
            
            # Verify vector clock was updated on peer 2
            clock2 = sync2._get_or_create_clock(board_id)
            assert clock2.get(identity1.peer_id) == 1, "Peer 2's clock should reflect peer 1's post"
            
        finally:
            await network1.stop()
            await network2.stop()
            if db1.engine:
                db1.engine.dispose()
            if db2.engine:
                db2.engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_posts_converge():
    """
    Integration test: Concurrent posts on both peers converge to same state.
    
    This test verifies that:
    1. Two peers can create posts simultaneously
    2. After synchronization, both peers have all posts
    3. Vector clocks correctly track concurrent updates
    """
    from core.sync_manager import SyncManager
    from core.network_manager import NetworkManager
    from core.db_manager import DBManager
    from core.crypto_manager import CryptoManager
    from models.database import Post, Thread, Board, PeerInfo
    from pathlib import Path
    import tempfile
    import uuid
    from datetime import datetime
    from cryptography.hazmat.primitives import serialization
    
    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        db_path1 = Path(tmpdir1) / "peer1.db"
        db_path2 = Path(tmpdir2) / "peer2.db"
        
        # Initialize components for both peers
        crypto1 = CryptoManager()
        identity1 = crypto1.generate_identity()
        db1 = DBManager(db_path1)
        db1.initialize_database()
        network1 = NetworkManager(identity1, crypto1, enable_mdns=False)
        sync1 = SyncManager(network1, db1, crypto1, identity1.peer_id)
        
        crypto2 = CryptoManager()
        identity2 = crypto2.generate_identity()
        db2 = DBManager(db_path2)
        db2.initialize_database()
        network2 = NetworkManager(identity2, crypto2, enable_mdns=False)
        sync2 = SyncManager(network2, db2, crypto2, identity2.peer_id)
        
        try:
            # Start network managers
            await network2.start(port=9201, host='127.0.0.1')
            peer2_id = await network1.connect_to_peer('127.0.0.1', 9201)
            await asyncio.sleep(0.2)
            
            # Create shared board and thread on both peers
            board_id = str(uuid.uuid4())
            thread_id = str(uuid.uuid4())
            
            # Create separate objects for peer 1
            board1 = Board(
                id=board_id,
                name="Shared Board",
                description="Board for concurrent posts",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            thread1 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Shared Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            # Create separate objects for peer 2
            board2 = Board(
                id=board_id,
                name="Shared Board",
                description="Board for concurrent posts",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            thread2 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Shared Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            # Save board and thread on both peers
            db1.save_board(board1)
            db1.save_thread(thread1)
            db2.save_board(board2)
            db2.save_thread(thread2)
            
            # Save peer info for each other
            peer1_info = PeerInfo(
                peer_id=identity1.peer_id,
                public_key=identity1.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ),
                last_seen=datetime.utcnow(),
                address="127.0.0.1",
                port=9201,
                is_trusted=False,
                is_banned=False,
                reputation_score=0
            )
            db2.save_peer_info(peer1_info)
            
            peer2_info = PeerInfo(
                peer_id=identity2.peer_id,
                public_key=identity2.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ),
                last_seen=datetime.utcnow(),
                address="127.0.0.1",
                port=9201,
                is_trusted=False,
                is_banned=False,
                reputation_score=0
            )
            db1.save_peer_info(peer2_info)
            
            # Create concurrent posts on both peers
            # Post 1 from peer 1
            post1_id = str(uuid.uuid4())
            created_at1 = datetime.utcnow()
            content1 = "Post from peer 1"
            sequence1 = 1
            
            message1 = f"{post1_id}{thread_id}{identity1.peer_id}{content1}{created_at1.isoformat()}{sequence1}".encode('utf-8')
            signature1 = crypto1.sign_data(message1, identity1.signing_private_key)
            
            post1 = Post(
                id=post1_id,
                thread_id=thread_id,
                author_peer_id=identity1.peer_id,
                content=content1,
                created_at=created_at1,
                sequence_number=sequence1,
                signature=signature1,
                parent_post_id=None
            )
            db1.save_post(post1)
            sync1._get_or_create_clock(board_id).increment(identity1.peer_id)
            
            # Post 2 from peer 2
            post2_id = str(uuid.uuid4())
            created_at2 = datetime.utcnow()
            content2 = "Post from peer 2"
            sequence2 = 1
            
            message2 = f"{post2_id}{thread_id}{identity2.peer_id}{content2}{created_at2.isoformat()}{sequence2}".encode('utf-8')
            signature2 = crypto2.sign_data(message2, identity2.signing_private_key)
            
            post2 = Post(
                id=post2_id,
                thread_id=thread_id,
                author_peer_id=identity2.peer_id,
                content=content2,
                created_at=created_at2,
                sequence_number=sequence2,
                signature=signature2,
                parent_post_id=None
            )
            db2.save_post(post2)
            sync2._get_or_create_clock(board_id).increment(identity2.peer_id)
            
            # At this point, each peer has only their own post
            assert len(db1.get_posts_for_thread(thread_id)) == 1
            assert len(db2.get_posts_for_thread(thread_id)) == 1
            
            # Synchronize: send post1 to peer 2
            post1_data = {
                "id": post1.id,
                "thread_id": post1.thread_id,
                "author_peer_id": post1.author_peer_id,
                "content": post1.content,
                "created_at": post1.created_at.isoformat(),
                "sequence_number": post1.sequence_number,
                "signature": post1.signature.hex(),
                "parent_post_id": post1.parent_post_id,
                "board_id": board_id
            }
            await sync2.handle_incoming_post(post1_data, identity1.peer_id)
            
            # Synchronize: send post2 to peer 1
            post2_data = {
                "id": post2.id,
                "thread_id": post2.thread_id,
                "author_peer_id": post2.author_peer_id,
                "content": post2.content,
                "created_at": post2.created_at.isoformat(),
                "sequence_number": post2.sequence_number,
                "signature": post2.signature.hex(),
                "parent_post_id": post2.parent_post_id,
                "board_id": board_id
            }
            await sync1.handle_incoming_post(post2_data, identity2.peer_id)
            
            await asyncio.sleep(0.2)
            
            # Verify both peers now have both posts
            posts_on_peer1 = db1.get_posts_for_thread(thread_id)
            posts_on_peer2 = db2.get_posts_for_thread(thread_id)
            
            assert len(posts_on_peer1) == 2, "Peer 1 should have both posts"
            assert len(posts_on_peer2) == 2, "Peer 2 should have both posts"
            
            # Verify post IDs match
            post_ids_peer1 = {p.id for p in posts_on_peer1}
            post_ids_peer2 = {p.id for p in posts_on_peer2}
            assert post_ids_peer1 == post_ids_peer2, "Both peers should have same posts"
            assert post1_id in post_ids_peer1
            assert post2_id in post_ids_peer1
            
            # Verify vector clocks converged
            clock1 = sync1._get_or_create_clock(board_id)
            clock2 = sync2._get_or_create_clock(board_id)
            
            assert clock1.get(identity1.peer_id) == 1
            assert clock1.get(identity2.peer_id) == 1
            assert clock2.get(identity1.peer_id) == 1
            assert clock2.get(identity2.peer_id) == 1
            
            # Verify clocks are equal
            assert clock1.compare(clock2) == ClockComparison.EQUAL
            
        finally:
            await network1.stop()
            await network2.stop()
            if db1.engine:
                db1.engine.dispose()
            if db2.engine:
                db2.engine.dispose()


@pytest.mark.asyncio
async def test_sync_after_network_partition():
    """
    Integration test: Sync after simulated network partition.
    
    This test verifies that:
    1. Two peers are initially connected
    2. Network partition occurs (disconnect)
    3. Both peers create posts while disconnected
    4. After reconnection, posts are synchronized
    5. Both peers converge to same state
    """
    from core.sync_manager import SyncManager
    from core.network_manager import NetworkManager
    from core.db_manager import DBManager
    from core.crypto_manager import CryptoManager
    from models.database import Post, Thread, Board, PeerInfo
    from pathlib import Path
    import tempfile
    import uuid
    from datetime import datetime
    from cryptography.hazmat.primitives import serialization
    
    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        db_path1 = Path(tmpdir1) / "peer1.db"
        db_path2 = Path(tmpdir2) / "peer2.db"
        
        # Initialize components
        crypto1 = CryptoManager()
        identity1 = crypto1.generate_identity()
        db1 = DBManager(db_path1)
        db1.initialize_database()
        network1 = NetworkManager(identity1, crypto1, enable_mdns=False)
        sync1 = SyncManager(network1, db1, crypto1, identity1.peer_id)
        
        crypto2 = CryptoManager()
        identity2 = crypto2.generate_identity()
        db2 = DBManager(db_path2)
        db2.initialize_database()
        network2 = NetworkManager(identity2, crypto2, enable_mdns=False)
        sync2 = SyncManager(network2, db2, crypto2, identity2.peer_id)
        
        try:
            # Initial connection
            await network2.start(port=9202, host='127.0.0.1')
            peer2_id = await network1.connect_to_peer('127.0.0.1', 9202)
            await asyncio.sleep(0.2)
            
            # Setup shared board and thread
            board_id = str(uuid.uuid4())
            thread_id = str(uuid.uuid4())
            
            # Create separate objects for peer 1
            board1 = Board(
                id=board_id,
                name="Partition Test Board",
                description="Testing network partition recovery",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            thread1 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Partition Test Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            # Create separate objects for peer 2
            board2 = Board(
                id=board_id,
                name="Partition Test Board",
                description="Testing network partition recovery",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            thread2 = Thread(
                id=thread_id,
                board_id=board_id,
                title="Partition Test Thread",
                creator_peer_id=identity1.peer_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                signature=b"test_signature"
            )
            
            # Save on both peers
            db1.save_board(board1)
            db1.save_thread(thread1)
            db2.save_board(board2)
            db2.save_thread(thread2)
            
            # Save peer info
            peer1_info = PeerInfo(
                peer_id=identity1.peer_id,
                public_key=identity1.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ),
                last_seen=datetime.utcnow(),
                address="127.0.0.1",
                port=9202,
                is_trusted=False,
                is_banned=False,
                reputation_score=0
            )
            db2.save_peer_info(peer1_info)
            
            peer2_info = PeerInfo(
                peer_id=identity2.peer_id,
                public_key=identity2.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ),
                last_seen=datetime.utcnow(),
                address="127.0.0.1",
                port=9202,
                is_trusted=False,
                is_banned=False,
                reputation_score=0
            )
            db1.save_peer_info(peer2_info)
            
            # Verify initial connection
            assert network1.is_peer_connected(peer2_id)
            assert network2.is_peer_connected(identity1.peer_id)
            
            # SIMULATE NETWORK PARTITION: Disconnect peers
            await network1.disconnect_peer(peer2_id)
            await asyncio.sleep(0.2)
            
            # Verify disconnection
            assert not network1.is_peer_connected(peer2_id)
            
            # Create posts on both peers while disconnected
            # Peer 1 creates 2 posts
            posts_peer1 = []
            for i in range(2):
                post_id = str(uuid.uuid4())
                created_at = datetime.utcnow()
                content = f"Peer 1 post {i+1} during partition"
                sequence = i + 1
                
                message = f"{post_id}{thread_id}{identity1.peer_id}{content}{created_at.isoformat()}{sequence}".encode('utf-8')
                signature = crypto1.sign_data(message, identity1.signing_private_key)
                
                post = Post(
                    id=post_id,
                    thread_id=thread_id,
                    author_peer_id=identity1.peer_id,
                    content=content,
                    created_at=created_at,
                    sequence_number=sequence,
                    signature=signature,
                    parent_post_id=None
                )
                db1.save_post(post)
                posts_peer1.append(post)
                sync1._get_or_create_clock(board_id).set(identity1.peer_id, sequence)
            
            # Peer 2 creates 2 posts
            posts_peer2 = []
            for i in range(2):
                post_id = str(uuid.uuid4())
                created_at = datetime.utcnow()
                content = f"Peer 2 post {i+1} during partition"
                sequence = i + 1
                
                message = f"{post_id}{thread_id}{identity2.peer_id}{content}{created_at.isoformat()}{sequence}".encode('utf-8')
                signature = crypto2.sign_data(message, identity2.signing_private_key)
                
                post = Post(
                    id=post_id,
                    thread_id=thread_id,
                    author_peer_id=identity2.peer_id,
                    content=content,
                    created_at=created_at,
                    sequence_number=sequence,
                    signature=signature,
                    parent_post_id=None
                )
                db2.save_post(post)
                posts_peer2.append(post)
                sync2._get_or_create_clock(board_id).set(identity2.peer_id, sequence)
            
            # Verify each peer has only their own posts
            assert len(db1.get_posts_for_thread(thread_id)) == 2
            assert len(db2.get_posts_for_thread(thread_id)) == 2
            
            # RECONNECT: Simulate network recovery
            peer2_id = await network1.connect_to_peer('127.0.0.1', 9202)
            await asyncio.sleep(0.2)
            
            # Verify reconnection
            assert network1.is_peer_connected(peer2_id)
            
            # Synchronize posts from peer 1 to peer 2
            for post in posts_peer1:
                post_data = {
                    "id": post.id,
                    "thread_id": post.thread_id,
                    "author_peer_id": post.author_peer_id,
                    "content": post.content,
                    "created_at": post.created_at.isoformat(),
                    "sequence_number": post.sequence_number,
                    "signature": post.signature.hex(),
                    "parent_post_id": post.parent_post_id,
                    "board_id": board_id
                }
                await sync2.handle_incoming_post(post_data, identity1.peer_id)
            
            # Synchronize posts from peer 2 to peer 1
            for post in posts_peer2:
                post_data = {
                    "id": post.id,
                    "thread_id": post.thread_id,
                    "author_peer_id": post.author_peer_id,
                    "content": post.content,
                    "created_at": post.created_at.isoformat(),
                    "sequence_number": post.sequence_number,
                    "signature": post.signature.hex(),
                    "parent_post_id": post.parent_post_id,
                    "board_id": board_id
                }
                await sync1.handle_incoming_post(post_data, identity2.peer_id)
            
            await asyncio.sleep(0.2)
            
            # Verify both peers now have all 4 posts
            posts_on_peer1 = db1.get_posts_for_thread(thread_id)
            posts_on_peer2 = db2.get_posts_for_thread(thread_id)
            
            assert len(posts_on_peer1) == 4, "Peer 1 should have all 4 posts after sync"
            assert len(posts_on_peer2) == 4, "Peer 2 should have all 4 posts after sync"
            
            # Verify post IDs match
            post_ids_peer1 = {p.id for p in posts_on_peer1}
            post_ids_peer2 = {p.id for p in posts_on_peer2}
            assert post_ids_peer1 == post_ids_peer2, "Both peers should have same posts"
            
            # Verify all posts are present
            all_post_ids = {p.id for p in posts_peer1 + posts_peer2}
            assert post_ids_peer1 == all_post_ids
            
            # Verify vector clocks converged
            clock1 = sync1._get_or_create_clock(board_id)
            clock2 = sync2._get_or_create_clock(board_id)
            
            assert clock1.get(identity1.peer_id) == 2
            assert clock1.get(identity2.peer_id) == 2
            assert clock2.get(identity1.peer_id) == 2
            assert clock2.get(identity2.peer_id) == 2
            
            # Verify clocks are equal
            assert clock1.compare(clock2) == ClockComparison.EQUAL
            
        finally:
            await network1.stop()
            await network2.stop()
            if db1.engine:
                db1.engine.dispose()
            if db2.engine:
                db2.engine.dispose()
