# ============================================================================
# GRID CLASS
# ============================================================================

from typing import List, Tuple, Optional
from models.node import Node, NodeState

class Grid:
    """Represents the pathfinding grid for the race track"""
    def __init__(self, width: int, height: int, node_size: float = 10.0):
        self.width = width
        self.height = height
        self.node_size = node_size
        self.grid = [[Node(x, y) for y in range(height)] for x in range(width)]
        
    def set_state(self, x: int, y: int, state: NodeState):
        """Set node state"""
        if self.is_valid_position(x, y):
            self.grid[x][y].state = state
    
    def get_node(self, x: int, y: int) -> Optional[Node]:
        """Get node at position"""
        if self.is_valid_position(x, y):
            return self.grid[x][y]
        return None
    
    def is_valid_position(self, x: int, y: int) -> bool:
        """Check if position is within grid bounds"""
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get_neighbors(self, node: Node) -> List[Node]:
        """Get all neighboring nodes (8-directional)"""
        neighbors = []
        for x in range(node.x - 1, node.x + 2):
            for y in range(node.y - 1, node.y + 2):
                if x == node.x and y == node.y:
                    continue
                    
                if self.is_valid_position(x, y):
                    neighbor = self.grid[x][y]
                    # Only allow movement on track cells - NO EXCEPTIONS
                    if neighbor.state == NodeState.RACE_TRACK:
                        neighbors.append(neighbor)
        
        return neighbors
    
    def world_to_grid(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convert world coordinates to grid coordinates"""
        grid_x = int(world_x / self.node_size)
        grid_y = int(world_y / self.node_size)
        # Clamp to grid bounds
        grid_x = max(0, min(grid_x, self.width - 1))
        grid_y = max(0, min(grid_y, self.height - 1))
        return int(grid_x), int(grid_y)
    
    def grid_to_world(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid coordinates to world coordinates (center of cell)"""
        world_x = grid_x * self.node_size + self.node_size / 2
        world_y = grid_y * self.node_size + self.node_size / 2
        return world_x, world_y
    
    def create_track_barriers(self, track_points: List[Tuple[float, float]], track_width: int):
        """Create barriers around the track to keep horses on the track"""
        if len(track_points) < 2:
            return
        
        # First, mark all cells as UNWALKABLE initially
        for x in range(self.width):
            for y in range(self.height):
                self.grid[x][y].state = NodeState.UNWALKABLE
        
        # Mark track cells as RACE_TRACK
        for i in range(len(track_points)):
            p1 = track_points[i]
            p2 = track_points[(i + 1) % len(track_points)]
            
            # Convert to grid coordinates
            start_grid = self.world_to_grid(p1[0], p1[1])
            end_grid = self.world_to_grid(p2[0], p2[1])
            
            # Mark the track path with width
            self._mark_track_width(start_grid, end_grid, track_width)
        
        # Also mark a small buffer zone around track as UNWALKABLE to prevent cutting corners
        self._add_barrier_buffer()
    
    def _mark_track_width(self, start: Tuple[int, int], end: Tuple[int, int], width: int):
        """Mark a wider path for the track"""
        x0, y0 = start
        x1, y1 = end
        
        # Use Bresenham's line algorithm to get center line
        points = self._get_line_points(x0, y0, x1, y1)
        
        # Calculate radius in cells
        radius_cells = max(1, int(width / (2 * self.node_size)))
        
        for x, y in points:
            # Mark a circle of cells around each point to create width
            for dx in range(-radius_cells, radius_cells + 1):
                for dy in range(-radius_cells, radius_cells + 1):
                    nx, ny = x + dx, y + dy
                    if self.is_valid_position(nx, ny):
                        # Check if within radius
                        if dx*dx + dy*dy <= radius_cells*radius_cells:
                            self.grid[nx][ny].state = NodeState.RACE_TRACK

    def _add_barrier_buffer(self):
        """Add a buffer zone of unwalkable cells around the track"""
        # Create a copy of current states
        current_states = [[self.grid[x][y].state for y in range(self.height)] for x in range(self.width)]
        
        # For each cell, if it's track, mark neighbors as buffer
        for x in range(self.width):
            for y in range(self.height):
                if current_states[x][y] == NodeState.RACE_TRACK:
                    # Mark all adjacent cells as buffer (they will become UNWALKABLE)
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = x + dx, y + dy
                            if self.is_valid_position(nx, ny) and current_states[nx][ny] != NodeState.RACE_TRACK:
                                self.grid[nx][ny].state = NodeState.UNWALKABLE

    def _get_line_points(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Get all points on a line using Bresenham's algorithm"""
        points = []
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        
        while True:
            points.append((x0, y0))
            
            if x0 == x1 and y0 == y1:
                break
            
            e2 = 2 * err
            if e2 >= dy:
                if x0 == x1:
                    break
                err += dy
                x0 += sx
            
            if e2 <= dx:
                if y0 == y1:
                    break
                err += dx
                y0 += sy
        
        return points