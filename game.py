import math, random, pygame
import settings as cfg 
from settings import set_screen_metrics, DT, DEFAULT_TIME_SCALE, ACTION_TIME_SCALE, WHITE
from assets import load_img, load_spritesheet, fade_surface, load_grid_spritesheet
from entities import Planet, LaunchSite, Rocket, Explosion
import assets

class Player:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.alive = True
        self.shots = 100
        self.site = None

class Game:
    def __init__(self):
        pygame.display.set_caption("I.S.A.C. — InterStellar Artillery Commander")
        info = pygame.display.Info()
        set_screen_metrics(info.current_w, info.current_h)

        self.screen = pygame.display.set_mode((cfg.WIDTH, cfg.HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)

        # Load Sounds
        assets.load_sounds()                      # <-- load sounds once
        pygame.mixer.set_num_channels(16)    

        # assets
        self.bg = load_img("background.jpg")
        self.bg = pygame.transform.scale(self.bg, (cfg.WIDTH, cfg.HEIGHT))

        self.sunone_frames = load_spritesheet("s1ss.png", 80, 80)
        self.suntwo_frames = load_spritesheet("suntwo.png", 80, 80)
        self.sunone_index = 0
        self.suntwo_index = 0

        # + LOAD PLANET EXPLOSION SHEET (5x10 grid -> 50 frames)
        self.planet_explosion_frames = load_grid_spritesheet(
            "planet_explosion.png", cols=5, rows=10
        )

        # players
        self.players = [Player("Blue", (120,200,255)), Player("Red", (255,120,120))]

        # planets
        self.planets = self.create_planets()
        for p in self.planets:
            for s in p.sites:
                s.owner = p.owner
                for pl in self.players:
                    if s.owner == pl.name and pl.site is None:
                        pl.site = s

        # state
        self.rockets = []
        self.running = True
        self.t_sim = 0.0
        self.time_scale = DEFAULT_TIME_SCALE

        # + EFFECTS (explosions, etc.)
        self.effects = []

        # winner tracking
        self.game_over = False
        self.winner = None   # Player instance or None on tie

    def _scores(self):
        blue = sum(p.health for p in self.planets if p.owner == "Blue")
        red  = sum(p.health for p in self.planets if p.owner == "Red")
        return blue, red

    def _check_game_over(self):
        # --- planet wipeout first ---
        blue_gone = not any(p.owner == "Blue" for p in self.planets)
        red_gone  = not any(p.owner == "Red"  for p in self.planets)

        if blue_gone and red_gone:
            self.winner = None  # total annihilation -> draw
            self.game_over = True
            return
        if blue_gone:
            self.winner = next(pl for pl in self.players if pl.name == "Red")
            self.game_over = True
            return
        if red_gone:
            self.winner = next(pl for pl in self.players if pl.name == "Blue")
            self.game_over = True
            return

        # --- otherwise, only end when neither side can shoot and nothing is pending ---
        rockets_alive = any(r.alive for r in self.rockets)
        if self.players[0].shots == 0 and self.players[1].shots == 0 and not rockets_alive:
            blue_score, red_score = self._scores()
            if blue_score > red_score:
                self.winner = next(pl for pl in self.players if pl.name == "Blue")
            elif red_score > blue_score:
                self.winner = next(pl for pl in self.players if pl.name == "Red")
            else:
                self.winner = None  # tie
            self.game_over = True

    def ensure_player_site(self, player):
        if player.site and player.site.planet in self.planets:
            return
        for p in self.planets:
            for s in p.sites:
                if s.owner == player.name:
                    player.site = s
                    return
        player.site = None

    def create_planets(self):
        sprites = [
        ("BlueIce.png", 50, 0.8, "Blue"),       
        ("RedLava.png", 60, 0.7, "Red"),
        ("BlueGas.png", 70, 1.0, "Blue"),
        ("RedGas.png", 80, 0.9, "Red"),
        #("RedVoid.png", 64, 0.8),
        ]
        planets = []
        for i, (name, px_size, mass_scale, owner) in enumerate(sprites):
            sprite = load_img(name)
            orbit_radius = 100 + i*80 + (random.random() * 50 - 25)
            orbit_period = 3 + (random.random() * 50) + (i * 5)
            radius_px = px_size//2
            mass = 1200 * mass_scale
            initial_angle = i * (math.tau/len(sprites))
            spin_period = 6+(random.random()*4-2)
            num_sites = random.choice([1,2])
            p = Planet(name, sprite, orbit_radius * 1.0, orbit_period, radius_px, mass,
                       initial_angle, spin_period, num_sites=num_sites, owner=owner)
            planets.append(p)
        return planets

    def plan_adjust(self, player, dx_angle=0.0):
        from settings import ANGLE_LIMIT_DEG
        self.ensure_player_site(player)
        if not player.site:
            return
        s = player.site
        s.planned_angle_offset += dx_angle
        limit = math.radians(ANGLE_LIMIT_DEG)
        s.planned_angle_offset = max(-limit, min(limit, s.planned_angle_offset))

    def fire(self, player):
        self.ensure_player_site(player)
        if not player.site:
            return
        if player.shots < 1:
            empty_sound = assets.get_sound("empty")
            empty_sound.play()
            return
        player.shots -= 1
        self.spawn_rocket(player, player.site, player.site.planned_angle_offset, player.site.planned_speed)

    def spawn_rocket(self, player, site, angle_offset, speed):
        (x,y), tower_ang = site.get_world_pos()
        base = tower_ang - math.pi/2
        direction = base + angle_offset
        vx = math.cos(direction) * speed
        vy = math.sin(direction) * speed
        self.rockets.append(Rocket(player, (x,y), (vx,vy)))

    def update(self):
        self.time_scale = ACTION_TIME_SCALE if any(r.alive for r in self.rockets) else DEFAULT_TIME_SCALE
        dt = DT * self.time_scale
        self.t_sim += dt

        # animate stars
        self.sunone_index = (self.sunone_index + 1) % len(self.sunone_frames)
        self.suntwo_index = (self.suntwo_index + 1) % len(self.suntwo_frames)

        # planets move
        for p in self.planets:
            p.update(dt)

        # rockets
        for r in self.rockets:
            if r.alive:
                r.update(self.planets, dt)
        self.rockets = [r for r in self.rockets if r.alive]

        # --- handle destroyed planets: spawn explosion; remove planet from game ---
        removed = []
        for p in self.planets:
            if p.health <= 0:
                # capture current position
                x, y = p.pos
                # scale explosion roughly to planet size (diameter/texture size heuristic)
                # Base the scale so the explosion is a bit larger than the planet
                base_frame = self.planet_explosion_frames[0]
                bw, bh = base_frame.get_size()
                target_diam = int(p.radius_px * 3)  # a touch bigger than planet
                # keep aspect based on width
                scale = max(0.1, target_diam / max(1, bw))

                boom = assets.get_sound("planet_explosion")  # <-- get the sound
                
                self.effects.append(
                    Explosion(self.planet_explosion_frames, (x, y), frame_time=0.015, scale=scale, sound=boom)
                )
                removed.append(p)

        if removed:
            removed_set = set(removed)
            # prune planets
            self.planets = [p for p in self.planets if p not in removed_set]
            # clear any player site referencing removed planets
            for pl in self.players:
                if pl.site and pl.site.planet in removed_set:
                    pl.site = None

        # effects
        for fx in self.effects:
            fx.update(dt)
        self.effects = [fx for fx in self.effects if fx.alive]
        self._check_game_over()

    def draw_finish_screen(self):
        # Background tint in winner color (or gray if tie)
        if self.winner is None:
            color = (180, 180, 180)
            title = "DRAW"
        else:
            color = self.winner.color
            title = f"{self.winner.name} WINS douglas was here !"

        # Fullscreen color fill
        overlay = pygame.Surface((cfg.WIDTH, cfg.HEIGHT))
        overlay.fill(color)
        self.screen.blit(overlay, (0, 0))

        # Big centered text
        big_font  = pygame.font.SysFont("consolas", 72, bold=True)
        mid_font  = pygame.font.SysFont("consolas", 32)
        small_font = pygame.font.SysFont("consolas", 20)

        blue_score, red_score = self._scores()
        subtitle = f"Blue: {blue_score}   |   Red: {red_score}"
        hint = "Press ESC to quit"

        title_surf = big_font.render(title, True, (0,0,0))
        sub_surf   = mid_font.render(subtitle, True, (0,0,0))
        hint_surf  = small_font.render(hint, True, (0,0,0))

        # Center them
        title_rect = title_surf.get_rect(center=(cfg.WIDTH//2, cfg.HEIGHT//2 - 40))
        sub_rect   = sub_surf.get_rect(center=(cfg.WIDTH//2, cfg.HEIGHT//2 + 10))
        hint_rect  = hint_surf.get_rect(center=(cfg.WIDTH//2, cfg.HEIGHT//2 + 60))

        self.screen.blit(title_surf, title_rect)
        self.screen.blit(sub_surf, sub_rect)
        self.screen.blit(hint_surf, hint_rect)


    def draw_ui(self):
        from settings import WHITE
        pygame.draw.rect(self.screen, (0,0,0,60), (0,0,cfg.WIDTH,40))

        # Draw score panels
        panelH = 40
        panelW = 80
        padding = 5
        boxLeft = (padding,cfg.HEIGHT - panelH - padding,panelW,panelH)
        boxRight = (cfg.WIDTH - padding - panelW,cfg.HEIGHT - panelH - padding,panelW,panelH)

        pygame.draw.rect(self.screen,(255,10,10,255), boxLeft)
        pygame.draw.rect(self.screen,(10,10,255,255), boxRight)

        # Update scores
        blueScore = sum(p.health for p in self.planets if p.owner == "Blue")
        redScore = sum(p.health for p in self.planets if p.owner == "Red")

        # Render score text
        blueText = self.font.render(str(blueScore), True, WHITE)
        redText = self.font.render(str(redScore), True, WHITE)

        # Center text in the boxes
        blueTextRect = blueText.get_rect(center=(boxRight[0] + panelW // 2, boxRight[1] + panelH // 2))
        redTextRect = redText.get_rect(center=(boxLeft[0] + panelW // 2, boxLeft[1] + panelH // 2))

        # Draw text
        self.screen.blit(blueText, blueTextRect)
        self.screen.blit(redText, redTextRect)

        txt = (
            f"Blue shots: {self.players[0].shots} | Red shots: {self.players[1].shots} | "
            "Controls - Blue: A/D angle, S fire | Red: ;/' angle, # fire"
        )
        self.screen.blit(self.font.render(txt, True, WHITE), (12,10))

    def draw(self):
        self.screen.blit(self.bg, (0, 0))

        # star composite
        sun_layer = pygame.Surface((cfg.WIDTH, cfg.HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(sun_layer, (255, 223, 0), cfg.CENTER, 30)
        sun1 = fade_surface(self.sunone_frames[self.sunone_index], 0.2)
        sun2 = fade_surface(self.suntwo_frames[self.suntwo_index], 0.4)
        sun2 = pygame.transform.rotozoom(sun2, 0, 0.8)
        rect1 = sun1.get_rect(center=cfg.CENTER)
        rect2 = sun2.get_rect(center=cfg.CENTER)
        sun_layer.blit(sun1, rect1)
        sun_layer.blit(sun2, rect2)
        self.screen.blit(sun_layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # orbits
        for p in self.planets:
            pygame.draw.circle(self.screen, (255, 255, 255, 30), cfg.CENTER, int(p.orbit_radius), 1)

        # planets & towers
        for p in self.planets:
            p.draw(self.screen)
            for s in p.sites:
                highlight = any(pl.site == s for pl in self.players)
                s.draw(self.screen, highlight=highlight)

        # rockets
        for r in self.rockets:
            r.draw(self.screen)

        # effects
        for fx in self.effects:
            fx.draw(self.screen)

        self.draw_ui()

        # <<< important >>>
        if self.game_over:
            self.draw_finish_screen()

        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_a:
                    self.plan_adjust(self.players[0], dx_angle=-math.radians(2))
                elif event.key == pygame.K_d:
                    self.plan_adjust(self.players[0], dx_angle= math.radians(2))
                elif event.key == pygame.K_s:
                    self.fire(self.players[0])
                elif event.key == pygame.K_SEMICOLON:
                    self.plan_adjust(self.players[1], dx_angle=-math.radians(2))
                elif event.key == pygame.K_QUOTE:
                    self.plan_adjust(self.players[1], dx_angle= math.radians(2))
                elif event.key == pygame.K_HASH:
                    self.fire(self.players[1])
                elif event.key == pygame.K_ESCAPE:
                    self.running = False

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
