import heapq
import math
from typing import List, Tuple, Set, Optional
from enum import Enum

class NodeState(Enum):
    """Represents the walkability state of a node"""
    WALKABLE = 0
    UNWALKABLE = 1

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

class Grid:
    """Represents the pathfinding grid"""
    def __init__(self, width: int, height: int, node_size: float = 1.0):
        self.width = width
        self.height = height
        self.node_size = node_size
        self.grid = [[Node(x, y) for y in range(height)] for x in range(width)]
        
    def set_walkable(self, x: int, y: int, walkable: bool):
        """Set whether a node is walkable"""
        if self.is_valid_position(x, y):
            self.grid[x][y].state = NodeState.WALKABLE if walkable else NodeState.UNWALKABLE
    
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
                    if neighbor.state == NodeState.WALKABLE:
                        neighbors.append(neighbor)
        
        return neighbors
    
    def world_to_grid(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convert world coordinates to grid coordinates"""
        grid_x = int(world_x / self.node_size)
        grid_y = int(world_y / self.node_size)
        return grid_x, grid_y
    
    def grid_to_world(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid coordinates to world coordinates"""
        world_x = grid_x * self.node_size + self.node_size / 2
        world_y = grid_y * self.node_size + self.node_size / 2
        return world_x, world_y

class PathRequest:
    """Represents a pathfinding request"""
    def __init__(self, start_pos: Tuple[float, float], end_pos: Tuple[float, float]):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.path = []
        self.success = False

class Pathfinding:
    """Main pathfinding class implementing A* algorithm"""
    
    def __init__(self, grid: Grid):
        self.grid = grid
        self.open_set = []  # Min-heap for nodes to evaluate
        self.closed_set = set()  # Set of evaluated nodes
        
    def find_path(self, start_world: Tuple[float, float], end_world: Tuple[float, float]) -> PathRequest:
        """
        Find a path from start_world to end_world coordinates
        Returns a PathRequest object with the result
        """
        request = PathRequest(start_world, end_world)
        
        # Convert world coordinates to grid coordinates
        start_grid = self.grid.world_to_grid(start_world[0], start_world[1])
        end_grid = self.grid.world_to_grid(end_world[0], end_world[1])
        
        start_node = self.grid.get_node(start_grid[0], start_grid[1])
        end_node = self.grid.get_node(end_grid[0], end_grid[1])
        
        if not start_node or not end_node:
            request.success = False
            return request
        
        if start_node.state == NodeState.UNWALKABLE or end_node.state == NodeState.UNWALKABLE:
            request.success = False
            return request
        
        # Reset the grid (clear previous path data)
        self._reset_grid()
        
        # Initialize start node
        start_node.g_cost = 0
        start_node.h_cost = self._get_distance(start_node, end_node)
        
        # Clear and initialize open set
        self.open_set = []
        self.closed_set = set()
        
        # Add start node to open set
        heapq.heappush(self.open_set, start_node)
        
        # Main A* loop
        while self.open_set:
            current_node = heapq.heappop(self.open_set)
            self.closed_set.add(current_node)
            
            # Found the target
            if current_node == end_node:
                request.path = self._retrace_path(start_node, end_node)
                request.success = True
                return request
            
            # Check neighbors
            for neighbor in self.grid.get_neighbors(current_node):
                if neighbor in self.closed_set:
                    continue
                
                # Calculate new g cost to neighbor
                new_g_cost = current_node.g_cost + self._get_distance(current_node, neighbor)
                
                if new_g_cost < neighbor.g_cost:
                    # Found a better path to neighbor
                    neighbor.parent = current_node
                    neighbor.g_cost = new_g_cost
                    neighbor.h_cost = self._get_distance(neighbor, end_node)
                    
                    # Add to open set if not already there
                    if neighbor not in self.open_set:
                        heapq.heappush(self.open_set, neighbor)
        
        # No path found
        request.success = False
        return request
    
    def _reset_grid(self):
        """Reset node costs and parents for new pathfinding"""
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                node = self.grid.grid[x][y]
                node.g_cost = float('inf')
                node.h_cost = float('inf')
                node.parent = None
    
    def _get_distance(self, node_a: Node, node_b: Node) -> float:
        """
        Calculate distance between two nodes
        Uses octile distance for 8-directional movement
        """
        dx = abs(node_a.x - node_b.x)
        dy = abs(node_a.y - node_b.y)
        
        # Octile distance (allows diagonal movement)
        if dx > dy:
            return 14 * dy + 10 * (dx - dy)  # Assuming 10 for straight, 14 for diagonal
        return 14 * dx + 10 * (dy - dx)
    
    def _retrace_path(self, start_node: Node, end_node: Node) -> List[Tuple[float, float]]:
        """
        Retrace path from end to start and convert to world coordinates
        """
        path = []
        current = end_node
        
        while current != start_node:
            world_pos = self.grid.grid_to_world(current.x, current.y)
            path.append(world_pos)
            current = current.parent
        
        # Add start position
        start_world = self.grid.grid_to_world(start_node.x, start_node.y)
        path.append(start_world)
        
        # Reverse to get path from start to end
        path.reverse()
        
        # Smooth the path (remove redundant waypoints)
        path = self._smooth_path(path)
        
        return path
    
    def _smooth_path(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Smooth the path by removing redundant points
        Uses a simple raycasting approach
        """
        if len(path) <= 2:
            return path
        
        smoothed = [path[0]]
        current_index = 0
        
        while current_index < len(path) - 1:
            # Try to find the furthest point we can reach directly
            for i in range(len(path) - 1, current_index, -1):
                if self._has_line_of_sight(path[current_index], path[i]):
                    smoothed.append(path[i])
                    current_index = i
                    break
            else:
                # If no direct line of sight, move to next point
                current_index += 1
                if current_index < len(path):
                    smoothed.append(path[current_index])
        
        return smoothed
    
    def _has_line_of_sight(self, point_a: Tuple[float, float], point_b: Tuple[float, float]) -> bool:
        """
        Check if there's a clear line of sight between two world points
        Uses Bresenham's line algorithm to check grid cells
        """
        # Convert to grid coordinates
        start_grid = self.grid.world_to_grid(point_a[0], point_a[1])
        end_grid = self.grid.world_to_grid(point_b[0], point_b[1])
        
        x0, y0 = start_grid
        x1, y1 = end_grid
        
        # Bresenham's line algorithm
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        
        while True:
            # Check current cell
            node = self.grid.get_node(x0, y0)
            if node and node.state == NodeState.UNWALKABLE:
                return False
            
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
        
        return True

class PathfindingManager:
    """Manages multiple pathfinding requests and provides a simple interface"""
    
    def __init__(self, grid: Grid):
        self.pathfinding = Pathfinding(grid)
        
    def request_path(self, start_pos: Tuple[float, float], end_pos: Tuple[float, float]) -> PathRequest:
        """Request a path from start to end position"""
        return self.pathfinding.find_path(start_pos, end_pos)
    
    def visualize_path(self, path: List[Tuple[float, float]]):
        """Simple console visualization of the path"""
        if not path:
            print("No path to visualize")
            return
        
        print(f"Path found with {len(path)} waypoints:")
        for i, point in enumerate(path):
            print(f"  {i}: ({point[0]:.1f}, {point[1]:.1f})")

# Example usage and testing
def create_test_grid():
    """Create a test grid with some obstacles"""
    grid = Grid(10, 10)
    
    # Add some obstacles (unwalkable cells)
    # Create a wall
    for y in range(3, 7):
        grid.set_walkable(5, y, False)
    
    # Add some scattered obstacles
    obstacles = [(2, 2), (7, 7), (3, 8), (8, 3)]
    for x, y in obstacles:
        grid.set_walkable(x, y, False)
    
    return grid

def main():
    # Create grid and pathfinding manager
    grid = create_test_grid()
    manager = PathfindingManager(grid)
    
    # Test pathfinding from (0.5, 0.5) to (9.5, 9.5)
    start = (0.5, 0.5)
    end = (9.5, 9.5)
    
    print(f"Requesting path from {start} to {end}")
    result = manager.request_path(start, end)
    
    if result.success:
        print("Path found successfully!")
        manager.visualize_path(result.path)
        
        # Calculate path length
        if len(result.path) > 1:
            total_length = 0
            for i in range(len(result.path) - 1):
                p1 = result.path[i]
                p2 = result.path[i + 1]
                distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                total_length += distance
            print(f"Total path length: {total_length:.2f}")
    else:
        print("No path found!")

if __name__ == "__main__":
    main()