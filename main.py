import heapq
import json
import ctypes
import os
import queue
import random
import re
import shutil
import threading
import time
import tkinter as tk
import math
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import messagebox, simpledialog

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
        self.execution_mode = "free"
        self.blocks = []
        self.block_size = (48, 48)
        self.max_blocks = 20
        self.object_assets_dir = Path(__file__).resolve().parent.parent / "objets"
        self.block_image_paths = []
        self.block_image_cache = {}
        self.auto_block_job = None
        self.auto_block_interval_range = (900, 1800)
        self.auto_jump_interval_range = (2.4, 4.6)
        self.next_auto_jump_at = 0.0
        self.floor_margin = 48
        self.gravity = 1.15
        self.vertical_velocity = 0.0
        self.max_fall_speed = 22.0
        self.jump_strength = -16.0
        self.platform_jump_height = int((abs(self.jump_strength) ** 2) / (2 * self.gravity))
        self.on_ground = False
        self.fall_start_y = 0
        self.is_in_air = False
        self.fall_death_threshold = self.platform_jump_height * 2
        self.drag_attack_states = ["attack_1", "attack_2", "attack_3", "attack_4"]
        self.current_drag_attack_state = "attack_1"
        self.next_drag_attack_change = 0.0
        self.cursor_attack_distance = 78
        self.cursor_disengage_distance = 125
        self.is_cursor_attacking = False
        self.next_obstacle_clear_at = 0.0
        self.next_stuck_jump_at = 0.0
        self.pursuit_bias_direction = 0
        self.pursuit_bias_until = 0.0
        self.jump_start_time = 0.0
        self.jump_duration = 0.75
        self.jump_height = 70
        self.jump_base_y = 0
        self.dead_until = 0.0
        self.dead_recovery_seconds = 3.0
        self.move_phase = random.uniform(0, math.pi * 2)
        self.base_y = 0
        self.walk_mode = "normal"
        self.walk_mode_until = 0.0
        self.sandbox_mode = False
        self.path_nodes = []
        self.next_path_recalc_at = 0.0
        self.last_path_target = None
        self.path_recalc_seconds = 0.42
        self.manual_nudge_speed = 28
        self.last_cursor_distance = None
        self.stuck_toward_cursor_ticks = 0
        self.free_moods = ["brava", "feliz"]
        self.free_mood = random.choice(self.free_moods)
        self.free_mood_interval_range = (8, 16)
        self.next_free_mood_change_at = time.time() + random.uniform(*self.free_mood_interval_range)
        self.free_chase_distance = 280
        self.free_attack_distance = 84
        self.is_cursor_attacking = False
        self.next_platform_behavior_change = 0.0
        self.platform_idle_until = 0.0
        self.block_lifetime_seconds = 16.0

        self.hold_to_explode_seconds = 1.8
        self.asset_dir = Path(__file__).resolve().parent
        self.save_file = self.asset_dir / "pet_state.json"
        self.assistant_config_file = self.asset_dir / "assistant_config.json"
        self.available_styles = self.discover_available_styles()
        self.current_style = random.choice(self.available_styles)
        self.style_cycle_queue = []
        self.color_change_interval_range = (12, 22)

        self.personality_profiles = {
            "explorador": {
                "speed_boost": 1.15,
                "build_rate": (850, 1550),
                "jump_rate": (2.0, 4.0),
                "need_drain": 1.12,
            },
            "guardian": {
                "speed_boost": 0.95,
                "build_rate": (1100, 1900),
                "jump_rate": (2.8, 5.0),
                "need_drain": 0.9,
            },
            "caotico": {
                "speed_boost": 1.28,
                "build_rate": (700, 1350),
                "jump_rate": (1.6, 3.2),
                "need_drain": 1.25,
            },
        }
        self.personality_name = random.choice(list(self.personality_profiles.keys()))
        self.active_personality = self.personality_profiles[self.personality_name]

        self.needs = {
            "hunger": 75.0,
            "energy": 78.0,
            "fun": 72.0,
            "social": 65.0,
            "health": 100.0,
        }
        self.needs_tick_ms = 1200
        self.needs_job = None

        self.stats = {
            "total_sessions": 0,
            "total_runtime_seconds": 0,
            "jumps": 0,
            "deaths": 0,
            "blocks_created": 0,
            "style_changes": 0,
            "care_actions": 0,
            "pc_actions": 0,
            "saves": 0,
            "loads": 0,
        }
        self.session_started_at = time.time()
        self.hud_enabled = False
        self.hud_job = None
        self.hud_update_ms = 2000
        self.hud_window = None
        self.hud_label = None
        self.desktop_path = Path.home() / "Desktop"
        self.archive_folder_name = "Archivado_Mascota"
        self.action_log_file = self.asset_dir / "assistant_actions.json"
        self.max_action_log_entries = 120
        self.system_action_cooldown_until = 0.0
        self.system_action_cooldown_seconds = 0.9
        self.visibility_guard_job = None
        self.visibility_guard_ms = 1800
        self.assistant_job = None
        self.assistant_tick_ms = 6000
        self.next_desktop_maintenance_at = 0.0
        self.autocare_cooldowns = {"feed": 0.0, "play": 0.0, "rest": 0.0}
        self.voice_wake_word = "asistente"
        self.require_wake_word = True
        self.permission_level = "full"  # query | files | full
        self.permission_levels = ("query", "files", "full")
        self.llm_enabled = bool(os.getenv("OPENAI_API_KEY"))
        self.llm_provider = "openai"
        self.llm_model = os.getenv("ASSISTANT_LLM_MODEL", "gpt-4o-mini")
        self.llm_api_key = os.getenv("OPENAI_API_KEY", "")
        self.llm_endpoint = "https://api.openai.com/v1/chat/completions"
        self.llm_timeout_seconds = 9
        self.allowed_roots = [
            self.desktop_path.resolve(),
            (Path.home() / "Documents").resolve(),
            self.asset_dir.resolve(),
        ]

        self.animation_sources = self.build_animation_sources_for_style(self.current_style)
        self.block_image_paths = self.load_block_image_paths()
        print(f"[Mascota] Estilo inicial: {self.current_style}")

        # Configuración ventana
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "white")

        # Cargar animaciones por estado con fallback.
        self.state_animations = self.load_state_animations()
        self.animation_state = "walking"
        sprite_width, _ = self.get_walking_sprite_size()
        # Mantener bloques menores al tamano de la mascota para evitar colisiones extranas.
        block_edge = max(32, min(56, sprite_width - 16))
        self.block_size = (block_edge, block_edge)
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
        self.menu.add_separator()
        self.menu.add_command(label="🎮 Modo Libre", command=self.set_mode_free)
        self.menu.add_command(label="🕹️ Modo Suelo", command=self.set_mode_platform)
        self.menu.add_command(label="🎤 Escuchar", command=self.start_listening)
        self.menu.add_separator()
        self.menu.add_command(label="⏯️ Musica play/pausa", command=lambda: self.control_media_key("play_pause"))
        self.menu.add_command(label="⏭️ Siguiente cancion", command=lambda: self.control_media_key("next"))
        self.menu.add_command(label="⏮️ Cancion anterior", command=lambda: self.control_media_key("prev"))
        self.menu.add_separator()
        self.menu.add_command(label="🧪 Sandbox ON/OFF", command=self.toggle_sandbox)
        self.menu.add_command(label="🧹 Limpiar bloques", command=self.clear_blocks)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Salir", command=self.root.destroy)

        self.root.bind_all("<Left>", lambda _event: self.sandbox_nudge(-1))
        self.root.bind_all("<Right>", lambda _event: self.sandbox_nudge(1))
        self.root.bind_all("<Up>", lambda _event: self.sandbox_jump())
        self.root.bind_all("<b>", lambda _event: self.place_block_at_cursor() if self.sandbox_mode else None)
        self.root.bind_all("<c>", lambda _event: self.clear_blocks() if self.sandbox_mode else None)

        # Iniciar ciclos
        self.load_assistant_config()
        self.apply_personality(self.personality_name)
        self.load_pet_state(quiet=True)
        self.stats["total_sessions"] += 1
        self.animate()
        self.move()
        self.process_ui_queue()
        self.schedule_visibility_guard()
        self.schedule_assistant_autonomy()
        self.schedule_needs_tick()
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

    def schedule_visibility_guard(self):
        if self.is_destroying:
            return

        self.ensure_visible_and_topmost()
        self.visibility_guard_job = self.root.after(
            self.visibility_guard_ms, self.schedule_visibility_guard
        )

    def ensure_visible_and_topmost(self):
        if self.is_destroying:
            return

        sprite_width, sprite_height = self.get_walking_sprite_size()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        self.x = max(0, min(screen_width - sprite_width, self.x))
        self.y = max(0, min(screen_height - sprite_height, self.y))
        self.base_y = self.y

        try:
            self.root.deiconify()
        except Exception:
            pass

        # Reafirma prioridad de capa para evitar perderse detras de otras ventanas.
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.geometry(f"+{self.x}+{self.y}")

    def schedule_assistant_autonomy(self):
        if self.is_destroying:
            return

        self.run_autocare_if_needed()
        self.run_desktop_maintenance_if_needed()
        self.assistant_job = self.root.after(self.assistant_tick_ms, self.schedule_assistant_autonomy)

    def run_autocare_if_needed(self):
        now = time.time()

        if self.needs["hunger"] < 34 and now >= self.autocare_cooldowns["feed"]:
            self.feed_pet(auto=True)
            self.autocare_cooldowns["feed"] = now + random.uniform(28, 55)

        if self.needs["fun"] < 26 and now >= self.autocare_cooldowns["play"]:
            self.play_with_pet(auto=True)
            self.autocare_cooldowns["play"] = now + random.uniform(30, 62)

        if self.needs["energy"] < 24 and now >= self.autocare_cooldowns["rest"]:
            self.rest_pet(auto=True)
            self.autocare_cooldowns["rest"] = now + random.uniform(42, 78)

    def run_desktop_maintenance_if_needed(self):
        if not self.has_permission("automation"):
            return

        now = time.time()
        if now < self.next_desktop_maintenance_at:
            return

        self.next_desktop_maintenance_at = now + random.uniform(90, 160)
        desktop = self.desktop_path
        if not desktop.exists():
            return

        helper_folder = desktop / "AsistentePC"
        if self.is_allowed_path(helper_folder) and not helper_folder.exists():
            try:
                helper_folder.mkdir(parents=False, exist_ok=True)
                self.stats["pc_actions"] += 1
                self.append_action_log("auto_create_folder", str(helper_folder), "ok")
                print("[Asistente] Cree carpeta base de trabajo en el escritorio.")
            except Exception as error:
                self.append_action_log("auto_create_folder", str(helper_folder), f"error:{error}")

        archive_targets = []
        for item in desktop.iterdir():
            if item.name == self.archive_folder_name:
                continue
            lower_name = item.name.lower()
            is_default_folder = lower_name.startswith("nueva carpeta") or lower_name.startswith("new folder")
            is_temp_file = item.is_file() and lower_name.endswith((".tmp", ".log", ".bak"))
            if is_default_folder or is_temp_file:
                archive_targets.append(item)

        if archive_targets:
            selected = random.choice(archive_targets)
            self.archive_desktop_item(selected.name, auto=True)

    def load_block_image_paths(self):
        if not self.object_assets_dir.exists():
            print("[Bloque] Carpeta 'objets' no encontrada, usando bloques simples.")
            return []

        patterns = ["**/*.png", "**/*.webp", "**/*.jpg", "**/*.jpeg"]
        candidates = []

        for pattern in patterns:
            candidates.extend(self.object_assets_dir.glob(pattern))

        filtered = []
        for image_path in candidates:
            lowered = str(image_path).lower()
            if "\\tiles\\" in lowered or "/tiles/" in lowered or "tile" in image_path.name.lower():
                filtered.append(image_path)

        if not filtered:
            filtered = candidates

        random.shuffle(filtered)
        print(f"[Bloque] Skins cargadas: {len(filtered)}")
        return filtered

    def get_random_block_skin(self):
        if not self.block_image_paths:
            return None

        image_path = random.choice(self.block_image_paths)
        cache_key = f"{image_path}|{self.block_size[0]}x{self.block_size[1]}"

        if cache_key in self.block_image_cache:
            return self.block_image_cache[cache_key]

        try:
            with Image.open(image_path) as block_img:
                resized = block_img.convert("RGBA").resize(self.block_size, Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(resized)
            self.block_image_cache[cache_key] = photo
            return photo
        except Exception:
            return None

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
            self.stats["style_changes"] += 1
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

        if self.state == "cursor_attack" or self.is_cursor_attacking:
            self.update_drag_attack_state()
            return self.current_drag_attack_state

        if self.is_dragging:
            self.update_drag_attack_state()
            return self.current_drag_attack_state

        if self.state == "walking" and self.is_running and self.execution_mode == "free":
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

    def get_floor_y(self):
        _, sprite_height = self.get_walking_sprite_size()
        return max(0, self.root.winfo_screenheight() - sprite_height - self.floor_margin)

    def set_mode_free(self):
        self.execution_mode = "free"
        self.is_cursor_attacking = False
        self.path_nodes.clear()
        self.last_path_target = None
        self.cancel_auto_blocks()
        self.auto_block_interval_range = self.active_personality["build_rate"]
        self.max_blocks = 20
        self.next_free_mood_change_at = time.time() + random.uniform(*self.free_mood_interval_range)
        self.vertical_velocity = 0.0
        self.on_ground = False
        self.is_in_air = False
        self.next_auto_jump_at = 0.0
        self.fall_start_y = self.y
        self.set_walking()
        print("[Modo] Libre")

    def set_mode_platform(self):
        self.execution_mode = "platform"
        self.is_cursor_attacking = False
        base_min, base_max = self.active_personality["build_rate"]
        self.auto_block_interval_range = (int(base_min * 2.6), int(base_max * 2.8))
        self.max_blocks = 10
        self.block_lifetime_seconds = 14.0
        if not self.sandbox_mode:
            self.start_auto_blocks()
        self.vertical_velocity = 0.0
        self.is_in_air = True
        self.on_ground = False
        self.base_y = self.y
        self.fall_start_y = self.y
        self.next_auto_jump_at = time.time() + random.uniform(*self.auto_jump_interval_range)
        self.path_nodes.clear()
        self.last_path_target = None
        self.next_platform_behavior_change = 0.0
        self.platform_idle_until = 0.0
        self.set_walking()
        print("[Modo] Suelo - Patrón: caminar y dormir")

    def start_auto_blocks(self):
        self.cancel_auto_blocks()
        self.auto_block_job = self.root.after(
            random.randint(*self.auto_block_interval_range), self.auto_place_block
        )

    def cancel_auto_blocks(self):
        if self.auto_block_job is not None:
            self.root.after_cancel(self.auto_block_job)
            self.auto_block_job = None

    def schedule_next_auto_block(self):
        if self.execution_mode != "platform" or self.is_destroying or self.sandbox_mode:
            return

        self.auto_block_job = self.root.after(
            random.randint(*self.auto_block_interval_range), self.auto_place_block
        )

    def auto_place_block(self):
        self.auto_block_job = None

        if self.execution_mode != "platform" or self.is_destroying or self.sandbox_mode:
            return

        # Reduce la frecuencia real: no siempre construye cuando vence el temporizador.
        if random.random() < 0.45:
            self.schedule_next_auto_block()
            return

        screen_width = self.root.winfo_screenwidth()
        floor_y = self.get_floor_y()
        width, height = self.block_size

        sprite_width, sprite_height = self.get_walking_sprite_size()
        target_x = self.x + random.randint(-160, 160)
        target_y = self.y + random.randint(-120, 120)
        pet_center_x = self.x + sprite_width // 2
        pet_level = self.get_level_from_y(self.y)
        target_level = self.get_level_from_y(target_y - sprite_height // 2)

        direction = 1 if target_x >= pet_center_x else -1
        cursor_above = target_y < (self.y - sprite_height // 4)
        horizontal_gap = random.randint(width + 4, width + 16)
        if cursor_above:
            horizontal_gap = random.randint(width // 2, width + 10)

        desired_level = pet_level
        if target_level > pet_level:
            desired_level = pet_level + 1
        elif target_level < pet_level:
            desired_level = max(0, pet_level - 1)

        base_x = self.x + direction * horizontal_gap
        base_x = max(0, min(screen_width - width, base_x))
        base_y = max(80, floor_y - (desired_level * height))

        if cursor_above:
            # Prioriza escaleras para subir hacia el cursor.
            candidate_offsets = [
                (direction * (width // 2), -height),
                (direction * (width + 4), -height),
                (direction * (width // 2), 0),
                (0, -height),
                (0, 0),
            ]
        else:
            candidate_offsets = [
                (0, 0),
                (direction * (width + 6), 0),
                (-direction * (width + 6), 0),
                (0, -height),
                (0, height),
            ]

        placed = False
        for offset_x, offset_y in candidate_offsets:
            block_x = max(0, min(screen_width - width, base_x + offset_x))
            block_y = max(80, base_y + offset_y)

            if self.is_harmful_block_candidate(
                block_x,
                block_y,
                width,
                height,
                target_y,
                sprite_width,
                sprite_height,
                direction,
            ):
                continue

            if not self.is_block_slot_free(block_x, block_y, width, height):
                continue

            self.create_block(block_x, block_y, cast_from_pet=True)
            placed = True
            break

        if not placed:
            print("[Bloque] Sin espacio util para construir hacia el cursor.")

        self.schedule_next_auto_block()

    def get_level_from_y(self, y):
        floor_y = self.get_floor_y()
        _, height = self.block_size
        level = round((floor_y - y) / max(1, height))
        return max(0, level)

    def is_harmful_block_candidate(
        self,
        block_x,
        block_y,
        width,
        height,
        pointer_y,
        sprite_width,
        sprite_height,
        direction,
    ):
        pet_left = self.x - 8
        pet_right = self.x + sprite_width + 8
        pet_top = self.y
        pet_bottom = self.y + sprite_height

        block_right = block_x + width
        block_bottom = block_y + height

        overlap_pet_x = block_right > pet_left and block_x < pet_right

        # Evita crear un "techo" sobre la mascota cuando necesita subir.
        if overlap_pet_x and block_bottom > pet_top and block_y < (pet_top + sprite_height // 2):
            return True

        cursor_below_pet = pointer_y > (pet_top + sprite_height // 2)
        # Evita crear soporte debajo del personaje cuando el objetivo esta abajo.
        if cursor_below_pet and overlap_pet_x and block_y >= (pet_bottom - 10):
            return True

        # Evita bloquear el carril frontal inmediato en direccion de persecucion.
        if direction == 1:
            front_gap = block_x - (self.x + sprite_width)
            if 0 <= front_gap <= (width + 10) and block_bottom > pet_top + 8:
                return True
        else:
            front_gap = self.x - block_right
            if 0 <= front_gap <= (width + 10) and block_bottom > pet_top + 8:
                return True

        return False

    def is_block_slot_free(self, block_x, block_y, width, height):
        left_a = block_x
        top_a = block_y
        right_a = block_x + width
        bottom_a = block_y + height

        for block in self.blocks:
            left_b = block["x"]
            top_b = block["y"]
            right_b = block["x"] + block["w"]
            bottom_b = block["y"] + block["h"]

            overlaps = (
                left_a < right_b
                and right_a > left_b
                and top_a < bottom_b
                and bottom_a > top_b
            )
            if overlaps:
                return False

        return True

    def create_block(self, block_x, block_y, cast_from_pet=False):
        width, height = self.block_size

        if not self.is_block_slot_free(block_x, block_y, width, height):
            return False

        if cast_from_pet:
            sprite_width, sprite_height = self.get_walking_sprite_size()
            self.cast_spell_effect(self.x + sprite_width // 2, self.y + sprite_height // 2)

        block_window = tk.Toplevel(self.root)
        block_window.overrideredirect(True)
        block_window.attributes("-topmost", True)
        block_window.geometry(f"{width}x{height}+{block_x}+{block_y}")

        canvas = tk.Canvas(block_window, width=width, height=height, bg="#2f5d62", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        skin = self.get_random_block_skin()
        if skin is not None:
            canvas.create_image(0, 0, anchor="nw", image=skin)
            block_window._skin_ref = skin
        else:
            canvas.create_rectangle(0, 0, width, height, fill="#2f5d62", outline="#1b3a4b", width=2)

        self.blocks.append(
            {
                "x": block_x,
                "y": block_y,
                "w": width,
                "h": height,
                "window": block_window,
                "created_at": time.time(),
            }
        )
        self.path_nodes.clear()
        self.last_path_target = None
        self.stats["blocks_created"] += 1

        if len(self.blocks) > self.max_blocks:
            oldest = self.blocks.pop(0)
            try:
                oldest["window"].destroy()
            except Exception:
                pass

        print(f"[Bloque] Creado en ({block_x}, {block_y})")
        return True

    def place_block_at_cursor(self):
        width, height = self.block_size
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        block_x = pointer_x - (width // 2)
        block_y = pointer_y - (height // 2)

        self.cast_spell_effect(pointer_x, pointer_y)
        self.create_block(block_x, block_y, cast_from_pet=False)

    def cast_spell_effect(self, center_x, center_y):
        effect_size = 120
        effect = tk.Toplevel(self.root)
        effect.overrideredirect(True)
        effect.attributes("-topmost", True)
        effect.config(bg="white")
        effect.wm_attributes("-transparentcolor", "white")
        effect.geometry(
            f"{effect_size}x{effect_size}+{center_x - effect_size // 2}+{center_y - effect_size // 2}"
        )

        canvas = tk.Canvas(effect, width=effect_size, height=effect_size, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        colors = ["#8ecae6", "#219ebc", "#90e0ef", "#48cae4"]

        def animate(frame=0):
            canvas.delete("all")
            radius = 14 + frame * 7

            for index, color in enumerate(colors):
                r = max(2, radius - index * 9)
                canvas.create_oval(
                    effect_size // 2 - r,
                    effect_size // 2 - r,
                    effect_size // 2 + r,
                    effect_size // 2 + r,
                    outline=color,
                    width=2,
                )

            for _ in range(8):
                px = random.randint(14, effect_size - 14)
                py = random.randint(14, effect_size - 14)
                size = random.randint(2, 5)
                canvas.create_oval(px, py, px + size, py + size, fill="#ade8f4", outline="")

            if frame < 7:
                effect.after(36, lambda: animate(frame + 1))
            else:
                effect.destroy()

        animate()

    def clear_blocks(self):
        for block in self.blocks:
            try:
                block["window"].destroy()
            except Exception:
                pass
        self.blocks.clear()
        self.path_nodes.clear()
        self.last_path_target = None
        print("[Bloque] Limpiados")

    def cleanup_expired_blocks(self):
        if not self.blocks:
            return

        now = time.time()
        expired = [
            block
            for block in list(self.blocks)
            if now - float(block.get("created_at", now)) >= self.block_lifetime_seconds
        ]

        for block in expired:
            self.remove_block(block)

    def remove_block(self, block):
        if block not in self.blocks:
            return

        self.blocks.remove(block)
        self.path_nodes.clear()
        self.last_path_target = None
        try:
            block["window"].destroy()
        except Exception:
            pass

    def find_support_y(self, pet_x, pet_y, sprite_width, sprite_height):
        floor_y = self.get_floor_y()
        support_y = floor_y

        pet_left = pet_x
        pet_right = pet_x + sprite_width
        pet_bottom = pet_y + sprite_height

        for block in self.blocks:
            block_left = block["x"]
            block_right = block["x"] + block["w"]
            block_top = block["y"]

            overlap_x = pet_right > block_left and pet_left < block_right
            near_top_margin = max(16, min(sprite_height // 2, block["h"] + 12))
            near_top = pet_bottom <= block_top + near_top_margin

            if overlap_x and near_top and (block_top - sprite_height) < support_y:
                support_y = block_top - sprite_height

        return support_y

    def should_auto_jump_platform(self, pointer_x, pointer_y, sprite_width, sprite_height):
        if not self.on_ground:
            return False

        current_support = self.find_support_y(self.x, self.y, sprite_width, sprite_height)

        look_ahead = self.direction_x * (sprite_width // 2 + self.block_size[0] // 2)
        ahead_x = self.x + look_ahead
        screen_width = self.root.winfo_screenwidth()
        ahead_x = max(0, min(screen_width - sprite_width, ahead_x))
        ahead_support = self.find_support_y(ahead_x, self.y, sprite_width, sprite_height)

        # Necesita salto si hay un escalon/plataforma mas alta en la direccion de avance.
        needs_climb = ahead_support < (current_support - 6)

        # Detecta pared corta al frente que bloquea el avance horizontal.
        front_blocking = False
        pet_right = self.x + sprite_width
        pet_left = self.x
        pet_bottom = self.y + sprite_height
        pet_top = self.y
        for block in self.blocks:
            block_left = block["x"]
            block_right = block["x"] + block["w"]
            block_top = block["y"]
            block_bottom = block["y"] + block["h"]

            overlap_y = pet_bottom > (block_top + 4) and pet_top < (block_bottom - 4)
            if not overlap_y:
                continue

            if self.direction_x == 1 and 0 <= (block_left - pet_right) <= (self.block_size[0] + 12):
                front_blocking = True
                break
            if self.direction_x == -1 and 0 <= (pet_left - block_right) <= (self.block_size[0] + 12):
                front_blocking = True
                break

        cursor_above = pointer_y < (self.y - 6)
        return cursor_above and (needs_climb or front_blocking)

    def clamp_need(self, value):
        return max(0.0, min(100.0, float(value)))

    def schedule_needs_tick(self):
        if self.is_destroying:
            return
        self.needs_job = self.root.after(self.needs_tick_ms, self.tick_needs)

    def tick_needs(self):
        if self.is_destroying:
            return

        drain = self.active_personality["need_drain"]
        movement_load = 1.0 if self.state in ("walking", "jump", "cursor_attack") else 0.55

        self.needs["hunger"] = self.clamp_need(self.needs["hunger"] - (0.7 * drain * movement_load))
        self.needs["fun"] = self.clamp_need(self.needs["fun"] - (0.55 * drain))
        self.needs["social"] = self.clamp_need(self.needs["social"] - (0.42 * drain))

        if self.state in ("idle", "dead"):
            self.needs["energy"] = self.clamp_need(self.needs["energy"] + 1.3)
        else:
            self.needs["energy"] = self.clamp_need(self.needs["energy"] - (0.85 * drain))

        if self.needs["hunger"] < 12 or self.needs["energy"] < 10:
            self.needs["health"] = self.clamp_need(self.needs["health"] - 1.8)
        else:
            self.needs["health"] = self.clamp_need(self.needs["health"] + 0.45)

        if self.needs["health"] <= 0 and self.state != "dead":
            print("[Needs] Salud critica: la mascota colapso.")
            self.needs["health"] = 35
            self.trigger_dead()

        if self.needs["energy"] < 18 and self.state == "walking" and random.random() < 0.1:
            self.set_idle()

        if self.needs["fun"] < 20 and self.execution_mode == "free" and random.random() < 0.12:
            self.trigger_jump()

        self.schedule_needs_tick()

    def feed_pet(self, auto=False):
        self.needs["hunger"] = self.clamp_need(self.needs["hunger"] + 25)
        self.needs["health"] = self.clamp_need(self.needs["health"] + 6)
        self.stats["care_actions"] += 1
        if auto:
            print("[Asistente] Autocuidado: alimento aplicado.")
        else:
            print("[Needs] Alimentada (+hambre, +salud)")

    def play_with_pet(self, auto=False):
        self.needs["fun"] = self.clamp_need(self.needs["fun"] + 26)
        self.needs["social"] = self.clamp_need(self.needs["social"] + 18)
        self.needs["energy"] = self.clamp_need(self.needs["energy"] - 7)
        self.stats["care_actions"] += 1
        if auto:
            print("[Asistente] Autocuidado: juego/estimulo aplicado.")
        else:
            print("[Needs] Jugando (+diversion, +social)")

    def rest_pet(self, auto=False):
        self.needs["energy"] = self.clamp_need(self.needs["energy"] + 30)
        self.needs["health"] = self.clamp_need(self.needs["health"] + 4)
        if not self.is_dragging and self.state != "dead":
            self.set_idle()
        self.stats["care_actions"] += 1
        if auto:
            print("[Asistente] Autocuidado: descanso activado.")
        else:
            print("[Needs] Descanso (+energia)")

    def apply_personality(self, personality_name):
        if personality_name not in self.personality_profiles:
            return

        self.personality_name = personality_name
        self.active_personality = self.personality_profiles[personality_name]
        if self.execution_mode == "platform":
            base_min, base_max = self.active_personality["build_rate"]
            self.auto_block_interval_range = (int(base_min * 2.6), int(base_max * 2.8))
        else:
            self.auto_block_interval_range = self.active_personality["build_rate"]
        self.auto_jump_interval_range = self.active_personality["jump_rate"]
        self.escape_distance = int(210 * self.active_personality["speed_boost"])
        print(f"[Personalidad] {self.personality_name}")

    def cycle_personality(self):
        keys = list(self.personality_profiles.keys())
        current_index = keys.index(self.personality_name)
        next_personality = keys[(current_index + 1) % len(keys)]
        self.apply_personality(next_personality)

    def toggle_sandbox(self):
        self.sandbox_mode = not self.sandbox_mode
        self.path_nodes.clear()
        self.last_path_target = None

        if self.sandbox_mode:
            self.cancel_auto_blocks()
            print("[Sandbox] ON - usa flechas, B para bloque y C para limpiar")
        else:
            if self.execution_mode == "platform":
                self.start_auto_blocks()
            print("[Sandbox] OFF")

    def sandbox_nudge(self, direction):
        if not self.sandbox_mode:
            return

        sprite_width, sprite_height = self.get_walking_sprite_size()
        screen_width = self.root.winfo_screenwidth()
        self.direction_x = 1 if direction >= 0 else -1
        self.x = max(0, min(screen_width - sprite_width, self.x + direction * self.manual_nudge_speed))

        if self.execution_mode == "platform":
            self.y = self.find_support_y(self.x, self.y, sprite_width, sprite_height)
            self.base_y = self.y
            self.on_ground = True
            self.vertical_velocity = 0.0

        self.root.geometry(f"+{self.x}+{self.y}")

    def sandbox_jump(self):
        if not self.sandbox_mode:
            return
        self.trigger_jump()

    def get_session_runtime_seconds(self):
        return max(0, int(time.time() - self.session_started_at))

    def format_seconds(self, total_seconds):
        total_seconds = max(0, int(total_seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def load_assistant_config(self):
        if not self.assistant_config_file.exists():
            return

        try:
            data = json.loads(self.assistant_config_file.read_text(encoding="utf-8"))
        except Exception:
            return

        wake = str(data.get("wake_word", self.voice_wake_word)).strip().lower()
        if wake:
            self.voice_wake_word = wake

        self.require_wake_word = bool(data.get("require_wake_word", self.require_wake_word))

        level = str(data.get("permission_level", self.permission_level)).strip().lower()
        if level in self.permission_levels:
            self.permission_level = level

        llm_enabled_cfg = data.get("llm_enabled")
        if llm_enabled_cfg is not None:
            self.llm_enabled = bool(llm_enabled_cfg)

        llm_model_cfg = str(data.get("llm_model", self.llm_model)).strip()
        if llm_model_cfg:
            self.llm_model = llm_model_cfg

    def save_assistant_config(self):
        payload = {
            "wake_word": self.voice_wake_word,
            "require_wake_word": self.require_wake_word,
            "permission_level": self.permission_level,
            "llm_enabled": self.llm_enabled,
            "llm_model": self.llm_model,
        }
        try:
            self.assistant_config_file.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def has_permission(self, category):
        if self.permission_level == "full":
            return True
        if self.permission_level == "files":
            return category in ("query", "files", "media")
        return category == "query"

    def set_permission_level(self, level):
        normalized = str(level).strip().lower()
        if normalized not in self.permission_levels:
            return False
        self.permission_level = normalized
        self.save_assistant_config()
        return True

    def strip_wake_word(self, text):
        phrase = (text or "").strip().lower()
        if not self.require_wake_word:
            return phrase

        wake = self.voice_wake_word.strip().lower()
        if not wake:
            return phrase

        if not phrase.startswith(wake):
            return ""

        trimmed = phrase[len(wake) :].strip(" ,.:;!?-")
        return trimmed

    def query_optional_llm(self, user_prompt):
        if not self.llm_enabled or not self.llm_api_key:
            return ""

        system_prompt = (
            "Eres un asistente de PC en español. Responde breve, clara y útil, "
            "sin inventar acciones que no puedes ejecutar."
        )
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
        }

        request_body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }

        request = urllib.request.Request(
            self.llm_endpoint,
            data=request_body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.llm_timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            choices = parsed.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = str(message.get("content", "")).strip()
            return content
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return ""

    def init_hud(self):
        if self.hud_window is not None:
            return

        self.hud_window = tk.Toplevel(self.root)
        self.hud_window.overrideredirect(True)
        self.hud_window.attributes("-topmost", True)
        self.hud_window.geometry("260x90+12+12")

        self.hud_label = tk.Label(
            self.hud_window,
            text="",
            justify="left",
            bg="#111111",
            fg="#d7f7ff",
            font=("Consolas", 9),
            padx=8,
            pady=6,
        )
        self.hud_label.pack(fill="both", expand=True)
        self.schedule_hud_update()

    def schedule_hud_update(self):
        if self.is_destroying or not self.hud_enabled:
            return
        self.hud_job = self.root.after(self.hud_update_ms, self.update_hud)

    def update_hud(self):
        if self.is_destroying:
            return

        if not self.hud_enabled:
            if self.hud_window is not None:
                self.hud_window.withdraw()
            return

        if self.hud_window is None:
            self.init_hud()
            return

        self.hud_window.deiconify()
        text = (
            f"Modo:{self.execution_mode}  Pers:{self.personality_name}\n"
            f"H:{int(self.needs['hunger'])} E:{int(self.needs['energy'])} F:{int(self.needs['fun'])} S:{int(self.needs['social'])} V:{int(self.needs['health'])}\n"
            f"Sesion {self.format_seconds(self.get_session_runtime_seconds())}  J:{self.stats['jumps']} D:{self.stats['deaths']} A:{self.stats['pc_actions']}"
        )
        self.hud_label.config(text=text)
        self.schedule_hud_update()

    def toggle_hud(self):
        self.hud_enabled = not self.hud_enabled

        if self.hud_job is not None:
            self.root.after_cancel(self.hud_job)
            self.hud_job = None

        if self.hud_enabled:
            if self.hud_window is None:
                self.init_hud()
            else:
                self.hud_window.deiconify()
            self.update_hud()
            print("[HUD] ON")
        else:
            if self.hud_window is not None:
                self.hud_window.withdraw()
            print("[HUD] OFF")

    def sanitize_folder_name(self, raw_name):
        cleaned = re.sub(r'[<>:"/\\|?*]+', "", raw_name or "")
        cleaned = cleaned.strip().strip(".")
        if not cleaned:
            return ""
        return cleaned[:80]

    def is_allowed_path(self, target_path):
        try:
            resolved = target_path.resolve()
        except Exception:
            return False

        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def can_run_system_action(self, bypass_cooldown=False):
        now = time.time()
        if (not bypass_cooldown) and now < self.system_action_cooldown_until:
            print("[PC] Espera un momento antes de otra accion.")
            return False

        if not bypass_cooldown:
            self.system_action_cooldown_until = now + self.system_action_cooldown_seconds
        return True

    def append_action_log(self, action, detail, status):
        payload = {
            "timestamp": int(time.time()),
            "action": action,
            "detail": detail,
            "status": status,
        }

        entries = []
        if self.action_log_file.exists():
            try:
                entries = json.loads(self.action_log_file.read_text(encoding="utf-8"))
            except Exception:
                entries = []

        if not isinstance(entries, list):
            entries = []

        entries.append(payload)
        if len(entries) > self.max_action_log_entries:
            entries = entries[-self.max_action_log_entries :]

        try:
            self.action_log_file.write_text(json.dumps(entries, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception:
            pass

    def prompt_create_desktop_folder(self):
        if not self.can_run_system_action():
            return

        name = simpledialog.askstring(
            "Crear Carpeta",
            "Nombre de la nueva carpeta en el Escritorio:",
            parent=self.root,
        )
        if not name:
            return

        safe_name = self.sanitize_folder_name(name)
        if not safe_name:
            messagebox.showwarning("Nombre invalido", "Usa un nombre valido para carpeta.", parent=self.root)
            return

        target = self.desktop_path / safe_name
        if not self.is_allowed_path(target):
            self.append_action_log("create_folder", str(target), "blocked")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Crear carpeta:\n{target}",
            parent=self.root,
        )
        if not confirm:
            self.append_action_log("create_folder", str(target), "cancelled")
            return

        self.create_desktop_folder(safe_name, auto=False)

    def create_desktop_folder(self, folder_name, auto=False):
        if not self.has_permission("files"):
            self.append_action_log("create_folder", folder_name, "blocked-permission")
            return False

        safe_name = self.sanitize_folder_name(folder_name)
        if not safe_name:
            return False

        target = self.desktop_path / safe_name
        if not self.is_allowed_path(target):
            self.append_action_log("create_folder", str(target), "blocked")
            return False

        try:
            target.mkdir(parents=False, exist_ok=False)
            self.stats["pc_actions"] += 1
            self.append_action_log("create_folder", str(target), "ok")
            if auto:
                print(f"[Asistente] Carpeta creada automaticamente: {target.name}")
            else:
                print(f"[PC] Carpeta creada: {target.name}")
            return True
        except FileExistsError:
            self.append_action_log("create_folder", str(target), "exists")
            if not auto:
                messagebox.showinfo("Existe", "Esa carpeta ya existe.", parent=self.root)
        except Exception as error:
            self.append_action_log("create_folder", str(target), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No se pudo crear la carpeta.\n{error}", parent=self.root)

        return False

    def prompt_archive_desktop_item(self):
        if not self.can_run_system_action():
            return

        item_name = simpledialog.askstring(
            "Archivar En Escritorio",
            "Nombre del archivo/carpeta del Escritorio a mover:",
            parent=self.root,
        )
        if not item_name:
            return

        safe_name = self.sanitize_folder_name(item_name)
        if not safe_name:
            messagebox.showwarning("Nombre invalido", "No se pudo interpretar el nombre.", parent=self.root)
            return

        self.archive_desktop_item(safe_name, auto=False)

    def archive_desktop_item(self, item_name, auto=False):
        if not self.has_permission("files"):
            self.append_action_log("archive_item", item_name, "blocked-permission")
            return False

        safe_name = self.sanitize_folder_name(item_name)
        if not safe_name:
            return False

        source = self.desktop_path / safe_name
        archive_dir = self.desktop_path / self.archive_folder_name
        destination = archive_dir / safe_name

        if not self.is_allowed_path(source) or not self.is_allowed_path(destination):
            self.append_action_log("archive_item", str(source), "blocked")
            return False

        if not source.exists():
            self.append_action_log("archive_item", str(source), "missing")
            if not auto:
                messagebox.showinfo("No encontrado", "No existe ese archivo/carpeta en el Escritorio.", parent=self.root)
            return False

        if not auto:
            confirm = messagebox.askyesno(
                "Confirmar",
                f"Mover a '{self.archive_folder_name}':\n{source.name}",
                parent=self.root,
            )
            if not confirm:
                self.append_action_log("archive_item", str(source), "cancelled")
                return False

        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            suffix = 1
            while destination.exists():
                destination = archive_dir / f"{safe_name}_{suffix}"
                suffix += 1

            shutil.move(str(source), str(destination))
            self.stats["pc_actions"] += 1
            self.append_action_log("archive_item", f"{source} -> {destination}", "ok")
            if auto:
                print(f"[Asistente] Elemento archivado automaticamente: {source.name}")
            else:
                print(f"[PC] Elemento archivado: {source.name}")
            return True
        except Exception as error:
            self.append_action_log("archive_item", str(source), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No se pudo mover el elemento.\n{error}", parent=self.root)
            return False

    def control_media_key(self, action, auto=False):
        if not self.has_permission("media"):
            self.append_action_log("media_key", action, "blocked-permission")
            return

        if not auto and not self.can_run_system_action():
            return

        key_map = {
            "play_pause": 0xB3,
            "next": 0xB0,
            "prev": 0xB1,
        }

        vk = key_map.get(action)
        if vk is None:
            return

        if os.name != "nt":
            self.append_action_log("media_key", action, "unsupported-os")
            return

        if not auto:
            confirm = messagebox.askyesno(
                "Confirmar",
                f"Enviar accion multimedia: {action}",
                parent=self.root,
            )
            if not confirm:
                self.append_action_log("media_key", action, "cancelled")
                return

        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            self.stats["pc_actions"] += 1
            self.append_action_log("media_key", action, "ok")
            print(f"[PC] Media key enviada: {action}")
        except Exception as error:
            self.append_action_log("media_key", action, f"error:{error}")
            messagebox.showerror("Error", f"No se pudo enviar la tecla multimedia.\n{error}", parent=self.root)

    def save_pet_state(self):
        try:
            self.stats["total_runtime_seconds"] += self.get_session_runtime_seconds()
            self.session_started_at = time.time()
            self.stats["saves"] += 1

            data = {
                "version": 1,
                "x": int(self.x),
                "y": int(self.y),
                "state": self.state,
                "style": self.current_style,
                "mode": self.execution_mode,
                "personality": self.personality_name,
                "sandbox_mode": self.sandbox_mode,
                "needs": self.needs,
                "stats": self.stats,
                "blocks": [
                    {
                        "x": int(block["x"]),
                        "y": int(block["y"]),
                        "w": int(block["w"]),
                        "h": int(block["h"]),
                    }
                    for block in self.blocks
                ],
            }
            self.save_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"[Save] Estado guardado en {self.save_file.name}")
        except Exception as error:
            print(f"[Save] Error guardando estado: {error}")

    def load_pet_state(self, quiet=False):
        if not self.save_file.exists():
            if not quiet:
                print("[Load] No existe archivo de guardado.")
            return

        try:
            data = json.loads(self.save_file.read_text(encoding="utf-8"))

            style = data.get("style", self.current_style)
            if style in self.available_styles and style != self.current_style:
                self.switch_style(style)

            self.apply_personality(data.get("personality", self.personality_name))
            self.sandbox_mode = bool(data.get("sandbox_mode", self.sandbox_mode))

            loaded_needs = data.get("needs", {})
            for key in self.needs:
                if key in loaded_needs:
                    self.needs[key] = self.clamp_need(loaded_needs[key])

            loaded_stats = data.get("stats", {})
            for key in self.stats:
                if key in loaded_stats:
                    self.stats[key] = max(0, int(loaded_stats[key]))

            mode = data.get("mode", self.execution_mode)
            if mode == "platform":
                self.set_mode_platform()
            else:
                self.set_mode_free()

            sprite_width, sprite_height = self.get_walking_sprite_size()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.x = max(0, min(screen_width - sprite_width, int(data.get("x", self.x))))
            self.y = max(0, min(screen_height - sprite_height, int(data.get("y", self.y))))
            self.base_y = self.y

            self.clear_blocks()
            for block in data.get("blocks", []):
                bx = int(block.get("x", 0))
                by = int(block.get("y", 0))
                self.create_block(bx, by, cast_from_pet=False)

            loaded_state = data.get("state", "walking")
            if loaded_state in ("walking", "idle", "listening", "jump", "dead"):
                self.state = loaded_state
            else:
                self.state = "walking"

            self.root.geometry(f"+{self.x}+{self.y}")
            self.path_nodes.clear()
            self.last_path_target = None
            self.stats["loads"] += 1
            self.session_started_at = time.time()
            self.update_hud()

            if not quiet:
                print(f"[Load] Estado cargado desde {self.save_file.name}")
        except Exception as error:
            print(f"[Load] Error cargando estado: {error}")

    def get_support_y_for_x(self, x, sprite_width, sprite_height, reference_y=None):
        floor_y = self.get_floor_y()
        pet_left = x
        pet_right = x + sprite_width
        support_candidates = [floor_y]
        if reference_y is None:
            reference_y = self.y

        for block in self.blocks:
            block_left = block["x"]
            block_right = block["x"] + block["w"]
            overlap_x = pet_right > block_left and pet_left < block_right
            if overlap_x:
                support_candidates.append(block["y"] - sprite_height)

        supports_below_ref = [value for value in support_candidates if value >= (reference_y - 10)]
        if supports_below_ref:
            return min(supports_below_ref)

        # Si no hay soporte cercano por debajo, toma el mas cercano por encima.
        return max(support_candidates)

    def build_navigation_nodes(self, sprite_width, sprite_height, reference_y=None):
        screen_width = self.root.winfo_screenwidth()
        step = max(24, self.block_size[0] // 2)
        nodes = []
        x_positions = list(range(0, max(1, screen_width - sprite_width + 1), step))

        if (screen_width - sprite_width) not in x_positions:
            x_positions.append(max(0, screen_width - sprite_width))

        for x_pos in x_positions:
            support_y = self.get_support_y_for_x(
                x_pos,
                sprite_width,
                sprite_height,
                reference_y=reference_y,
            )
            nodes.append((x_pos, support_y))

        return nodes

    def find_nearest_node_index(self, nodes, x, y):
        best_index = None
        best_dist = float("inf")
        for index, (node_x, node_y) in enumerate(nodes):
            dist = abs(node_x - x) + abs(node_y - y)
            if dist < best_dist:
                best_dist = dist
                best_index = index
        return best_index

    def a_star_indices(self, nodes, start_idx, goal_idx):
        if start_idx is None or goal_idx is None:
            return []
        if start_idx == goal_idx:
            return [nodes[start_idx]]

        step_limit = max(28, self.block_size[0] // 2)
        open_heap = []
        heapq.heappush(open_heap, (0.0, start_idx))
        came_from = {}
        g_score = {start_idx: 0.0}
        closed = set()

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal_idx:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return [nodes[idx] for idx in path]

            closed.add(current)
            cx, cy = nodes[current]

            for neighbor_index, (nx, ny) in enumerate(nodes):
                if neighbor_index == current:
                    continue

                dx = abs(nx - cx)
                dy = ny - cy

                # Grafo ligero: movimiento horizontal corto + saltos razonables.
                if dx > (step_limit * 2):
                    continue
                if dy < -(self.platform_jump_height + 14):
                    continue
                if dy > (self.block_size[1] + 16):
                    continue

                vertical_penalty = 6 if dy < 0 else 1
                tentative_g = g_score[current] + dx + abs(dy) * vertical_penalty

                if tentative_g >= g_score.get(neighbor_index, float("inf")):
                    continue

                came_from[neighbor_index] = current
                g_score[neighbor_index] = tentative_g
                hx = abs(nodes[goal_idx][0] - nx)
                hy = abs(nodes[goal_idx][1] - ny)
                f_score = tentative_g + hx + hy
                heapq.heappush(open_heap, (f_score, neighbor_index))

        return []

    def recalc_path_to_cursor(self, pointer_x, pointer_y, sprite_width, sprite_height):
        screen_width = self.root.winfo_screenwidth()
        target_x = max(0, min(screen_width - sprite_width, pointer_x - sprite_width // 2))
        target_y = self.get_support_y_for_x(
            target_x,
            sprite_width,
            sprite_height,
            reference_y=pointer_y - sprite_height // 2,
        )

        nodes = self.build_navigation_nodes(sprite_width, sprite_height, reference_y=self.y)
        start_idx = self.find_nearest_node_index(nodes, self.x, self.y)
        goal_idx = self.find_nearest_node_index(nodes, target_x, target_y)

        path = self.a_star_indices(nodes, start_idx, goal_idx)
        if path:
            # Descarta primer nodo si es casi la posicion actual.
            if abs(path[0][0] - self.x) < 6:
                path = path[1:]
        self.path_nodes = path
        self.last_path_target = (target_x, target_y)
        self.next_path_recalc_at = time.time() + self.path_recalc_seconds

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

        self.cleanup_expired_blocks()

        if self.state == "dead":
            if time.time() >= self.dead_until:
                if self.execution_mode == "platform":
                    self.y = self.get_floor_y()
                    self.base_y = self.y
                    self.vertical_velocity = 0.0
                    self.on_ground = True
                self.set_walking()
            self.root.after(40, self.move)
            return

        # Durante arrastre no hay movimiento autonomo.
        if self.is_dragging:
            self.root.after(40, self.move)
            return

        if self.execution_mode == "platform":
            self.move_platform()
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
            if not (self.execution_mode == "free" and self.is_running):
                self.direction_y = random.choice([-1, 1])
            self.speed_x = random.uniform(2.5, 6.5)
            self.speed_y = random.uniform(2.4, 5.8)
            self.next_direction_change = now + random.uniform(1.2, 3.6)

            # Esporadicamente acelera para dar variedad al movimiento.
            if random.random() < 0.35:
                self.walk_mode = "dash"
                self.walk_mode_until = now + random.uniform(0.5, 1.2)

        if self.walk_mode == "dash" and now >= self.walk_mode_until:
            self.walk_mode = "normal"

        speed_multiplier = 1.0 if self.walk_mode == "normal" else 1.7
        speed_multiplier *= self.active_personality["speed_boost"]

        energy_ratio = self.needs["energy"] / 100.0
        if energy_ratio < 0.2:
            speed_multiplier *= 0.6
        elif energy_ratio < 0.4:
            speed_multiplier *= 0.8

        if self.is_running:
            speed_multiplier = max(speed_multiplier, 2.3)

        self.x += int(self.speed_x * self.direction_x * speed_multiplier)

        # Oscilacion vertical suave para evitar un desplazamiento robotico.
        self.move_phase += 0.22
        bob = int(math.sin(self.move_phase) * (2 if self.walk_mode == "normal" else 4))
        self.base_y += int(self.speed_y * self.direction_y * 0.7)

        # En modo libre, mejora seguimiento/escape vertical respecto al cursor.
        if self.execution_mode == "free" and self.is_running:
            pointer_x, pointer_y = self.root.winfo_pointerxy()
            center_y = self.base_y + sprite_height // 2
            vertical_gap = pointer_y - center_y

            if self.free_mood == "brava":
                vertical_gap = -vertical_gap

            if abs(vertical_gap) > 6:
                vertical_push = int(max(-8, min(8, vertical_gap * 0.22)))
                self.base_y += vertical_push

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

    def move_platform(self):
        now = time.time()
        sprite_width, sprite_height = self.get_walking_sprite_size()

        screen_width = self.root.winfo_screenwidth()

        # En modo suelo alterna entre caminar y dormir.
        if now >= self.next_platform_behavior_change:
            if random.random() < 0.35:
                self.state = "idle"
                self.platform_idle_until = now + random.uniform(1.8, 3.8)
            else:
                self.state = "walking"
            self.next_platform_behavior_change = now + random.uniform(1.2, 3.4)

        if self.state == "idle" and now >= self.platform_idle_until:
            self.state = "walking"

        if self.state == "walking" and now >= self.next_direction_change:
            self.direction_x = random.choice([-1, 1])
            self.speed_x = random.uniform(2.3, 4.5)
            self.next_direction_change = now + random.uniform(1.1, 2.6)

        desired_direction = self.direction_x if self.state == "walking" else 0
        self.direction_x = desired_direction
        if now >= self.next_direction_change:
            self.speed_x = random.uniform(2.8, 5.5)
            self.next_direction_change = now + random.uniform(1.1, 2.5)

        speed_multiplier = self.active_personality["speed_boost"]
        if self.needs["energy"] < 20:
            speed_multiplier *= 0.62
        elif self.needs["energy"] < 35:
            speed_multiplier *= 0.82

        next_x = self.x + int(self.speed_x * self.direction_x * speed_multiplier)
        if next_x <= 0:
            next_x = 0
            self.direction_x = 1
        elif next_x >= screen_width - sprite_width:
            next_x = screen_width - sprite_width
            self.direction_x = -1

        self.x = next_x

        support_y = self.find_support_y(self.x, self.y, sprite_width, sprite_height)

        if self.on_ground and self.y < support_y - 2:
            self.on_ground = False
            self.is_in_air = True
            self.fall_start_y = self.y

        if not self.on_ground:
            self.vertical_velocity = min(self.max_fall_speed, self.vertical_velocity + self.gravity)
            self.y += int(self.vertical_velocity)
            if self.y < 0:
                self.y = 0
                if self.vertical_velocity < 0:
                    self.vertical_velocity = 0
            self.state = "jump"

            if self.y >= support_y:
                self.y = support_y
                self.base_y = self.y
                self.vertical_velocity = 0.0
                self.on_ground = True
                self.is_in_air = False

                fallen_distance = self.y - self.fall_start_y
                if fallen_distance > self.fall_death_threshold:
                    self.trigger_dead()
                    return

                self.state = "walking"
        else:
            self.y = support_y
            self.base_y = self.y

        self.root.geometry(f"+{self.x}+{self.y}")

    def update_running_from_cursor(self):
        if self.execution_mode != "free":
            self.is_running = False
            self.is_cursor_attacking = False
            return

        now = time.time()
        if now < self.run_boost_until:
            self.is_running = True
            return

        if now >= self.next_free_mood_change_at:
            previous = self.free_mood
            self.free_mood = random.choice(self.free_moods)
            self.next_free_mood_change_at = now + random.uniform(*self.free_mood_interval_range)
            if self.free_mood != previous:
                print(f"[Libre] Estado animico: {self.free_mood}")

        pointer_x, pointer_y = self.root.winfo_pointerxy()
        sprite_width, sprite_height = self.get_walking_sprite_size()
        center_x = self.x + sprite_width // 2
        center_y = self.y + sprite_height // 2

        delta_x = center_x - pointer_x
        delta_y = center_y - pointer_y
        distance = math.hypot(delta_x, delta_y)

        if self.free_mood == "brava":
            self.is_cursor_attacking = False
            if distance <= self.escape_distance:
                self.is_running = True
                if abs(delta_x) > 4:
                    self.direction_x = 1 if delta_x > 0 else -1
                if abs(delta_y) > 4:
                    self.direction_y = 1 if delta_y > 0 else -1
            else:
                self.is_running = False
        else:
            # Feliz: persigue al cursor y ataca cuando esta cerca.
            if distance <= self.free_chase_distance:
                self.is_running = True
                if abs(delta_x) > 4:
                    self.direction_x = -1 if delta_x > 0 else 1
                if abs(delta_y) > 4:
                    self.direction_y = -1 if delta_y > 0 else 1
            else:
                self.is_running = False

            self.is_cursor_attacking = distance <= self.free_attack_distance

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
        if self.execution_mode == "platform":
            self.vertical_velocity = 0.0
        self.base_y = self.y

    def set_idle(self):
        self.state = "idle"
        self.is_running = False
        if self.execution_mode == "platform":
            self.vertical_velocity = 0.0
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
            if self.execution_mode == "free":
                self.run_boost_until = time.time() + random.uniform(1.8, 2.8)
            else:
                self.vertical_velocity = 0.0
                self.on_ground = False
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

        if self.execution_mode == "platform":
            if not self.on_ground:
                return

            self.state = "jump"
            self.on_ground = False
            self.is_in_air = True
            self.fall_start_y = self.y
            self.vertical_velocity = self.jump_strength
            self.stats["jumps"] += 1
            return

        self.state = "jump"
        self.jump_start_time = time.time()
        self.jump_base_y = self.y
        self.stats["jumps"] += 1

    def trigger_dead(self):
        if self.is_destroying:
            return

        self.state = "dead"
        self.is_dragging = False
        self.is_running = False
        self.vertical_velocity = 0.0
        self.on_ground = False
        self.dead_until = time.time() + self.dead_recovery_seconds
        self.stats["deaths"] += 1

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

        self.clear_blocks()
        self.cancel_auto_blocks()
        if self.hud_job is not None:
            self.root.after_cancel(self.hud_job)
            self.hud_job = None
        if self.hud_window is not None:
            try:
                self.hud_window.destroy()
            except Exception:
                pass

        if self.color_change_job is not None:
            self.root.after_cancel(self.color_change_job)
            self.color_change_job = None

        if self.visibility_guard_job is not None:
            self.root.after_cancel(self.visibility_guard_job)
            self.visibility_guard_job = None

        if self.assistant_job is not None:
            self.root.after_cancel(self.assistant_job)
            self.assistant_job = None

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
            normalized = self.strip_wake_word(text)
            if self.require_wake_word and not normalized:
                print("[Asistente] Wake word no detectada; ignoro comando.")
                return

            response = self.handle_voice_or_text_command(normalized or text)
            if response:
                print(f"[Asistente] {response}")
                self._speak(response)
        except Exception as error:
            print(f"[Escucha] {error}")
        finally:
            self.ui_queue.put(("set_state", "walking"))

    def handle_voice_or_text_command(self, text):
        command = (text or "").strip().lower()
        if not command:
            return "No escuche un comando claro."

        if "activar palabra clave" in command:
            self.require_wake_word = True
            self.save_assistant_config()
            return f"Palabra clave activada: {self.voice_wake_word}."

        if "desactivar palabra clave" in command:
            self.require_wake_word = False
            self.save_assistant_config()
            return "Palabra clave desactivada temporalmente."

        if command.startswith("palabra clave "):
            new_wake = self.sanitize_folder_name(command.replace("palabra clave ", "", 1)).lower()
            if not new_wake:
                return "No detecte una palabra clave valida."
            self.voice_wake_word = new_wake
            self.save_assistant_config()
            return f"Nueva palabra clave configurada: {self.voice_wake_word}."

        if "permiso consulta" in command:
            self.set_permission_level("query")
            return "Permiso cambiado a consulta."

        if "permiso archivos" in command:
            self.set_permission_level("files")
            return "Permiso cambiado a archivos."

        if "permiso completo" in command:
            self.set_permission_level("full")
            return "Permiso cambiado a completo."

        if "activar ia" in command or "activar llm" in command:
            self.llm_enabled = True
            self.save_assistant_config()
            return "IA conversacional activada."

        if "desactivar ia" in command or "desactivar llm" in command:
            self.llm_enabled = False
            self.save_assistant_config()
            return "IA conversacional desactivada."

        if "que hora" in command or "hora es" in command:
            now = time.strftime("%H:%M")
            return f"Son las {now}."

        if "como estas" in command or "como te sientes" in command:
            avg_needs = sum(self.needs.values()) / max(1, len(self.needs))
            if avg_needs >= 70:
                return "Estoy muy bien y lista para ayudarte."
            if avg_needs >= 45:
                return "Estoy estable, puedo seguir trabajando."
            return "Estoy algo cansada, pero aun puedo ayudar."

        if "quien eres" in command or "que eres" in command:
            return "Soy tu asistente de PC y tambien conservo comportamientos de mascota."

        if command.startswith("crea carpeta "):
            if not self.has_permission("files"):
                return "Tu nivel de permisos actual no permite crear carpetas."
            folder_name = command.replace("crea carpeta ", "", 1).strip()
            if self.create_desktop_folder(folder_name, auto=True):
                return f"Carpeta {folder_name} creada en tu escritorio."
            return "No pude crear esa carpeta."

        if command.startswith("archiva "):
            if not self.has_permission("files"):
                return "Tu nivel de permisos actual no permite archivar elementos."
            item_name = command.replace("archiva ", "", 1).strip()
            if self.archive_desktop_item(item_name, auto=True):
                return f"Elemento {item_name} movido a archivado."
            return "No pude archivar ese elemento."

        if "siguiente cancion" in command or "siguiente canción" in command:
            if not self.has_permission("media"):
                return "Tu nivel de permisos actual no permite controlar multimedia."
            self.control_media_key("next", auto=True)
            return "Envie siguiente cancion."

        if "cancion anterior" in command or "canción anterior" in command:
            if not self.has_permission("media"):
                return "Tu nivel de permisos actual no permite controlar multimedia."
            self.control_media_key("prev", auto=True)
            return "Envie cancion anterior."

        if "pausa musica" in command or "pausar musica" in command or "play pausa" in command:
            if not self.has_permission("media"):
                return "Tu nivel de permisos actual no permite controlar multimedia."
            self.control_media_key("play_pause", auto=True)
            return "Alternando reproduccion de musica."

        if "modo libre" in command:
            self.set_mode_free()
            return "Modo libre activado."

        if "modo suelo" in command:
            self.set_mode_platform()
            return "Modo suelo activado."

        if "persigue cursor" in command or "sigue cursor" in command:
            self.free_mood = "feliz"
            self.next_free_mood_change_at = time.time() + random.uniform(*self.free_mood_interval_range)
            return "De acuerdo, perseguire el cursor."

        if "huye cursor" in command or "escapa cursor" in command:
            self.free_mood = "brava"
            self.next_free_mood_change_at = time.time() + random.uniform(*self.free_mood_interval_range)
            return "Entendido, me alejare del cursor."

        if "ayuda" in command or "que puedes hacer" in command:
            return (
                "Puedo responder preguntas simples, cambiar modo, controlar musica, crear carpetas, "
                "archivar elementos y cuidarme sola cuando lo necesito."
            )

        if "hola" in command:
            return "Hola, estoy lista para asistirte."

        if self.llm_enabled and self.has_permission("query"):
            llm_response = self.query_optional_llm(command)
            if llm_response:
                return llm_response

        return "No entendi ese comando todavia, pero puedo aprender mas funciones."

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