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
    """Main entry point - no terminal controls needed"""
    
    # Always use windowed mode to ensure borders are visible
    # Ignore FULLSCREEN flag to keep windowed mode
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    current_width, current_height = WIDTH, HEIGHT
    
    pygame.display.set_caption("Horse Race Simulator")
    
    # Show welcome message
    print("=" * 60)
    print("HORSE RACE SIMULATOR")
    print("=" * 60)
    print(f"\nScreen size: {current_width} x {current_height}")
    print("\nGame Controls:")
    print("  SPACE      - Pause/Resume race")
    print("  R          - Reset race")
    print("  D          - Toggle debug view")
    print("  Mouse Click - Select a horse")
    print("  ESC        - Deselect horse")
    print("  Q          - Quit game")
    print("\nThe race will start automatically!")
    print("The game will end when all horses complete 1 lap!")
    print("-" * 60)
    
    # Create and run the game
    try:
        game = HorseRaceGame(screen, current_width, current_height)
        
        # Modified game loop
        running = True
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_r:
                        game.reset_race()
                    elif event.key == pygame.K_SPACE:
                        game.toggle_pause()
                    elif event.key == pygame.K_d:
                        game.show_debug = not game.show_debug
                    elif event.key == pygame.K_ESCAPE:
                        game.selected_horse = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    for button in game.buttons:
                        if button["rect"].collidepoint(mouse_pos):
                            game._handle_button_action(button["action"])
                    
                    # Select horse (only if race isn't finished)
                    if not game.race_finished:
                        for horse in game.horses:
                            dx = horse.position.x - mouse_pos[0]
                            dy = horse.position.y - mouse_pos[1]
                            if dx*dx + dy*dy < 900:  # 30^2
                                game.selected_horse = horse
                                break
            
            # Update game state if not paused and race not complete
            if not game.paused and not game.race_finished:
                game.update()
            
            # Draw everything
            game.draw()
            game.clock.tick(FPS)
            
            # Check if race is complete and all horses have finished
            if game.race_finished and len(game.finished_horses) >= NUM_HORSES:
                # Keep displaying results for a few seconds then exit
                pygame.display.set_caption("Race Complete! - Horse Race Simulator")
                pygame.time.wait(5000)  # Wait 5 seconds to show results
                
                # Print final summary with numerical rankings
                print("\n" + "="*60)
                print("FINAL RACE RESULTS")
                print("="*60)
                for i, (hid, ftime, _, resets) in enumerate(game.finished_horses):
                    print(f"{i+1:2d}. Horse {hid:2d} | {ftime:7.2f}s | tries {resets}")
                print("="*60)
                print("\nRace complete! Thanks for playing!")
                
                running = False
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        pygame.quit()
        print("\n[SYSTEM] Race simulation ended. Thanks for watching!")


if __name__ == "__main__":
    main()