# ============================================================================
# A* PATHFINDING - MOST DIRECT ROUTE
# ============================================================================

import heapq
import math
from typing import List, Tuple, Set, Optional
from models.node import Node, NodeState
from models.vector2 import Vector2

class PathRequest:
    """Represents a pathfinding request"""
    def __init__(self, start_pos: Tuple[float, float], end_pos: Tuple[float, float]):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.path = []
        self.success = False


class Pathfinding:
    """Main pathfinding class implementing A* algorithm for most direct route"""
    
    def __init__(self, grid):
        self.grid = grid
        self.open_set = []
        self.closed_set = set()
        self.cache = {}
        self.track_direction = None
        
    def set_track_direction(self, track_direction):
        """Set the track direction for forward-only movement"""
        self.track_direction = track_direction
        
    def find_path(self, start_world: Tuple[float, float], end_world: Tuple[float, float], 
                  use_cache: bool = True, avoid_positions: Set[Tuple[int, int]] = None) -> PathRequest:
        """
        Find the most direct path from start_world to end_world coordinates
        Optimizes for shortest distance (most direct route)
        """
        # Check cache first
        cache_key = (start_world, end_world)
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            if cached.success:
                return cached
        
        request = PathRequest(start_world, end_world)
        
        # Convert world coordinates to grid coordinates
        start_grid = self.grid.world_to_grid(start_world[0], start_world[1])
        end_grid = self.grid.world_to_grid(end_world[0], end_world[1])
        
        start_node = self.grid.get_node(start_grid[0], start_grid[1])
        end_node = self.grid.get_node(end_grid[0], end_grid[1])
        
        if not start_node or not end_node:
            request.success = False
            return request
        
        if start_node.state != NodeState.RACE_TRACK or end_node.state != NodeState.RACE_TRACK:
            request.success = False
            return request
        
        # Reset node costs
        self._reset_grid()
        
        # Initialize start node
        start_node.g_cost = 0
        start_node.h_cost = self._get_direct_distance(start_node, end_node)
        
        # Clear and initialize open set
        self.open_set = []
        self.closed_set = set()
        
        # Add start node to open set
        heapq.heappush(self.open_set, start_node)
        
        # Main A* loop
        iterations = 0
        max_iterations = 3000  # Increased for complex paths
        
        while self.open_set and iterations < max_iterations:
            current_node = heapq.heappop(self.open_set)
            self.closed_set.add(current_node)
            
            # Found the target
            if current_node == end_node:
                request.path = self._retrace_path(start_node, end_node)
                request.success = True
                if use_cache:
                    self.cache[cache_key] = request
                return request
            
            # Check neighbors - prioritize most direct route
            for neighbor in self.grid.get_neighbors(current_node):
                if neighbor in self.closed_set:
                    continue
                
                # Skip avoided positions if specified
                if avoid_positions and (neighbor.x, neighbor.y) in avoid_positions:
                    continue
                
                # Calculate new g cost - use actual distance for most direct route
                new_g_cost = current_node.g_cost + self._get_direct_distance(current_node, neighbor)
                
                if new_g_cost < neighbor.g_cost:
                    # Found a better path to neighbor
                    neighbor.parent = current_node
                    neighbor.g_cost = new_g_cost
                    # Use direct distance heuristic for most direct route
                    neighbor.h_cost = self._get_direct_distance(neighbor, end_node)
                    
                    if neighbor not in self.open_set:
                        heapq.heappush(self.open_set, neighbor)
            
            iterations += 1
        
        # If no path found, try with larger search area
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
    
    def _get_direct_distance(self, node_a: Node, node_b: Node) -> float:
        """
        Calculate the most direct distance between two nodes
        Uses straight-line (Euclidean) distance for most direct route
        """
        dx = node_a.x - node_b.x
        dy = node_a.y - node_b.y
        
        # Euclidean distance - most direct line
        return math.sqrt(dx*dx + dy*dy) * 10  # Scale for grid
    
    def _get_manhattan_distance(self, node_a: Node, node_b: Node) -> float:
        """
        Calculate Manhattan distance (grid-based)
        Useful for 4-directional movement
        """
        dx = abs(node_a.x - node_b.x)
        dy = abs(node_a.y - node_b.y)
        return (dx + dy) * 10
    
    def _get_octile_distance(self, node_a: Node, node_b: Node) -> float:
        """
        Calculate octile distance (allows diagonal movement)
        Useful for 8-directional movement
        """
        dx = abs(node_a.x - node_b.x)
        dy = abs(node_a.y - node_b.y)
        
        if dx > dy:
            return 14 * dy + 10 * (dx - dy)
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
        
        # Reverse to get path from start to end
        path.reverse()
        
        # Simplify the path for most direct route (remove unnecessary points)
        path = self._simplify_path(path)
        
        return path
    
    def _simplify_path(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Simplify the path by removing redundant points
        Creates a more direct route by removing unnecessary waypoints
        """
        if len(path) <= 2:
            return path
        
        simplified = [path[0]]
        current_index = 0
        
        while current_index < len(path) - 1:
            # Try to find the furthest point we can reach directly
            for i in range(len(path) - 1, current_index, -1):
                if self._has_direct_line_of_sight(path[current_index], path[i]):
                    simplified.append(path[i])
                    current_index = i
                    break
            else:
                # If no direct line of sight, move to next point
                current_index += 1
                if current_index < len(path):
                    simplified.append(path[current_index])
        
        return simplified
    
    def _has_direct_line_of_sight(self, point_a: Tuple[float, float], point_b: Tuple[float, float]) -> bool:
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
            if node and node.state != NodeState.RACE_TRACK:
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
    
    def optimize_path_for_directness(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Additional optimization to make the path more direct
        Removes zig-zags and straightens curves where possible
        """
        if len(path) <= 2:
            return path
        
        optimized = [path[0]]
        
        for i in range(1, len(path) - 1):
            prev = Vector2(optimized[-1][0], optimized[-1][1])
            curr = Vector2(path[i][0], path[i][1])
            next_point = Vector2(path[i + 1][0], path[i + 1][1])
            
            # Calculate vectors
            to_curr = curr - prev
            to_next = next_point - curr
            
            # If the direction change is too sharp, keep the point
            # Otherwise, it's likely a redundant point
            if to_curr.mag() > 0 and to_next.mag() > 0:
                to_curr.normalize()
                to_next.normalize()
                
                # Dot product - if close to 1, directions are similar (redundant point)
                dot = to_curr.x * to_next.x + to_curr.y * to_next.y
                
                # If directions are very different, keep the point
                if dot < 0.8:  # Threshold for direction change
                    optimized.append(path[i])
       