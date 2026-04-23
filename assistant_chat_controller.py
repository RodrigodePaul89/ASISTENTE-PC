import threading
import tkinter as tk
import math


class ChatUIController:
    def __init__(self, owner):
        self.owner = owner

    def position_chat_window(self):
        if self.owner.chat_window is None or not self.owner.chat_window.winfo_exists():
            return

        content = ""
        if self.owner.chat_history is not None and self.owner.chat_history.winfo_exists():
            content = self.owner.chat_history.get("1.0", "end-1c").strip()

        lines = content.splitlines() if content else ["Chat local listo."]
        estimated_lines = sum(max(1, math.ceil(len(line) / 30)) for line in lines)
        visible_lines = max(3, min(8, estimated_lines + 1))
        visible_chars = max(24, min(42, max((len(line) for line in lines), default=24) + 2))

        if self.owner.chat_history is not None and self.owner.chat_history.winfo_exists():
            self.owner.chat_history.configure(height=visible_lines, width=visible_chars)

        window_width = max(250, min(420, 44 + visible_chars * 7))
        window_height = max(135, min(280, 92 + visible_lines * 18))
        screen_width = self.owner.root.winfo_screenwidth()
        screen_height = self.owner.root.winfo_screenheight()
        sprite_width, _ = self.owner.get_walking_sprite_size()
        chat_x = min(screen_width - window_width - 12, max(12, self.owner.x + sprite_width + 10))
        chat_y = min(screen_height - window_height - 12, max(12, self.owner.y - 20))
        self.owner.chat_window.geometry(f"{window_width}x{window_height}+{chat_x}+{chat_y}")

    def touch_chat_activity(self):
        if self.owner.chat_autohide_job is not None:
            self.owner.root.after_cancel(self.owner.chat_autohide_job)
            self.owner.chat_autohide_job = None

        if self.owner.chat_inactivity_ms <= 0:
            return

        if self.owner.chat_window is not None and self.owner.chat_window.winfo_exists():
            self.owner.chat_autohide_job = self.owner.root.after(
                self.owner.chat_inactivity_ms,
                self.close_chat_if_inactive,
            )

    def close_chat_if_inactive(self):
        self.owner.chat_autohide_job = None
        if self.owner.chat_request_in_flight:
            self.touch_chat_activity()
            return
        self.close_chat_bubble()

    def _handle_chat_focus_out(self, _event=None):
        if self.owner.chat_window is None or not self.owner.chat_window.winfo_exists():
            return

        def _close_if_focus_left():
            if self.owner.chat_window is None or not self.owner.chat_window.winfo_exists():
                return
            focused = self.owner.chat_window.focus_displayof()
            if focused is None:
                self.close_chat_bubble()
                return
            # Si el foco sigue dentro de la misma burbuja, no cerrar.
            focused_toplevel = focused.winfo_toplevel()
            if focused_toplevel != self.owner.chat_window:
                self.close_chat_bubble()

        self.owner.root.after(20, _close_if_focus_left)

    def open_chat_bubble(self):
        if self.owner.chat_window is not None and self.owner.chat_window.winfo_exists():
            self.position_chat_window()
            self.owner.chat_window.deiconify()
            self.owner.chat_window.lift()
            if self.owner.chat_entry is not None:
                self.owner.chat_entry.focus_set()
            self.owner.set_listening()
            self.touch_chat_activity()
            return

        self.owner.chat_window = tk.Toplevel(self.owner.root)
        self.owner.chat_window.overrideredirect(True)
        self.owner.chat_window.attributes("-topmost", True)
        self.owner.chat_window.configure(bg="#0b2440", highlightthickness=2, highlightbackground="#07172a")
        self.owner.chat_window.protocol("WM_DELETE_WINDOW", self.close_chat_bubble)
        self.owner.chat_window.bind("<FocusOut>", self._handle_chat_focus_out)
        container = tk.Frame(
            self.owner.chat_window,
            bg="#123b6b",
            highlightthickness=2,
            highlightbackground="#07172a",
            highlightcolor="#07172a",
        )
        container.pack(fill="both", expand=True)

        header = tk.Label(
            container,
            text=self.owner.get_chat_header_text(),
            bg="#123b6b",
            fg="white",
            anchor="w",
            padx=10,
            pady=5,
            font=("Segoe UI", 10, "bold"),
        )
        header.pack(fill="x")
        self.owner.chat_header_label = header

        self.owner.chat_history = tk.Text(
            container,
            wrap="word",
            height=4,
            bg="#123b6b",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9),
            insertbackground="white",
            highlightthickness=0,
            borderwidth=0,
            padx=2,
            pady=2,
        )
        self.owner.chat_history.pack(fill="both", expand=True, padx=8, pady=(8, 6))
        for speaker, message in self.owner.chat_transcript:
            self.owner.chat_history.insert("end", f"{speaker}: {message}\n")
        self.owner.chat_history.config(state="disabled")

        input_frame = tk.Frame(container, bg="#123b6b")
        input_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.owner.chat_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 9),
            bg="#1d4f87",
            fg="white",
            insertbackground="white",
            relief="flat",
        )
        self.owner.chat_entry.pack(side="left", fill="x", expand=True)
        self.owner.chat_entry.bind("<Return>", self.submit_chat_message)
        self.owner.chat_entry.bind("<KeyRelease>", lambda _event: self.touch_chat_activity())

        self.owner.chat_send_button = tk.Button(
            input_frame,
            text="Enviar",
            command=self.submit_chat_message,
            bg="#0e2d51",
            fg="white",
            activebackground="#07172a",
            activeforeground="white",
            relief="flat",
            padx=10,
            borderwidth=0,
        )
        self.owner.chat_send_button.pack(side="left", padx=(6, 0))

        self.owner.chat_status_label = tk.Label(
            container,
            text="Doble clic en la mascota o clic derecho > Chat para abrir esto.",
            bg="#123b6b",
            fg="white",
            anchor="w",
            padx=10,
            pady=4,
            font=("Segoe UI", 8),
        )
        self.owner.chat_status_label.pack(fill="x")
        self.owner.chat_entry.focus_set()
        self.position_chat_window()
        self.owner.set_listening()
        self.owner.root.after(80, lambda: self.owner.chat_window.focus_force() if self.owner.chat_window is not None and self.owner.chat_window.winfo_exists() else None)
        self.touch_chat_activity()

    def close_chat_bubble(self):
        if self.owner.chat_autohide_job is not None:
            self.owner.root.after_cancel(self.owner.chat_autohide_job)
            self.owner.chat_autohide_job = None
        if self.owner.chat_window is None:
            return
        try:
            self.owner.chat_window.destroy()
        except Exception:
            pass
        self.owner.chat_window = None
        self.owner.chat_header_label = None
        self.owner.chat_history = None
        self.owner.chat_entry = None
        self.owner.chat_status_label = None
        self.owner.chat_send_button = None
        if not self.owner.is_destroying:
            self.owner.set_walking()

    def append_chat_message(self, speaker, text):
        message = str(text or "").strip()
        if not message:
            return

        self.owner.chat_transcript.append((speaker, message))
        if len(self.owner.chat_transcript) > 80:
            self.owner.chat_transcript = self.owner.chat_transcript[-80:]
        self.owner.save_assistant_config()

        if self.owner.chat_history is not None and self.owner.chat_history.winfo_exists():
            self.owner.chat_history.config(state="normal")
            self.owner.chat_history.insert("end", f"{speaker}: {message}\n")
            self.owner.chat_history.see("end")
            self.owner.chat_history.config(state="disabled")
            self.position_chat_window()
            self.touch_chat_activity()

    def set_chat_status(self, text):
        if self.owner.chat_status_label is None or not self.owner.chat_status_label.winfo_exists():
            return
        self.owner.chat_status_label.config(text=text)
        self.touch_chat_activity()

    def submit_chat_message(self, _event=None):
        if self.owner.chat_request_in_flight:
            self.set_chat_status("Espera a que termine la respuesta actual.")
            return "break"

        if self.owner.chat_entry is None or not self.owner.chat_entry.winfo_exists():
            self.open_chat_bubble()
            return "break"

        raw_text = self.owner.chat_entry.get().strip()
        if not raw_text:
            return "break"

        self.owner.chat_entry.delete(0, "end")
        self.append_chat_message("Tu", raw_text)
        self.set_chat_status("Pensando...")
        self.owner.chat_request_in_flight = True
        self.owner.set_listening()
        self.owner.face_user()

        worker = threading.Thread(target=self._chat_worker, args=(raw_text,), daemon=True)
        worker.start()
        return "break"

    def _chat_worker(self, raw_text):
        try:
            response = self.owner.handle_voice_or_text_command(raw_text)
        except Exception as error:
            response = f"Error procesando mensaje: {error}"

        self.owner.ui_queue.put(("chat_response", response or "No obtuve respuesta."))
        self.owner.ui_queue.put(("chat_status", "Listo."))
        self.owner.ui_queue.put(("set_state", "walking"))
