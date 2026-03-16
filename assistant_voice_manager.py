import threading


class VoiceManager:
    def __init__(self, owner, voice_available, sr_module=None, tts_module=None):
        self.owner = owner
        self.voice_available = bool(voice_available)
        self.sr_module = sr_module
        self.tts_module = tts_module

    def start_listening(self):
        self.owner.set_listening()

        if not self.voice_available or self.sr_module is None:
            if not self.owner.voice_warning_shown:
                print("[Aviso] speech_recognition/pyttsx3 no disponibles en el entorno.")
                self.owner.voice_warning_shown = True
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

            text = recognizer.recognize_google(audio, language="es-ES").lower()
            print(f"[Escuchado] {text}")
            normalized = self.owner.strip_wake_word(text)
            if self.owner.require_wake_word and not normalized:
                print("[Asistente] Wake word no detectada; ignoro comando.")
                return

            response = self.owner.handle_voice_or_text_command(normalized or text)
            if response:
                print(f"[Asistente] {response}")
                self.speak(response)
        except Exception as error:
            print(f"[Escucha] {error}")
        finally:
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
