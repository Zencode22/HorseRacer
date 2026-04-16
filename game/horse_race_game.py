# ============================================================================
# GAME CLASS - OPTIMIZED
# ============================================================================

import pygame
import math
import random
import time
from typing import List, Tuple
from config import NUM_HORSES, GOAL_RADIUS, HORSE_NAMES
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
        self.waiting_for_restart_decision = False
        self.should_quit = False
        
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
            horse.name = HORSE_NAMES[i] if i < len(HORSE_NAMES) else f"H{i+1}"
            
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
            self.ranking_manager.register_horse(horse.horse_id, horse.color, horse.name)
            horse.ranking_manager = self.ranking_manager
        
        # Game state
        self.paused = False  # Kept for internal use but not accessible to player
        self.show_debug = False  # Kept for internal use but not accessible
        self.selected_horse = None
        self.race_active = False
        self.race_finished = False
        self.finish_time = None
        
        # Results tracking
        self.finished_horses = []
        self.total_resets = 0
        
        # UI elements - only reset button
        self.buttons = []
        self._create_buttons()
        
        # Start race
        self.start_race()
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            
            if not self.paused and not self.race_finished and not self.waiting_for_restart_decision:
                self.update()
            
            self.draw()
            self.clock.tick(60)
    
    def _create_buttons(self):
        button_y = self.height - 35
        self.buttons = [
            {"rect": pygame.Rect(10, button_y, 90, 25), "text": "Reset Race", "action": "reset"},
        ]
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.should_quit = True
            elif event.type == pygame.KEYDOWN:
                if self.waiting_for_restart_decision:
                    # Only handle restart/quit keys
                    if event.key == pygame.K_r:
                        self.reset_race(is_manual_reset=True)
                        self.waiting_for_restart_decision = False
                    elif event.key == pygame.K_q:
                        self.running = False
                        self.should_quit = True
                else:
                    # Only allow R to reset during race
                    if event.key == pygame.K_r:
                        self.reset_race(is_manual_reset=True)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                
                # Check restart/quit buttons if waiting for decision
                if self.waiting_for_restart_decision:
                    for button in self.restart_buttons:
                        if button["rect"].collidepoint(mouse_pos):
                            self._handle_restart_action(button["action"])
                    continue
                
                # Check reset button
                for button in self.buttons:
                    if button["rect"].collidepoint(mouse_pos):
                        self._handle_button_action(button["action"])
                
                # Select horse by clicking
                if not self.race_finished:
                    for horse in self.horses:
                        dx = horse.position.x - mouse_pos[0]
                        dy = horse.position.y - mouse_pos[1]
                        if dx*dx + dy*dy < 900:  # 30^2
                            self.selected_horse = horse
                            break
    
    def _handle_button_action(self, action: str):
        if action == "reset":
            self.reset_race(is_manual_reset=True)
    
    def _handle_restart_action(self, action: str):
        """Handle restart/quit prompt actions"""
        if action == "restart":
            self.reset_race(is_manual_reset=True)
            self.waiting_for_restart_decision = False
        elif action == "quit":
            self.running = False
            self.should_quit = True
    
    def start_race(self):
        self.race_active = True
        self.race_finished = False
        self.finished_horses = []
        self.finish_time = None
        self.ranking_manager.start_race()
        for horse in self.horses:
            self.ranking_manager.start_lap(horse.horse_id)
    
    def reset_race(self, is_manual_reset=False):
        """Reset the race. is_manual_reset=True means user pressed reset button."""
        self.race_active = False
        self.race_finished = False
        self.finished_horses = []
        self.finish_time = None
        self.waiting_for_restart_decision = False
        self.selected_horse = None
        
        start_positions = self.track.get_spread_start_positions(NUM_HORSES)
        
        # Reset ranking manager stats if manual reset
        if is_manual_reset:
            self.ranking_manager.reset_all_stats()
            for horse in self.horses:
                self.ranking_manager.register_horse(horse.horse_id, horse.color, horse.name)
                horse.ranking_manager = self.ranking_manager
        
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
            
            # Reset horse's own attempt count and confidence
            horse.attempt_count = 0
            horse.confidence_score = 0.0
            
            if len(self.track.checkpoint_positions) > 0:
                horse.set_target(self.track.checkpoint_positions[0], self.track.pathfinder)
        
        self.start_race()
    
    def update(self):
        """Update game state"""
        if not self.race_active:
            self.start_race()
        
        for horse in self.horses:
            if horse.has_finished:
                continue
                
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished:
                continue
            
            horse.path_update_timer += 1
            if horse.path_update_timer >= horse.path_update_interval:
                if horse.target:
                    horse.request_new_path(self.track.pathfinder)
                horse.path_update_timer = 0
            
            horse.flock(self.horses, self.track.pathfinder)
            horse.update((self.width, self.height), self.track)
            
            if horse.has_finished and stats and not stats.finished:
                self.ranking_manager.finish_race(horse.horse_id)
        
        # Update finished horses list
        self.finished_horses = []
        for horse in self.horses:
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished and stats.finish_time:
                self.finished_horses.append((
                    horse.horse_id,
                    horse.name,
                    stats.finish_time,
                    stats.reset_count
                ))
        
        # Check if all horses have finished
        if len(self.finished_horses) >= NUM_HORSES and not self.race_finished:
            self.race_finished = True
            self.waiting_for_restart_decision = True
            self.finish_time = self.ranking_manager.get_race_time()
            self.finished_horses.sort(key=lambda x: x[2])  # Sort by finish time
            
            print("\n" + "="*60)
            print("RACE COMPLETE! All horses have finished!")
            print("="*60)
            for i, (hid, name, ftime, resets) in enumerate(self.finished_horses):
                print(f"{i+1}. {name} | {ftime:.2f}s | {resets} resets")
            print("="*60)
            print("\nClick RESTART to race again or QUIT to exit")
    
    def is_race_complete(self) -> bool:
        return self.race_finished
    
    def draw(self):
        """Draw everything"""
        self.track.draw(self.screen, show_ideal_path=False)
        
        for horse in self.horses:
            horse.draw(self.screen)
        
        self._draw_buttons()
        self._draw_status()
        self._draw_timer()
        
        if self.race_finished or self.waiting_for_restart_decision:
            self._draw_results_board()
        else:
            self._draw_rankings()
        
        if self.selected_horse and not self.race_finished and not self.waiting_for_restart_decision:
            self._draw_horse_info()
        
        pygame.display.flip()
    
    def _draw_buttons(self):
        for button in self.buttons:
            color = COLORS['GRAY']
            pygame.draw.rect(self.screen, color, button["rect"])
            pygame.draw.rect(self.screen, COLORS['BLACK'], button["rect"], 2)
            
            text = self.font.render(button["text"], True, COLORS['WHITE'])
            text_rect = text.get_rect(center=button["rect"].center)
            self.screen.blit(text, text_rect)
    
    def _draw_status(self):
        status = f"Horses: {len(self.horses)} | FPS: {int(self.clock.get_fps())}"
        if self.race_finished:
            status += " | RACE COMPLETE"
        elif not self.waiting_for_restart_decision:
            finished_count = sum(1 for horse in self.horses if horse.has_finished)
            status += f" | Finished: {finished_count}/{NUM_HORSES}"
        
        text = self.font.render(status, True, COLORS['WHITE'])
        self.screen.blit(text, (10, 10))
    
    def _draw_timer(self):
        if self.race_finished:
            if self.finish_time:
                mins = int(self.finish_time // 60)
                secs = int(self.finish_time % 60)
                ms = int((self.finish_time * 100) % 100)
                time_str = f"{secs}.{ms:02d}s" if mins == 0 else f"{mins}:{secs:02d}.{ms:02d}"
            else:
                time_str = "0.00s"
            color = COLORS['GREEN']
        else:
            race_time = self.ranking_manager.get_race_time()
            mins = int(race_time // 60)
            secs = int(race_time % 60)
            ms = int((race_time * 100) % 100)
            time_str = f"{secs}.{ms:02d}s" if mins == 0 else f"{mins}:{secs:02d}.{ms:02d}"
            color = COLORS['YELLOW']
        
        surf = self.timer_font.render(time_str, True, color)
        rect = surf.get_rect(center=(self.width//2, 35))
        
        pygame.draw.rect(self.screen, COLORS['BLACK'], rect.inflate(15, 8))
        pygame.draw.rect(self.screen, COLORS['GRAY'], rect.inflate(15, 8), 2)
        self.screen.blit(surf, rect)
    
    def _draw_results_board(self):
        panel_width = 450
        panel_height = 450
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2
        
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(180)
        overlay.fill(COLORS['BLACK'])
        self.screen.blit(overlay, (0, 0))
        
        panel = pygame.Surface((panel_width, panel_height))
        panel.set_alpha(240)
        panel.fill(COLORS['DARK_BROWN'])
        self.screen.blit(panel, (panel_x, panel_y))
        
        pygame.draw.rect(self.screen, COLORS['YELLOW'], 
                        (panel_x, panel_y, panel_width, panel_height), 4)
        
        title = self.big_font.render("RACE RESULTS", True, COLORS['YELLOW'])
        title_rect = title.get_rect(center=(self.width//2, panel_y + 50))
        self.screen.blit(title, title_rect)
        
        if self.finish_time:
            time_text = self.large_font.render(f"Race Time: {self.finish_time:.2f} seconds", True, COLORS['WHITE'])
            time_rect = time_text.get_rect(center=(self.width//2, panel_y + 90))
            self.screen.blit(time_text, time_rect)
        
        headers = ["Pos", "Horse", "Time", "Resets"]
        x_positions = [panel_x + 60, panel_x + 140, panel_x + 220, panel_x + 320]
        
        for i, header in enumerate(headers):
            text = self.font.render(header, True, COLORS['YELLOW'])
            self.screen.blit(text, (x_positions[i], panel_y + 120))
        
        pygame.draw.line(self.screen, COLORS['GRAY'],
                        (panel_x + 30, panel_y + 140),
                        (panel_x + panel_width - 30, panel_y + 140), 2)
        
        y = panel_y + 160
        for i, (horse_id, name, finish_time, resets) in enumerate(self.finished_horses):
            stats = self.ranking_manager.get_horse_stats(horse_id)
            color = stats.color if stats else COLORS['WHITE']
            
            pos_text = f"{i+1}."
            time_str = f"{finish_time:.2f}s"
            
            self.screen.blit(self.font.render(pos_text, True, COLORS['WHITE']), (x_positions[0], y))
            self.screen.blit(self.font.render(name, True, color), (x_positions[1], y))
            self.screen.blit(self.font.render(time_str, True, COLORS['WHITE']), (x_positions[2], y))
            self.screen.blit(self.font.render(str(resets), True, COLORS['WHITE']), (x_positions[3], y))
            
            y += 25
        
        if self.waiting_for_restart_decision:
            button_width = 120
            button_height = 40
            button_spacing = 40
            
            restart_btn_x = panel_x + panel_width//2 - button_width - button_spacing//2
            quit_btn_x = panel_x + panel_width//2 + button_spacing//2
            button_y = panel_y + panel_height - 70
            
            self.restart_buttons = [
                {"rect": pygame.Rect(restart_btn_x, button_y, button_width, button_height), 
                 "text": "RESTART (R)", "action": "restart"},
                {"rect": pygame.Rect(quit_btn_x, button_y, button_width, button_height), 
                 "text": "QUIT (Q)", "action": "quit"},
            ]
            
            for button in self.restart_buttons:
                pygame.draw.rect(self.screen, COLORS['GREEN'] if button["action"] == "restart" else COLORS['RED'], button["rect"])
                pygame.draw.rect(self.screen, COLORS['WHITE'], button["rect"], 2)
                
                text = self.font.render(button["text"], True, COLORS['WHITE'])
                text_rect = text.get_rect(center=button["rect"].center)
                self.screen.blit(text, text_rect)
        else:
            inst_text = self.font.render("Press R to restart or Q to quit", True, COLORS['WHITE'])
            inst_rect = inst_text.get_rect(center=(self.width//2, panel_y + panel_height - 30))
            self.screen.blit(inst_text, inst_rect)
    
    def _draw_rankings(self):
        panel_width = 280
        panel_x = self.width - panel_width - 15
        panel_y = 70
        
        row_height = 22
        header_height = 60
        footer_height = 30
        total_height = header_height + (len(self.horses) * row_height) + footer_height
        panel_height = min(total_height, self.height - 100)
        
        if len(self.horses) > 8:
            current_font = pygame.font.Font(None, 16)
            row_height = 18
        else:
            current_font = self.font
            row_height = 22
        
        panel = pygame.Surface((panel_width, panel_height))
        panel.set_alpha(200)
        panel.fill(COLORS['BLACK'])
        self.screen.blit(panel, (panel_x, panel_y))
        
        title_font = pygame.font.Font(None, 24)
        title = "LIVE RANKINGS"
        text = title_font.render(title, True, COLORS['YELLOW'])
        self.screen.blit(text, (panel_x + 15, panel_y + 10))
        
        header_font = pygame.font.Font(None, 16)
        headers = ["Pos", "Horse", "Time", "Resets"]
        x_pos = [panel_x + 15, panel_x + 75, panel_x + 145, panel_x + 220]
        
        for i, h in enumerate(headers):
            t = header_font.render(h, True, COLORS['GRAY'])
            self.screen.blit(t, (x_pos[i], panel_y + 35))
        
        pygame.draw.line(self.screen, COLORS['GRAY'], 
                        (panel_x + 10, panel_y + 50), 
                        (panel_x + panel_width - 10, panel_y + 50), 1)
        
        y = panel_y + 55
        
        def sort_key(horse):
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if stats and stats.finished and stats.finish_time is not None:
                return (0, stats.finish_time, horse.horse_id)
            else:
                return (1, -horse.current_checkpoint_index, horse.horse_id)
        
        sorted_horses = sorted(self.horses, key=sort_key)
        
        max_visible = min(len(sorted_horses), (panel_height - 80) // row_height)
        visible_horses = sorted_horses[:max_visible]
        
        for i, horse in enumerate(visible_horses):
            stats = self.ranking_manager.get_horse_stats(horse.horse_id)
            if not stats:
                continue
            
            rank = i + 1
            rank_display = f"{rank}"
            
            if stats.finished and stats.finish_time is not None:
                time_disp = f"{stats.finish_time:.2f}s"
                time_color = COLORS['GREEN']
            else:
                time_disp = "---"
                time_color = COLORS['GRAY']
            
            color = horse.color
            if self.selected_horse == horse:
                pygame.draw.rect(self.screen, (80, 80, 100), 
                               (panel_x + 5, y - 2, panel_width - 10, row_height))
                color = COLORS['YELLOW']
            
            if len(self.horses) > 8:
                text_surf = pygame.font.Font(None, 16)
            else:
                text_surf = self.font
            
            self.screen.blit(text_surf.render(rank_display, True, COLORS['WHITE']), (x_pos[0], y))
            self.screen.blit(text_surf.render(horse.name, True, color), (x_pos[1], y))
            self.screen.blit(text_surf.render(time_disp, True, time_color), (x_pos[2], y))
            self.screen.blit(text_surf.render(str(stats.reset_count), True, COLORS['WHITE']), (x_pos[3], y))
            
            y += row_height
        
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
            f"{horse.name} - {status}",
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