import queue
import random
import threading
import time
import tkinter as tk
import math
import os
from pathlib import Path

from PIL import Image, ImageSequence, ImageTk
from assistant_alias_manager import AliasManager
from assistant_config_store import JsonConfigStore
from assistant_chat_controller import ChatUIController
from assistant_command_handler import AssistantCommandHandler
from assistant_design_manager import PetDesignManager
from assistant_actions_manager import SystemActionManager
from assistant_identity_manager import PetIdentityManager
from assistant_llm_gateway import LLMGateway
from assistant_permissions import PermissionManager
from assistant_state_manager import PetStateManager
from assistant_text_utils import CommandTextParser
from assistant_ui_event_controller import UIEventController
from assistant_voice_manager import VoiceManager

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
        self._init_assistant_core()
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

        # Widget principal
        self.label = tk.Label(self.root, bg="white", borderwidth=0, highlightthickness=0)
        self.label.pack()

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
        self.label.bind("<Double-Button-1>", lambda _event: self.open_chat_bubble())
        self.label.bind("<Button-3>", self.show_menu)

        # -------- MENÚ --------
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="🐸 Caminar", command=self.set_walking)
        self.menu.add_command(label="🛑 Detener", command=self.set_idle)
        
        self.menu.add_command(label="⬆️ Saltar", command=self.trigger_jump)
        self.menu.add_command(label="💀 Morir (test)", command=self.trigger_dead)
        self.menu.add_separator()
        self.menu.add_command(label="🎮 Modo Libre", command=self.set_mode_free)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Salir", command=self.root.destroy)

        # Iniciar ciclos
        self.menu.add_command(label="⏯️ Musica play/pausa", command=lambda: self.control_media_key("play_pause"))
        self.menu.add_command(label="⏭️ Siguiente cancion", command=lambda: self.control_media_key("next"))
        self.menu.add_command(label="⏮️ Cancion anterior", command=lambda: self.control_media_key("prev"))
        self.menu.add_separator()
        self.menu.add_command(label="🧪 Sandbox ON/OFF", command=self.toggle_sandbox)
        self.menu.add_command(label="🔒 IA Local (solo Ollama)", command=self.activate_local_ai_mode)
        self.menu.add_command(label="🌐 IA + Internet", command=self.activate_cloud_ai_mode)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Salir", command=self.on_app_close)

        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)

        self.root.bind_all("<Left>", lambda _event: self.sandbox_nudge(-1))
        self.root.bind_all("<Right>", lambda _event: self.sandbox_nudge(1))
        self.root.bind_all("<Up>", lambda _event: self.sandbox_jump())

        # Iniciar ciclos
        self.load_assistant_config()
        self.apply_personality(self.personality_name)
        self.load_pet_state(quiet=True)
        # Requisito del proyecto: arrancar siempre en modo suelo.
        self.set_mode_platform()
        self.stats["total_sessions"] += 1
        self.animate()
        self.move()
        self.process_ui_queue()
        self.schedule_auto_color_change()
        if self.voice_realtime_enabled:
            self.start_realtime_listening()

    def discover_available_styles(self):
        return self.design_manager.discover_available_styles()

    def build_animation_sources_for_style(self, style_name):
        return self.design_manager.build_animation_sources_for_style(style_name)

    def _init_assistant_core(self):
        # Estado base para que los managers externos puedan operar sin fallar al inicio.
        self.assistant_config_file = self.asset_dir / "assistant_config.json"
        self.save_file = self.asset_dir / "assistant_state.json"
        desktop_default = Path.home() / "Desktop"
        onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
        self.desktop_path = onedrive_desktop if onedrive_desktop.exists() else desktop_default
        self.archive_folder_name = "Archivado_Mimi"
        self.action_log_file = self.asset_dir / "assistant_actions.json"
        self.max_action_log_entries = 300
        self.system_action_cooldown_seconds = 1.0
        self.system_action_cooldown_until = 0.0
        self.pending_action_timeout_seconds = 45

        self.execution_mode = "platform"
        self.sandbox_mode = False
        self.permission_levels = ("query", "files", "full")
        self.permission_level = "query"
        self.llm_providers = ("ollama", "openai")
        self.llm_provider = "ollama"
        self.llm_enabled = True
        self.llm_model = "llama3.2:3b"
        self.llm_endpoint = "http://127.0.0.1:11434/api/chat"
        self.llm_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.llm_offline_only = True
        self.functional_automation_enabled = True
        self.voice_wake_word = "mimi"
        self.require_wake_word = False
        self.voice_realtime_enabled = False
        self.voice_response_enabled = False
        self.voice_phrase_timeout_seconds = 2
        self.voice_phrase_max_seconds = 5
        self.pet_name = "Mimi"
        self.personality_name = "amigable"
        self.user_name_memory = ""
        self.pet_memory_notes = []
        self.chat_transcript = [("Mimi", "Lista para ayudarte.")]

        self.chat_window = None
        self.chat_header_label = None
        self.chat_history = None
        self.chat_entry = None
        self.chat_status_label = None
        self.chat_send_button = None
        self.chat_autohide_job = None
        self.chat_inactivity_ms = 120000
        self.chat_request_in_flight = False
        self.pending_action = None
        self.free_mood = "feliz"
        self.free_mood_interval_range = (8.0, 18.0)
        self.next_free_mood_change_at = time.time() + random.uniform(*self.free_mood_interval_range)

        self.needs = {"energia": 100, "hambre": 0, "higiene": 100, "diversion": 100}
        self.stats = {
            "total_sessions": 0,
            "total_runtime_seconds": 0,
            "loads": 0,
            "saves": 0,
        }
        self.session_started_at = time.time()
        self.path_nodes = []
        self.last_path_target = None

        self.config_store = JsonConfigStore()
        self.text_parser = CommandTextParser()
        self.llm_gateway = LLMGateway()
        self.design_manager = PetDesignManager(self)
        self.identity_manager = PetIdentityManager(self)
        self.permission_manager = PermissionManager(self)
        self.action_manager = SystemActionManager(self)
        self.alias_manager = AliasManager(self)
        self.state_manager = PetStateManager(self)
        self.chat_controller = ChatUIController(self)
        self.command_handler = AssistantCommandHandler(self)
        self.ui_event_controller = UIEventController(self)
        self.voice_manager = VoiceManager(
            self,
            VOICE_AVAILABLE,
            sr_module=sr if VOICE_AVAILABLE else None,
            tts_module=pyttsx3 if VOICE_AVAILABLE else None,
        )

    def load_assistant_config(self):
        return self.state_manager.load_assistant_config()

    def save_assistant_config(self):
        return self.state_manager.save_assistant_config()

    def save_pet_state(self):
        return self.state_manager.save_pet_state()

    def load_pet_state(self, quiet=False):
        return self.state_manager.load_pet_state(quiet=quiet)

    def apply_personality(self, personality_name):
        candidate = str(personality_name or "").strip().lower()
        if not candidate:
            candidate = "amigable"
        self.personality_name = candidate[:40]
        self.refresh_chat_header_mode()

    def set_mode_platform(self):
        self.execution_mode = "platform"

    def set_mode_free(self):
        self.execution_mode = "free"

    def toggle_sandbox(self):
        self.sandbox_mode = not self.sandbox_mode
        state = "ON" if self.sandbox_mode else "OFF"
        self.set_chat_status(f"Sandbox {state}")

    def sandbox_nudge(self, direction):
        if not self.sandbox_mode or self.is_destroying:
            return
        self.direction_x = 1 if int(direction) >= 0 else -1
        self.x += int(15 * self.direction_x)
        sprite_width, _ = self.get_walking_sprite_size()
        screen_width = self.root.winfo_screenwidth()
        self.x = max(0, min(screen_width - sprite_width, self.x))
        self.root.geometry(f"+{self.x}+{self.y}")

    def sandbox_jump(self):
        if not self.sandbox_mode:
            return
        self.trigger_jump()

    def control_media_key(self, action, auto=False):
        self.action_manager.control_media_key(action, auto=auto)

    def activate_local_ai_mode(self):
        self.llm_provider = "ollama"
        self.llm_offline_only = True
        self.llm_endpoint = "http://127.0.0.1:11434/api/chat"
        self.llm_enabled = True
        self.save_assistant_config()
        self.refresh_chat_header_mode()

    def activate_cloud_ai_mode(self):
        self.llm_provider = "openai"
        self.llm_offline_only = False
        self.llm_endpoint = "https://api.openai.com/v1/chat/completions"
        self.llm_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.llm_enabled = bool(self.llm_api_key)
        self.save_assistant_config()
        self.refresh_chat_header_mode()

    def has_permission(self, category):
        return self.permission_manager.has_permission(category)

    def set_permission_level(self, level):
        return self.permission_manager.set_permission_level(level)

    def sanitize_folder_name(self, raw_name):
        return self.text_parser.sanitize_folder_name(raw_name)

    def normalize_command_text(self, text):
        return self.text_parser.normalize_command_text(text)

    def extract_folder_name_from_command(self, command):
        return self.text_parser.extract_folder_name_from_command(command)

    def extract_json_object(self, raw_text):
        return self.text_parser.extract_json_object(raw_text)

    def is_allowed_path(self, target_path):
        try:
            candidate = Path(target_path).resolve()
        except Exception:
            return False

        safe_roots = [
            self.desktop_path.resolve(),
            self.asset_dir.resolve(),
            (Path.home() / "Documents" / "MimiAsistente").resolve(),
        ]
        return any(candidate == root or root in candidate.parents for root in safe_roots)

    def format_pet_memory(self):
        return self.identity_manager.format_pet_memory()

    def get_chat_header_text(self):
        mode = "Local" if self.llm_provider == "ollama" else "Nube"
        return f"{self.pet_name} [{mode}]"

    def refresh_chat_header_mode(self):
        if self.chat_header_label is None or not self.chat_header_label.winfo_exists():
            return
        self.chat_header_label.config(text=self.get_chat_header_text())

    def open_chat_bubble(self):
        self.chat_controller.open_chat_bubble()

    def close_chat_bubble(self):
        self.chat_controller.close_chat_bubble()

    def append_chat_message(self, speaker, text):
        self.chat_controller.append_chat_message(speaker, text)

    def set_chat_status(self, text):
        self.chat_controller.set_chat_status(text)

    def submit_chat_message(self, _event=None):
        if self.chat_entry is None or not self.chat_entry.winfo_exists():
            return "break"

        user_text = self.chat_entry.get().strip()
        self.chat_entry.delete(0, "end")
        if not user_text:
            return "break"

        self.append_chat_message("Tu", user_text)
        response = self.handle_voice_or_text_command(user_text)
        if response:
            self.append_chat_message("Mimi", response)
            if self.voice_response_enabled:
                self._speak(response)
        return "break"

    def handle_voice_or_text_command(self, text):
        try:
            return self.command_handler.handle(text)
        except Exception as error:
            print(f"[Comando] Error: {error}")
            return "No pude procesar ese comando en este momento."

    def strip_wake_word(self, text):
        normalized = str(text or "").strip().lower()
        wake = str(self.voice_wake_word or "").strip().lower()
        if not normalized:
            return ""
        if not wake:
            return normalized
        if normalized.startswith(wake):
            return normalized[len(wake) :].strip(" ,:;.-")
        return ""

    def query_ollama_local_with_system(self, system_prompt, user_prompt, timeout_seconds=20):
        return self.llm_gateway.query_ollama_local_chat(
            self.llm_model,
            str(system_prompt or ""),
            str(user_prompt or ""),
            timeout_seconds,
        )

    def query_ollama_llm(self, user_prompt, timeout_seconds=20):
        system_prompt = self.identity_manager.build_pet_identity_system_prompt()
        return self.query_ollama_local_with_system(system_prompt, user_prompt, timeout_seconds=timeout_seconds)

    def query_optional_llm(self, user_prompt, timeout_seconds=20):
        if not self.llm_enabled:
            return ""

        system_prompt = self.identity_manager.build_pet_identity_system_prompt()
        prompt = str(user_prompt or "").strip()
        if not prompt:
            return ""

        if self.llm_provider == "openai" and not self.llm_offline_only and self.llm_api_key:
            return self.llm_gateway.query_openai_chat(
                endpoint=self.llm_endpoint,
                api_key=self.llm_api_key,
                model=self.llm_model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                timeout_seconds=timeout_seconds,
            )

        return self.llm_gateway.query_ollama_chat(
            endpoint=self.llm_endpoint,
            model=self.llm_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            timeout_seconds=timeout_seconds,
        )

    def check_ollama_health(self):
        return self.llm_gateway.check_ollama_health(self.llm_endpoint, timeout_seconds=6)

    def clamp_need(self, value):
        return max(0, min(100, int(value)))

    def clear_blocks(self):
        return None

    def update_hud(self):
        return None

    def face_user(self):
        pointer_x, _pointer_y = self.root.winfo_pointerxy()
        sprite_width, _sprite_height = self.get_walking_sprite_size()
        center_x = self.x + sprite_width // 2
        self.direction_x = 1 if pointer_x >= center_x else -1

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
        return self.design_manager.choose_next_style()

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
            self.face_user()
            self.root.geometry(f"+{self.x}+{self.y}")

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
        self.is_running = False
        self.face_user()

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
        self.voice_manager.start_listening()

    def start_realtime_listening(self):
        ok = self.voice_manager.start_continuous_listening()
        if ok:
            self.set_chat_status("Voz continua activada.")
        else:
            self.set_chat_status("No pude activar voz continua en este entorno.")

    def stop_realtime_listening(self):
        self.voice_manager.stop_continuous_listening()
        self.set_chat_status("Voz continua desactivada.")

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
        self.voice_manager.speak(text)

    def on_app_close(self):
        if self.is_destroying:
            return
        self.is_destroying = True
        self.voice_manager.stop_continuous_listening()
        self.save_assistant_config()
        self.root.destroy()

    def process_ui_queue(self):
        self.ui_event_controller.process_ui_queue()

if __name__ == "__main__":
    root = tk.Tk()
    pet = DesktopPet(root)
    root.mainloop()