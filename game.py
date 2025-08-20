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

        # players & turn
        self.players = [Player("Blue", (120,200,255)), Player("Red", (255,120,120))]
        self.turn_index = 0

        # planets
        self.planets = self.create_planets()
        owners = [self.players[0], self.players[1]]
        for pi, p in enumerate(self.planets):
            for si, site in enumerate(p.sites):
                site.owner = p.owner

        # state
        self.rockets = []
        self.queued_shots = []  # (player, site, angle_offset, speed, fire_time_abs)
        self.selected_site = None
        self.preview_traj = []
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

    def _shots_left(self):
        blue = sum(p.shots for p in self.planets if p.owner == "Blue")
        red  = sum(p.shots for p in self.planets if p.owner == "Red")
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
        blue_shots, red_shots = self._shots_left()
        rockets_alive = any(r.alive for r in self.rockets)
        nothing_pending = (not rockets_alive) and (len(self.queued_shots) == 0)

        if blue_shots == 0 and red_shots == 0 and nothing_pending:
            blue_score, red_score = self._scores()
            if blue_score > red_score:
                self.winner = next(pl for pl in self.players if pl.name == "Blue")
            elif red_score > blue_score:
                self.winner = next(pl for pl in self.players if pl.name == "Red")
            else:
                self.winner = None  # tie
            self.game_over = True

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

    def current_player(self):
        return self.players[self.turn_index % len(self.players)]

    def cycle_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.players)

    def select_site_by_click(self, mx, my):
        my_planets = [p for p in self.planets if p.owner ==  self.current_player().name]

        best = None
        best_d2 = 20**2
        for p in my_planets:
            for s in p.sites:
                (x,y), _ = s.get_world_pos()
                d2 = (mx-x)**2 + (my-y)**2
                if d2 < best_d2:
                    best = s
                    best_d2 = d2
        if best:
            self.selected_site = best
            self.update_preview()

    def plan_adjust(self, dx_angle=0.0, dspeed=0.0, ddelay=0.0):
        from settings import ANGLE_LIMIT_DEG, MIN_SPEED, MAX_SPEED
        if not self.selected_site: return
        s = self.selected_site
        s.planned_angle_offset += dx_angle
        limit = math.radians(ANGLE_LIMIT_DEG)
        s.planned_angle_offset = max(-limit, min(limit, s.planned_angle_offset))
        s.planned_speed = max(MIN_SPEED, min(MAX_SPEED, s.planned_speed + dspeed))
        
        self.update_preview()

    def queue_shot(self):
        if not self.selected_site: return

        # If you have now 
        if self.selected_site.planet.shots < 1: 
            empty_sound = assets.get_sound("empty")
            empty_sound.play()
            return
        
        now = self.t_sim
        fire_time = now
        self.queued_shots.append((
            self.current_player(), self.selected_site,
            self.selected_site.planned_angle_offset,
            self.selected_site.planned_speed, fire_time
        ))
        self.cycle_turn()
        # auto-select a site owned by next player
        for p in self.planets:
            for s in p.sites:
                if s.owner == self.current_player():
                    self.selected_site = s
                    self.update_preview()
                    return
        self.selected_site = None

    def spawn_rocket(self, player, site, angle_offset, speed):
        (x,y), tower_ang = site.get_world_pos()
        base = tower_ang - math.pi/2
        direction = base + angle_offset
        vx = math.cos(direction) * speed
        vy = math.sin(direction) * speed
        self.rockets.append(Rocket(player, (x,y), (vx,vy)))

    def simulate_preview(self, steps=80):
        import settings as cfg
        from settings import DT, PREVIEW_DT_SCALE, G, STAR_MASS
        if not self.selected_site:
            self.preview_traj = []
            return

        clones = []
        for p in self.planets:
            clones.append({"theta": p.theta, "spin": p.spin, "p": p})

        (x, y), tower_ang = self.selected_site.get_world_pos()
        base = tower_ang - math.pi / 2
        direction = base + self.selected_site.planned_angle_offset
        vx = math.cos(direction) * self.selected_site.planned_speed
        vy = math.sin(direction) * self.selected_site.planned_speed
        rx, ry = x, y
        rvx, rvy = vx, vy
        traj = [(int(rx), int(ry))]
        dt = DT * PREVIEW_DT_SCALE

        for _ in range(steps):
            # advance planets (local)
            for c in clones:
                p = c["p"]
                c["theta"] += math.tau * dt / p.orbit_period
                c["spin"]  += math.tau * dt / p.spin_period

            # gravity
            ax, ay = 0.0, 0.0
            sx, sy = cfg.CENTER
            dx, dy = sx - rx, sy - ry
            r2 = dx * dx + dy * dy + 1e-6
            invr3 = 1.0 / (r2 * math.sqrt(r2))
            a = G * STAR_MASS
            ax += a * dx * invr3
            ay += a * dy * invr3
            for c in clones:
                p = c["p"]
                px = cfg.CENTER[0] + p.orbit_radius * math.cos(c["theta"])
                py = cfg.CENTER[1] + p.orbit_radius * math.sin(c["theta"])
                dx, dy = px - rx, py - ry
                r2 = dx * dx + dy * dy + 1e-6
                invr3 = 1.0 / (r2 * math.sqrt(r2))
                ax += G * p.mass * dx * invr3
                ay += G * p.mass * dy * invr3

            rvx += ax * dt
            rvy += ay * dt
            rx  += rvx * dt
            ry  += rvy * dt
            traj.append((int(rx), int(ry)))

            if rx < -200 or rx > cfg.WIDTH + 200 or ry < -200 or ry > cfg.HEIGHT + 200:
                break

        self.preview_traj = traj


    def update_preview(self):
        # return
        self.simulate_preview()

    def _auto_select_site_for_current_player(self):
        self.selected_site = None
        for p in self.planets:
            for s in p.sites:
                if s.owner == self.current_player().name and s.planet.shots > 0:
                    self.selected_site = s
                    self.update_preview()
                    return
        self.update_preview()

    def update(self):
        self.time_scale = ACTION_TIME_SCALE if any(r.alive for r in self.rockets) else DEFAULT_TIME_SCALE
        dt = DT * self.time_scale
        self.t_sim += dt

        # --- auto-skip if current player cannot shoot ---
        if not self.game_over:
            cp = self.current_player().name
            opp = "Red" if cp == "Blue" else "Blue"
            cp_shots  = sum(p.shots for p in self.planets if p.owner == cp)
            opp_shots = sum(p.shots for p in self.planets if p.owner == opp)
            nothing_pending = (not any(r.alive for r in self.rockets)) and (len(self.queued_shots) == 0)
            if cp_shots == 0 and opp_shots > 0 and nothing_pending:
                self.cycle_turn()
                self._auto_select_site_for_current_player()

        # animate stars
        self.sunone_index = (self.sunone_index + 1) % len(self.sunone_frames)
        self.suntwo_index = (self.suntwo_index + 1) % len(self.suntwo_frames)

        # planets move
        for p in self.planets:
            p.update(dt)

        # fire queued (only if site/planet still exists)
        to_fire = [q for q in self.queued_shots if q[4] <= self.t_sim]
        self.queued_shots = [q for q in self.queued_shots if q[4] > self.t_sim]
        for player, site, ang_off, speed, _ in to_fire:
            if site.planet in self.planets:
                if site.planet.shots > 0:
                    site.planet.shots -= 1
                    self.spawn_rocket(player, site, ang_off, speed)

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
            # clear selection & queue that reference removed planets
            if self.selected_site and self.selected_site.planet in removed_set:
                self.selected_site = None
                self.preview_traj = []
            self.queued_shots = [q for q in self.queued_shots if q[1].planet not in removed_set]

        # effects
        for fx in self.effects:
            fx.update(dt)
        self.effects = [fx for fx in self.effects if fx.alive]

        # remove
        self.update_preview()

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
        from settings import WHITE, YELLOW, ANGLE_LIMIT_DEG
        pygame.draw.rect(self.screen, (0,0,0,60), (0,0,cfg.WIDTH,40))
        
        # Draw score panels
        panelH = 40
        panelW = 80
        padding = 5
        boxLeft = (padding,cfg.HEIGHT - panelH - padding,panelW,panelH)
        boxRight = (cfg.WIDTH - padding - panelW,cfg.HEIGHT - panelH - padding,panelW,panelH)
    
        pygame.draw.rect(self.screen,(255,10,10,255), boxLeft)
        pygame.draw.rect(self.screen,(10,10,255,255), boxRight)

        # Highlight whoevers turn it is
        if self.current_player().name == "Blue":            
            pygame.draw.rect(self.screen, (255, 255, 255), boxRight, width=4)
        else:
            pygame.draw.rect(self.screen, (255, 255, 255), boxLeft, width=4)
        
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


        planet_status = ""
        for p in self.planets:
            planet_status += str(p.shots) + " "

        txt = f"Shots :  {planet_status}   | Player: {self.current_player().name} | A/D angle | W/S speed | SPACE fire | Click a tower"
        self.screen.blit(self.font.render(txt, True, WHITE), (12,10))

        panel = pygame.Surface((260, 170), pygame.SRCALPHA)
        panel.fill((20,30,52,200))
        y = 10

        def wr(s):
            nonlocal y
            panel.blit(self.font.render(s, True, WHITE), (10,y)); y += 22
        wr(f"Selected: {self.selected_site.planet.name if self.selected_site else 'None'}")
        if self.selected_site:
            deg = math.degrees(self.selected_site.planned_angle_offset)
            wr(f"Angle offset: {deg:+.1f}° (±{ANGLE_LIMIT_DEG}°)")
            wr(f"Speed: {self.selected_site.planned_speed:.0f}")
        wr(f"Queued shots: {len(self.queued_shots)}")
        self.screen.blit(panel, (cfg.WIDTH-280, 50))

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
                s.draw(self.screen, highlight=(s == self.selected_site))

        # rockets
        for r in self.rockets:
            r.draw(self.screen)

        # effects
        for fx in self.effects:
            fx.draw(self.screen)

        # preview
        if self.selected_site and len(self.preview_traj) > 2:
            try:
                pygame.draw.aalines(self.screen, (255, 255, 180), False, self.preview_traj, 1)
            except Exception:
                pass

        self.draw_ui()

        # <<< important >>>
        if self.game_over:
            self.draw_finish_screen()

        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.select_site_by_click(*event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_a:
                    self.plan_adjust(dx_angle=-math.radians(2))
                elif event.key == pygame.K_d:
                    self.plan_adjust(dx_angle= math.radians(2))
                elif event.key == pygame.K_w:
                    self.plan_adjust(dspeed=+10)
                elif event.key == pygame.K_s:
                    self.plan_adjust(dspeed=-10)
                elif event.key == pygame.K_SPACE:

                    self.queue_shot()
                elif event.key == pygame.K_ESCAPE:
                    self.running = False

    def run(self):
        # auto-select first owned site
        if not self.selected_site:
            for p in self.planets:
                for s in p.sites:
                    if s.owner == self.current_player():
                        self.selected_site = s
                        self.update_preview()
                        break
                if self.selected_site: break

        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
