#!/usr/bin/env python3
# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

import pygame
import sys

# Initialize pygame first
pygame.init()

# Import config
from config import WIDTH, HEIGHT, FULLSCREEN, NUM_HORSES, FPS
from game.horse_race_game import HorseRaceGame


def main():
    """Main entry point - mouse-only controls with R key for reset"""
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    current_width, current_height = WIDTH, HEIGHT
    
    pygame.display.set_caption("Horse Race Derby")
    
    # Show welcome message
    print("=" * 60)
    print("HORSE RACE DERBY")
    print("=" * 60)
    print(f"\nScreen size: {current_width} x {current_height}")
    print("\nControls:")
    print("  Mouse Click - Select a horse")
    print("  R Key       - Reset race")
    print("  Reset Button - Click to reset race")
    print("\nThe race will start automatically!")
    print("First horse to complete 1 lap wins!")
    print("-" * 60)
    
    try:
        game = HorseRaceGame(screen, current_width, current_height)
        
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if game.waiting_for_restart_decision:
                        if event.key == pygame.K_r:
                            game.reset_race(is_manual_reset=True)
                            game.waiting_for_restart_decision = False
                        elif event.key == pygame.K_q:
                            running = False
                    else:
                        if event.key == pygame.K_r:
                            game.reset_race(is_manual_reset=True)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    
                    if game.waiting_for_restart_decision:
                        for button in game.restart_buttons:
                            if button["rect"].collidepoint(mouse_pos):
                                game._handle_restart_action(button["action"])
                                if button["action"] == "quit":
                                    running = False
                    else:
                        for button in game.buttons:
                            if button["rect"].collidepoint(mouse_pos):
                                game._handle_button_action(button["action"])
                        
                        if not game.race_finished:
                            for horse in game.horses:
                                dx = horse.position.x - mouse_pos[0]
                                dy = horse.position.y - mouse_pos[1]
                                if dx*dx + dy*dy < 900:
                                    game.selected_horse = horse
                                    break
            
            if game.should_quit:
                running = False
            
            if not game.paused and not game.race_finished and not game.waiting_for_restart_decision:
                game.update()
            
            game.draw()
            game.clock.tick(FPS)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        pygame.quit()
        print("\nThanks for watching the Horse Race Derby!")


if __name__ == "__main__":
    main()