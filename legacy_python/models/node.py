# ============================================================================
# NODE CLASSES
# ============================================================================

from enum import Enum

class NodeState(Enum):
    """Represents the walkability state of a node"""
    WALKABLE = 0
    UNWALKABLE = 1
    RACE_TRACK = 2  # Special track cells


class Node:
    """Represents a single node in the grid"""
    def __init__(self, x: int, y: int, state: NodeState = NodeState.WALKABLE):
        self.x = x
        self.y = y
        self.state = state
        self.g_cost = float('inf')  # Distance from start node
        self.h_cost = float('inf')  # Distance to target node
        self.parent = None
        self.heap_index = 0  # For heap optimization
        
    @property
    def f_cost(self) -> float:
        """Total cost (g + h)"""
        return self.g_cost + self.h_cost
    
    def __lt__(self, other):
        """Comparison for heap queue"""
        return self.f_cost < other.f_cost
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __repr__(self):
        return f"Node({self.x}, {self.y}, {self.state})"