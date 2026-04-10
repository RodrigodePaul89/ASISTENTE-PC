import threading
import time


class VoiceManager:
    def __init__(self, owner, voice_available, sr_module=None, tts_module=None):
        self.owner = owner
        self.voice_available = bool(voice_available)
        self.sr_module = sr_module
        self.tts_module = tts_module
        self.continuous_thread = None
        self.continuous_stop_event = threading.Event()

    def _ensure_voice_stack(self):
        if self.voice_available and self.sr_module is not None:
            return True

        if not self.owner.voice_warning_shown:
            print("[Aviso] speech_recognition/pyttsx3 no disponibles en el entorno.")
            self.owner.voice_warning_shown = True
        return False

    def _process_recognized_text(self, text):
        recognized = str(text or "").strip().lower()
        if not recognized:
            return

        print(f"[Escuchado] {recognized}")
        normalized = self.owner.strip_wake_word(recognized)
        if self.owner.require_wake_word and not normalized:
            print("[Asistente] Wake word no detectada; ignoro comando.")
            return

        response = self.owner.handle_voice_or_text_command(normalized or recognized)
        if response:
            print(f"[Asistente] {response}")
            if self.owner.voice_response_enabled:
                self.speak(response)

    def start_listening(self):
        self.owner.set_listening()

        if not self._ensure_voice_stack():
            self.owner.root.after(1200, self.owner.set_walking)
            return

        if self.owner.listening_thread and self.owner.listening_thread.is_alive():
            return

        self.owner.listening_thread = threading.Thread(target=self.listen_worker, daemon=True)
        self.owner.listening_thread.start()

    def listen_worker(self):
        recognizer = self.sr_module.Recognizer()

        try:
            with self.sr_module.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=4)

            text = recognizer.recognize_google(audio, language="es-ES")
            self._process_recognized_text(text)
        except Exception as error:
            print(f"[Escucha] {error}")
        finally:
            self.owner.ui_queue.put(("set_state", "walking"))

    def start_continuous_listening(self):
        self.owner.set_listening()

        if not self._ensure_voice_stack():
            self.owner.voice_realtime_enabled = False
            self.owner.save_assistant_config()
            self.owner.root.after(1200, self.owner.set_walking)
            return False

        if self.continuous_thread and self.continuous_thread.is_alive():
            self.owner.voice_realtime_enabled = True
            self.owner.save_assistant_config()
            return True

        self.continuous_stop_event.clear()
        self.continuous_thread = threading.Thread(target=self._continuous_worker, daemon=True)
        self.continuous_thread.start()
        self.owner.voice_realtime_enabled = True
        self.owner.save_assistant_config()
        return True

    def stop_continuous_listening(self):
        self.continuous_stop_event.set()
        self.owner.voice_realtime_enabled = False
        self.owner.save_assistant_config()
        self.owner.ui_queue.put(("set_state", "walking"))
        return True

    def _continuous_worker(self):
        recognizer = self.sr_module.Recognizer()
        wait_timeout = max(1, int(getattr(self.owner, "voice_phrase_timeout_seconds", 2)))
        phrase_limit = max(2, int(getattr(self.owner, "voice_phrase_max_seconds", 5)))

        try:
            with self.sr_module.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                while not self.continuous_stop_event.is_set() and not self.owner.is_destroying:
                    try:
                        audio = recognizer.listen(source, timeout=wait_timeout, phrase_time_limit=phrase_limit)
                        text = recognizer.recognize_google(audio, language="es-ES")
                        self._process_recognized_text(text)
                    except Exception:
                        # Mantiene escucha continua aunque una iteracion falle.
                        pass

                    time.sleep(0.08)
        except Exception as error:
            print(f"[Escucha continua] {error}")
        finally:
            self.owner.voice_realtime_enabled = False
            self.owner.save_assistant_config()
            self.owner.ui_queue.put(("set_state", "walking"))

    def speak(self, text):
        if not self.voice_available or self.tts_module is None:
            return
        try:
            engine = self.tts_module.init()
            engine.setProperty("rate", 180)
            engine.say(text)
            engine.runAndWait()
        except Exception as error:
            print(f"[Voz] {error}")
