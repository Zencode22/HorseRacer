// ============================================================================
// CONFIGURATION - port of config.py (browser version)
// ============================================================================

export const WIDTH = 1280;
export const HEIGHT = 720;
export const UI_HEIGHT = 340;               // betting / stats panel below canvas
export const CANVAS_HEIGHT = HEIGHT + UI_HEIGHT;
export const FPS = 60;
export const NUM_HORSES = 6;
export const TRACK_WIDTH = 90;
export const GOAL_RADIUS = 50;

// Horse names - Derby themed
export const HORSE_NAMES = [
  'DASHER', // Fast runner
  'BOLTO',  // Lightning bolt
  'STORM',  // Storm runner
  'FLASH',  // Quick flash
  'RACER',  // Pure racer
  'ZIPPY',  // Quick and zippy
];

export const COLORS = {
  BLACK: '#000000',
  WHITE: '#ffffff',
  GREEN: '#228b22',
  DARK_GREEN: '#006400',
  BROWN: '#8b4513',
  GRAY: '#808080',
  RED: '#ff3b30',
  BLUE: '#3b82f6',
  YELLOW: '#ffd60a',
  PURPLE: '#a855f7',
  ORANGE: '#ff9500',
  LIGHT_BROWN: '#deb887',
  DARK_BROWN: '#654321',
  WOOD: '#a0522d',
};

// Betting system
export const STARTING_BALANCE = 500;
export const BET_CHIP_VALUES = [10, 25, 50, 100];

// Learning / memory persistence
export const MEMORY_KEY = 'horseDerbyMemory';       // horse memories (localStorage)
export const BALANCE_KEY = 'horseDerbyBalance';     // player bankroll (sessionStorage: wiped on exit)
