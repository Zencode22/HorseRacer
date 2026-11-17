# 🏇 Horse Racer - A* Pathfinding & Flocking Simulation (HTML Browser Edition)

An **HTML5 / JavaScript** browser game featuring autonomous AI horses that navigate a square race track using A* pathfinding and Boids flocking algorithms. Watch six uniquely named horses compete, learn from their past runs, place bets with fake money, and race to the finish — all inside your web browser. No Python, no installs, no dependencies.

> This project was rewritten from the original pygame desktop game into a pure web application. The old Python source is preserved in `legacy_python/` for reference only.

---

## 🎮 Quick Start

```bash
# Option 1: just open the file
open web/index.html          # macOS
xdg-open web/index.html      # Linux
start web\index.html         # Windows

# Option 2: serve it (recommended - ES modules need http:// in some browsers)
python3 -m http.server 8000 --directory web
# then visit http://localhost:8000
```

**Requirements:** Any modern browser (Chrome, Firefox, Safari, Edge). That's it.

### Page load performance

The page paints instantly: a loading overlay appears immediately and the game
boots in a deferred macrotask, with heavy setup (pathfinding cache priming and
static track pre-render) moved to **after the first frame**. A* now uses a
binary-heap priority queue over typed-array buffers with a per-search
wall-clock budget and straight-line fallback, so no single computation can
block the main thread. Measured: constructor ≈3 ms, 120 idle frames ≈12 ms,
full race loop <200 ms headless — versus multi-minute freezes before this fix.

---

## 🕹️ Controls

| Input | Action |
|-------|--------|
| **Mouse Click on a horse** (betting phase) | Place a chip bet on that horse |
| **+ / − buttons** | Add / remove bets per horse |
| **START RACE button** or **SPACE** | Begin the race |
| **R Key** | Reset the current race to the start line |
| **NEXT RACE NOW** button | Skip the results board, return to betting |
| **Chip size selector** | Choose $10 / $25 / $50 / $100 chips |
| **Wipe All Horse Memory** | Make every horse forget its past runs |

---

## 🏁 How It Works

Each meeting follows a loop: **Betting → Racing → Results → repeat.**

Six horses start staggered along the right side of a square track and must navigate **9 checkpoints** in clockwise order to complete one lap. Each horse is an independent AI agent that:

- Builds an **A* path** from its current position to the next checkpoint
- Uses **flocking behaviors** to avoid collisions with other horses
- **Remembers barriers** it hits to avoid them in future attempts
- **Remembers every past race** (times, best racing lines) via `localStorage` and gets faster with experience
- **Auto-resets** if it gets stuck or goes the wrong way

The race ends when all horses finish; results are shown on screen and winnings are paid out pari-mutuel style.

---

## 💰 Betting System

- Bankroll starts at **$500** (fake money), held in `sessionStorage` so it resets when the tab closes.
- Place chips on any horse during the betting window; odds are computed from each horse's remembered performance.
- Payouts use a pari-mutuel pool with an 8% house takeout.

---

## 🧠 AI Systems

### A* Pathfinding
Each horse uses the A* algorithm to find the most direct route along the track while avoiding walls and the invisible barrier that prevents counter-clockwise shortcuts.

- **Grid resolution:** 10 pixels per cell
- **Heuristic:** Euclidean (straight-line) distance
- **Optimizations:** Path caching, line-of-sight smoothing, barrier memory

### Flocking (Boids)
Inspired by Craig Reynolds' Boids algorithm, each horse balances several simultaneous steering forces:

| Force | Weight | Purpose |
|-------|--------|---------|
| Separation | 1.0 | Don't crowd other horses |
| Path Following | 3.0 | Stick to the A* waypoint path |
| Track Attraction | 3.0 | Stay on the brown track surface |
| Barrier Avoidance | 5.0 | Steer away from walls |
| Checkpoint Pull | 5.0 | Move toward the next checkpoint |
| Clockwise Force | 4.0 | Prevent wrong-direction shortcuts |

Forces are combined into a single steering vector each frame. Horses that hit too many barriers, stop moving, or go the wrong way too long will **automatically reset** to the starting line.

### Persistent Learning
After every race each horse's stats (runs, wins, average/best time, skill, preferred lines) are saved to `localStorage`. Higher-skill horses run faster, so tracks get quicker over time until you wipe their memory.

---

## 📊 Live Standings

The sidebar shows real-time info per horse:

- Runs completed, wins, best time, recent times
- Current decimal odds derived from remembered performance
- Your wager on each horse and running bankroll
- Recent payout log

---

## 📁 Project Structure

```
HorseRacer/
├── web/                        # THE GAME (HTML/CSS/JS, zero dependencies)
│   ├── index.html              # Page + UI panel markup
│   ├── style.css               # Styling for the page and panels
│   └── js/
│       ├── config.js           # Settings: canvas size, horse names, colors, keys
│       ├── main.js             # Game loop, state machine, HUD, DOM wiring
│       ├── horse.js            # AI agent: flocking + pathfollowing + learning
│       ├── track.js            # Square track, checkpoints, barriers
│       ├── grid.js             # Grid system for A* pathfinding
│       ├── astar.js            # A* algorithm implementation
│       ├── vector2.js          # 2D vector math library
│       ├── memory.js           # Persistent horse memory + odds/skill model
│       └── betting.js          # Fake-money bankroll & pari-mutuel payouts
│
├── tests/
│   └── harness.js              # Headless Node simulation test (run: node tests/harness.js)
│
└── legacy_python/              # Original pygame desktop version (kept for reference)
    ├── main.py                 # Old entry point
    ├── config.py               # Old settings
    ├── game/ models/ pathfinding/ track/ utils/
    └── HorseRacer.spec requirements.txt horse_rankings.json
```

---

## 🏇 The Horses

| Name | Color |
|------|-------|
| DASHER | Red |
| BOLTO | Blue |
| STORM | Yellow |
| FLASH | Purple |
| RACER | Orange |
| ZIPPY | White |

Each horse has the same AI but different starting positions, leading to emergent, unpredictable races every time.

---

## ⚙️ Configuration

Edit `web/js/config.js` to customize:

```js
export const WIDTH = 1280;   // Canvas width
export const HEIGHT = 720;   // Canvas height
export const FPS = 60;       // Frame rate
export const NUM_HORSES = 6; // Number of racers
export const STARTING_BALANCE = 500;
export const HORSE_NAMES = ['DASHER', 'BOLTO', 'STORM', 'FLASH', 'RACER', 'ZIPPY'];
```

---

## ✅ Testing

The simulation logic can be verified headlessly without a browser:

```bash
node tests/harness.js
```

It runs full races, checks that all horses complete the checkpoint circuit (no soft-locks), that the learning/skill system improves horses, and that betting probabilities sum to 1.

---

## ⚠️ Development Attribution

- **Code Generation:** Core game logic, pathfinding algorithms, and agent behaviors were generated with assistance from DeepSeek AI; the browser port rewrites the pygame original in HTML/Canvas/ES modules.
- **Documentation:** This README was written by Lumo (Proton's AI assistant).

*This project is an educational example of human-AI collaborative software development.*

---

## 📄 License

This project is for educational purposes. Feel free to modify, extend, and learn from it.

---

## 🙏 Credits

- **A* Algorithm:** Based on Unity pathfinding tutorial logic
- **Flocking Behavior:** Craig Reynolds' Boids algorithm (1986)
- **Graphics:** HTML5 Canvas 2D rendering (replacing Pygame)
- **AI Assistance:** DeepSeek (code generation), Lumo (documentation)

---

*Built for learning game AI and emergent behavior through human-AI collaboration*
