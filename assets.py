import os, pygame
from settings import ASSET_DIR, SOUND_DIR

_sounds = {}

def load_sounds():
    # Prefer .wav or .ogg for best compatibility/latency
    path = os.path.join("sounds", "planet_boom.mp3")  # or .wav
    _sounds["planet_explosion"] = pygame.mixer.Sound(path)
    _sounds["planet_explosion"].set_volume(0.8)
    
    path = os.path.join("sounds", "wilhelm.wav")  # or .wav
    _sounds["wilhelm"] = pygame.mixer.Sound(path)
    _sounds["wilhelm"].set_volume(0.3)

    path = os.path.join("sounds", "empty.mp3")  # or .wav
    _sounds["empty"] = pygame.mixer.Sound(path)
    _sounds["empty"].set_volume(0.9)

def get_sound(name: str) -> pygame.mixer.Sound | None:
    return _sounds.get(name)

def load_img(name: str) -> pygame.Surface:
    return pygame.image.load(os.path.join(ASSET_DIR, name)).convert_alpha()

def load_spritesheet(path: str, frame_width: int, frame_height: int):
    sheet = pygame.image.load(os.path.join(ASSET_DIR, path)).convert_alpha()
    sheet_width, _ = sheet.get_size()
    frames = []
    for x in range(0, sheet_width, frame_width):
        frame = sheet.subsurface((x, 0, frame_width, frame_height))
        frames.append(frame)
    return frames

def fade_surface(surface: pygame.Surface, factor: float) -> pygame.Surface:
    """Multiply per-pixel alpha and RGB by factor (0.0–1.0)."""
    faded = surface.copy()
    rgb_array = pygame.surfarray.pixels3d(faded)
    rgb_array[:] = (rgb_array[:] * factor).astype(rgb_array.dtype)
    del rgb_array
    alpha_array = pygame.surfarray.pixels_alpha(faded)
    alpha_array[:] = (alpha_array[:] * factor).astype(alpha_array.dtype)
    del alpha_array
    return faded

def load_grid_spritesheet(path: str, cols: int, rows: int):
    """Load a grid sprite sheet and return frames left->right, top->bottom."""
    sheet = pygame.image.load(os.path.join(ASSET_DIR, path)).convert_alpha()
    sw, sh = sheet.get_size()
    fw, fh = sw // cols, sh // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            rect = pygame.Rect(c * fw, r * fh, fw, fh)
            frames.append(sheet.subsurface(rect))
    return frames
