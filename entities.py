import math, random, pygame
import settings as cfg
from settings import (DT, PREVIEW_DT_SCALE, G, STAR_MASS, ANGLE_LIMIT_DEG, MIN_SPEED, MAX_SPEED, YELLOW, GREEN, RED, SHOTS_PER_PLANET)

from assets import load_img

class Explosion:
    """One-shot sprite animation at a fixed position."""
    def __init__(self, frames, pos, frame_time=0.01, scale=1.0, sound=None):
        self.pos = (int(pos[0]), int(pos[1]))
        self.frame_time = frame_time
        self.t = 0.0
        self.alive = True
        # Pre-scale frames for this explosion size
        self.frames = [
            pygame.transform.rotozoom(f, 0, scale) for f in frames
        ]
        self.index = 0

                # Play sound immediately if provided
        if sound:
            sound.play()

    def update(self, dt):
        if not self.alive: 
            return
        self.t += dt
        self.index = int(self.t / self.frame_time)
        if self.index >= len(self.frames):
            self.alive = False
            self.index = len(self.frames) - 1

    def draw(self, surf):
        if not self.alive:
            return
        img = self.frames[self.index]
        rect = img.get_rect(center=self.pos)
        surf.blit(img, rect)

class Planet:
    def __init__(self, name, sprite, orbit_radius, orbit_period, radius_px, mass,
                 initial_angle=0.0, spin_period=None, num_sites=1, owner=None):
        self.name = name
        self.sprite = sprite
        self.orbit_radius = orbit_radius
        self.orbit_period = orbit_period
        self.radius_px = radius_px
        self.mass = mass
        self.theta = initial_angle
        self.spin = 0.0
        self.spin_period = spin_period if spin_period else orbit_period * 0.5
        self.owner = owner
        self.sites = []
        # Health (30 hits to destroy)
        self.max_health = 30
        self.health = self.max_health
        # Shots per planet (unused when tracking per-player shots)
        self.shots = SHOTS_PER_PLANET
        for i in range(num_sites):
            site_angle = (i / num_sites) * math.tau
            self.sites.append(LaunchSite(self, site_angle))

    @property
    def pos(self):
        cx, cy = cfg.CENTER
        x = cx + self.orbit_radius * math.cos(self.theta)
        y = cy + self.orbit_radius * math.sin(self.theta)
        return (x, y)

    def update(self, dt):
        self.theta += math.tau * dt / self.orbit_period
        self.spin  += math.tau * dt / self.spin_period
        self.theta %= math.tau
        self.spin  %= math.tau

    def take_damage(self, amount):
        self.health = max(0, min(self.max_health, self.health - amount))

    def draw(self, surf):
        x, y = self.pos
        rect = self.sprite.get_rect(center=(x, y))
        surf.blit(self.sprite, rect)

        # Health ring inside the planet
        ring_thickness = max(3, int(self.radius_px * 0.12))
        ring_radius = max(4, self.radius_px - ring_thickness - 2)

        # Red base ring
        pygame.draw.circle(surf, RED, (int(x), int(y)), ring_radius, ring_thickness)

        # Green arc for remaining health
        if self.health > 0:
            frac = self.health / self.max_health
            start_ang = -math.pi / 2
            stop_ang  = start_ang + frac * math.tau
            bbox = pygame.Rect(0, 0, ring_radius * 2, ring_radius * 2)
            bbox.center = (int(x), int(y))
            pygame.draw.arc(surf, GREEN, bbox, start_ang, stop_ang, ring_thickness)

class LaunchSite:
    def __init__(self, planet, angle_on_planet):
        self.planet = planet
        self.angle_on_planet = angle_on_planet
        self.sprite = load_img("tower2.png")
        self.planned_angle_offset = 0.0
        self.planned_speed = 300.0

    def get_world_pos(self):
        px, py = self.planet.pos
        ang = self.angle_on_planet + self.planet.spin
        ox = math.cos(ang) * (self.planet.radius_px + 10)
        oy = math.sin(ang) * (self.planet.radius_px + 10)
        return (px + ox, py + oy), ang

    def draw(self, surf, highlight=False):
        (x, y), ang = self.get_world_pos()
        deg = math.degrees(ang) - 90
        img = pygame.transform.rotozoom(self.sprite, -deg, 1)
        rect = img.get_rect(center=(x, y))
        surf.blit(img, rect)
        if highlight:
            pygame.draw.circle(surf, YELLOW, (int(x), int(y)), 10, 2)
            r = 24
            base = ang - math.pi/2
            a1 = base - math.radians(ANGLE_LIMIT_DEG) + self.planned_angle_offset
            a2 = base + math.radians(ANGLE_LIMIT_DEG) + self.planned_angle_offset
            for a in (a1, a2):
                ex = x + math.cos(a) * r
                ey = y + math.sin(a) * r
                pygame.draw.line(surf, YELLOW, (x,y), (ex,ey), 1)
            pygame.draw.circle(surf, (255,255,255), (int(x),int(y)), r, 1)

class Rocket:
    def __init__(self, owner, pos, vel):
        self.owner = owner
        self.pos = list(pos)
        self.vel = list(vel)
        self.alive = True
        sprite_name = f"{owner.name.lower()}_rocket.png"
        self.sprite = load_img(sprite_name)
        self.rotate_deg = 0.0
        self.trail = []

    def apply_gravity(self, planets, dt, star_mass=STAR_MASS):
        ax, ay = 0.0, 0.0
        # star
        sx, sy = cfg.CENTER
        dx, dy = sx - self.pos[0], sy - self.pos[1]
        r2 = dx*dx + dy*dy + 1e-6
        invr3 = 1.0 / (r2 * math.sqrt(r2))
        a = G * star_mass
        ax += a * dx * invr3
        ay += a * dy * invr3
        # planets
        for p in planets:
            px, py = p.pos
            dx, dy = px - self.pos[0], py - self.pos[1]
            r2 = dx*dx + dy*dy + 1e-6
            invr3 = 1.0 / (r2 * math.sqrt(r2))
            a = G * p.mass
            ax += a * dx * invr3
            ay += a * dy * invr3
        self.vel[0] += ax * dt
        self.vel[1] += ay * dt

    def update(self, planets, dt):
        self.apply_gravity(planets, dt)
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.trail.append((int(self.pos[0]), int(self.pos[1])))
        if len(self.trail) > 800:
            self.trail.pop(0)
        self.rotate_deg = math.degrees(math.atan2(self.vel[1], self.vel[0])) + 90

        # collisions with planets
        for p in planets:
            px, py = p.pos
            if (self.pos[0]-px)**2 + (self.pos[1]-py)**2 <= (p.radius_px)**2:
                p.take_damage(1)
                self.alive = False
                break

    def draw(self, surf):
        if len(self.trail) > 2:
            try:
                pygame.draw.aalines(surf, (255,255,255,30), False, self.trail, 1)
            except Exception:
                pass
        img = pygame.transform.rotozoom(self.sprite, -self.rotate_deg, 0.9)
        rect = img.get_rect(center=(int(self.pos[0]), int(self.pos[1])))
        surf.blit(img, rect)
