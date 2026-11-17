# ============================================================================
# RACE TRACK CLASS - SQUARE TRACK VERSION
# ============================================================================

import math
import random
import pygame
from typing import List, Tuple
from models.grid import Grid
from models.node import NodeState
from pathfinding.astar import Pathfinding
from models.vector2 import Vector2, distance
from utils.colors import COLORS
from config import WIDTH, HEIGHT, TRACK_WIDTH

class RaceTrack:
    """Creates and manages the race track - SQUARE version"""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        
        # Create track points (SQUARE shape)
        self.track_points = self._create_square_track()
        
        # Calculate track direction (clockwise)
        self.track_direction = self._calculate_track_direction()
        
        # Start and finish on the SAME CORNER (top-right corner)
        # SWAPPED: Start is now on the right edge, finish on the top edge
        self.start_line_pos = self._get_point_on_edge('right', 0.1)  # Near top of right edge (START)
        self.finish_line_pos = self._get_point_on_edge('top', 0.9)   # Near right side of top edge (FINISH)
        
        # Create visible checkpoints (including start and finish as checkpoints)
        self.checkpoints = self._create_checkpoints_with_start_finish()
        self.checkpoint_positions = []
        self.checkpoint_radius = 40
        
        for cp in self.checkpoints:
            self.checkpoint_positions.append(Vector2(cp[0], cp[1]))
        
        # Colors for checkpoints (start=green, finish=red, others=rainbow)
        self.checkpoint_colors = self._create_checkpoint_colors()
        
        # Fixed start positions
        self.fixed_start_positions = self._calculate_fixed_start_positions()
        
        # Grid for pathfinding
        grid_width = int(width // 12)
        grid_height = int(height // 12)
        self.grid = Grid(grid_width, grid_height, 12.0)
        
        self._setup_track()
        self._add_invisible_barrier()
        
        # Pathfinder
        self.pathfinder = Pathfinding(self.grid)
        self.pathfinder.set_track_direction(self.track_direction)
        
        self.goal = Vector2(self.finish_line_pos[0], self.finish_line_pos[1])
        
        # Create ideal path (EMPTY - no line to follow)
        self.ideal_path = self._create_ideal_path()
        
        # Pre-render static elements
        self._create_static_surfaces()
        
    def _create_square_track(self) -> List[Tuple[float, float]]:
        """Create a SQUARE race track"""
        points = []
        
        # Square dimensions
        left_x = self.width * 0.25
        right_x = self.width * 0.55
        top_y = self.height * 0.2
        bottom_y = self.height * 0.8
        
        # Create points in clockwise order with more points for smoother corners
        # Top edge (left to right)
        for i in range(12):
            x = left_x + (right_x - left_x) * (i / 11)
            y = top_y
            points.append((x, y))
        
        # Right edge (top to bottom)
        for i in range(1, 12):
            x = right_x
            y = top_y + (bottom_y - top_y) * (i / 11)
            points.append((x, y))
        
        # Bottom edge (right to left)
        for i in range(1, 12):
            x = right_x - (right_x - left_x) * (i / 11)
            y = bottom_y
            points.append((x, y))
        
        # Left edge (bottom to top)
        for i in range(1, 12):
            x = left_x
            y = bottom_y - (bottom_y - top_y) * (i / 11)
            points.append((x, y))
        
        return points
    
    def _get_point_on_edge(self, edge: str, t: float) -> Tuple[float, float]:
        """Get a point on a specific edge of the square (t from 0 to 1)"""
        left_x = self.width * 0.25
        right_x = self.width * 0.55
        top_y = self.height * 0.2
        bottom_y = self.height * 0.8
        
        if edge == 'top':
            x = left_x + (right_x - left_x) * t
            y = top_y
        elif edge == 'right':
            x = right_x
            y = top_y + (bottom_y - top_y) * t
        elif edge == 'bottom':
            x = right_x - (right_x - left_x) * t
            y = bottom_y
        elif edge == 'left':
            x = left_x
            y = bottom_y - (bottom_y - top_y) * t
        else:
            x, y = left_x, top_y
        
        return (x, y)
    
    def _create_ideal_path(self) -> List[Vector2]:
        """Create an empty ideal path - horses only need to hit checkpoints in order"""
        # Return empty list - no ideal path to follow
        return []
    
    def _create_static_surfaces(self):
        """Pre-render static elements to surfaces"""
        # Create a surface for the grass background
        self.grass_surface = pygame.Surface((self.width, self.height))
        self.grass_surface.fill(COLORS['GREEN'])
        
        # Create a surface for the track elements
        self.track_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Draw the SQUARE track
        if len(self.track_points) > 1:
            # Draw the main track as a thick brown line
            pygame.draw.lines(self.track_surface, COLORS['BROWN'], True, 
                             [(int(x), int(y)) for x, y in self.track_points], TRACK_WIDTH)
            
            # Draw inner edge for texture (lighter brown) - slightly thinner
            pygame.draw.lines(self.track_surface, COLORS['LIGHT_BROWN'], True, 
                             [(int(x), int(y)) for x, y in self.track_points], TRACK_WIDTH - 20)
            
            # Draw track center line (dashed)
            for i in range(0, len(self.track_points), 2):
                p1 = self.track_points[i]
                p2 = self.track_points[(i + 1) % len(self.track_points)]
                pygame.draw.line(self.track_surface, COLORS['YELLOW'], 
                                (int(p1[0]), int(p1[1])), 
                                (int(p2[0]), int(p2[1])), 3)
        
        # Create a surface for text and overlays
        self.text_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
    
    def _create_checkpoints_with_start_finish(self) -> List[Tuple[float, float]]:
        """Create checkpoints including START and FINISH as checkpoints 0 and 8"""
        checkpoints = []
        
        # Add START as checkpoint 0
        checkpoints.append(self.start_line_pos)
        
        # Add 7 intermediate checkpoints
        num_intermediate = 7
        total_points = len(self.track_points)
        
        # Find the index closest to start position
        start_idx = 0
        min_dist = float('inf')
        
        for i, point in enumerate(self.track_points):
            dist = distance(Vector2(point[0], point[1]), Vector2(self.start_line_pos[0], self.start_line_pos[1]))
            if dist < min_dist:
                min_dist = dist
                start_idx = i
        
        # Place intermediate checkpoints evenly spaced after start (clockwise)
        for i in range(1, num_intermediate + 1):
            # Calculate index offset from start
            offset = int(i * (total_points / (num_intermediate + 1)))
            idx = (start_idx + offset) % total_points
            checkpoints.append(self.track_points[idx])
        
        # Add FINISH as checkpoint 8 (last checkpoint)
        checkpoints.append(self.finish_line_pos)
        
        return checkpoints
    
    def _create_checkpoint_colors(self) -> List[Tuple[int, int, int]]:
        """Create colors for checkpoints (0=start/green, 1-7=rainbow, 8=finish/red)"""
        colors = []
        
        # Start checkpoint (index 0) - Green
        colors.append((0, 255, 0))  # Bright green
        
        # Intermediate checkpoints (indices 1-7) - Rainbow
        rainbow = [
            (255, 0, 0),      # Red
            (255, 165, 0),    # Orange
            (255, 255, 0),    # Yellow
            (0, 255, 0),      # Green
            (0, 255, 255),    # Cyan
            (0, 0, 255),      # Blue
            (128, 0, 128)     # Purple
        ]
        colors.extend(rainbow)
        
        # Finish checkpoint (index 8) - Red
        colors.append((255, 0, 0))  # Bright red
        
        return colors
    
    def _calculate_track_direction(self) -> List[Vector2]:
        """Calculate forward direction at each track point (clockwise)"""
        directions = []
        for i in range(len(self.track_points)):
            current = self.track_points[i]
            next_point = self.track_points[(i + 1) % len(self.track_points)]
            dx = next_point[0] - current[0]
            dy = next_point[1] - current[1]
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                directions.append(Vector2(dx/length, dy/length))
            else:
                directions.append(Vector2(0, 0))
        return directions
    
    def _setup_track(self):
        """Setup track with barriers"""
        self.grid.create_track_barriers(self.track_points, TRACK_WIDTH)
    
    def _add_invisible_barrier(self):
        """Add invisible barrier between finish and start to force clockwise movement"""
        # This creates a barrier along the short path between finish and start
        # to force horses to go the long way around (through all checkpoints)
        
        # Find indices of start and finish points
        start_idx = None
        finish_idx = None
        
        for i, point in enumerate(self.track_points):
            if distance(Vector2(point[0], point[1]), Vector2(self.start_line_pos[0], self.start_line_pos[1])) < 20:
                start_idx = i
            if distance(Vector2(point[0], point[1]), Vector2(self.finish_line_pos[0], self.finish_line_pos[1])) < 20:
                finish_idx = i
        
        if start_idx is None or finish_idx is None:
            return
        
        # Determine the short path between finish and start (going counter-clockwise)
        # This is the path we want to block
        if finish_idx < start_idx:
            short_segment = list(range(finish_idx, start_idx + 1))
        else:
            # Wrap around
            short_segment = list(range(finish_idx, len(self.track_points))) + list(range(0, start_idx + 1))
        
        # Create a much narrower barrier that blocks the path but leaves the finish line accessible
        barrier_width = 2  # Reduced from 4
        for idx in short_segment:
            point = self.track_points[idx]
            grid_x, grid_y = self.grid.world_to_grid(point[0], point[1])
            for dx in range(-barrier_width, barrier_width + 1):
                for dy in range(-barrier_width, barrier_width + 1):
                    nx, ny = grid_x + dx, grid_y + dy
                    if self.grid.is_valid_position(nx, ny):
                        # Only block cells that are on the track and NOT at the finish line
                        if self.grid.get_node(nx, ny).state == NodeState.RACE_TRACK:
                            # Check if this cell is too close to the finish line
                            world_x, world_y = self.grid.grid_to_world(nx, ny)
                            dist_to_finish = distance(Vector2(world_x, world_y), 
                                                    Vector2(self.finish_line_pos[0], self.finish_line_pos[1]))
                            # Don't block cells very close to the finish line
                            if dist_to_finish > 40:  # Leave a clear area around finish line
                                self.grid.set_state(nx, ny, NodeState.UNWALKABLE)
    
    def _calculate_fixed_start_positions(self) -> List[Vector2]:
        """Pre-calculate fixed starting positions along the start line on the right edge"""
        positions = []
        
        if not self.start_line_pos:
            return positions
        
        # Find the two track points that define the start line segment
        start_point = Vector2(self.start_line_pos[0], self.start_line_pos[1])
        
        # Find the next point on the track (going clockwise)
        next_idx = None
        for i, point in enumerate(self.track_points):
            if distance(Vector2(point[0], point[1]), start_point) < 20:
                next_idx = (i + 1) % len(self.track_points)
                break
        
        if next_idx is None:
            return positions
        
        next_point = Vector2(self.track_points[next_idx][0], self.track_points[next_idx][1])
        
        # Calculate direction along start line (clockwise direction)
        dx = next_point.x - start_point.x
        dy = next_point.y - start_point.y
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            dir_x = dx / length
            dir_y = dy / length
            
            # Perpendicular direction for spreading across track width (pointing inward)
            perp_x = -dir_y
            perp_y = dir_x
            
            spacing = TRACK_WIDTH / 7
            
            for i in range(6):
                offset = (i + 1 - 3.5) * spacing
                # Start position is along the start line with perpendicular offset
                start_x = start_point.x + dir_x * 10 + perp_x * offset
                start_y = start_point.y + dir_y * 10 + perp_y * offset
                positions.append(Vector2(start_x, start_y))
        
        return positions
    
    def get_start_position(self, horse_index: int) -> Vector2:
        if not self.fixed_start_positions:
            return Vector2(self.width * 0.4, self.height * 0.5)
        idx = horse_index % len(self.fixed_start_positions)
        return self.fixed_start_positions[idx].copy()
    
    def get_spread_start_positions(self, num_horses: int) -> List[Vector2]:
        return [self.get_start_position(i) for i in range(num_horses)]
    
    def get_checkpoint_position(self, index: int) -> Vector2:
        if 0 <= index < len(self.checkpoint_positions):
            return self.checkpoint_positions[index].copy()
        return None
    
    def get_checkpoint_color(self, index: int) -> Tuple[int, int, int]:
        return self.checkpoint_colors[index % len(self.checkpoint_colors)]
    
    def get_total_checkpoints(self) -> int:
        """Get total number of checkpoints (including start and finish)"""
        return len(self.checkpoint_positions)
    
    def is_position_on_track(self, pos: Vector2) -> bool:
        grid_x, grid_y = self.grid.world_to_grid(pos.x, pos.y)
        node = self.grid.get_node(grid_x, grid_y)
        return node and node.state == NodeState.RACE_TRACK
    
    def get_nearest_track_position(self, pos: Vector2) -> Vector2:
        min_dist = float('inf')
        nearest = Vector2(pos.x, pos.y)
        for point in self.track_points:
            dist = math.sqrt((point[0] - pos.x) ** 2 + (point[1] - pos.y) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest = Vector2(point[0], point[1])
        return nearest
    
    def get_forward_direction(self, pos: Vector2) -> Vector2:
        min_dist = float('inf')
        closest_idx = 0
        for i, point in enumerate(self.track_points):
            dist = math.sqrt((point[0] - pos.x) ** 2 + (point[1] - pos.y) ** 2)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        return self.track_direction[closest_idx].copy()
    
    def is_moving_forward(self, pos: Vector2, velocity: Vector2) -> bool:
        forward = self.get_forward_direction(pos)
        if velocity.mag() > 0:
            vel_norm = velocity.copy()
            vel_norm.normalize()
            dot = vel_norm.x * forward.x + vel_norm.y * forward.y
            return dot > -0.3
        return True
    
    def calculate_path_percentage(self, path: List[Tuple[float, float]]) -> float:
        """Path percentage calculation removed - always returns 0"""
        return 0.0
    
    def draw(self, screen, show_ideal_path=True):
        """Draw the square race track"""
        # Draw grass background FIRST
        screen.blit(self.grass_surface, (0, 0))
        
        # Draw the track surface (brown square)
        screen.blit(self.track_surface, (0, 0))
        
        # NO IDEAL PATH DRAWING - horses just need to hit checkpoints in order
        
        # Draw checkpoints (on top of track)
        for i, cp in enumerate(self.checkpoint_positions):
            color = self.get_checkpoint_color(i)
            
            # Draw different sizes for start/finish
            if i == 0:  # Start checkpoint
                radius = 18
                pygame.draw.circle(screen, color, (int(cp.x), int(cp.y)), radius, 0)
                pygame.draw.circle(screen, COLORS['WHITE'], (int(cp.x), int(cp.y)), radius, 3)
                font = pygame.font.Font(None, 24)
                text = font.render("S", True, COLORS['BLACK'])
            elif i == len(self.checkpoint_positions) - 1:  # Finish checkpoint
                radius = 18
                pygame.draw.circle(screen, color, (int(cp.x), int(cp.y)), radius, 0)
                pygame.draw.circle(screen, COLORS['WHITE'], (int(cp.x), int(cp.y)), radius, 3)
                font = pygame.font.Font(None, 24)
                text = font.render("F", True, COLORS['BLACK'])
            else:  # Regular checkpoints
                radius = 14
                pygame.draw.circle(screen, color, (int(cp.x), int(cp.y)), radius, 0)
                pygame.draw.circle(screen, COLORS['WHITE'], (int(cp.x), int(cp.y)), radius, 2)
                font = pygame.font.Font(None, 20)
                text = font.render(str(i), True, COLORS['WHITE'])
            
            text_rect = text.get_rect(center=(int(cp.x), int(cp.y)))
            screen.blit(text, text_rect)
        
        # Draw direction arrows (fewer arrows for cleaner look)
        for i in range(0, len(self.track_points), 15):
            point = self.track_points[i]
            direction = self.track_direction[i]
            end_x = point[0] + direction.x * 30
            end_y = point[1] + direction.y * 30
            pygame.draw.line(screen, COLORS['WHITE'],
                            (int(point[0]), int(point[1])),
                            (int(end_x), int(end_y)), 2)
        
        # Draw text overlay (START/FINISH labels)
        if self.start_line_pos:
            font = pygame.font.Font(None, 36)
            text = font.render("START", True, COLORS['WHITE'])
            outline = font.render("START", True, COLORS['BLACK'])
            text_x = self.start_line_pos[0] + 40
            text_y = self.start_line_pos[1] - 40
            for dx, dy in [(-2,-2), (-2,2), (2,-2), (2,2)]:
                screen.blit(outline, (int(text_x + dx), int(text_y + dy)))
            screen.blit(text, (int(text_x), int(text_y)))
        
        if self.finish_line_pos:
            font = pygame.font.Font(None, 36)
            text = font.render("FINISH", True, COLORS['WHITE'])
            outline = font.render("FINISH", True, COLORS['BLACK'])
            text_x = self.finish_line_pos[0] - 90
            text_y = self.finish_line_pos[1] - 70
            for dx, dy in [(-2,-2), (-2,2), (2,-2), (2,2)]:
                screen.blit(outline, (int(text_x + dx), int(text_y + dy)))
            screen.blit(text, (int(text_x), int(text_y)))
        
        # Draw barriers
        self._draw_barriers(screen)
    
    def _draw_barriers(self, screen):
        """Simplified barrier drawing"""
        if len(self.track_points) <= 1:
            return
            
        outer_points = []
        inner_points = []
        
        for i in range(len(self.track_points)):
            p = self.track_points[i]
            p_next = self.track_points[(i + 1) % len(self.track_points)]
            dx = p_next[0] - p[0]
            dy = p_next[1] - p[1]
            length = math.sqrt(dx*dx + dy*dy)
            
            if length > 0:
                perp_x = -dy / length * (TRACK_WIDTH//2 + 20)
                perp_y = dx / length * (TRACK_WIDTH//2 + 20)
                outer_points.append((p[0] + perp_x, p[1] + perp_y))
                inner_points.append((p[0] - perp_x, p[1] - perp_y))
        
        if len(outer_points) > 1:
            pygame.draw.lines(screen, COLORS['WOOD'], True, 
                             [(int(x), int(y)) for x, y in outer_points], 3)
        if len(inner_points) > 1:
            pygame.draw.lines(screen, COLORS['WOOD'], True, 
                             [(int(x), int(y)) for x, y in inner_points], 3)