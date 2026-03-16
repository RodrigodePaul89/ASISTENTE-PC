import ctypes
import json
import os
import shutil
import subprocess
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog


class SystemActionManager:
    def __init__(self, owner):
        self.owner = owner

    def can_run_system_action(self, bypass_cooldown=False):
        now = time.time()
        if (not bypass_cooldown) and now < self.owner.system_action_cooldown_until:
            print("[PC] Espera un momento antes de otra accion.")
            return False

        if not bypass_cooldown:
            self.owner.system_action_cooldown_until = now + self.owner.system_action_cooldown_seconds
        return True

    def append_action_log(self, action, detail, status):
        payload = {
            "timestamp": int(time.time()),
            "action": action,
            "detail": detail,
            "status": status,
        }

        entries = []
        if self.owner.action_log_file.exists():
            try:
                entries = json.loads(self.owner.action_log_file.read_text(encoding="utf-8"))
            except Exception:
                entries = []

        if not isinstance(entries, list):
            entries = []

        entries.append(payload)
        if len(entries) > self.owner.max_action_log_entries:
            entries = entries[-self.owner.max_action_log_entries :]

        try:
            self.owner.action_log_file.write_text(json.dumps(entries, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_action_log_entries(self):
        if not self.owner.action_log_file.exists():
            return []

        try:
            entries = json.loads(self.owner.action_log_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        if not isinstance(entries, list):
            return []
        return entries

    def format_recent_actions(self, limit=6):
        entries = self.load_action_log_entries()
        if not entries:
            return "Todavia no hay acciones registradas."

        recent = entries[-max(1, limit) :]
        lines = []
        for entry in reversed(recent):
            timestamp = int(entry.get("timestamp", 0))
            action = str(entry.get("action", "accion")).strip()
            detail = str(entry.get("detail", "")).strip()
            status = str(entry.get("status", "")).strip()
            hour = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "--:--:--"
            lines.append(f"{hour} | {action} | {detail} | {status}")
        return "Ultimas acciones:\n" + "\n".join(lines)

    def is_affirmative_command(self, command):
        return command in {"si","s","y","SI","yes", "sí", "sip", "simon", "confirmo", "confirmar", "ok", "dale", "hazlo", "adelante"}

    def is_negative_command(self, command):
        return command in {"no", "nop", "n", "NO", "nope", "cancelar", "cancela", "deten", "detener", "olvidalo", "olvidalo por ahora"}

    def has_active_pending_action(self):
        if not self.owner.pending_action:
            return False
        created_at = float(self.owner.pending_action.get("created_at", 0.0))
        if time.time() - created_at > self.owner.pending_action_timeout_seconds:
            self.owner.pending_action = None
            return False
        return True

    def queue_pending_action(self, action_name, args, description):
        self.owner.pending_action = {
            "action": action_name,
            "args": dict(args or {}),
            "description": str(description or "accion"),
            "created_at": time.time(),
        }
        return f"Entendi esto: {description}. Estas seguro de realizar el cambio especificado?, si/no."

    def execute_pending_action(self):
        if not self.has_active_pending_action():
            self.owner.pending_action = None
            return "No hay ninguna accion pendiente por confirmar."

        action_name = self.owner.pending_action.get("action")
        action_args = self.owner.pending_action.get("args", {})
        description = self.owner.pending_action.get("description", "accion")
        self.owner.pending_action = None

        if action_name == "create_folder":
            folder_name = self.owner.sanitize_folder_name(action_args.get("folder_name", ""))
            if not folder_name:
                return "La accion pendiente no tenia un nombre de carpeta valido."
            if self.create_desktop_folder(folder_name, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "archive_item":
            item_name = self.owner.sanitize_folder_name(action_args.get("item_name", ""))
            if not item_name:
                return "La accion pendiente no tenia un elemento valido."
            if self.archive_desktop_item(item_name, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "delete_item":
            item_name = self.owner.sanitize_folder_name(action_args.get("item_name", ""))
            if not item_name:
                return "La accion pendiente no tenia un elemento valido para eliminar."
            if self.delete_desktop_item(item_name, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "rename_item":
            source_name = self.owner.sanitize_folder_name(action_args.get("source_name", ""))
            target_name = self.owner.sanitize_folder_name(action_args.get("target_name", ""))
            if not source_name or not target_name:
                return "La accion pendiente no tenia nombres validos para renombrar."
            if self.rename_desktop_item(source_name, target_name, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "move_item":
            item_name = self.owner.sanitize_folder_name(action_args.get("item_name", ""))
            target_folder = self.owner.sanitize_folder_name(action_args.get("target_folder", ""))
            if not item_name or not target_folder:
                return "La accion pendiente no tenia datos validos para mover."
            if self.move_desktop_item(item_name, target_folder, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "open_app":
            app_name = str(action_args.get("app_name", "")).strip()
            if not app_name:
                return "La accion pendiente no tenia una aplicacion valida."
            if self.open_app(app_name, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "open_website":
            url = str(action_args.get("url", "")).strip()
            if not url:
                return "La accion pendiente no tenia una URL valida."
            if self.open_website(url, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        if action_name == "take_screenshot":
            screenshot_name = self.owner.sanitize_folder_name(action_args.get("name", "captura")) or "captura"
            destination = self.take_screenshot(screenshot_name, auto=True)
            if destination:
                return f"Listo. {description}. Archivo: {destination.name}."
            return f"No pude completar esto: {description}."

        if action_name == "system_control":
            operation = str(action_args.get("operation", "")).strip().lower()
            if operation in {"lock", "shutdown", "restart"} and self.system_control(operation, auto=True):
                return f"Listo. {description}."
            return f"No pude completar esto: {description}."

        return "La accion pendiente ya no es compatible."

    def _documents_path(self):
        return Path.home() / "Documents"

    def _assistant_data_path(self):
        data_path = self._documents_path() / "MimiAsistente"
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def _notes_path(self):
        notes_dir = self._assistant_data_path() / "Notas"
        notes_dir.mkdir(parents=True, exist_ok=True)
        return notes_dir

    def _reminders_path(self):
        reminder_file = self._assistant_data_path() / "recordatorios.json"
        if not reminder_file.exists():
            reminder_file.write_text("[]", encoding="utf-8")
        return reminder_file

    def _safe_desktop_item(self, item_name):
        safe_item = self.owner.sanitize_folder_name(item_name)
        if not safe_item:
            return None
        target = self.owner.desktop_path / safe_item
        if not self.owner.is_allowed_path(target):
            return None
        return target

    def _parse_time_to_seconds(self, value, unit):
        try:
            amount = int(value)
        except Exception:
            return 0
        unit_norm = str(unit or "").strip().lower()
        if unit_norm.startswith("seg"):
            return max(0, amount)
        if unit_norm.startswith("min"):
            return max(0, amount * 60)
        if unit_norm.startswith("hora"):
            return max(0, amount * 3600)
        return 0

    def open_app(self, app_name, auto=False):
        if not self.owner.has_permission("full"):
            self.append_action_log("open_app", app_name, "blocked-permission")
            return False

        app = str(app_name or "").strip().lower()
        app_map = {
            "chrome": ["chrome"],
            "google chrome": ["chrome"],
            "brave": ["brave"],
            "brave browser": ["brave"],
            "edge": ["msedge"],
            "firefox": ["firefox"],
            "explorador": ["explorer"],
            "explorer": ["explorer"],
            "notepad": ["notepad"],
            "bloc de notas": ["notepad"],
            "paint": ["mspaint"],
            "calculadora": ["calc"],
            "calculator": ["calc"],
            "cmd": ["cmd"],
            "terminal": ["wt"],
            "powershell": ["powershell"],
            "vscode": ["code"],
            "visual studio code": ["code"],
        }
        command = app_map.get(app, [app])
        try:
            subprocess.Popen(command, shell=False)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("open_app", app_name, "ok")
            return True
        except Exception as error:
            self.append_action_log("open_app", app_name, f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude abrir la aplicacion.\n{error}", parent=self.owner.root)
            return False

    def open_website(self, url, auto=False):
        if not self.owner.has_permission("full"):
            self.append_action_log("open_website", url, "blocked-permission")
            return False

        final_url = str(url or "").strip()
        if not final_url:
            return False
        if not final_url.startswith(("http://", "https://")):
            final_url = f"https://{final_url}"

        try:
            webbrowser.open(final_url, new=2)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("open_website", final_url, "ok")
            return True
        except Exception as error:
            self.append_action_log("open_website", final_url, f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude abrir la URL.\n{error}", parent=self.owner.root)
            return False

    def create_note(self, note_title, note_content):
        if not self.owner.has_permission("files"):
            self.append_action_log("create_note", note_title, "blocked-permission")
            return None

        safe_title = self.owner.sanitize_folder_name(note_title) or "nota"
        final_name = safe_title[:60]
        notes_dir = self._notes_path()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        note_file = notes_dir / f"{timestamp}_{final_name}.md"

        body = str(note_content or "").strip() or "(sin contenido)"
        payload = f"# {final_name}\n\n{body}\n"
        try:
            note_file.write_text(payload, encoding="utf-8")
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("create_note", str(note_file), "ok")
            return note_file
        except Exception as error:
            self.append_action_log("create_note", str(note_file), f"error:{error}")
            return None

    def search_desktop_items(self, query, limit=10):
        cleaned = str(query or "").strip().lower()
        if not cleaned:
            return []
        matches = []
        try:
            for item in self.owner.desktop_path.iterdir():
                if cleaned in item.name.lower():
                    matches.append(item.name)
                if len(matches) >= max(1, limit):
                    break
        except Exception:
            return []
        return matches

    def _computer_search_roots(self):
        home = Path.home()
        roots = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "Pictures",
            home / "Videos",
            home / "Music",
        ]
        onedrive = home / "OneDrive"
        if onedrive.exists():
            roots.extend([onedrive / "Desktop", onedrive / "Documents", onedrive / "Pictures"])

        unique = []
        seen = set()
        for root in roots:
            try:
                resolved = root.resolve()
            except Exception:
                continue
            if not resolved.exists() or not resolved.is_dir():
                continue
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(resolved)
        return unique

    def search_computer_items(self, query, limit=20, max_scan=30000):
        cleaned = str(query or "").strip().lower()
        if not cleaned:
            return []

        roots = self._computer_search_roots()
        if not roots:
            return []

        matches = []
        scanned = 0
        for root in roots:
            for current_root, dirnames, filenames in os.walk(root, topdown=True):
                dirnames[:] = [
                    name
                    for name in dirnames
                    if name.lower() not in {"$recycle.bin", "system volume information", ".git", "node_modules", "__pycache__"}
                ]

                scanned += 1
                if scanned > max_scan:
                    self.append_action_log("search_computer_items", cleaned, "stopped:max_scan")
                    return matches

                current_path = Path(current_root)
                for folder_name in dirnames:
                    if cleaned in folder_name.lower():
                        matches.append(str(current_path / folder_name))
                        if len(matches) >= max(1, int(limit)):
                            self.append_action_log("search_computer_items", cleaned, "ok")
                            return matches

                for file_name in filenames:
                    if cleaned in file_name.lower():
                        matches.append(str(current_path / file_name))
                        if len(matches) >= max(1, int(limit)):
                            self.append_action_log("search_computer_items", cleaned, "ok")
                            return matches

        self.append_action_log("search_computer_items", cleaned, "ok")
        return matches

    def get_computer_context_summary(self):
        roots = self._computer_search_roots()
        lines = ["Contexto local cargado para exploracion:"]
        for root in roots:
            lines.append(f"- {root}")
        lines.append("Puedes usar: localizar archivo <nombre> para buscar fuera del escritorio.")
        self.append_action_log("computer_context", "summary", "ok")
        return "\n".join(lines)

    def get_active_window_title(self):
        if os.name != "nt":
            return ""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            return str(buffer.value or "").strip()
        except Exception:
            return ""

    def build_casual_recommendation(self):
        title = self.get_active_window_title()
        lower = title.lower()
        suggestion = "Si quieres, te organizo una tarea rapida o te preparo un recordatorio."

        if any(token in lower for token in ("youtube", "netflix", "spotify")):
            suggestion = "Parece momento de ocio. Te recuerdo hidratarte y descansar la vista en 20 minutos."
        elif any(token in lower for token in ("code", "visual studio", "pycharm", "terminal", "powershell")):
            suggestion = "Estas en modo trabajo tecnico. Si quieres, te creo una nota de pendientes del bloque actual."
        elif any(token in lower for token in ("excel", "word", "powerpoint", "docs", "notion")):
            suggestion = "Veo trabajo de documentos. Te conviene guardar version y crear respaldo rapido."
        elif any(token in lower for token in ("chrome", "edge", "firefox", "brave")):
            suggestion = "Estas navegando. Puedo buscar archivos locales o abrir sitios por alias para acelerar flujo."

        if not title:
            return "No pude leer la ventana activa, pero puedo ayudarte con recordatorios o busquedas locales."
        return f"Veo que estas en: {title}. Recomendacion: {suggestion}"

    def rename_desktop_item(self, source_name, target_name, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("rename_item", source_name, "blocked-permission")
            return False

        source = self._safe_desktop_item(source_name)
        safe_target_name = self.owner.sanitize_folder_name(target_name)
        if source is None or not safe_target_name:
            return False
        destination = source.parent / safe_target_name

        if not self.owner.is_allowed_path(destination):
            self.append_action_log("rename_item", f"{source_name}->{safe_target_name}", "blocked")
            return False
        if not source.exists():
            self.append_action_log("rename_item", source_name, "missing")
            return False
        if destination.exists():
            self.append_action_log("rename_item", str(destination), "exists")
            return False

        try:
            source.rename(destination)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("rename_item", f"{source} -> {destination}", "ok")
            return True
        except Exception as error:
            self.append_action_log("rename_item", str(source), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude renombrar el elemento.\n{error}", parent=self.owner.root)
            return False

    def move_desktop_item(self, item_name, target_folder, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("move_item", item_name, "blocked-permission")
            return False

        source = self._safe_desktop_item(item_name)
        safe_target = self.owner.sanitize_folder_name(target_folder)
        if source is None or not safe_target:
            return False
        destination_dir = self.owner.desktop_path / safe_target
        destination = destination_dir / source.name

        if not self.owner.is_allowed_path(destination_dir) or not self.owner.is_allowed_path(destination):
            self.append_action_log("move_item", f"{item_name}->{target_folder}", "blocked")
            return False
        if not source.exists():
            self.append_action_log("move_item", str(source), "missing")
            return False

        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
            suffix = 1
            while destination.exists():
                destination = destination_dir / f"{source.stem}_{suffix}{source.suffix}"
                suffix += 1
            shutil.move(str(source), str(destination))
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("move_item", f"{source} -> {destination}", "ok")
            return True
        except Exception as error:
            self.append_action_log("move_item", str(source), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude mover el elemento.\n{error}", parent=self.owner.root)
            return False

    def delete_desktop_item(self, item_name, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("delete_item", item_name, "blocked-permission")
            return False

        target = self._safe_desktop_item(item_name)
        if target is None:
            return False
        if not target.exists():
            self.append_action_log("delete_item", str(target), "missing")
            return False

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=False)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("delete_item", str(target), "ok")
            return True
        except Exception as error:
            self.append_action_log("delete_item", str(target), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude eliminar el elemento.\n{error}", parent=self.owner.root)
            return False

    def create_folder_structure(self, folder_names):
        if not self.owner.has_permission("files"):
            self.append_action_log("create_folder_structure", "sin permisos", "blocked-permission")
            return []

        created = []
        for folder_name in folder_names:
            safe_name = self.owner.sanitize_folder_name(folder_name)
            if not safe_name:
                continue
            target = self.owner.desktop_path / safe_name
            if not self.owner.is_allowed_path(target) or target.exists():
                continue
            try:
                target.mkdir(parents=False, exist_ok=False)
                created.append(target.name)
            except Exception as error:
                self.append_action_log("create_folder_structure", str(target), f"error:{error}")

        if created:
            self.owner.stats["pc_actions"] += len(created)
            self.append_action_log("create_folder_structure", ", ".join(created), "ok")
        return created

    def create_reminder(self, seconds_from_now, message):
        if not self.owner.has_permission("query"):
            self.append_action_log("create_reminder", message, "blocked-permission")
            return False

        seconds = max(1, int(seconds_from_now))
        content = str(message or "Recordatorio").strip()[:140]
        run_at = int(time.time() + seconds)
        reminder = {"run_at": run_at, "message": content}

        file_path = self._reminders_path()
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
        data.append(reminder)
        try:
            file_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception:
            pass

        def notify_user():
            try:
                self.owner.append_chat_message("Mimi", f"Recordatorio: {content}")
                self.owner.set_chat_status("Recordatorio disparado.")
            except Exception:
                pass

        self.owner.root.after(seconds * 1000, notify_user)
        self.append_action_log("create_reminder", f"{seconds}s: {content}", "ok")
        return True

    def take_screenshot(self, name_hint, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("screenshot", name_hint, "blocked-permission")
            return None

        try:
            from PIL import ImageGrab
        except Exception as error:
            self.append_action_log("screenshot", name_hint, f"error:{error}")
            return None

        captures_dir = self._assistant_data_path() / "Capturas"
        captures_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self.owner.sanitize_folder_name(name_hint) or "captura"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = captures_dir / f"{timestamp}_{safe_name}.png"

        try:
            image = ImageGrab.grab(all_screens=True)
            image.save(output)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("screenshot", str(output), "ok")
            return output
        except Exception as error:
            self.append_action_log("screenshot", str(output), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude hacer captura.\n{error}", parent=self.owner.root)
            return None

    def run_desktop_cleanup(self):
        if not self.owner.has_permission("files"):
            self.append_action_log("desktop_cleanup", "sin permisos", "blocked-permission")
            return 0

        moved = 0
        for item in self.owner.desktop_path.iterdir():
            lower_name = item.name.lower()
            if item.name == self.owner.archive_folder_name:
                continue
            if lower_name.endswith((".tmp", ".log", ".bak")):
                if self.archive_desktop_item(item.name, auto=True):
                    moved += 1
                continue
            if item.is_dir() and (lower_name.startswith("nueva carpeta") or lower_name.startswith("new folder")):
                if self.archive_desktop_item(item.name, auto=True):
                    moved += 1

        self.append_action_log("desktop_cleanup", f"moved={moved}", "ok")
        return moved

    def system_control(self, operation, auto=False):
        if not self.owner.has_permission("full"):
            self.append_action_log("system_control", operation, "blocked-permission")
            return False

        op = str(operation or "").strip().lower()
        if op not in {"lock", "shutdown", "restart"}:
            return False

        try:
            if op == "lock":
                ctypes.windll.user32.LockWorkStation()
            elif op == "shutdown":
                os.system("shutdown /s /t 0")
            elif op == "restart":
                os.system("shutdown /r /t 0")
            self.append_action_log("system_control", op, "ok")
            self.owner.stats["pc_actions"] += 1
            return True
        except Exception as error:
            self.append_action_log("system_control", op, f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No pude ejecutar la accion del sistema.\n{error}", parent=self.owner.root)
            return False

    def get_capability_diagnostics(self):
        return {
            "carpetas": ["create_folder", "create_folder_structure", "archive_item", "move_item", "rename_item", "delete_item"],
            "productividad": ["create_note", "create_reminder", "search_desktop_items", "search_computer_items", "take_screenshot", "run_desktop_cleanup"],
            "contexto": ["get_computer_context_summary", "get_active_window_title", "build_casual_recommendation"],
            "lanzadores": ["open_app", "open_website"],
            "sistema": ["system_control(lock/restart/shutdown)"],
            "multimedia": ["media_next", "media_prev", "media_play_pause"],
            "ia": ["llm_enable", "llm_disable", "llm_mode_local", "llm_mode_cloud", "set_model", "ollama_status", "ollama_test"],
        }

    def looks_like_system_request(self, command):
        keywords = (
            "carpeta",
            "estructura",
            "archiva",
            "archivar",
            "mueve",
            "renombra",
            "elimina",
            "borra",
            "archivo",
            "escritorio",
            "cancion",
            "musica",
            "pausa",
            "siguiente",
            "anterior",
            "abre",
            "navega",
            "sitio",
            "pagina",
            "recordatorio",
            "nota",
            "captura",
            "limpia escritorio",
            "localizar archivo",
            "buscar en computadora",
            "contexto del equipo",
            "que estoy haciendo",
            "pantalla",
            "apaga",
            "reinicia",
            "bloquea",
            "diagnostico",
            "modo suelo",
            "modo libre",
            "ollama",
            "ia local",
            "modelo ia",
            "permiso",
            "activar ia",
            "desactivar ia",
        )
        return any(keyword in command for keyword in keywords)

    def prompt_create_desktop_folder(self):
        if not self.can_run_system_action():
            return

        name = simpledialog.askstring(
            "Crear Carpeta",
            "Nombre de la nueva carpeta en el Escritorio:",
            parent=self.owner.root,
        )
        if not name:
            return

        safe_name = self.owner.sanitize_folder_name(name)
        if not safe_name:
            messagebox.showwarning("Nombre invalido", "Usa un nombre valido para carpeta.", parent=self.owner.root)
            return

        target = self.owner.desktop_path / safe_name
        if not self.owner.is_allowed_path(target):
            self.append_action_log("create_folder", str(target), "blocked")
            return

        confirm = messagebox.askyesno("Confirmar", f"Crear carpeta:\n{target}", parent=self.owner.root)
        if not confirm:
            self.append_action_log("create_folder", str(target), "cancelled")
            return

        self.create_desktop_folder(safe_name, auto=False)

    def create_desktop_folder(self, folder_name, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("create_folder", folder_name, "blocked-permission")
            return False

        safe_name = self.owner.sanitize_folder_name(folder_name)
        if not safe_name:
            return False

        target = self.owner.desktop_path / safe_name
        if not self.owner.is_allowed_path(target):
            self.append_action_log("create_folder", str(target), "blocked")
            return False

        try:
            target.mkdir(parents=False, exist_ok=False)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("create_folder", str(target), "ok")
            if auto:
                print(f"[Asistente] Carpeta creada automaticamente: {target.name}")
            else:
                print(f"[PC] Carpeta creada: {target.name}")
            return True
        except FileExistsError:
            self.append_action_log("create_folder", str(target), "exists")
            if not auto:
                messagebox.showinfo("Existe", "Esa carpeta ya existe.", parent=self.owner.root)
        except Exception as error:
            self.append_action_log("create_folder", str(target), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No se pudo crear la carpeta.\n{error}", parent=self.owner.root)
        return False

    def prompt_archive_desktop_item(self):
        if not self.can_run_system_action():
            return

        item_name = simpledialog.askstring(
            "Archivar En Escritorio",
            "Nombre del archivo/carpeta del Escritorio a mover:",
            parent=self.owner.root,
        )
        if not item_name:
            return

        safe_name = self.owner.sanitize_folder_name(item_name)
        if not safe_name:
            messagebox.showwarning("Nombre invalido", "No se pudo interpretar el nombre.", parent=self.owner.root)
            return

        self.archive_desktop_item(safe_name, auto=False)

    def archive_desktop_item(self, item_name, auto=False):
        if not self.owner.has_permission("files"):
            self.append_action_log("archive_item", item_name, "blocked-permission")
            return False

        safe_name = self.owner.sanitize_folder_name(item_name)
        if not safe_name:
            return False

        source = self.owner.desktop_path / safe_name
        archive_dir = self.owner.desktop_path / self.owner.archive_folder_name
        destination = archive_dir / safe_name

        if not self.owner.is_allowed_path(source) or not self.owner.is_allowed_path(destination):
            self.append_action_log("archive_item", str(source), "blocked")
            return False

        if not source.exists():
            self.append_action_log("archive_item", str(source), "missing")
            if not auto:
                messagebox.showinfo("No encontrado", "No existe ese archivo/carpeta en el Escritorio.", parent=self.owner.root)
            return False

        if not auto:
            confirm = messagebox.askyesno(
                "Confirmar",
                f"Mover a '{self.owner.archive_folder_name}':\n{source.name}",
                parent=self.owner.root,
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
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("archive_item", f"{source} -> {destination}", "ok")
            if auto:
                print(f"[Asistente] Elemento archivado automaticamente: {source.name}")
            else:
                print(f"[PC] Elemento archivado: {source.name}")
            return True
        except Exception as error:
            self.append_action_log("archive_item", str(source), f"error:{error}")
            if not auto:
                messagebox.showerror("Error", f"No se pudo mover el elemento.\n{error}", parent=self.owner.root)
            return False

    def control_media_key(self, action, auto=False):
        if not self.owner.has_permission("media"):
            self.append_action_log("media_key", action, "blocked-permission")
            return

        if not auto and not self.can_run_system_action():
            return

        key_map = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1}
        vk = key_map.get(action)
        if vk is None:
            return

        if os.name != "nt":
            self.append_action_log("media_key", action, "unsupported-os")
            return

        if not auto:
            confirm = messagebox.askyesno("Confirmar", f"Enviar accion multimedia: {action}", parent=self.owner.root)
            if not confirm:
                self.append_action_log("media_key", action, "cancelled")
                return

        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            self.owner.stats["pc_actions"] += 1
            self.append_action_log("media_key", action, "ok")
            print(f"[PC] Media key enviada: {action}")
        except Exception as error:
            self.append_action_log("media_key", action, f"error:{error}")
            messagebox.showerror("Error", f"No se pudo enviar la tecla multimedia.\n{error}", parent=self.owner.root)
