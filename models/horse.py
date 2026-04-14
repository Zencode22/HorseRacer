# ============================================================================
# HORSE CLASS - OPTIMIZED
# ============================================================================

import math
import random
import pygame
from typing import List, Tuple, Optional, Set, Dict
from models.vector2 import Vector2, distance
from utils.colors import COLORS
from models.node import NodeState
from models.ranking import RankingManager

class Horse:
    """Optimized horse agent"""
    
    def __init__(self, x: float, y: float, color: Tuple[int, int, int]):
        self.position = Vector2(x, y)
        self.velocity = Vector2(random.uniform(-2, 2), random.uniform(-2, 2))
        self.acceleration = Vector2(0, 0)
        
        # Flocking parameters
        self.max_speed = 4.0
        self.max_force = 0.3
        self.neighbor_radius = 150
        self.separation_radius = 15
        
        # Flocking weights (optimized)
        self.separation_weight = 1.0
        self.alignment_weight = 1.2
        self.cohesion_weight = 1.0
        self.path_weight = 3.0
        self.track_attraction_weight = 3.0
        self.barrier_avoidance_weight = 5.0
        self.checkpoint_weight = 5.0
        self.clockwise_weight = 4.0
        
        # Pathfinding
        self.target = None
        self.current_path = []
        self.path_update_timer = 0
        self.path_update_interval = 30  # Increased for performance
        self.track = None
        
        # Visualization
        self.color = color
        self.size = 10
        self.horse_id = id(self) % 1000
        
        # Performance tracking
        self.distance_traveled = 0
        self.laps_completed = 0
        
        # Checkpoint tracking - START is index 0, FINISH is last index
        self.current_checkpoint_index = 0
        self.total_checkpoints = 9  # Start (0) + 7 intermediate + Finish (8)
        self.checkpoint_reached_time = 0
        self.checkpoints_visited = []
        
        # NEW: Flag to indicate horse has finished the race
        self.has_finished = False
        
        # Barrier memory (limited size for performance)
        self.barrier_memory = set()
        self.max_memory_size = 50  # Reduced from 100
        
        # Best path memory (simplified)
        self.best_paths = {}
        
        # Learning (simplified)
        self.attempt_count = 0
        self.confidence_score = 0.0
        
        # Barrier detection
        self.barrier_detection_radius = 80
        self.last_barrier_hit = 0
        self.consecutive_barrier_hits = 0
        self.max_consecutive_hits = 8
        
        # Stuck detection
        self.stuck_timer = 0
        self.stuck_threshold = 250
        self.last_position = Vector2(x, y)
        self.reset_cooldown = 0
        
        # Clockwise tracking
        self.clockwise_history = []
        self.clockwise_history_size = 5  # Reduced for performance
        self.wrong_direction_penalty = 0
        
        # Path history for visualization (limited for performance)
        self.path_history = []
        self.path_history_max = 30  # Reduced from 100
        self.show_path = True
        
        # Ranking system
        self.ranking_manager = None
        
    def set_target(self, target: Vector2, pathfinder):
        # Don't set new targets if horse has finished
        if self.has_finished:
            return
        self.target = target
        self.request_new_path(pathfinder)
    
    def request_new_path(self, pathfinder):
        if self.target is None or self.has_finished:
            return
        
        start = (self.position.x, self.position.y)
        end = (self.target.x, self.target.y)
        
        # Use best path if available and confident
        if self.current_checkpoint_index in self.best_paths and self.confidence_score > 0.5:
            self.current_path = self.best_paths[self.current_checkpoint_index].copy()
            return
        
        # Try to find path avoiding known barriers
        result = pathfinder.find_path(start, end, avoid_positions=self.barrier_memory)
        
        if result.success:
            self.current_path = result.path
            if self.current_path and len(self.current_path) > 1:
                first = self.current_path[0]
                dist = math.sqrt((first[0] - self.position.x) ** 2 + 
                                 (first[1] - self.position.y) ** 2)
                if dist < 20:
                    self.current_path.pop(0)
    
    def get_current_target(self) -> Optional[Vector2]:
        # Return None if horse has finished
        if self.has_finished:
            return None
            
        if not self.track or not hasattr(self.track, 'checkpoint_positions'):
            return self.target
        
        # If we've reached the finish checkpoint, no target needed
        if self.current_checkpoint_index >= self.total_checkpoints:
            return None
        
        return self.track.checkpoint_positions[self.current_checkpoint_index].copy()
    
    def update_checkpoint(self):
        # Skip checkpoint updates if horse has finished
        if self.has_finished:
            return
            
        if not self.track or not hasattr(self.track, 'checkpoint_positions'):
            return
        
        # If we've already passed all checkpoints, don't continue
        if self.current_checkpoint_index >= self.total_checkpoints:
            return
        
        checkpoint = self.track.checkpoint_positions[self.current_checkpoint_index]
        dist = distance(self.position, checkpoint)
        
        if dist < self.track.checkpoint_radius and self.checkpoint_reached_time == 0:
            self.checkpoints_visited.append(self.current_checkpoint_index)
            
            # Special messages for start and finish
            if self.current_checkpoint_index == 0:
                print(f"Horse {self.horse_id} passed START checkpoint!")
            elif self.current_checkpoint_index == self.total_checkpoints - 1:
                print(f"Horse {self.horse_id} reached FINISH checkpoint! Race complete!")
                # Mark as finished immediately
                self.mark_finished()
                # Notify ranking manager about completion
                if self.ranking_manager:
                    self.ranking_manager.finish_race(self.horse_id)
                return
            else:
                print(f"Horse {self.horse_id} reached checkpoint {self.current_checkpoint_index}")
            
            if self.ranking_manager:
                self.ranking_manager.reached_checkpoint(self.horse_id)
            
            # Store successful path (simplified - no path percentage needed)
            if len(self.current_path) > 0 and self.current_checkpoint_index < self.total_checkpoints - 1:
                if self.current_checkpoint_index not in self.best_paths:
                    self.best_paths[self.current_checkpoint_index] = self.current_path.copy()
                    self.confidence_score = min(1.0, self.confidence_score + 0.2)
            
            self.barrier_memory.clear()
            self.consecutive_barrier_hits = 0
            self.stuck_timer = 0
            self.wrong_direction_penalty = 0
            
            # Move to next checkpoint
            self.current_checkpoint_index += 1
            self.checkpoint_reached_time = 20
            
            # Check if this was the finish checkpoint
            if self.current_checkpoint_index >= self.total_checkpoints:
                # Horse has completed the race!
                self.mark_finished()
                if self.ranking_manager:
                    self.ranking_manager.finish_race(self.horse_id)
                return
            else:
                # Set target to next checkpoint
                self.target = self.track.checkpoint_positions[self.current_checkpoint_index]
            
            if hasattr(self, 'track') and self.track:
                self.request_new_path(self.track.pathfinder)
        
        if self.checkpoint_reached_time > 0:
            self.checkpoint_reached_time -= 1
    
    def check_if_stuck(self) -> bool:
        # Never consider a finished horse as stuck
        if self.has_finished:
            return False
            
        if self.reset_cooldown > 0:
            self.reset_cooldown -= 1
            return False
        
        moved = distance(self.position, self.last_position)
        self.last_position = Vector2(self.position.x, self.position.y)
        
        if moved < 1.0:
            self.stuck_timer += 2
        else:
            self.stuck_timer = max(0, self.stuck_timer - 1)
        
        if self.stuck_timer > self.stuck_threshold:
            return True
        
        if self.consecutive_barrier_hits > self.max_consecutive_hits:
            return True
        
        if self.wrong_direction_penalty > 5:
            return True
        
        return False
    
    def reset_to_start(self):
        # Don't reset if horse has finished
        if self.has_finished:
            return
            
        if not self.track:
            return
        
        if self.ranking_manager:
            self.ranking_manager.add_reset(self.horse_id)
        
        self.attempt_count += 1
        self.confidence_score = max(0, self.confidence_score - 0.1)
        
        horse_idx = self.horse_id % 6
        start_pos = self.track.get_start_position(horse_idx)
        self.position = Vector2(start_pos.x, start_pos.y)
        
        forward = self.track.get_forward_direction(self.position)
        self.velocity = Vector2(forward.x * 2, forward.y * 2)
        
        # Reset to START checkpoint (index 0)
        self.current_checkpoint_index = 0
        self.checkpoint_reached_time = 0
        self.checkpoints_visited = []
        self.barrier_memory.clear()
        self.consecutive_barrier_hits = 0
        self.stuck_timer = 0
        self.reset_cooldown = 60  # Reduced from 120
        self.clockwise_history.clear()
        self.wrong_direction_penalty = 0
        self.path_history.clear()
        
        if len(self.track.checkpoint_positions) > 0:
            self.target = self.track.checkpoint_positions[0]
            self.request_new_path(self.track.pathfinder)
    
    def mark_finished(self):
        """Mark the horse as finished the race"""
        self.has_finished = True
        self.velocity = Vector2(0, 0)
        self.target = None
        self.current_path = []
        print(f"Horse {self.horse_id} has finished the race and stopped!")
    
    def update_path_history(self):
        # Don't update path history if finished (optional - can keep to show final position)
        self.path_history.append((self.position.x, self.position.y))
        if len(self.path_history) > self.path_history_max:
            self.path_history.pop(0)
    
    def flock(self, horses: List['Horse'], pathfinder=None):
        # Don't do anything if horse has finished
        if self.has_finished:
            return
            
        # Update position history
        self.update_path_history()
        
        # Check if stuck (but not if finished)
        if self.check_if_stuck():
            self.reset_to_start()
            return
        
        # Update checkpoint
        self.update_checkpoint()
        
        # If we just finished, don't apply any more forces
        if self.has_finished:
            return
        
        # Calculate forces (optimized - only separation and path following)
        sep = self.separation(horses)
        sep.mult(self.separation_weight)
        self.apply_force(sep)
        
        # Path following
        if pathfinder:
            current_target = self.get_current_target()
            if current_target:
                original_target = self.target
                self.target = current_target
                path_force = self.follow_path(pathfinder)
                path_force.mult(self.path_weight)
                self.apply_force(path_force)
                self.target = original_target
        
        # Track attraction
        if self.track:
            track_force = self.attract_to_track()
            track_force.mult(self.track_attraction_weight)
            self.apply_force(track_force)
        
        # Barrier avoidance
        barrier_force = self.avoid_barriers()
        barrier_force.mult(self.barrier_avoidance_weight)
        self.apply_force(barrier_force)
        
        # Checkpoint attraction
        checkpoint_force = self.attract_to_checkpoint()
        checkpoint_force.mult(self.checkpoint_weight)
        self.apply_force(checkpoint_force)
        
        # Clockwise enforcement
        clockwise_force = self.enforce_clockwise()
        clockwise_force.mult(self.clockwise_weight)
        self.apply_force(clockwise_force)
    
    def separation(self, horses: List['Horse']) -> Vector2:
        steer = Vector2(0, 0)
        count = 0
        
        for other in horses:
            if other is self:
                continue
            d = distance(self.position, other.position)
            if 0 < d < self.separation_radius:
                diff = self.position.copy()
                diff.sub(other.position)
                diff.normalize()
                diff.div(max(d, 1.0))
                steer.add(diff)
                count += 1
        
        if count > 0:
            steer.div(count)
            if steer.mag() > 0:
                steer.normalize()
                steer.mult(self.max_speed)
                steer.sub(self.velocity)
                steer.limit(self.max_force)
        
        return steer
    
    def attract_to_checkpoint(self) -> Vector2:
        # Don't attract to checkpoint if finished
        if self.has_finished:
            return Vector2(0, 0)
            
        if not self.track or not hasattr(self.track, 'checkpoint_positions'):
            return Vector2(0, 0)
        
        # If we've passed all checkpoints, no attraction
        if self.current_checkpoint_index >= self.total_checkpoints:
            return Vector2(0, 0)
        
        checkpoint = self.track.checkpoint_positions[self.current_checkpoint_index]
        return self.seek(checkpoint)
    
    def attract_to_track(self) -> Vector2:
        # Still attract to track even if finished? Probably not needed
        if self.has_finished:
            return Vector2(0, 0)
            
        if not self.track:
            return Vector2(0, 0)
        
        nearest = self.track.get_nearest_track_position(self.position)
        if distance(self.position, nearest) > 20:
            return self.seek(nearest)
        return Vector2(0, 0)
    
    def avoid_barriers(self) -> Vector2:
        # Don't avoid barriers if finished
        if self.has_finished:
            return Vector2(0, 0)
            
        if not self.track or not hasattr(self.track, 'grid'):
            return Vector2(0, 0)
        
        grid = self.track.grid
        steer = Vector2(0, 0)
        count = 0
        hit = False
        
        center = grid.world_to_grid(self.position.x, self.position.y)
        
        # Reduced check radius for performance
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx == 0 and dy == 0:
                    continue
                gx, gy = center[0] + dx, center[1] + dy
                node = grid.get_node(gx, gy)
                
                if node and node.state != NodeState.RACE_TRACK:
                    barrier = Vector2(
                        gx * grid.node_size + grid.node_size/2,
                        gy * grid.node_size + grid.node_size/2
                    )
                    
                    if len(self.barrier_memory) < self.max_memory_size:
                        self.barrier_memory.add((gx, gy))
                    
                    away = self.position.copy()
                    away.sub(barrier)
                    dist = distance(self.position, barrier)
                    
                    if dist < self.barrier_detection_radius:
                        away.normalize()
                        weight = 5.0 if (gx, gy) in self.barrier_memory else 3.0
                        if dist < 20:
                            weight *= 2.0
                            hit = True
                        away.mult(weight / max(dist, 1.0))
                        steer.add(away)
                        count += 1
        
        if hit:
            self.consecutive_barrier_hits += 1
            self.last_barrier_hit = 10
        else:
            self.consecutive_barrier_hits = max(0, self.consecutive_barrier_hits - 1)
        
        if count > 0:
            steer.div(count)
            if steer.mag() > 0:
                steer.normalize()
                steer.mult(self.max_speed * 1.5)
                steer.sub(self.velocity)
                steer.limit(self.max_force * 2.0)
        
        return steer
    
    def enforce_clockwise(self) -> Vector2:
        # Don't enforce direction if finished
        if self.has_finished:
            return Vector2(0, 0)
            
        if not self.track:
            return Vector2(0, 0)
        
        forward = self.track.get_forward_direction(self.position)
        
        if self.velocity.mag() > 0:
            vel_norm = self.velocity.copy()
            vel_norm.normalize()
            dot = vel_norm.x * forward.x + vel_norm.y * forward.y
            
            if dot < 0:
                self.wrong_direction_penalty += 1
                turn = Vector2(forward.x * self.max_speed, forward.y * self.max_speed)
                turn.sub(self.velocity)
                turn.limit(self.max_force * 2.0)
                return turn
            elif dot < 0.5:
                nudge = Vector2(forward.x * self.max_speed, forward.y * self.max_speed)
                nudge.sub(self.velocity)
                nudge.limit(self.max_force * 0.5)
                return nudge
        
        return Vector2(0, 0)
    
    def seek(self, target: Vector2) -> Vector2:
        desired = target.copy()
        desired.sub(self.position)
        if desired.mag() == 0:
            return Vector2(0, 0)
        desired.normalize()
        desired.mult(self.max_speed)
        steer = desired.copy()
        steer.sub(self.velocity)
        steer.limit(self.max_force)
        return steer
    
    def follow_path(self, pathfinder) -> Vector2:
        if not self.current_path:
            return Vector2(0, 0)
        
        next_point = None
        min_dist = float('inf')
        
        for point in self.current_path:
            point_vec = Vector2(point[0], point[1])
            dist = distance(self.position, point_vec)
            if dist < 40:
                continue
            elif dist < min_dist:
                min_dist = dist
                next_point = point_vec
        
        if next_point is None and self.target:
            return self.seek(self.target)
        
        return self.seek(next_point) if next_point else Vector2(0, 0)
    
    def apply_force(self, force: Vector2):
        self.acceleration.add(force)
    
    def update(self, bounds: Tuple[int, int], track=None):
        if self.last_barrier_hit > 0:
            self.last_barrier_hit -= 1
        
        old_pos = Vector2(self.position.x, self.position.y)
        
        self.velocity.add(self.acceleration)
        self.velocity.limit(self.max_speed)
        
        if self.velocity.mag() > 0:
            self.distance_traveled += self.velocity.mag()
        
        self.position.add(self.velocity)
        self.acceleration = Vector2(0, 0)
        
        # Update path history
        self.update_path_history()
        
        # Update distance for ranking (only if not finished)
        if self.ranking_manager and not self.has_finished:
            moved = distance(self.position, old_pos)
            self.ranking_manager.update_distance(self.horse_id, moved)
        
        # Boundary wrapping
        w, h = bounds
        if self.position.x < 0:
            self.position.x = w
        elif self.position.x > w:
            self.position.x = 0
        if self.position.y < 0:
            self.position.y = h
        elif self.position.y > h:
            self.position.y = 0
        
        # Track confinement (skip if finished)
        if track and hasattr(track, 'is_position_on_track') and not self.has_finished:
            if not track.is_position_on_track(self.position):
                nearest = track.get_nearest_track_position(self.position)
                if distance(self.position, nearest) > 50:
                    direction = nearest - self.position
                    if direction.mag() > 0:
                        direction.normalize()
                        self.velocity = direction * self.max_speed
    
    def draw(self, screen):
        # Draw path history (simplified - fewer points)
        if self.show_path and len(self.path_history) > 1:
            for i in range(0, len(self.path_history) - 1, 2):  # Skip every other point
                start = self.path_history[i]
                end = self.path_history[i + 1]
                alpha = int(100 + 155 * (i / len(self.path_history)))
                pygame.draw.line(screen, self.color,
                                (int(start[0]), int(start[1])),
                                (int(end[0]), int(end[1])), 1)
        
        # Draw horse - if finished, draw a special marker
        if self.has_finished:
            # Draw a "finished" marker (star or circle with F)
            pygame.draw.circle(screen, COLORS['YELLOW'], 
                              (int(self.position.x), int(self.position.y)), self.size + 5, 3)
            pygame.draw.circle(screen, self.color, 
                              (int(self.position.x), int(self.position.y)), self.size, 0)
            font = pygame.font.Font(None, 16)
            text = font.render("F", True, COLORS['BLACK'])
            text_rect = text.get_rect(center=(int(self.position.x), int(self.position.y)))
            screen.blit(text, text_rect)
            return
            
        if self.velocity.mag() < 0.1:
            return
            
        angle = math.atan2(self.velocity.y, self.velocity.x)
        tip = Vector2(self.size * 1.5 * math.cos(angle), self.size * 1.5 * math.sin(angle))
        left = Vector2(-self.size * math.cos(angle) + self.size * math.sin(angle),
                       -self.size * math.sin(angle) - self.size * math.cos(angle))
        right = Vector2(-self.size * math.cos(angle) - self.size * math.sin(angle),
                        -self.size * math.sin(angle) + self.size * math.cos(angle))
        
        tip.x += self.position.x
        tip.y += self.position.y
        left.x += self.position.x
        left.y += self.position.y
        right.x += self.position.x
        right.y += self.position.y
        
        points = [(int(tip.x), int(tip.y)), 
                  (int(left.x), int(left.y)), 
                  (int(right.x), int(right.y))]
        
        pygame.draw.polygon(screen, self.color, points)
        pygame.draw.polygon(screen, COLORS['BLACK'], points, 1)  # Thinner outline