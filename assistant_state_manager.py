import json
import time


class PetStateManager:
    def __init__(self, pet):
        self.pet = pet

    def get_session_runtime_seconds(self):
        return max(0, int(time.time() - self.pet.session_started_at))

    def format_seconds(self, total_seconds):
        total_seconds = max(0, int(total_seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def load_assistant_config(self):
        data = self.pet.config_store.load(self.pet.assistant_config_file)
        if not data:
            return

        wake = str(data.get("wake_word", self.pet.voice_wake_word)).strip().lower()
        if wake:
            self.pet.voice_wake_word = wake

        self.pet.require_wake_word = bool(data.get("require_wake_word", self.pet.require_wake_word))

        voice_realtime_cfg = data.get("voice_realtime_enabled")
        if voice_realtime_cfg is not None:
            self.pet.voice_realtime_enabled = bool(voice_realtime_cfg)

        voice_response_cfg = data.get("voice_response_enabled")
        if voice_response_cfg is not None:
            self.pet.voice_response_enabled = bool(voice_response_cfg)

        timeout_cfg = data.get("voice_phrase_timeout_seconds")
        if timeout_cfg is not None:
            try:
                self.pet.voice_phrase_timeout_seconds = max(1, int(timeout_cfg))
            except Exception:
                pass

        max_phrase_cfg = data.get("voice_phrase_max_seconds")
        if max_phrase_cfg is not None:
            try:
                self.pet.voice_phrase_max_seconds = max(2, int(max_phrase_cfg))
            except Exception:
                pass

        level = str(data.get("permission_level", self.pet.permission_level)).strip().lower()
        if level in self.pet.permission_levels:
            self.pet.permission_level = level

        llm_enabled_cfg = data.get("llm_enabled")
        if llm_enabled_cfg is not None:
            self.pet.llm_enabled = bool(llm_enabled_cfg)

        llm_provider_cfg = str(data.get("llm_provider", self.pet.llm_provider)).strip().lower()
        if llm_provider_cfg in self.pet.llm_providers:
            self.pet.llm_provider = llm_provider_cfg

        llm_model_cfg = str(data.get("llm_model", self.pet.llm_model)).strip()
        if llm_model_cfg:
            self.pet.llm_model = llm_model_cfg

        llm_endpoint_cfg = str(data.get("llm_endpoint", self.pet.llm_endpoint)).strip()
        if llm_endpoint_cfg:
            self.pet.llm_endpoint = llm_endpoint_cfg

        llm_offline_only_cfg = data.get("llm_offline_only")
        if llm_offline_only_cfg is not None:
            self.pet.llm_offline_only = bool(llm_offline_only_cfg)

        automation_cfg = data.get("functional_automation_enabled")
        if automation_cfg is not None:
            self.pet.functional_automation_enabled = bool(automation_cfg)

        companion_mode_cfg = data.get("companion_mode_enabled")
        if companion_mode_cfg is not None:
            self.pet.companion_mode_enabled = bool(companion_mode_cfg)

        auto_open_chat_cfg = data.get("auto_open_chat_on_context")
        if auto_open_chat_cfg is not None:
            self.pet.auto_open_chat_on_context = bool(auto_open_chat_cfg)

        proactive_research_cfg = data.get("proactive_research_enabled")
        if proactive_research_cfg is not None:
            self.pet.proactive_research_enabled = bool(proactive_research_cfg)

        browser_context_enabled_cfg = data.get("browser_context_server_enabled")
        if browser_context_enabled_cfg is not None:
            self.pet.browser_context_server_enabled = bool(browser_context_enabled_cfg)

        browser_context_port_cfg = data.get("browser_context_port")
        if browser_context_port_cfg is not None:
            try:
                self.pet.browser_context_port = max(1024, min(65535, int(browser_context_port_cfg)))
            except Exception:
                pass

        pet_name_cfg = str(data.get("pet_name", self.pet.pet_name)).strip()
        if pet_name_cfg:
            self.pet.pet_name = pet_name_cfg[:40]

        user_name_cfg = str(data.get("user_name_memory", self.pet.user_name_memory)).strip()
        self.pet.user_name_memory = user_name_cfg[:40]

        notes_cfg = data.get("pet_memory_notes", self.pet.pet_memory_notes)
        if isinstance(notes_cfg, list):
            cleaned_notes = []
            for note in notes_cfg:
                text = str(note).strip()
                if text:
                    cleaned_notes.append(text[:120])
            self.pet.pet_memory_notes = cleaned_notes[-20:]

        music_cfg = data.get("music_memory", self.pet.music_memory)
        if isinstance(music_cfg, list):
            cleaned_music = []
            for item in music_cfg:
                if not isinstance(item, dict):
                    continue
                query = str(item.get("query", "")).strip()[:120]
                if not query:
                    continue
                source = str(item.get("source", "youtube_music")).strip()[:30] or "youtube_music"
                lyrics = str(item.get("lyrics_snippet", "")).strip()[:800]
                micro_snippet = str(item.get("micro_snippet", "")).strip()[:180]
                transcription_source = str(item.get("transcription_source", "none")).strip()[:20] or "none"
                raw_concepts = item.get("concepts", [])
                concepts = []
                if isinstance(raw_concepts, list):
                    for concept in raw_concepts:
                        token = str(concept).strip().lower()[:24]
                        if token and token not in concepts:
                            concepts.append(token)
                try:
                    timestamp = int(item.get("timestamp", int(time.time())))
                except Exception:
                    timestamp = int(time.time())
                cleaned_music.append(
                    {
                        "timestamp": timestamp,
                        "query": query,
                        "source": source,
                        "lyrics_snippet": lyrics,
                        "micro_snippet": micro_snippet,
                        "transcription_source": transcription_source,
                        "concepts": concepts[:8],
                    }
                )
            self.pet.music_memory = cleaned_music[-40:]

        concept_cfg = data.get("music_personality_concepts", self.pet.music_personality_concepts)
        if isinstance(concept_cfg, list):
            normalized = []
            for item in concept_cfg:
                token = str(item).strip().lower()[:24]
                if token and token not in normalized:
                    normalized.append(token)
            self.pet.music_personality_concepts = normalized[-24:]

        queue_cfg = data.get("music_queue", self.pet.music_queue)
        if isinstance(queue_cfg, list):
            normalized_queue = []
            for item in queue_cfg:
                song = str(item).strip()[:120]
                if song:
                    normalized_queue.append(song)
            self.pet.music_queue = normalized_queue[-25:]

        music_active_cfg = data.get("music_session_active")
        if music_active_cfg is not None:
            self.pet.music_session_active = bool(music_active_cfg)

        current_song_cfg = str(data.get("music_current_song", self.pet.music_current_song)).strip()
        self.pet.music_current_song = current_song_cfg[:120]

        transcript_cfg = data.get("chat_transcript", self.pet.chat_transcript)
        if isinstance(transcript_cfg, list):
            cleaned_transcript = []
            for item in transcript_cfg:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                speaker = str(item[0]).strip()[:24]
                message = str(item[1]).strip()[:280]
                if speaker and message:
                    cleaned_transcript.append((speaker, message))
            if cleaned_transcript:
                self.pet.chat_transcript = cleaned_transcript[-120:]

        interest_cfg = data.get("interest_profile", self.pet.interest_profile)
        if isinstance(interest_cfg, list):
            normalized_interests = []
            for item in interest_cfg:
                if not isinstance(item, dict):
                    continue
                topic = str(item.get("topic", "")).strip()[:60]
                if not topic:
                    continue
                try:
                    score = float(item.get("score", 0.0))
                except Exception:
                    score = 0.0
                normalized_interests.append({"topic": topic, "score": max(0.0, min(25.0, score))})
            self.pet.interest_profile = normalized_interests[-40:]

        knowledge_cfg = data.get("background_knowledge", self.pet.background_knowledge)
        if isinstance(knowledge_cfg, list):
            normalized_knowledge = []
            for item in knowledge_cfg:
                if not isinstance(item, dict):
                    continue
                topic = str(item.get("topic", "")).strip()[:70]
                summary = str(item.get("summary", "")).strip()[:420]
                if not topic or not summary:
                    continue
                try:
                    timestamp = int(item.get("timestamp", int(time.time())))
                except Exception:
                    timestamp = int(time.time())
                normalized_knowledge.append({"topic": topic, "summary": summary, "timestamp": timestamp})
            self.pet.background_knowledge = normalized_knowledge[-40:]

        checkins_cfg = data.get("emotional_checkins", self.pet.emotional_checkins)
        if isinstance(checkins_cfg, list):
            normalized_checkins = []
            for item in checkins_cfg:
                if not isinstance(item, dict):
                    continue
                summary = str(item.get("summary", "")).strip()[:180]
                context = str(item.get("context", "")).strip()[:100]
                if not summary:
                    continue
                try:
                    timestamp = int(item.get("timestamp", int(time.time())))
                except Exception:
                    timestamp = int(time.time())
                normalized_checkins.append({"summary": summary, "context": context, "timestamp": timestamp})
            self.pet.emotional_checkins = normalized_checkins[-30:]

    def save_assistant_config(self):
        payload = {
            "wake_word": self.pet.voice_wake_word,
            "require_wake_word": self.pet.require_wake_word,
            "voice_realtime_enabled": self.pet.voice_realtime_enabled,
            "voice_response_enabled": self.pet.voice_response_enabled,
            "voice_phrase_timeout_seconds": self.pet.voice_phrase_timeout_seconds,
            "voice_phrase_max_seconds": self.pet.voice_phrase_max_seconds,
            "permission_level": self.pet.permission_level,
            "llm_enabled": self.pet.llm_enabled,
            "llm_provider": self.pet.llm_provider,
            "llm_model": self.pet.llm_model,
            "llm_endpoint": self.pet.llm_endpoint,
            "llm_offline_only": self.pet.llm_offline_only,
            "functional_automation_enabled": self.pet.functional_automation_enabled,
            "companion_mode_enabled": self.pet.companion_mode_enabled,
            "auto_open_chat_on_context": self.pet.auto_open_chat_on_context,
            "proactive_research_enabled": self.pet.proactive_research_enabled,
            "browser_context_server_enabled": self.pet.browser_context_server_enabled,
            "browser_context_port": self.pet.browser_context_port,
            "pet_name": self.pet.pet_name,
            "user_name_memory": self.pet.user_name_memory,
            "pet_memory_notes": self.pet.pet_memory_notes[-20:],
            "music_memory": self.pet.music_memory[-40:],
            "music_personality_concepts": self.pet.music_personality_concepts[-24:],
            "music_queue": self.pet.music_queue[-25:],
            "music_session_active": self.pet.music_session_active,
            "music_current_song": self.pet.music_current_song,
            "chat_transcript": self.pet.chat_transcript[-120:],
            "interest_profile": self.pet.interest_profile[-40:],
            "background_knowledge": self.pet.background_knowledge[-40:],
            "emotional_checkins": self.pet.emotional_checkins[-30:],
        }
        self.pet.config_store.save(self.pet.assistant_config_file, payload)

    def save_pet_state(self):
        try:
            self.pet.stats["total_runtime_seconds"] += self.get_session_runtime_seconds()
            self.pet.session_started_at = time.time()
            self.pet.stats["saves"] += 1

            data = {
                "version": 1,
                "x": int(self.pet.x),
                "y": int(self.pet.y),
                "state": self.pet.state,
                "style": self.pet.current_style,
                "mode": self.pet.execution_mode,
                "personality": self.pet.personality_name,
                "sandbox_mode": self.pet.sandbox_mode,
                "needs": self.pet.needs,
                "stats": self.pet.stats,
                "blocks": [],
            }
            self.pet.save_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"[Save] Estado guardado en {self.pet.save_file.name}")
        except Exception as error:
            print(f"[Save] Error guardando estado: {error}")

    def load_pet_state(self, quiet=False):
        if not self.pet.save_file.exists():
            if not quiet:
                print("[Load] No existe archivo de guardado.")
            return

        try:
            data = json.loads(self.pet.save_file.read_text(encoding="utf-8"))

            style = data.get("style", self.pet.current_style)
            if style in self.pet.available_styles and style != self.pet.current_style:
                self.pet.switch_style(style)

            self.pet.apply_personality(data.get("personality", self.pet.personality_name))
            self.pet.sandbox_mode = bool(data.get("sandbox_mode", self.pet.sandbox_mode))

            loaded_needs = data.get("needs", {})
            for key in self.pet.needs:
                if key in loaded_needs:
                    self.pet.needs[key] = self.pet.clamp_need(loaded_needs[key])

            loaded_stats = data.get("stats", {})
            for key in self.pet.stats:
                if key in loaded_stats:
                    self.pet.stats[key] = max(0, int(loaded_stats[key]))

            mode = data.get("mode", self.pet.execution_mode)
            if mode == "platform":
                self.pet.set_mode_platform()
            else:
                self.pet.set_mode_free()

            sprite_width, sprite_height = self.pet.get_walking_sprite_size()
            screen_width = self.pet.root.winfo_screenwidth()
            screen_height = self.pet.root.winfo_screenheight()
            self.pet.x = max(0, min(screen_width - sprite_width, int(data.get("x", self.pet.x))))
            self.pet.y = max(0, min(screen_height - sprite_height, int(data.get("y", self.pet.y))))
            self.pet.base_y = self.pet.y

            self.pet.clear_blocks()

            loaded_state = data.get("state", "walking")
            if loaded_state in ("walking", "idle", "listening", "jump", "dead"):
                self.pet.state = loaded_state
            else:
                self.pet.state = "walking"

            self.pet.root.geometry(f"+{self.pet.x}+{self.pet.y}")
            self.pet.path_nodes.clear()
            self.pet.last_path_target = None
            self.pet.stats["loads"] += 1
            self.pet.session_started_at = time.time()
            self.pet.update_hud()

            if not quiet:
                print(f"[Load] Estado cargado desde {self.pet.save_file.name}")
        except Exception as error:
            print(f"[Load] Error cargando estado: {error}")
