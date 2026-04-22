import heapq
import http.server
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
import urllib.parse
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog

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
        self.execution_mode = "platform"
        self.blocks_enabled = False
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
        self.config_store = JsonConfigStore()
        self.text_parser = CommandTextParser()
        self.llm_gateway = LLMGateway()
        self.design_manager = PetDesignManager(self)
        self.identity_manager = PetIdentityManager(self)
        self.chat_controller = ChatUIController(self)
        self.action_manager = SystemActionManager(self)
        self.alias_manager = AliasManager(self)
        self.command_handler = AssistantCommandHandler(self)
        self.state_manager = PetStateManager(self)
        self.ui_event_controller = UIEventController(self)
        self.voice_manager = VoiceManager(
            owner=self,
            voice_available=VOICE_AVAILABLE,
            sr_module=sr if VOICE_AVAILABLE else None,
            tts_module=pyttsx3 if VOICE_AVAILABLE else None,
        )
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
        self.chat_window = None
        self.chat_history = None
        self.chat_entry = None
        self.chat_status_label = None
        self.chat_send_button = None
        self.chat_request_in_flight = False
        self.chat_autohide_job = None
        self.chat_inactivity_ms = 0
        self.chat_header_label = None
        self.chat_transcript = [("Mascota", "Chat local listo. Puedes escribirme aqui.")]
        self.pending_action = None
        self.pending_action_timeout_seconds = 25
        self.functional_automation_enabled = False
        self.next_desktop_maintenance_at = 0.0
        self.autocare_cooldowns = {"feed": 0.0, "play": 0.0, "rest": 0.0}
        self.voice_wake_word = "asistente"
        self.require_wake_word = True
        self.voice_realtime_enabled = False
        self.voice_response_enabled = True
        self.voice_phrase_timeout_seconds = 2
        self.voice_phrase_max_seconds = 5
        self.permission_level = "full"  # query | files | full
        self.permission_levels = ("query", "files", "full")
        self.permission_manager = PermissionManager(self)
        self.llm_provider = str(os.getenv("ASSISTANT_LLM_PROVIDER", "ollama")).strip().lower()
        self.llm_enabled = bool(os.getenv("OPENAI_API_KEY")) if self.llm_provider == "openai" else True
        self.llm_model = os.getenv("ASSISTANT_LLM_MODEL", "qwen2.5:1.5b-instruct")
        self.local_intent_model = os.getenv("ASSISTANT_LOCAL_INTENT_MODEL", "qwen2.5:1.5b-instruct")
        self.llm_api_key = os.getenv("OPENAI_API_KEY", "")
        self.llm_endpoint = os.getenv("ASSISTANT_LLM_ENDPOINT", "http://127.0.0.1:11434/api/chat")
        self.llm_timeout_seconds = 9
        self.llm_offline_only = True
        self.llm_providers = ("ollama", "openai")
        self.pet_name = "Mimi"
        self.user_name_memory = ""
        self.pet_memory_notes = []
        self.music_memory = []
        self.music_personality_concepts = []
        self.music_queue = []
        self.music_session_active = False
        self.music_current_song = ""
        self.music_backend = ""
        self.music_player = None
        self.music_vlc_instance = None
        self.music_temp_file = ""
        self.music_paused = False
        self.last_music_error_detail = ""
        self.music_track_started_at = 0.0
        self.music_track_duration_seconds = 0.0
        self.music_controls_window = None
        self.music_controls_drag_offset = (0, 0)
        self.music_mini_chat_window = None
        self.music_mini_chat_label = None
        self.music_mini_mode = "subtitle"
        self.music_mini_mode_button = None
        self.music_mini_command_frame = None
        self.music_mini_entry = None
        self.music_mini_send_button = None
        self.music_subtitle_words = []
        self.music_subtitle_index = 0
        self.music_subtitle_job = None
        self.music_monitor_job = None
        self.music_monitor_ms = 1200
        self.music_current_lyrics = ""
        self.screen_awareness_job = None
        self.screen_awareness_interval_ms = 5000
        self.last_active_window_title = ""
        self.last_context_message_at = 0.0
        self.companion_mode_enabled = True
        self.auto_open_chat_on_context = True
        self.proactive_research_enabled = True
        self.interest_profile = []
        self.background_knowledge = []
        self.emotional_checkins = []
        self.last_auto_open_chat_at = 0.0
        self.auto_open_chat_cooldown_seconds = 45
        self.last_emotional_checkin_at = 0.0
        self.emotional_checkin_cooldown_seconds = 420
        self.last_background_research_at = 0.0
        self.background_research_cooldown_seconds = 120
        self.last_background_research_topic = ""
        self.pending_background_research_topics = set()
        self.browser_context_server_enabled = True
        self.browser_context_port = 37655
        self.latest_browser_context = {}
        self.latest_browser_context_at = 0.0
        self.browser_context_server = None
        self.browser_context_server_thread = None
        self.browser_context_lock = threading.Lock()
        if self.llm_provider not in self.llm_providers:
            self.llm_provider = "ollama"
        if self.llm_provider == "openai" and not self.llm_endpoint.startswith("https://"):
            self.llm_endpoint = "https://api.openai.com/v1/chat/completions"
        if self.llm_provider == "ollama" and "openai.com" in self.llm_endpoint:
            self.llm_endpoint = "http://127.0.0.1:11434/api/chat"
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
        self.menu.add_separator()
        self.menu.add_command(label="🎮 Modo Libre", command=self.set_mode_free)
        self.menu.add_command(label="🕹️ Modo Suelo", command=self.set_mode_platform)
        self.menu.add_command(label="💬 Chat", command=self.open_chat_bubble)
        self.menu.add_command(label="🎤 Escuchar", command=self.start_listening)
        self.menu.add_command(label="🟢 Voz continua ON", command=self.start_realtime_listening)
        self.menu.add_command(label="⛔ Voz continua OFF", command=self.stop_realtime_listening)
        self.menu.add_separator()
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
        if self.music_session_active:
            self.show_music_controls()
        self.apply_personality(self.personality_name)
        self.load_pet_state(quiet=True)
        # Requisito del proyecto: arrancar siempre en modo suelo.
        self.set_mode_platform()
        self.stats["total_sessions"] += 1
        self.animate()
        self.move()
        self.process_ui_queue()
        self.schedule_visibility_guard()
        self.schedule_assistant_autonomy()
        self.schedule_needs_tick()
        self.schedule_auto_color_change()
        self.start_browser_context_server()
        self.schedule_screen_awareness()
        if self.voice_realtime_enabled:
            self.start_realtime_listening()

    def start_browser_context_server(self):
        if not self.browser_context_server_enabled:
            return
        if self.browser_context_server is not None:
            return

        owner = self

        class BrowserContextHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/context":
                    self.send_response(404)
                    self.end_headers()
                    return

                content_length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(max(0, content_length)).decode("utf-8", errors="ignore")
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {}

                title = str(payload.get("title", "")).strip()[:220]
                url = str(payload.get("url", "")).strip()[:500]
                browser = str(payload.get("browser", "brave")).strip()[:30] or "brave"
                if title or url:
                    with owner.browser_context_lock:
                        owner.latest_browser_context = {
                            "title": title,
                            "url": url,
                            "browser": browser,
                            "timestamp": int(time.time()),
                        }
                        owner.latest_browser_context_at = time.time()

                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, _format, *_args):
                return

        class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
            daemon_threads = True

        try:
            server = ThreadingHTTPServer(("127.0.0.1", int(self.browser_context_port)), BrowserContextHandler)
        except Exception as error:
            print(f"[BrowserContext] No pude iniciar servidor local: {error}")
            return

        self.browser_context_server = server

        def serve():
            try:
                server.serve_forever(poll_interval=0.4)
            except Exception:
                pass

        self.browser_context_server_thread = threading.Thread(target=serve, daemon=True)
        self.browser_context_server_thread.start()
        print(f"[BrowserContext] Servidor activo en 127.0.0.1:{self.browser_context_port}")

    def stop_browser_context_server(self):
        server = self.browser_context_server
        self.browser_context_server = None
        if server is None:
            return
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass

    def get_recent_browser_context(self, freshness_seconds=15):
        with self.browser_context_lock:
            if not self.latest_browser_context:
                return {}
            age = time.time() - float(self.latest_browser_context_at or 0.0)
            if age > float(freshness_seconds):
                return {}
            return dict(self.latest_browser_context)

    def discover_available_styles(self):
        return self.design_manager.discover_available_styles()

    def build_animation_sources_for_style(self, style_name):
        return self.design_manager.build_animation_sources_for_style(style_name)

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
        self.position_chat_window()

    def schedule_assistant_autonomy(self):
        if self.is_destroying:
            return

        if not self.functional_automation_enabled:
            self.assistant_job = self.root.after(self.assistant_tick_ms, self.schedule_assistant_autonomy)
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
        if not self.has_permission("files"):
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
        if not self.blocks_enabled:
            return []
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
        return

    def cancel_auto_blocks(self):
        if self.auto_block_job is not None:
            self.root.after_cancel(self.auto_block_job)
            self.auto_block_job = None

    def schedule_next_auto_block(self):
        return

    def auto_place_block(self):
        self.auto_block_job = None
        return

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
        if not self.blocks_enabled:
            return False
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
        return False

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
        if not self.blocks:
            return
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
        if not self.blocks_enabled or not self.blocks:
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
        if self.execution_mode == "platform" and self.blocks_enabled:
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
            print("[Sandbox] ON - usa flechas para mover y salto manual")
        else:
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
        return self.state_manager.get_session_runtime_seconds()

    def format_seconds(self, total_seconds):
        return self.state_manager.format_seconds(total_seconds)

    def load_assistant_config(self):
        return self.state_manager.load_assistant_config()

    def save_assistant_config(self):
        return self.state_manager.save_assistant_config()

    def has_permission(self, category):
        return self.permission_manager.has_permission(category)

    def set_permission_level(self, level):
        return self.permission_manager.set_permission_level(level)

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
        if not self.llm_enabled:
            return ""

        if self.llm_offline_only and self.llm_provider != "ollama":
            return ""

        if self.llm_provider == "openai":
            return self.query_openai_llm(user_prompt)
        if self.llm_provider == "ollama":
            return self.query_ollama_llm(user_prompt)
        return ""

    def build_pet_identity_system_prompt(self):
        return self.identity_manager.build_pet_identity_system_prompt()

    def query_openai_llm(self, user_prompt):
        system_prompt = self.build_pet_identity_system_prompt()
        return self.llm_gateway.query_openai_chat(
            endpoint=self.llm_endpoint,
            api_key=self.llm_api_key,
            model=self.llm_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.llm_timeout_seconds,
        )

    def query_ollama_llm(self, user_prompt):
        system_prompt = self.build_pet_identity_system_prompt()
        return self.query_ollama_llm_with_system(system_prompt, user_prompt)

    def query_ollama_llm_with_system(self, system_prompt, user_prompt):
        return self.llm_gateway.query_ollama_chat(
            endpoint=self.llm_endpoint,
            model=self.llm_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.llm_timeout_seconds,
            temperature=0.4,
            num_ctx=2048,
        )

    def check_ollama_health(self):
        return self.llm_gateway.check_ollama_health(self.llm_endpoint, self.llm_timeout_seconds)

    def format_pet_memory(self):
        return self.identity_manager.format_pet_memory()

    def format_music_memory(self):
        return self.identity_manager.format_music_memory()

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

    def position_chat_window(self):
        self.chat_controller.position_chat_window()

    def get_ai_mode_badge_text(self):
        if self.llm_offline_only:
            return "Modo IA: LOCAL"
        return "Modo IA: LOCAL + INTERNET"

    def get_chat_header_text(self):
        return f"{self.pet_name}  |  {self.get_ai_mode_badge_text()}"

    def refresh_chat_header_mode(self):
        if self.chat_header_label is None or not self.chat_header_label.winfo_exists():
            return
        self.chat_header_label.config(text=self.get_chat_header_text())

    def activate_local_ai_mode(self):
        self.llm_provider = "ollama"
        self.llm_endpoint = "http://127.0.0.1:11434/api/chat"
        self.llm_offline_only = True
        self.llm_enabled = True
        self.save_assistant_config()
        self.refresh_chat_header_mode()
        self.set_chat_status("Modo IA local activado.")

    def activate_cloud_ai_mode(self):
        self.llm_provider = "openai"
        self.llm_endpoint = "https://api.openai.com/v1/chat/completions"
        self.llm_offline_only = False
        self.llm_enabled = bool(self.llm_api_key)
        self.save_assistant_config()
        self.refresh_chat_header_mode()
        if self.llm_enabled:
            self.set_chat_status("Modo IA + internet activado.")
        else:
            self.set_chat_status("Modo IA + internet sin API key activa.")

    def query_ollama_local_with_system(self, system_prompt, user_prompt):
        return self.llm_gateway.query_ollama_local_chat(
            model=self.local_intent_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.llm_timeout_seconds,
        )

    def touch_chat_activity(self):
        self.chat_controller.touch_chat_activity()

    def close_chat_if_inactive(self):
        self.chat_controller.close_chat_if_inactive()

    def face_user(self):
        pointer_x, _pointer_y = self.root.winfo_pointerxy()
        sprite_width, _sprite_height = self.get_walking_sprite_size()
        center_x = self.x + sprite_width // 2
        self.direction_x = 1 if pointer_x >= center_x else -1

    def open_chat_bubble(self):
        self.chat_controller.open_chat_bubble()

    def close_chat_bubble(self):
        self.chat_controller.close_chat_bubble()

    def append_chat_message(self, speaker, text):
        self.chat_controller.append_chat_message(speaker, text)

    def set_chat_status(self, text):
        self.chat_controller.set_chat_status(text)

    def submit_chat_message(self, _event=None):
        return self.chat_controller.submit_chat_message(_event)

    def _chat_worker(self, raw_text):
        self.chat_controller._chat_worker(raw_text)

    def sanitize_folder_name(self, raw_name):
        return self.text_parser.sanitize_folder_name(raw_name)

    def normalize_command_text(self, text):
        return self.text_parser.normalize_command_text(text)

    def extract_json_object(self, raw_text):
        return self.text_parser.extract_json_object(raw_text)

    def interpret_local_action(self, raw_command):
        return self.command_handler.interpret_local_action(raw_command)

    def extract_folder_name_from_command(self, command):
        return self.text_parser.extract_folder_name_from_command(command)

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
        return self.action_manager.can_run_system_action(bypass_cooldown)

    def append_action_log(self, action, detail, status):
        self.action_manager.append_action_log(action, detail, status)

    def load_action_log_entries(self):
        return self.action_manager.load_action_log_entries()

    def format_recent_actions(self, limit=6):
        return self.action_manager.format_recent_actions(limit)

    def is_affirmative_command(self, command):
        return self.action_manager.is_affirmative_command(command)

    def is_negative_command(self, command):
        return self.action_manager.is_negative_command(command)

    def has_active_pending_action(self):
        return self.action_manager.has_active_pending_action()

    def queue_pending_action(self, action_name, args, description):
        return self.action_manager.queue_pending_action(action_name, args, description)

    def execute_pending_action(self):
        return self.action_manager.execute_pending_action()

    def looks_like_system_request(self, command):
        return self.action_manager.looks_like_system_request(command)

    def prompt_create_desktop_folder(self):
        self.action_manager.prompt_create_desktop_folder()

    def create_desktop_folder(self, folder_name, auto=False):
        return self.action_manager.create_desktop_folder(folder_name, auto)

    def prompt_archive_desktop_item(self):
        self.action_manager.prompt_archive_desktop_item()

    def archive_desktop_item(self, item_name, auto=False):
        return self.action_manager.archive_desktop_item(item_name, auto)

    def control_media_key(self, action, auto=False):
        self.action_manager.control_media_key(action, auto)

    def _music_controls_on_press(self, event):
        self.music_controls_drag_offset = (event.x, event.y)

    def _music_controls_on_drag(self, event):
        if self.music_controls_window is None or not self.music_controls_window.winfo_exists():
            return
        offset_x, offset_y = self.music_controls_drag_offset
        new_x = max(0, event.x_root - offset_x)
        new_y = max(0, event.y_root - offset_y)
        self.music_controls_window.geometry(f"+{new_x}+{new_y}")

    def _create_music_icon_button(self, parent, icon_name, command, bg_color="#1a4e84"):
        canvas = tk.Canvas(parent, width=42, height=42, bg="#10253f", highlightthickness=0, bd=0)
        circle = canvas.create_oval(3, 3, 39, 39, fill=bg_color, outline="#0b1f34", width=2)

        if icon_name == "pause":
            canvas.create_rectangle(15, 13, 19, 29, fill="white", outline="white")
            canvas.create_rectangle(23, 13, 27, 29, fill="white", outline="white")
        elif icon_name == "next":
            canvas.create_polygon(14, 12, 24, 21, 14, 30, fill="white", outline="white")
            canvas.create_polygon(22, 12, 32, 21, 22, 30, fill="white", outline="white")
        elif icon_name == "exit":
            canvas.create_line(15, 15, 27, 27, fill="white", width=3)
            canvas.create_line(27, 15, 15, 27, fill="white", width=3)

        def _on_enter(_event):
            canvas.itemconfig(circle, fill="#2a6bab")

        def _on_leave(_event):
            canvas.itemconfig(circle, fill=bg_color)

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)
        canvas.bind("<Button-1>", lambda _event: command())
        return canvas

    def _music_mini_on_press(self, event):
        self.music_controls_drag_offset = (event.x, event.y)

    def _music_mini_on_drag(self, event):
        if self.music_mini_chat_window is None or not self.music_mini_chat_window.winfo_exists():
            return
        offset_x, offset_y = self.music_controls_drag_offset
        new_x = max(0, event.x_root - offset_x)
        new_y = max(0, event.y_root - offset_y)
        self.music_mini_chat_window.geometry(f"+{new_x}+{new_y}")

    def toggle_music_mini_mode(self):
        self.music_mini_mode = "command" if self.music_mini_mode == "subtitle" else "subtitle"
        if self.music_mini_mode_button is not None and self.music_mini_mode_button.winfo_exists():
            icon = "⌨" if self.music_mini_mode == "command" else "♪"
            self.music_mini_mode_button.config(text=icon)
        self.refresh_music_mini_layout()

    def refresh_music_mini_layout(self):
        if self.music_mini_chat_window is None or not self.music_mini_chat_window.winfo_exists():
            return

        if self.music_mini_mode == "command":
            if self.music_mini_command_frame is not None and self.music_mini_command_frame.winfo_exists():
                self.music_mini_command_frame.pack(side="left", fill="x", expand=True, padx=(2, 6), pady=3)
            if self.music_mini_chat_label is not None and self.music_mini_chat_label.winfo_exists():
                self.music_mini_chat_label.pack_forget()
            self.music_mini_chat_window.geometry("420x44+" + self.music_mini_chat_window.geometry().split("+")[1] + "+" + self.music_mini_chat_window.geometry().split("+")[2])
            if self.music_mini_entry is not None and self.music_mini_entry.winfo_exists():
                self.music_mini_entry.focus_set()
            return

        if self.music_mini_command_frame is not None and self.music_mini_command_frame.winfo_exists():
            self.music_mini_command_frame.pack_forget()
        if self.music_mini_chat_label is not None and self.music_mini_chat_label.winfo_exists():
            self.music_mini_chat_label.pack(side="left", fill="x", expand=True)
        self.music_mini_chat_window.geometry("340x40+" + self.music_mini_chat_window.geometry().split("+")[1] + "+" + self.music_mini_chat_window.geometry().split("+")[2])

    def _music_mini_submit_command(self, _event=None):
        if self.music_mini_entry is None or not self.music_mini_entry.winfo_exists():
            return "break"
        raw = self.music_mini_entry.get().strip()
        if not raw:
            return "break"
        self.music_mini_entry.delete(0, "end")

        if not raw.startswith("!"):
            raw = f"!{raw}"

        self.show_music_mini_chat(f"Cmd: {raw}")

        def worker(command_text):
            try:
                answer = self.handle_voice_or_text_command(command_text)
            except Exception as error:
                answer = f"Error comando musical: {error}"
            self.ui_queue.put(("music_mini_feedback", str(answer or "Listo.")))

        threading.Thread(target=worker, args=(raw,), daemon=True).start()
        return "break"

    def _build_subtitle_chunks(self, text, chunk_words=6):
        raw = " ".join(str(text or "").split()).strip()
        if not raw:
            return []
        words = raw.split(" ")
        chunks = []
        step = max(3, int(chunk_words))
        for index in range(0, len(words), step):
            chunks.append(" ".join(words[index : index + step]))
        return chunks

    def schedule_music_subtitles(self):
        if self.music_subtitle_job is not None:
            self.root.after_cancel(self.music_subtitle_job)
            self.music_subtitle_job = None

        if not self.music_session_active:
            return
        if self.music_mini_mode != "subtitle":
            self.music_subtitle_job = self.root.after(1200, self.schedule_music_subtitles)
            return

        if self.music_mini_chat_label is not None and self.music_mini_chat_label.winfo_exists():
            if self.music_subtitle_words:
                line = self.music_subtitle_words[self.music_subtitle_index % len(self.music_subtitle_words)]
                self.music_mini_chat_label.config(text=line[:95])
                self.music_subtitle_index += 1
            else:
                self.music_mini_chat_label.config(text=f"Sonando: {self.music_current_song}"[:95])

        self.music_subtitle_job = self.root.after(1700, self.schedule_music_subtitles)

    def _music_backend_is_playing(self):
        backend = str(getattr(self, "music_backend", "")).strip().lower()

        if backend == "pygame":
            try:
                pygame = __import__("pygame")
                if not pygame.mixer.get_init():
                    return False
                return bool(pygame.mixer.music.get_busy())
            except Exception:
                return False

        if backend == "winsound":
            duration = float(getattr(self, "music_track_duration_seconds", 0.0) or 0.0)
            started_at = float(getattr(self, "music_track_started_at", 0.0) or 0.0)
            if duration <= 0.0 or started_at <= 0.0:
                return False
            return (time.time() - started_at) < (duration + 0.35)

        if backend == "vlc":
            player = getattr(self, "music_player", None)
            if player is None:
                return False
            try:
                state = str(player.get_state())
                return state not in {"State.Ended", "State.Stopped", "State.Error", "Ended", "Stopped", "Error"}
            except Exception:
                return False

        return False

    def schedule_music_monitor(self):
        if self.is_destroying:
            return

        if self.music_monitor_job is not None:
            self.root.after_cancel(self.music_monitor_job)
            self.music_monitor_job = None

        self.music_monitor_job = self.root.after(self.music_monitor_ms, self.run_music_monitor_tick)

    def run_music_monitor_tick(self):
        if self.is_destroying:
            return

        self.music_monitor_job = None
        if self.music_session_active:
            queue = list(getattr(self, "music_queue", []))
            is_playing = self._music_backend_is_playing()
            if queue and not is_playing:
                self.play_next_from_queue()
            elif not queue and not is_playing and not self.music_paused:
                self.deactivate_music_session()

        self.schedule_music_monitor()

    def update_music_mini_feedback(self, message):
        feedback = str(message or "Listo").strip()
        if not feedback:
            return
        self.show_music_mini_chat(feedback[:90])
        self.append_chat_message("Mimi", feedback[:200])

    def show_music_mini_chat(self, message=""):
        if self.music_mini_chat_window is not None and self.music_mini_chat_window.winfo_exists():
            if self.music_mini_chat_label is not None and message:
                self.music_mini_chat_label.config(text=message[:90])
            self.music_mini_chat_window.deiconify()
            self.music_mini_chat_window.lift()
            return

        self.music_mini_chat_window = tk.Toplevel(self.root)
        self.music_mini_chat_window.overrideredirect(True)
        self.music_mini_chat_window.attributes("-topmost", True)
        self.music_mini_chat_window.configure(bg="#0b2440", highlightthickness=2, highlightbackground="#07172a")

        container = tk.Frame(self.music_mini_chat_window, bg="#123b6b")
        container.pack(fill="both", expand=True)
        container.bind("<ButtonPress-1>", self._music_mini_on_press)
        container.bind("<B1-Motion>", self._music_mini_on_drag)

        badge = tk.Label(
            container,
            text="Mimi ♪",
            bg="#123b6b",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
        )
        badge.pack(side="left")
        badge.bind("<ButtonPress-1>", self._music_mini_on_press)
        badge.bind("<B1-Motion>", self._music_mini_on_drag)

        self.music_mini_mode_button = tk.Button(
            container,
            text="♪",
            command=self.toggle_music_mini_mode,
            bg="#123b6b",
            fg="white",
            activebackground="#0e2d51",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            padx=6,
            pady=0,
            font=("Segoe UI", 9, "bold"),
        )
        self.music_mini_mode_button.pack(side="left")
        self.music_mini_mode_button.bind("<ButtonPress-1>", self._music_mini_on_press)
        self.music_mini_mode_button.bind("<B1-Motion>", self._music_mini_on_drag)

        self.music_mini_chat_label = tk.Label(
            container,
            text=message[:90] if message else "Reproduciendo musica",
            bg="#123b6b",
            fg="#d6e9ff",
            font=("Segoe UI", 8),
            anchor="w",
            padx=6,
            pady=3,
        )
        self.music_mini_chat_label.pack(side="left", fill="x", expand=True)
        self.music_mini_chat_label.bind("<ButtonPress-1>", self._music_mini_on_press)
        self.music_mini_chat_label.bind("<B1-Motion>", self._music_mini_on_drag)

        self.music_mini_command_frame = tk.Frame(container, bg="#123b6b")
        self.music_mini_entry = tk.Entry(
            self.music_mini_command_frame,
            font=("Segoe UI", 8),
            bg="#1d4f87",
            fg="white",
            insertbackground="white",
            relief="flat",
        )
        self.music_mini_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.music_mini_entry.bind("<Return>", self._music_mini_submit_command)

        self.music_mini_send_button = tk.Button(
            self.music_mini_command_frame,
            text=">",
            command=self._music_mini_submit_command,
            bg="#0e2d51",
            fg="white",
            activebackground="#07172a",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            padx=8,
        )
        self.music_mini_send_button.pack(side="left")

        bubble_x = min(self.root.winfo_screenwidth() - 360, max(10, self.x + 90))
        bubble_y = min(self.root.winfo_screenheight() - 90, max(10, self.y + 120))
        self.music_mini_chat_window.geometry(f"340x40+{bubble_x}+{bubble_y}")
        self.refresh_music_mini_layout()

    def hide_music_mini_chat(self):
        if self.music_mini_chat_window is None:
            return
        try:
            self.music_mini_chat_window.withdraw()
        except Exception:
            pass

    def show_music_controls(self):
        if self.music_controls_window is not None and self.music_controls_window.winfo_exists():
            self.music_controls_window.deiconify()
            self.music_controls_window.lift()
            return

        self.music_controls_window = tk.Toplevel(self.root)
        self.music_controls_window.overrideredirect(True)
        self.music_controls_window.attributes("-topmost", True)
        self.music_controls_window.configure(bg="#10253f", highlightthickness=2, highlightbackground="#081523")

        frame = tk.Frame(self.music_controls_window, bg="#10253f")
        frame.pack(fill="both", expand=True)
        frame.bind("<ButtonPress-1>", self._music_controls_on_press)
        frame.bind("<B1-Motion>", self._music_controls_on_drag)

        title = tk.Label(
            frame,
            text="Mimi Music",
            bg="#10253f",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4,
        )
        title.pack(fill="x")
        title.bind("<ButtonPress-1>", self._music_controls_on_press)
        title.bind("<B1-Motion>", self._music_controls_on_drag)

        controls = tk.Frame(frame, bg="#10253f")
        controls.pack(fill="x", padx=8, pady=(2, 8))

        pause_btn = self._create_music_icon_button(
            controls,
            icon_name="pause",
            command=lambda: self.action_manager.toggle_music_pause(),
            bg_color="#1a4e84",
        )
        pause_btn.pack(side="left")

        next_btn = self._create_music_icon_button(
            controls,
            icon_name="next",
            command=self.play_next_from_queue,
            bg_color="#1a4e84",
        )
        next_btn.pack(side="left", padx=(8, 0))

        exit_btn = self._create_music_icon_button(
            controls,
            icon_name="exit",
            command=self.exit_music_session,
            bg_color="#7a1d1d",
        )
        exit_btn.pack(side="left", padx=(8, 0))

        panel_x = min(self.root.winfo_screenwidth() - 210, max(10, self.x + 90))
        panel_y = min(self.root.winfo_screenheight() - 112, max(10, self.y + 20))
        self.music_controls_window.geometry(f"200x92+{panel_x}+{panel_y}")

    def hide_music_controls(self):
        if self.music_controls_window is None:
            return
        try:
            self.music_controls_window.withdraw()
        except Exception:
            pass

    def activate_music_session(self, song_query, lyrics_preview=""):
        self.music_session_active = True
        self.music_current_song = str(song_query or "").strip()[:120]
        self.music_current_lyrics = str(lyrics_preview or "").strip()[:500]
        self.music_subtitle_words = self._build_subtitle_chunks(self.music_current_lyrics, chunk_words=6)
        self.music_subtitle_index = 0
        self.music_mini_mode = "subtitle"
        self.show_music_controls()
        self.show_music_mini_chat(f"Sonando: {self.music_current_song}")
        self.schedule_music_subtitles()
        self.schedule_music_monitor()
        self.set_listening()
        self.save_assistant_config()

    def deactivate_music_session(self):
        self.music_session_active = False
        self.music_current_song = ""
        self.music_current_lyrics = ""
        self.music_subtitle_words = []
        self.music_subtitle_index = 0
        if self.music_subtitle_job is not None:
            self.root.after_cancel(self.music_subtitle_job)
            self.music_subtitle_job = None
        if self.music_monitor_job is not None:
            self.root.after_cancel(self.music_monitor_job)
            self.music_monitor_job = None
        self.hide_music_controls()
        self.hide_music_mini_chat()
        self.set_walking()

    def play_next_from_queue(self):
        ok, message = self.action_manager.play_next_queued_song()
        self.set_chat_status(message)
        if ok:
            self.show_music_mini_chat(message)
        if ok:
            self.append_chat_message("Mimi", message)
        else:
            self.append_chat_message("Mimi", "La cola musical esta vacia.")

    def exit_music_session(self):
        self.action_manager.exit_music_session()
        self.set_chat_status("Sesion musical finalizada.")
        self.append_chat_message("Mimi", "Cerrando la sesion musical y limpiando cola.")

    def schedule_screen_awareness(self):
        if self.is_destroying:
            return
        self.run_screen_awareness_tick()
        self.screen_awareness_job = self.root.after(self.screen_awareness_interval_ms, self.schedule_screen_awareness)

    def run_screen_awareness_tick(self):
        context_source = "window"
        browser_context = self.get_recent_browser_context(freshness_seconds=18)
        if browser_context:
            title = str(browser_context.get("title", "")).strip()
            url = str(browser_context.get("url", "")).strip()
            if url and title:
                title = f"{title} | {url}"
            elif url:
                title = url
            context_source = str(browser_context.get("browser", "brave")).strip() or "browser"
        else:
            title = self.action_manager.get_active_window_title()

        if not title:
            return

        if title == self.last_active_window_title:
            return
        self.last_active_window_title = title

        topic = self.action_manager.update_interest_profile_from_window(title)
        if topic:
            self.save_assistant_config()
            self.queue_background_topic_research(topic)

        message = self.action_manager.build_window_personalized_message(title)
        if context_source == "brave":
            message = f"[Brave] {message}"
        self.set_chat_status(message)

        now = time.time()
        if now - self.last_context_message_at >= 18:
            self.maybe_auto_open_chat_bubble(now)
            self.append_chat_message("Mimi", message)
            self.last_context_message_at = now

        if self.companion_mode_enabled and now - self.last_emotional_checkin_at >= self.emotional_checkin_cooldown_seconds:
            checkin_message = self.action_manager.build_emotional_checkin_message(title)
            if checkin_message:
                self.maybe_auto_open_chat_bubble(now)
                self.append_chat_message("Mimi", checkin_message)
                self.record_emotional_checkin(f"Check-in: {checkin_message}", title)
                self.last_emotional_checkin_at = now

    def maybe_auto_open_chat_bubble(self, now=None):
        if not self.auto_open_chat_on_context:
            return
        if self.chat_window is not None and self.chat_window.winfo_exists():
            return
        now = time.time() if now is None else float(now)
        if now - self.last_auto_open_chat_at < self.auto_open_chat_cooldown_seconds:
            return
        self.open_chat_bubble()
        self.last_auto_open_chat_at = now

    def record_emotional_checkin(self, summary, context):
        note = {
            "timestamp": int(time.time()),
            "summary": str(summary or "").strip()[:180],
            "context": str(context or "").strip()[:100],
        }
        if not note["summary"]:
            return
        self.emotional_checkins.append(note)
        self.emotional_checkins = self.emotional_checkins[-30:]
        self.save_assistant_config()

    def queue_background_topic_research(self, topic):
        if not self.proactive_research_enabled:
            return

        cleaned_topic = str(topic or "").strip()[:70]
        if not cleaned_topic:
            return

        now = time.time()
        if now - self.last_background_research_at < self.background_research_cooldown_seconds:
            return
        if cleaned_topic.lower() == self.last_background_research_topic.lower():
            return
        if cleaned_topic.lower() in self.pending_background_research_topics:
            return

        self.pending_background_research_topics.add(cleaned_topic.lower())

        def worker():
            summary = self.action_manager.fetch_topic_background_summary(cleaned_topic)
            if summary:
                self.action_manager.remember_background_knowledge(cleaned_topic, summary)
                self.last_background_research_at = time.time()
                self.last_background_research_topic = cleaned_topic
                self.save_assistant_config()
            self.pending_background_research_topics.discard(cleaned_topic.lower())

        threading.Thread(target=worker, daemon=True).start()

    def save_pet_state(self):
        return self.state_manager.save_pet_state()

    def load_pet_state(self, quiet=False):
        return self.state_manager.load_pet_state(quiet=quiet)

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

        # Mientras el chat esta abierto, la mascota permanece quieta y atenta.
        if self.chat_window is not None and self.chat_window.winfo_exists():
            if self.state != "listening":
                self.set_listening()
            self.root.geometry(f"+{self.x}+{self.y}")
            self.root.after(40, self.move)
            return

        # Durante sesion musical se mantiene quieta para no distraer.
        if self.music_session_active:
            if self.state != "listening":
                self.set_listening()
            self.face_user()
            self.root.geometry(f"+{self.x}+{self.y}")
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

        if self.state == "listening":
            self.face_user()
            support_y = self.find_support_y(self.x, self.y, sprite_width, sprite_height)
            if self.y < support_y:
                self.vertical_velocity = min(self.max_fall_speed, self.vertical_velocity + self.gravity)
                self.y = min(support_y, self.y + int(self.vertical_velocity))
            else:
                self.y = support_y
                self.base_y = self.y
                self.vertical_velocity = 0.0
                self.on_ground = True
                self.is_in_air = False
            self.root.geometry(f"+{self.x}+{self.y}")
            return

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

        self.voice_manager.stop_continuous_listening()

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

        if self.screen_awareness_job is not None:
            self.root.after_cancel(self.screen_awareness_job)
            self.screen_awareness_job = None

        if self.music_controls_window is not None:
            try:
                self.music_controls_window.destroy()
            except Exception:
                pass
        if self.music_mini_chat_window is not None:
            try:
                self.music_mini_chat_window.destroy()
            except Exception:
                pass

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
        self.voice_manager.listen_worker()

    def handle_voice_or_text_command(self, text):
        return self.command_handler.handle(text)

    def _speak(self, text):
        self.voice_manager.speak(text)

    def on_app_close(self):
        if self.is_destroying:
            return
        self.is_destroying = True
        self.voice_manager.stop_continuous_listening()
        if self.screen_awareness_job is not None:
            self.root.after_cancel(self.screen_awareness_job)
            self.screen_awareness_job = None
        if self.music_controls_window is not None:
            try:
                self.music_controls_window.destroy()
            except Exception:
                pass
        if self.music_mini_chat_window is not None:
            try:
                self.music_mini_chat_window.destroy()
            except Exception:
                pass
        if self.music_monitor_job is not None:
            try:
                self.root.after_cancel(self.music_monitor_job)
            except Exception:
                pass
            self.music_monitor_job = None
        self.stop_browser_context_server()
        self.save_assistant_config()
        self.root.destroy()

    def process_ui_queue(self):
        self.ui_event_controller.process_ui_queue()

if __name__ == "__main__":
    root = tk.Tk()
    pet = DesktopPet(root)
    root.mainloop()