# ============================================================================
# GAME CLASS - OPTIMIZED
# ============================================================================

import pygame
import math
import random
import time
from typing import List, Tuple
from config import NUM_HORSES, GOAL_RADIUS
from utils.colors import COLORS
from models.vector2 import Vector2, distance
from models.horse import Horse
from track.race_track import RaceTrack
from models.ranking import RankingManager

class HorseRaceGame:
    """Optimized main game class"""
    
    def __init__(self, screen, width, height):
        self.screen = screen
        self.width = width
        self.height = height
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Fonts
        self.font = pygame.font.Font(None, 20)
        self.large_font = pygame.font.Font(None, 30)
        self.timer_font = pygame.font.Font(None, 42)
        self.results_font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 60)
        
        # Create track
        self.track = RaceTrack(self.width, self.height)
        
        # Create horses
        self.horses = []
        colors = [COLORS['RED'], COLORS['BLUE'], COLORS['YELLOW'], 
                  COLORS['PURPLE'], COLORS['ORANGE'], COLORS['WHITE']]
        
        start_positions = self.track.get_spread_start_positions(NUM_HORSES)
        
        for i in range(NUM_HORSES):
            start_pos = start_positions[i]
            horse = Horse(start_pos.x, start_pos.y, colors[i % len(colors)])
            
            # Set initial target to START checkpoint (index 0)
            if len(self.track.checkpoint_positions) > 0:
                horse.set_target(self.track.checkpoint_positions[0], self.track.pathfinder)
            
            forward = self.track.get_forward_direction(start_pos)
            horse.velocity = Vector2(forward.x * 2.0, forward.y * 2.0)
            horse.track = self.track
            
            # Set total checkpoints from track
            horse.total_checkpoints = self.track.get_total_checkpoints()
            self.horses.append(horse)
        
        # Ranking system
        self.ranking_manager = RankingManager()
        for horse in self.horses:
            self.ranking_manager.register_horse(horse.horse_id, horse.color)
            horse.ranking_manager = self.ranking_manager
        
        # Game state
        self.paused = False
        self.show_debug = False
        self.selected_horse = None
        self.race_active = False
        self.race_finished = False
        self.finish_time = None  # Time when race completed
        
        # Results tracking
        self.finished_horses = []  # List of (horse_id, finish_time, path_percentage, resets) in order
        
        # Reset tracking
        self.total_resets = 0
        
        # UI elements
        self.buttons = []
        self._create_buttons()
        
        # Start race
        self.start_race()
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            
            if not self.paused and not self.race_finished:
                self.update()
            
            self.draw()
            self.clock.tick(60)  # Hardcoded FPS instead of importing
    
    def _create_buttons(self):
        button_y = self.height - 35
        self.buttons = [
            {"rect": pygame.Rect(10, button_y, 70, 25), "text": "Pause", "action": "pause"},
            {"rect": pygame.Rect(90, button_y, 90, 25), "text": "Debug", "action": "debug"},
            {"rect": pygame.Rect(190, button_y, 90, 25), "text": "Reset", "action": "reset"},
        ]
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.toggle_pause()
                elif event.key == pygame.K_d:
                    self.show_debug = not self.show_debug
                elif event.key == pygame.K_r:
                    self.reset_race()
                elif event.key == pygame.K_ESCAPE:
                    self.selected_horse = None
                elif event.key == pygame.K_q:
                    self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                for button in self.buttons:
                    if button["rect"].collidepoint(mouse_pos):
                        self._handle_button_action(button["action"])
                
                # Select horse (only if race isn't finished)
                if not self.race_finished:
                    for horse in self.horses:
                        dx = horse.position.x - mouse_pos[0]
                        dy = horse.position.y - mouse_pos[1]
                        if dx*dx + dy*dy < 900:  # 30^2
                            self.selected_horse = horse
                            break
    
    def _handle_button_action(self, action: str):
        if action == "pause":
            self.toggle_pause()
        elif action == "debug":
            self.show_debug = not self.show_debug
        elif action == "reset":
            self.reset_race()
    
    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.ranking_manager.pause_race()
        else:
            self.ranking_manager.resume_race()
    
    def start_race(self):
        self.race_active = True
        self.race_finished = False
        self.finished_horses = []
        self.finish_time = None
        self.ranking_manager.start_race()
        for horse in self.horses:
            self.ranking_manager.start_lap(horse.horse_id)
    
    def reset_race(self):
        self.race_active = False
        self.race_finished = False
        self.paused = False
        self.finished_horses = []
        self.finish_time = None
        
        start_positions = self.track.get_spread_start_positions(NUM_HORSES)
        
        for i, horse in enumerate(self.horses):
            start_pos = start_positions[i]
            horse.position = start_pos
            
            forward = self.track.get_forward_direction(start_pos)
            horse.velocity = Vector2(forward.x * 2.0, forward.y * 2.0)
            
            # Reset horse state
            horse.has_finished = False
            horse.current_checkpoint_index = 0
            horse.checkpoint_reached_time = 0
            horse.checkpoints_visited = []
            horse.barrier_memory.clear()
            horse.consecutive_barrier_hits = 0
            horse.stuck_timer = 0
            horse.last_position = Vector2(start_pos.x, start_pos.y)
            horse.reset_cooldown = 0
            horse.clockwise_history.clear()
            horse.wrong_direction_penalty = 0
            horse.path_history.clear()
            
            if len(self.track.checkpoint_positions) > 0:
                horse.set_target(self.track.checkpoint_positions[0], self.track.pathfinder)
        
        self.start_race()
    
    def update(self):
        """Update game state"""
        if not self.race_active:
            self.start_race()
        
        for horse in self.horses:
            # Skip if horse has already finished
            if horse.has_finished:
                continue
                
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished:
                continue
            
            # Update pathfinding less frequently
            horse.path_update_timer += 1
            if horse.path_update_timer >= horse.path_update_interval:
                if horse.target:
                    horse.request_new_path(self.track.pathfinder)
                horse.path_update_timer = 0
            
            horse.flock(self.horses, self.track.pathfinder)
            horse.update((self.width, self.height), self.track)
            
            # Check if horse just finished (has_finished flag set but stats not yet updated)
            if horse.has_finished and stats and not stats.finished:
                # This ensures the finish time is recorded
                self.ranking_manager.finish_race(horse.horse_id)
        
        # Update finished horses list from horses that have finished
        self.finished_horses = []
        for horse in self.horses:
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished and stats.finish_time:
                self.finished_horses.append((
                    horse.horse_id,
                    stats.finish_time,
                    0,  # No path percentage
                    stats.reset_count
                ))
        
        # Check if all horses have finished
        if len(self.finished_horses) >= NUM_HORSES and not self.race_finished:
            self.race_finished = True
            # Capture final race time BEFORE pausing
            self.finish_time = self.ranking_manager.get_race_time()
            # Sort finished horses by finish time
            self.finished_horses.sort(key=lambda x: x[1])  # Sort by time
            
            print("\n" + "="*60)
            print("RACE COMPLETE! All horses have finished!")
            print("="*60)
            for i, (hid, ftime, _, resets) in enumerate(self.finished_horses):
                print(f"{i+1}. Horse {hid} | {ftime:.2f}s | {resets} resets")
            print("="*60)
            
            # Automatically pause the game when race is complete
            self.paused = True
    
    def is_race_complete(self) -> bool:
        """Check if the race is complete (all horses finished)"""
        return self.race_finished
    
    def draw(self):
        """Draw everything"""
        # Draw track
        self.track.draw(self.screen, show_ideal_path=False)
        
        # Draw horses
        for horse in self.horses:
            horse.draw(self.screen)
        
        # Draw UI elements (always)
        self._draw_buttons()
        self._draw_status()
        self._draw_timer()
        
        # Draw rankings or results
        if self.race_finished:
            self._draw_results_board()
        else:
            self._draw_rankings()
        
        # Draw selected horse info (only if race isn't finished)
        if self.selected_horse and not self.show_debug and not self.race_finished:
            self._draw_horse_info()
        
        # Draw pause indicator
        if self.paused:
            self._draw_pause()
        
        pygame.display.flip()
    
    def _draw_buttons(self):
        for button in self.buttons:
            color = COLORS['GREEN'] if button["text"] == "Pause" and self.paused else COLORS['GRAY']
            pygame.draw.rect(self.screen, color, button["rect"])
            pygame.draw.rect(self.screen, COLORS['BLACK'], button["rect"], 2)
            
            text_str = "Resume" if button["text"] == "Pause" and self.paused else button["text"]
            text = self.font.render(text_str, True, COLORS['WHITE'])
            text_rect = text.get_rect(center=button["rect"].center)
            self.screen.blit(text, text_rect)
    
    def _draw_status(self):
        status = f"Horses: {len(self.horses)} | FPS: {int(self.clock.get_fps())}"
        if self.paused:
            status += " | PAUSED"
        if self.race_finished:
            status += " | RACE COMPLETE"
        else:
            finished_count = sum(1 for horse in self.horses if horse.has_finished)
            status += f" | Finished: {finished_count}/{NUM_HORSES}"
        
        text = self.font.render(status, True, COLORS['WHITE'])
        self.screen.blit(text, (10, 10))
    
    def _draw_timer(self):
        """Draw the race timer - stops when race is complete"""
        if self.race_finished:
            # Show final time when race is complete
            if self.finish_time:
                mins = int(self.finish_time // 60)
                secs = int(self.finish_time % 60)
                ms = int((self.finish_time * 100) % 100)
                time_str = f"{secs}.{ms:02d}s" if mins == 0 else f"{mins}:{secs:02d}.{ms:02d}"
            else:
                time_str = "0.00s"
            color = COLORS['GREEN']
        else:
            # Show running time
            race_time = self.ranking_manager.get_race_time()
            mins = int(race_time // 60)
            secs = int(race_time % 60)
            ms = int((race_time * 100) % 100)
            time_str = f"{secs}.{ms:02d}s" if mins == 0 else f"{mins}:{secs:02d}.{ms:02d}"
            color = COLORS['RED'] if self.paused else COLORS['YELLOW']
        
        surf = self.timer_font.render(time_str, True, color)
        rect = surf.get_rect(center=(self.width//2, 35))
        
        pygame.draw.rect(self.screen, COLORS['BLACK'], rect.inflate(15, 8))
        pygame.draw.rect(self.screen, COLORS['GRAY'], rect.inflate(15, 8), 2)
        self.screen.blit(surf, rect)
    
    def _draw_results_board(self):
        """Draw the final results board when race is complete"""
        panel_width = 450
        panel_height = 400
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2
        
        # Semi-transparent background
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(180)
        overlay.fill(COLORS['BLACK'])
        self.screen.blit(overlay, (0, 0))
        
        # Results panel
        panel = pygame.Surface((panel_width, panel_height))
        panel.set_alpha(240)
        panel.fill(COLORS['DARK_BROWN'])
        self.screen.blit(panel, (panel_x, panel_y))
        
        # Border
        pygame.draw.rect(self.screen, COLORS['YELLOW'], 
                        (panel_x, panel_y, panel_width, panel_height), 4)
        
        # Title
        title = self.big_font.render("RACE RESULTS", True, COLORS['YELLOW'])
        title_rect = title.get_rect(center=(self.width//2, panel_y + 50))
        self.screen.blit(title, title_rect)
        
        # Race time
        if self.finish_time:
            time_text = self.large_font.render(f"Race Time: {self.finish_time:.2f} seconds", True, COLORS['WHITE'])
            time_rect = time_text.get_rect(center=(self.width//2, panel_y + 90))
            self.screen.blit(time_text, time_rect)
        
        # Column headers
        headers = ["Pos", "Horse", "Time", "Resets"]
        x_positions = [panel_x + 60, panel_x + 140, panel_x + 220, panel_x + 320]
        
        for i, header in enumerate(headers):
            text = self.font.render(header, True, COLORS['YELLOW'])
            self.screen.blit(text, (x_positions[i], panel_y + 120))
        
        # Draw separator line
        pygame.draw.line(self.screen, COLORS['GRAY'],
                        (panel_x + 30, panel_y + 140),
                        (panel_x + panel_width - 30, panel_y + 140), 2)
        
        # Draw results
        y = panel_y + 160
        for i, (horse_id, finish_time, _, resets) in enumerate(self.finished_horses):
            # Get horse color
            stats = self.ranking_manager.get_horse_stats(horse_id)
            color = stats.color if stats else COLORS['WHITE']
            
            # Use numerical position
            pos_text = f"{i+1}."
            
            # Format time
            time_str = f"{finish_time:.2f}s"
            
            # Draw row
            self.screen.blit(self.font.render(pos_text, True, COLORS['WHITE']), (x_positions[0], y))
            self.screen.blit(self.font.render(f"{horse_id}", True, color), (x_positions[1], y))
            self.screen.blit(self.font.render(time_str, True, COLORS['WHITE']), (x_positions[2], y))
            self.screen.blit(self.font.render(str(resets), True, COLORS['WHITE']), (x_positions[3], y))
            
            y += 25
        
        # Instructions
        inst_text = self.font.render("Press R to restart or Q to quit", True, COLORS['WHITE'])
        inst_rect = inst_text.get_rect(center=(self.width//2, panel_y + panel_height - 30))
        self.screen.blit(inst_text, inst_rect)
    
    def _draw_rankings(self):
        """Draw rankings panel on the right side of screen - shows ALL horses with completion times"""
        panel_width = 280
        panel_x = self.width - panel_width - 15
        panel_y = 70
        
        # Calculate dynamic height based on number of horses
        row_height = 22
        header_height = 60
        footer_height = 30
        total_height = header_height + (len(self.horses) * row_height) + footer_height
        panel_height = min(total_height, self.height - 100)
        
        # Use smaller font if many horses
        if len(self.horses) > 8:
            current_font = pygame.font.Font(None, 16)
            row_height = 18
        else:
            current_font = self.font
            row_height = 22
        
        # Panel background
        panel = pygame.Surface((panel_width, panel_height))
        panel.set_alpha(200)
        panel.fill(COLORS['BLACK'])
        self.screen.blit(panel, (panel_x, panel_y))
        
        # Title
        title_font = pygame.font.Font(None, 24)
        title = "LIVE RANKINGS"
        text = title_font.render(title, True, COLORS['YELLOW'])
        self.screen.blit(text, (panel_x + 15, panel_y + 10))
        
        # Headers - simplified to show time only
        header_font = pygame.font.Font(None, 16)
        headers = ["Pos", "Horse", "Time", "Resets"]
        x_pos = [panel_x + 15, panel_x + 75, panel_x + 145, panel_x + 220]
        
        for i, h in enumerate(headers):
            t = header_font.render(h, True, COLORS['GRAY'])
            self.screen.blit(t, (x_pos[i], panel_y + 35))
        
        pygame.draw.line(self.screen, COLORS['GRAY'], 
                        (panel_x + 10, panel_y + 50), 
                        (panel_x + panel_width - 10, panel_y + 50), 1)
        
        # Rankings - show ALL horses, sorted by finish time and checkpoint progress
        y = panel_y + 55
        
        # Sort horses: finished horses first (by finish time), then by checkpoint progress
        def sort_key(horse):
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished and stats.finish_time is not None:
                # Finished horses: use finish time (lower is better)
                return (0, stats.finish_time, horse.horse_id)
            else:
                # Not finished: use negative checkpoint progress (higher is better)
                return (1, -horse.current_checkpoint_index, horse.horse_id)
        
        sorted_horses = sorted(self.horses, key=sort_key)
        
        # Determine scroll if needed (simple - show all, but cap height)
        max_visible = min(len(sorted_horses), (panel_height - 80) // row_height)
        visible_horses = sorted_horses[:max_visible]
        
        for i, horse in enumerate(visible_horses):
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if not stats:
                continue
            
            # Rank number (actual position in race)
            rank = i + 1
            
            # Display rank
            rank_display = f"{rank}"
            
            # Time display - show completion time for finished horses
            if stats.finished and stats.finish_time is not None:
                # Show the actual finish time
                time_disp = f"{stats.finish_time:.2f}s"
                time_color = COLORS['GREEN']  # Green for finished horses
            else:
                # Show "---" for horses still racing
                time_disp = "---"
                time_color = COLORS['GRAY']  # Gray for unfinished
            
            # Draw row with highlighting for selected horse
            color = horse.color
            if self.selected_horse == horse:
                # Highlight selected horse
                pygame.draw.rect(self.screen, (80, 80, 100), 
                               (panel_x + 5, y - 2, panel_width - 10, row_height))
                color = COLORS['YELLOW']
            
            # Use appropriate font size
            if len(self.horses) > 8:
                text_surf = pygame.font.Font(None, 16)
            else:
                text_surf = self.font
            
            self.screen.blit(text_surf.render(rank_display, True, COLORS['WHITE']), (x_pos[0], y))
            self.screen.blit(text_surf.render(f"{horse.horse_id}", True, color), (x_pos[1], y))
            self.screen.blit(text_surf.render(time_disp, True, time_color), (x_pos[2], y))
            self.screen.blit(text_surf.render(str(stats.reset_count), True, COLORS['WHITE']), (x_pos[3], y))
            
            y += row_height
        
        # Finished count
        finished_count = sum(1 for horse in self.horses if horse.has_finished)
        finished_text = f"Finished: {finished_count}/{NUM_HORSES}"
        self.screen.blit(header_font.render(finished_text, True, COLORS['WHITE']), 
                        (panel_x + 15, panel_y + panel_height - 25))
    
    def _draw_horse_info(self):
        if not self.selected_horse:
            return
        
        horse = self.selected_horse
        stats = self.ranking_manager.get_horse_stats(horse.horse_id)
        if not stats:
            return
        
        panel = pygame.Surface((250, 160))
        panel.set_alpha(200)
        panel.fill(COLORS['BLACK'])
        self.screen.blit(panel, (15, 70))
        
        y = 85
        status = "FINISHED" if horse.has_finished else "RACING"
        info = [
            f"Horse {horse.horse_id} - {status}",
            f"Speed: {horse.velocity.mag():.1f}",
            f"Checkpoint: {horse.current_checkpoint_index + 1}/{horse.total_checkpoints}",
            f"Resets: {stats.reset_count}",
        ]
        
        if horse.has_finished and stats.finish_time:
            info.append(f"Finish Time: {stats.finish_time:.2f}s")
        
        for line in info:
            t = self.font.render(line, True, horse.color)
            self.screen.blit(t, (25, y))
            y += 20
    
    def _draw_pause(self):
        text = self.large_font.render("PAUSED", True, COLORS['WHITE'])
        rect = text.get_rect(center=(self.width//2, 90))
        pygame.draw.rect(self.screen, COLORS['BLACK'], rect.inflate(15, 8))
        pygame.draw.rect(self.screen, COLORS['RED'], rect.inflate(15, 8), 2)
        self.screen.blit(text, rect)