import queue
import random
import threading
import time
import tkinter as tk
import math
from pathlib import Path

from PIL import Image, ImageSequence, ImageTk

try:
    import pyttsx3
    import speech_recognition as sr

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False


class DesktopPet:
    def __init__(self, root):
        self.root = root
        self.state = "walking"
        self.is_destroying = False
        self.is_pressing = False
        self.has_exploded = False
        self.press_started_at = 0.0
        self.long_press_job = None
        self.hold_vibration_job = None
        self.ui_queue = queue.Queue()
        self.listening_thread = None
        self.voice_warning_shown = False
        self.color_change_job = None
        self.drag_ready = False
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.is_running = False
        self.run_boost_until = 0.0
        self.escape_distance = 210
        self.drag_attack_states = ["attack_1", "attack_2", "attack_3", "attack_4"]
        self.current_drag_attack_state = "attack_1"
        self.next_drag_attack_change = 0.0
        self.jump_start_time = 0.0
        self.jump_duration = 0.75
        self.jump_height = 70
        self.jump_base_y = 0
        self.dead_until = 0.0
        self.move_phase = random.uniform(0, math.pi * 2)
        self.base_y = 0
        self.walk_mode = "normal"
        self.walk_mode_until = 0.0

        self.hold_to_explode_seconds = 1.8
        self.asset_dir = Path(__file__).resolve().parent
        self.available_styles = self.discover_available_styles()
        self.current_style = random.choice(self.available_styles)
        self.style_cycle_queue = []
        self.color_change_interval_range = (12, 22)

        self.animation_sources = self.build_animation_sources_for_style(self.current_style)
        print(f"[Mascota] Estilo inicial: {self.current_style}")

        # Configuración ventana
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "white")

        # Cargar animaciones por estado con fallback.
        self.state_animations = self.load_state_animations()
        self.animation_state = "walking"
        self.label = tk.Label(root, bg="white")
        self.label.pack()

        # Variables animación
        self.frame_index = 0

        # Dirección movimiento
        self.direction_x = random.choice([-1, 1])
        self.direction_y = random.choice([-1, 1])
        self.speed_x = random.uniform(3.0, 6.0)
        self.speed_y = random.uniform(2.0, 4.5)
        self.next_direction_change = time.time() + random.uniform(1.5, 4.0)

        # Mosca objetivo para modo idle
        self.fly_target = None
        self.next_fly_spawn = time.time() + random.uniform(1.0, 2.5)

        # Posición inicial aleatoria
        self.x = random.randint(0, self.root.winfo_screenwidth() - 300)
        self.y = random.randint(0, self.root.winfo_screenheight() - 300)
        self.base_y = self.y

        self.root.geometry(f"+{self.x}+{self.y}")

        # Eventos
        self.label.bind("<ButtonPress-1>", self.on_left_press)
        self.label.bind("<ButtonRelease-1>", self.on_left_release)
        self.label.bind("<B1-Motion>", self.on_left_drag)
        self.label.bind("<Button-3>", self.show_menu)

        # -------- MENÚ --------
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="🐸 Caminar", command=self.set_walking)
        self.menu.add_command(label="🛑 Detener", command=self.set_idle)
        self.menu.add_command(label="⬆️ Saltar", command=self.trigger_jump)
        self.menu.add_command(label="💀 Morir (test)", command=self.trigger_dead)
        self.menu.add_command(label="🎤 Escuchar", command=self.start_listening)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Salir", command=self.root.destroy)

        # Iniciar ciclos
        self.animate()
        self.move()
        self.process_ui_queue()
        self.schedule_auto_color_change()

    def discover_available_styles(self):
        img_root = self.asset_dir.parent / "img"
        required = ["Idle.png", "Walk.png"]

        discovered = []
        if img_root.exists():
            for entry in img_root.iterdir():
                if not entry.is_dir():
                    continue
                if all((entry / req).exists() for req in required):
                    discovered.append(entry.name)

        if discovered:
            preferred = ["Musketeer", "Knight", "Enchantress"]
            preferred_found = [name for name in preferred if name in discovered]

            if preferred_found:
                print(f"[Mascota] Estilos detectados: {', '.join(preferred_found)}")
                return preferred_found

            discovered_sorted = sorted(discovered)
            print(f"[Mascota] Estilos detectados: {', '.join(discovered_sorted)}")
            return discovered_sorted

        return ["Musketeer", "Knight", "Enchantress"]

    def build_animation_sources_for_style(self, style_name):
        style_base = (Path("..") / "img" / style_name).as_posix()

        return {
            "walking": [
                f"{style_base}/Walk.png",
                f"{style_base}/walk.png",
                f"{style_base}/Run.png",
                "walk.gif",
                "walking.gif",
                "ranaa.gif",
                "rana.gif",
                "ranaaa.gif",
            ],
            "idle": [
                f"{style_base}/Idle.png",
                "idle.gif",
                "breathing.gif",
                "ranaaa.gif",
                "ranaa.gif",
            ],
            "running": [
                f"{style_base}/Run.png",
                f"{style_base}/Walk.png",
                f"{style_base}/walk.png",
            ],
            "jump": [
                f"{style_base}/Jump.png",
                f"{style_base}/Run.png",
                f"{style_base}/Walk.png",
            ],
            "dead": [
                f"{style_base}/Dead.png",
                f"{style_base}/Hurt.png",
                f"{style_base}/Idle.png",
            ],
            "listening": [
                f"{style_base}/Attack_4.png",
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_1.png",
                f"{style_base}/Jump.png",
                f"{style_base}/Hurt.png",
                "listening.gif",
                "listen.gif",
                "rana.gif",
                "ranaa.gif",
            ],
            "attack_1": [
                f"{style_base}/Attack_1.png",
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_4.png",
            ],
            "attack_2": [
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_1.png",
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_4.png",
            ],
            "attack_3": [
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_1.png",
                f"{style_base}/Attack_4.png",
            ],
            "attack_4": [
                f"{style_base}/Attack_4.png",
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_1.png",
            ],
        }

    def schedule_auto_color_change(self):
        if self.is_destroying:
            return

        interval_seconds = random.randint(*self.color_change_interval_range)
        self.color_change_job = self.root.after(
            interval_seconds * 1000, self.auto_change_slime_color
        )

    def auto_change_slime_color(self):
        if self.is_destroying:
            return

        next_style = self.choose_next_style()
        self.switch_style(next_style)
        self.schedule_auto_color_change()

    def choose_next_style(self):
        if len(self.available_styles) <= 1:
            return self.current_style

        if not self.style_cycle_queue:
            self.style_cycle_queue = [
                style for style in self.available_styles if style != self.current_style
            ]
            random.shuffle(self.style_cycle_queue)

        return self.style_cycle_queue.pop(0)

    def switch_style(self, style_name):
        previous_sources = self.animation_sources
        previous_animations = self.state_animations
        previous_style = self.current_style

        self.animation_sources = self.build_animation_sources_for_style(style_name)

        try:
            self.state_animations = self.load_state_animations()
            self.current_style = style_name
            self.frame_index = 0
            self.animation_state = self.get_animation_state()
            self.style_cycle_queue = [
                style for style in self.style_cycle_queue if style != self.current_style
            ]
            print(f"[Mascota] Cambio automatico de estilo: {previous_style} -> {self.current_style}")
        except FileNotFoundError as error:
            self.animation_sources = previous_sources
            self.state_animations = previous_animations
            print(f"[Mascota] No se pudo cambiar a {style_name}: {error}")

    def load_state_animations(self):
        loaded_animations = {}
        fallback_pair = None

        for state, candidates in self.animation_sources.items():
            state_loaded = False

            for filename in candidates:
                animation_path = self.asset_dir / filename
                if not animation_path.exists():
                    continue

                frame_pair = self._load_animation_pair(animation_path)
                if frame_pair is None:
                    continue

                right_frames, left_frames = frame_pair
                loaded_animations[state] = {
                    "right": right_frames,
                    "left": left_frames,
                    "source": filename,
                }

                if fallback_pair is None:
                    fallback_pair = (right_frames, left_frames, filename)

                print(f"[Animacion] {state} -> {filename}")
                state_loaded = True
                break

            if not state_loaded:
                print(f"[Animacion] No se encontro archivo para estado '{state}', aplicando fallback.")

        if not loaded_animations:
            raise FileNotFoundError(
                "No se encontro ningun GIF valido. Coloca al menos un GIF en la carpeta del proyecto."
            )

        if fallback_pair is not None:
            fallback_right, fallback_left, fallback_source = fallback_pair
            for required_state in (
                "walking",
                "idle",
                "running",
                "jump",
                "dead",
                "listening",
                "attack_1",
                "attack_2",
                "attack_3",
                "attack_4",
            ):
                if required_state not in loaded_animations:
                    loaded_animations[required_state] = {
                        "right": fallback_right,
                        "left": fallback_left,
                        "source": fallback_source,
                    }

        return loaded_animations

    def _load_animation_pair(self, animation_path):
        suffix = animation_path.suffix.lower()
        if suffix == ".gif":
            return self._load_gif_pair(animation_path)
        if suffix == ".png":
            return self._load_sprite_sheet_pair(animation_path)
        return None

    def _load_gif_pair(self, gif_path):
        with Image.open(gif_path) as gif:
            rgba_frames = [
                frame.copy().convert("RGBA") for frame in ImageSequence.Iterator(gif)
            ]

        if not rgba_frames:
            return None

        right_frames = [ImageTk.PhotoImage(frame) for frame in rgba_frames]
        left_frames = [
            ImageTk.PhotoImage(frame.transpose(Image.FLIP_LEFT_RIGHT))
            for frame in rgba_frames
        ]

        return right_frames, left_frames

    def _load_sprite_sheet_pair(self, png_path):
        with Image.open(png_path) as sprite_sheet:
            sprite_sheet = sprite_sheet.convert("RGBA")
            sheet_width, sheet_height = sprite_sheet.size

            # Esta colección usa frames cuadrados de alto fijo (ej. 1024x128 -> 8 frames de 128).
            frame_width = sheet_height
            if frame_width <= 0:
                return None

            frame_count = sheet_width // frame_width
            if frame_count <= 0:
                return None

            rgba_frames = []
            for index in range(frame_count):
                left = index * frame_width
                top = 0
                right = left + frame_width
                bottom = sheet_height
                rgba_frames.append(sprite_sheet.crop((left, top, right, bottom)))

        if not rgba_frames:
            return None

        right_frames = [ImageTk.PhotoImage(frame) for frame in rgba_frames]
        left_frames = [
            ImageTk.PhotoImage(frame.transpose(Image.FLIP_LEFT_RIGHT))
            for frame in rgba_frames
        ]

        return right_frames, left_frames

    def get_animation_state(self):
        if self.state == "dead":
            return "dead"

        if self.state == "jump":
            return "jump"

        if self.is_dragging:
            self.update_drag_attack_state()
            return self.current_drag_attack_state

        if self.state == "walking" and self.is_running:
            return "running"

        if self.state in ("walking", "idle", "listening"):
            return self.state
        if self.state == "paused":
            return "idle"
        return "walking"

    def update_drag_attack_state(self):
        now = time.time()
        if now < self.next_drag_attack_change:
            return

        self.current_drag_attack_state = random.choice(self.drag_attack_states)
        self.next_drag_attack_change = now + random.uniform(0.25, 0.7)

    def get_frames_for_state(self, animation_state):
        state_frames = self.state_animations.get(animation_state)
        if state_frames is None:
            state_frames = self.state_animations["walking"]

        if self.direction_x == 1:
            return state_frames["right"]
        return state_frames["left"]

    def get_walking_sprite_size(self):
        walking_frames = self.state_animations["walking"]["right"]
        return walking_frames[0].width(), walking_frames[0].height()

    # ---------------- ANIMACIÓN ----------------
    def animate(self):
        if self.is_destroying:
            return

        current_animation_state = self.get_animation_state()
        if current_animation_state != self.animation_state:
            self.animation_state = current_animation_state
            self.frame_index = 0

        current_frames = self.get_frames_for_state(self.animation_state)

        self.label.config(image=current_frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(current_frames)

        if self.animation_state == "walking":
            delay = 100
        elif self.animation_state == "running":
            delay = 70
        elif self.animation_state == "idle":
            delay = 300
        elif self.animation_state == "listening":
            delay = 50
        elif self.animation_state == "jump":
            delay = 55
        elif self.animation_state == "dead":
            delay = 220
        elif self.animation_state.startswith("attack_"):
            delay = 65
        else:
            delay = 100

        self.root.after(delay, self.animate)

    # ---------------- MOVIMIENTO ----------------
    def move(self):
        if self.is_destroying:
            return

        if self.state == "dead":
            if time.time() >= self.dead_until:
                self.set_walking()
            self.root.after(40, self.move)
            return

        # Durante arrastre no hay movimiento autonomo.
        if self.is_dragging:
            self.root.after(40, self.move)
            return

        if self.state == "jump":
            self.move_jump()
            self.root.after(40, self.move)
            return

        if self.state == "walking":
            self.update_running_from_cursor()
            self.move_walking()

        elif self.state == "listening":
            # Pequeña vibración
            self.root.geometry(
                f"+{self.x + random.randint(-3,3)}+{self.y + random.randint(-3,3)}"
            )

        elif self.state == "idle":
            self.hunt_flies_idle()

        self.root.after(40, self.move)

    def move_walking(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        sprite_width, sprite_height = self.get_walking_sprite_size()

        now = time.time()
        if now >= self.next_direction_change:
            self.direction_x = random.choice([-1, 1])
            self.direction_y = random.choice([-1, 1])
            self.speed_x = random.uniform(2.5, 6.5)
            self.speed_y = random.uniform(2.0, 5.0)
            self.next_direction_change = now + random.uniform(1.2, 3.6)

            # Esporadicamente acelera para dar variedad al movimiento.
            if random.random() < 0.35:
                self.walk_mode = "dash"
                self.walk_mode_until = now + random.uniform(0.5, 1.2)

        if self.walk_mode == "dash" and now >= self.walk_mode_until:
            self.walk_mode = "normal"

        speed_multiplier = 1.0 if self.walk_mode == "normal" else 1.7
        if self.is_running:
            speed_multiplier = max(speed_multiplier, 2.3)

        self.x += int(self.speed_x * self.direction_x * speed_multiplier)

        # Oscilacion vertical suave para evitar un desplazamiento robotico.
        self.move_phase += 0.22
        bob = int(math.sin(self.move_phase) * (2 if self.walk_mode == "normal" else 4))
        self.base_y += int(self.speed_y * self.direction_y * 0.7)
        self.y = self.base_y + bob

        if self.x <= 0:
            self.x = 0
            self.direction_x = 1
            self.frame_index = 0
        elif self.x >= screen_width - sprite_width:
            self.x = screen_width - sprite_width
            self.direction_x = -1
            self.frame_index = 0

        if self.y <= 0:
            self.y = 0
            self.base_y = self.y
            self.direction_y = 1
        elif self.y >= screen_height - sprite_height:
            self.y = screen_height - sprite_height
            self.base_y = self.y
            self.direction_y = -1

        self.root.geometry(f"+{self.x}+{self.y}")

    def update_running_from_cursor(self):
        now = time.time()
        if now < self.run_boost_until:
            self.is_running = True
            return

        pointer_x, pointer_y = self.root.winfo_pointerxy()
        sprite_width, sprite_height = self.get_walking_sprite_size()
        center_x = self.x + sprite_width // 2
        center_y = self.y + sprite_height // 2

        delta_x = center_x - pointer_x
        delta_y = center_y - pointer_y
        distance = math.hypot(delta_x, delta_y)

        if distance <= self.escape_distance:
            self.is_running = True
            if abs(delta_x) > 4:
                self.direction_x = 1 if delta_x > 0 else -1
            if abs(delta_y) > 4:
                self.direction_y = 1 if delta_y > 0 else -1
        else:
            self.is_running = False

    def move_jump(self):
        now = time.time()
        progress = (now - self.jump_start_time) / self.jump_duration
        if progress >= 1.0:
            self.set_walking()
            self.y = self.base_y
            self.root.geometry(f"+{self.x}+{self.y}")
            return

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        sprite_width, sprite_height = self.get_walking_sprite_size()

        self.x += int((self.speed_x * 1.4) * self.direction_x)
        arc = 4 * progress * (1 - progress)
        self.y = int(self.jump_base_y - (self.jump_height * arc))

        if self.x <= 0:
            self.x = 0
            self.direction_x = 1
        elif self.x >= screen_width - sprite_width:
            self.x = screen_width - sprite_width
            self.direction_x = -1

        self.y = max(0, min(screen_height - sprite_height, self.y))
        self.root.geometry(f"+{self.x}+{self.y}")

    def hunt_flies_idle(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        now = time.time()

        if self.fly_target is None and now >= self.next_fly_spawn:
            offset_x = random.randint(-120, 120)
            offset_y = random.randint(-80, 80)
            target_x = max(0, min(screen_width - 100, self.x + offset_x))
            target_y = max(0, min(screen_height - 100, self.y + offset_y))
            self.fly_target = (target_x, target_y)

        if self.fly_target is None:
            return

        fly_x, fly_y = self.fly_target
        dx = fly_x - self.x
        dy = fly_y - self.y
        step = 3

        if abs(dx) < 8 and abs(dy) < 8:
            self.fly_target = None
            self.next_fly_spawn = now + random.uniform(0.8, 2.0)
            return

        if dx != 0:
            self.direction_x = 1 if dx > 0 else -1
            self.x += max(-step, min(step, dx))
        if dy != 0:
            self.direction_y = 1 if dy > 0 else -1
            self.y += max(-step, min(step, dy))
            self.base_y = self.y

        self.root.geometry(f"+{self.x}+{self.y}")

    # ---------------- MENÚ ----------------
    def show_menu(self, event):
        self.state = "menu"
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            if self.state == "menu":
                self.state = "walking"

    def set_walking(self):
        self.state = "walking"
        self.drag_ready = False
        self.is_dragging = False
        self.is_running = False
        self.base_y = self.y

    def set_idle(self):
        self.state = "idle"
        self.is_running = False
        self.fly_target = None
        self.next_fly_spawn = time.time() + random.uniform(0.5, 1.6)

    def set_listening(self):
        self.state = "listening"

    def toggle_state_cycle(self):
        if self.state == "walking":
            self.state = "idle"
        else:
            self.state = "walking"

    # ---------------- CLICK IZQUIERDO ----------------
    def on_left_press(self, event):
        if self.is_destroying:
            return
        if self.state == "dead":
            return

        # Al intentar agarrarla entra en arrastre y ataca.
        self.is_dragging = True
        self.state = "dragging"
        self.drag_offset_x = event.x
        self.drag_offset_y = event.y
        self.current_drag_attack_state = random.choice(self.drag_attack_states)
        self.next_drag_attack_change = time.time() + random.uniform(0.2, 0.6)

        self.is_pressing = True
        self.press_started_at = time.time()
        self.schedule_hold_vibration()

    def on_left_release(self, _event):
        if not self.is_pressing:
            return

        self.is_pressing = False

        if self.long_press_job is not None:
            self.root.after_cancel(self.long_press_job)
            self.long_press_job = None

        if self.hold_vibration_job is not None:
            self.root.after_cancel(self.hold_vibration_job)
            self.hold_vibration_job = None

        if self.is_dragging:
            self.is_dragging = False
            self.run_boost_until = time.time() + random.uniform(1.8, 2.8)
            self.set_walking()
            return

    def on_left_drag(self, event):
        if not self.is_dragging or self.is_destroying:
            return

        self.state = "dragging"
        self.update_drag_attack_state()

        new_x = event.x_root - self.drag_offset_x
        new_y = event.y_root - self.drag_offset_y

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        sprite_width, sprite_height = self.get_walking_sprite_size()

        self.x = max(0, min(screen_width - sprite_width, new_x))
        self.y = max(0, min(screen_height - sprite_height, new_y))
        self.base_y = self.y
        self.root.geometry(f"+{self.x}+{self.y}")

    def trigger_jump(self):
        if self.is_destroying or self.is_dragging or self.state == "dead":
            return

        self.state = "jump"
        self.jump_start_time = time.time()
        self.jump_base_y = self.y

    def trigger_dead(self):
        if self.is_destroying:
            return

        self.state = "dead"
        self.is_dragging = False
        self.is_running = False
        self.dead_until = time.time() + 2.6

    def schedule_hold_vibration(self):
        if not self.is_pressing or self.has_exploded or self.is_destroying:
            return

        if self.state != "listening" and not self.is_dragging:
            self.root.geometry(
                f"+{self.x + random.randint(-2,2)}+{self.y + random.randint(-2,2)}"
            )

        self.hold_vibration_job = self.root.after(50, self.schedule_hold_vibration)

    def explode_and_exit(self):
        if self.has_exploded or self.is_destroying:
            return
        self.has_exploded = True
        self.is_destroying = True

        if self.color_change_job is not None:
            self.root.after_cancel(self.color_change_job)
            self.color_change_job = None

        explosion = tk.Toplevel(self.root)
        explosion.overrideredirect(True)
        explosion.attributes("-topmost", True)
        explosion.config(bg="white")
        explosion.wm_attributes("-transparentcolor", "white")
        explosion.geometry(f"200x200+{max(0, self.x - 40)}+{max(0, self.y - 40)}")

        canvas = tk.Canvas(explosion, width=200, height=200, bg="white", highlightthickness=0)
        canvas.pack()

        def animate_boom(frame=0):
            canvas.delete("all")
            radius = 10 + frame * 8
            colors = ["#ffec99", "#ffb703", "#fb8500", "#d00000"]

            for i, color in enumerate(colors):
                r = max(2, radius - i * 12)
                canvas.create_oval(100 - r, 100 - r, 100 + r, 100 + r, fill=color, outline="")

            for _ in range(10):
                px = random.randint(20, 180)
                py = random.randint(20, 180)
                size = random.randint(3, 7)
                canvas.create_oval(px, py, px + size, py + size, fill="#3a0ca3", outline="")

            if frame < 9:
                explosion.after(45, lambda: animate_boom(frame + 1))
            else:
                explosion.destroy()
                self.root.destroy()

        animate_boom()

    # ---------------- VOZ ----------------
    def start_listening(self):
        self.set_listening()

        if not VOICE_AVAILABLE:
            if not self.voice_warning_shown:
                print("[Aviso] speech_recognition/pyttsx3 no disponibles en el entorno.")
                self.voice_warning_shown = True
            self.root.after(1200, self.set_walking)
            return

        if self.listening_thread and self.listening_thread.is_alive():
            return

        self.listening_thread = threading.Thread(target=self._listen_worker, daemon=True)
        self.listening_thread.start()

    def _listen_worker(self):
        recognizer = sr.Recognizer()

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=4)

            text = recognizer.recognize_google(audio, language="es-ES").lower()
            print(f"[Escuchado] {text}")

            if "hola" in text:
                self._speak("me pica la cola")
        except Exception as error:
            print(f"[Escucha] {error}")
        finally:
            self.ui_queue.put(("set_state", "walking"))

    def _speak(self, text):
        if not VOICE_AVAILABLE:
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            engine.say(text)
            engine.runAndWait()
        except Exception as error:
            print(f"[Voz] {error}")

    def process_ui_queue(self):
        if self.is_destroying:
            return

        while True:
            try:
                action, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if action == "set_state":
                self.state = payload

        self.root.after(120, self.process_ui_queue)

if __name__ == "__main__":
    root = tk.Tk()
    pet = DesktopPet(root)
    root.mainloop()