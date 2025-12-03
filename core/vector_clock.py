"""
Vector Clock implementation for distributed synchronization.

Vector clocks are used to track causality and detect concurrent updates
in the distributed BBS system. Each peer maintains a clock that tracks
the sequence number of messages from all known peers.
"""

from typing import Dict, Optional
from enum import Enum


class ClockComparison(Enum):
    """Result of comparing two vector clocks."""
    BEFORE = "before"  # Clock A happened before clock B
    AFTER = "after"  # Clock A happened after clock B
    CONCURRENT = "concurrent"  # Clocks are concurrent (neither before nor after)
    EQUAL = "equal"  # Clocks are identical


class VectorClock:
    """
    Vector clock for tracking causality in distributed systems.
    
    A vector clock is a dictionary mapping peer_id to sequence_number.
    Each peer increments its own sequence number when creating a new message.
    When receiving a message, peers merge the received clock with their own.
    
    Attributes:
        clocks: Dictionary mapping peer_id to sequence number
    """
    
    def __init__(self, peer_id: Optional[str] = None):
        """
        Initialize a vector clock.
        
        Args:
            peer_id: Optional peer ID to initialize with sequence 0
        """
        self.clocks: Dict[str, int] = {}
        if peer_id:
            self.clocks[peer_id] = 0
    
    def increment(self, peer_id: str) -> None:
        """
        Increment the sequence number for a specific peer.
        
        This should be called when the local peer creates a new message.
        
        Args:
            peer_id: Peer ID whose sequence number to increment
        """
        if peer_id not in self.clocks:
            self.clocks[peer_id] = 0
        self.clocks[peer_id] += 1
    
    def merge(self, other: 'VectorClock') -> None:
        """
        Merge another vector clock into this one.
        
        For each peer in the other clock, take the maximum sequence number
        between this clock and the other clock. This should be called when
        receiving a message from another peer.
        
        Args:
            other: Vector clock to merge
        """
        for peer_id, seq_num in other.clocks.items():
            if peer_id not in self.clocks:
                self.clocks[peer_id] = seq_num
            else:
                self.clocks[peer_id] = max(self.clocks[peer_id], seq_num)
    
    def compare(self, other: 'VectorClock') -> ClockComparison:
        """
        Compare this vector clock with another to detect causality.
        
        Returns:
            - BEFORE: if this clock happened before the other
            - AFTER: if this clock happened after the other
            - CONCURRENT: if the clocks are concurrent (neither before nor after)
            - EQUAL: if the clocks are identical
        
        Args:
            other: Vector clock to compare with
            
        Returns:
            ClockComparison: Result of the comparison
        """
        # Get all peer IDs from both clocks
        all_peers = set(self.clocks.keys()) | set(other.clocks.keys())
        
        # Track if this clock is less than, greater than, or equal to other
        has_less = False
        has_greater = False
        
        for peer_id in all_peers:
            self_seq = self.clocks.get(peer_id, 0)
            other_seq = other.clocks.get(peer_id, 0)
            
            if self_seq < other_seq:
                has_less = True
            elif self_seq > other_seq:
                has_greater = True
        
        # Determine relationship
        if not has_less and not has_greater:
            return ClockComparison.EQUAL
        elif has_less and not has_greater:
            return ClockComparison.BEFORE
        elif has_greater and not has_less:
            return ClockComparison.AFTER
        else:
            # Both has_less and has_greater are True
            return ClockComparison.CONCURRENT
    
    def get(self, peer_id: str) -> int:
        """
        Get the sequence number for a specific peer.
        
        Args:
            peer_id: Peer ID to query
            
        Returns:
            Sequence number for the peer (0 if not present)
        """
        return self.clocks.get(peer_id, 0)
    
    def set(self, peer_id: str, seq_num: int) -> None:
        """
        Set the sequence number for a specific peer.
        
        Args:
            peer_id: Peer ID
            seq_num: Sequence number to set
        """
        self.clocks[peer_id] = seq_num
    
    def copy(self) -> 'VectorClock':
        """
        Create a deep copy of this vector clock.
        
        Returns:
            New VectorClock instance with copied data
        """
        new_clock = VectorClock()
        new_clock.clocks = self.clocks.copy()
        return new_clock
    
    def to_dict(self) -> Dict[str, int]:
        """
        Convert vector clock to dictionary format for serialization.
        
        Returns:
            Dictionary mapping peer_id to sequence number
        """
        return self.clocks.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        """
        Create a vector clock from a dictionary.
        
        Args:
            data: Dictionary mapping peer_id to sequence number
            
        Returns:
            New VectorClock instance
        """
        clock = cls()
        clock.clocks = data.copy()
        return clock
    
    def __repr__(self) -> str:
        """String representation of the vector clock."""
        return f"VectorClock({self.clocks})"
    
    def __eq__(self, other: object) -> bool:
        """Check equality with another vector clock."""
        if not isinstance(other, VectorClock):
            return False
        return self.clocks == other.clocks
