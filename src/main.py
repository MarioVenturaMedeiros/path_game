# game_uart_control.py
import threading
import queue
import serial
import time
import pygame
import sys
import random

SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 115200
READ_TIMEOUT = 0.1
RECONNECT_DELAY = 2.0

WIDTH, HEIGHT = 480, 640
FPS = 60

LANE_X = [140, 340]
PLAYER_Y = 520

OBSTACLE_SPEED = 4
OBSTACLE_SPAWN_MS = 1100
STAR_SPAWN_MS = 1200
WIN_STARS = 6

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("T1 classic")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
big_font = pygame.font.SysFont(None, 64)

def load_image_safe(name, fallback_color=(255,0,255), scale=0.3):
    try:
        img = pygame.image.load(name).convert_alpha()
        if scale != 1.0:
            w,h = img.get_size()
            img = pygame.transform.smoothscale(img, (int(w*scale), int(h*scale)))
        return img
    except Exception:
        s = pygame.Surface((64,64), pygame.SRCALPHA)
        s.fill(fallback_color + (255,))
        return s

player_img = load_image_safe("../assets/images/t1.png", fallback_color=(0,200,0))
geng_img = load_image_safe("../assets/images/geng.png", fallback_color=(200,0,0))
star_img = load_image_safe("../assets/images/star.png", fallback_color=(255,255,0))

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = player_img
        self.rect = self.image.get_rect()
        self.lane = 0
        self.update_pos()
    def update_pos(self):
        self.rect.centerx = LANE_X[self.lane]
        self.rect.centery = PLAYER_Y
    def move_left(self):
        self.lane = 0
        self.update_pos()
    def move_right(self):
        self.lane = 1
        self.update_pos()

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, lane):
        super().__init__()
        self.image = geng_img
        self.rect = self.image.get_rect()
        self.rect.centerx = LANE_X[lane]
        self.rect.centery = -self.rect.height//2
        self.speed = OBSTACLE_SPEED
        self.lane = lane
    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT + 50:
            self.kill()

class Star(pygame.sprite.Sprite):
    def __init__(self, lane):
        super().__init__()
        self.image = star_img
        self.rect = self.image.get_rect()
        self.rect.centerx = LANE_X[lane]
        self.rect.centery = -self.rect.height//2 - random.randint(0,80)
        self.speed = OBSTACLE_SPEED
        self.lane = lane
    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT + 50:
            self.kill()


all_sprites = pygame.sprite.Group()
obstacles = pygame.sprite.Group()
stars = pygame.sprite.Group()

player = Player()
all_sprites.add(player)

star_count = 0
game_over = False
you_win = False

SPAWN_OBSTACLE = pygame.USEREVENT + 1
SPAWN_STAR = pygame.USEREVENT + 2
pygame.time.set_timer(SPAWN_OBSTACLE, OBSTACLE_SPAWN_MS)
pygame.time.set_timer(SPAWN_STAR, STAR_SPAWN_MS)


def serial_reader_thread(port, baudrate, out_queue, stop_event):
    ser = None
    while not stop_event.is_set():
        if ser is None:
            try:
                ser = serial.Serial(port, baudrate, timeout=READ_TIMEOUT)
                out_queue.put(("__INFO__", f"Opened {port}"))
            except Exception as e:
                out_queue.put(("__ERROR__", f"open error: {e}"))
                time.sleep(RECONNECT_DELAY)
                continue
        try:
            line = ser.readline()
            if line:
                try:
                    text = line.decode('utf-8', errors='replace').strip()
                except Exception:
                    text = repr(line)
                # Accept only lines that start exactly with "A UP" or "B UP"
                if text.startswith("A UP"):
                    out_queue.put(("CMD", "A UP"))
                elif text.startswith("B UP"):
                    out_queue.put(("CMD", "B UP"))
                else:
                    # ignore everything else; optionally log info
                    pass
        except serial.SerialException as e:
            out_queue.put(("__ERROR__", f"serial exception: {e}"))
            try:
                ser.close()
            except:
                pass
            ser = None
            time.sleep(RECONNECT_DELAY)
        except Exception as e:
            out_queue.put(("__ERROR__", f"other read error: {e}"))
            time.sleep(0.1)
    if ser:
        try:
            ser.close()
        except:
            pass


q = queue.Queue()
stop_event = threading.Event()
t = threading.Thread(target=serial_reader_thread, args=(SERIAL_PORT, BAUDRATE, q, stop_event), daemon=True)
t.start()


def draw_ui():
    txt = font.render(f"Stars: {star_count}/{WIN_STARS}", True, (255,255,255))
    screen.blit(txt, (10,10))

def draw_center_text(text, color=(255,255,255)):
    surf = big_font.render(text, True, color)
    r = surf.get_rect(center=(WIDTH//2, HEIGHT//2))
    screen.blit(surf, r)


try:
    clock = pygame.time.Clock()
    while True:
        dt = clock.tick(FPS)

        # consume serial queue: only CMD items arrive (or errors/info)
        while not q.empty():
            typ, payload = q.get_nowait()
            if typ == "CMD":
                if payload == "A UP":
                    # move to right lane
                    player.move_right()
                elif payload == "B UP":
                    # move to left lane
                    player.move_left()

        # events (keyboard kept only for restart / quit convenience)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and (game_over or you_win):
                    # restart
                    for s in obstacles: s.kill()
                    for s in stars: s.kill()
                    star_count = 0
                    game_over = False
                    you_win = False
                    OBSTACLE_SPEED = 4
                if event.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt()

            if event.type == SPAWN_OBSTACLE and not game_over and not you_win:
                lane = random.choice([0,1])
                obs = Obstacle(lane)
                obstacles.add(obs); all_sprites.add(obs)
            if event.type == SPAWN_STAR and not game_over and not you_win:
                if random.random() < 0.6:
                    lane = random.choice([0,1])
                    st = Star(lane); stars.add(st); all_sprites.add(st)

        if not game_over and not you_win:
            all_sprites.update()
            # collision with obstacles
            collided = pygame.sprite.spritecollide(player, obstacles, dokill=True)
            for c in collided:
                if c.lane == player.lane:
                    game_over = True
            # collision with stars
            got = pygame.sprite.spritecollide(player, stars, dokill=True)
            for s in got:
                if s.lane == player.lane:
                    star_count += 1
                    if star_count >= WIN_STARS:
                        you_win = True

        # draw
        screen.fill((30,30,30))
        pygame.draw.line(screen, (60,60,60), (WIDTH//2,0), (WIDTH//2,HEIGHT), 2)
        pygame.draw.rect(screen, (40,40,40), (0, PLAYER_Y + player.rect.height//2 + 10, WIDTH, 6))

        all_sprites.draw(screen)
        draw_ui()

        if game_over:
            draw_center_text("GAME OVER", (200,50,50))
            small = font.render("Press R to restart", True, (200,200,200))
            screen.blit(small, (WIDTH//2 - small.get_width()//2, HEIGHT//2 + 50))
        if you_win:
            draw_center_text("YOU WIN!", (50,200,50))
            small = font.render("Press R to play again", True, (200,200,200))
            screen.blit(small, (WIDTH//2 - small.get_width()//2, HEIGHT//2 + 50))

        pygame.display.flip()

except KeyboardInterrupt:
    pass
finally:
    stop_event.set()
    t.join(timeout=1.0)
    pygame.quit()
    sys.exit(0)
