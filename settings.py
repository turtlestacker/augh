import os, math

# Paths
ASSET_DIR = os.path.join(os.path.dirname(__file__), "isac_assets")
SOUND_DIR = os.path.join(os.path.dirname(__file__), "sounds")

# Timing
DT = 1/60.0
DEFAULT_TIME_SCALE = 0.5
ACTION_TIME_SCALE  = 0.35
PREVIEW_DT_SCALE   = 0.75

# Physics (gameplay-tuned)
G = 1500.0
STAR_MASS = 4.0e3
STAR_COLLISION_RADIUS = 40

# Controls
ANGLE_LIMIT_DEG = 20
MIN_SPEED, MAX_SPEED = 120.0, 520.0

# Colors
WHITE  = (240,240,240)
YELLOW = (255,220, 90)
GREEN  = (60, 220, 120)
RED    = (235, 70, 70)

# Screen metrics – set at runtime by game.py after pygame.init()
WIDTH, HEIGHT = 1280, 720
CENTER = (WIDTH // 2, HEIGHT // 2)

def set_screen_metrics(w: int, h: int):
    global WIDTH, HEIGHT, CENTER
    WIDTH, HEIGHT = w, h
    CENTER = (WIDTH // 2, HEIGHT // 2)

# shots per planet (unused with player-based shots)
SHOTS_PER_PLANET = 100

