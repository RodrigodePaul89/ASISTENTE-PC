class PetIdentityManager:
    def __init__(self, owner):
        self.owner = owner

    def build_pet_identity_system_prompt(self):
        user_name = self.owner.user_name_memory.strip() or "usuario"
        memory_lines = self.owner.pet_memory_notes[-6:]
        memory_block = "\n".join(f"- {item}" for item in memory_lines) if memory_lines else "- (sin notas aun)"
        emotional_notes = list(getattr(self.owner, "emotional_checkins", []))[-5:]
        if emotional_notes:
            emotional_block = "\n".join(
                f"- {str(item.get('summary', '')).strip()[:120]}" for item in emotional_notes if str(item.get("summary", "")).strip()
            )
            if not emotional_block.strip():
                emotional_block = "- (sin check-ins recientes)"
        else:
            emotional_block = "- (sin check-ins recientes)"

        interest_profile = list(getattr(self.owner, "interest_profile", []))
        if interest_profile:
            ranked = sorted(interest_profile, key=lambda item: (-float(item.get("score", 0.0)), str(item.get("topic", ""))))
            interest_block = "\n".join(
                f"- {str(item.get('topic', '')).strip()} (afinidad: {float(item.get('score', 0.0)):.1f})"
                for item in ranked[:8]
                if str(item.get("topic", "")).strip()
            )
            if not interest_block.strip():
                interest_block = "- (sin intereses detectados)"
        else:
            interest_block = "- (sin intereses detectados)"

        knowledge_items = list(getattr(self.owner, "background_knowledge", []))[-6:]
        if knowledge_items:
            knowledge_block = "\n".join(
                f"- {str(item.get('topic', '')).strip()}: {str(item.get('summary', '')).strip()[:170]}"
                for item in knowledge_items
                if str(item.get("topic", "")).strip() and str(item.get("summary", "")).strip()
            )
            if not knowledge_block.strip():
                knowledge_block = "- (sin conocimiento adicional aun)"
        else:
            knowledge_block = "- (sin conocimiento adicional aun)"

        songs = self.owner.music_memory[-5:]
        concept_profile = list(getattr(self.owner, "music_personality_concepts", []))[-12:]
        if songs:
            song_lines = []
            for item in songs:
                title = str(item.get("query", "")).strip()
                concepts = item.get("concepts", [])
                if isinstance(concepts, list) and concepts:
                    song_lines.append(f"- {title} | conceptos: {', '.join(concepts[:4])}")
                else:
                    song_lines.append(f"- {title}")
            song_block = "\n".join(song_lines)
        else:
            song_block = "- (sin canciones aun)"

        concept_block = ", ".join(concept_profile) if concept_profile else "(sin conceptos musicales aun)"
        companion_enabled = bool(getattr(self.owner, "companion_mode_enabled", True))
        companion_instructions = (
            "Tu rol principal es ser una companera de apoyo cotidiano: afectuosa, cercana, paciente y protectora. "
            "Valida emociones, ayuda a ordenar ideas y propone pasos pequenos, realistas y accionables. "
            "Puedes dar retroalimentacion honesta y directa cuando ayude, pero nunca con insultos ni humillacion. "
            "No des diagnosticos clinicos ni pautas de medicacion personalizada. "
            "Si te piden esos temas, ofrece psicoeducacion general y sugiere apoyo profesional. "
        ) if companion_enabled else "Mantente en modo asistente general, clara y util. "

        return (
            f"Tu nombre es {self.owner.pet_name}. "
            "Eres la mascota asistente de escritorio de esta app. "
            "Habla siempre en primera persona (yo/me/mi), nunca como si fueras una tercera persona. "
            "Si te hablan directamente, asume que te hablan a ti, la mascota. "
            "Actua como una mascota amigable y servicial. "
            f"{companion_instructions}"
            "Ten pensamiento propio, pero no seas creativa al inventar acciones del sistema que no puedas ejecutar. "
            f"El usuario principal se llama {user_name}. "
            "Mantente breve, clara y util; no inventes acciones del sistema que no puedas ejecutar. "
            "Memoria actual de la mascota:\n"
            f"{memory_block}\n"
            "Check-ins emocionales recientes:\n"
            f"{emotional_block}\n"
            "Intereses detectados del usuario:\n"
            f"{interest_block}\n"
            "Conocimiento tematico aprendido:\n"
            f"{knowledge_block}\n"
            "Memoria musical reciente:\n"
            f"{song_block}\n"
            "Perfil musical resumido (conceptos): "
            f"{concept_block}"
        )

    def format_pet_memory(self):
        lines = [f"Nombre de la mascota: {self.owner.pet_name}"]
        if self.owner.user_name_memory:
            lines.append(f"Nombre del usuario: {self.owner.user_name_memory}")
        else:
            lines.append("Nombre del usuario: (sin definir)")

        if self.owner.pet_memory_notes:
            lines.append("Recuerdos:")
            for note in self.owner.pet_memory_notes[-8:]:
                lines.append(f"- {note}")
        else:
            lines.append("Recuerdos: (vacio)")

        return "\n".join(lines)

    def format_music_memory(self):
        songs = self.owner.music_memory
        if not songs:
            return "Memoria musical: (vacia)"

        lines = ["Memoria musical reciente:"]
        for item in songs[-8:]:
            query = str(item.get("query", "")).strip() or "cancion"
            source = str(item.get("source", "youtube_music")).strip() or "youtube_music"
            lyric = str(item.get("lyrics_snippet", "")).strip()
            micro = str(item.get("micro_snippet", "")).strip()
            source = str(item.get("transcription_source", "none")).strip()
            concepts = item.get("concepts", [])
            lines.append(f"- {query} [{source}]")
            if isinstance(concepts, list) and concepts:
                lines.append(f"  conceptos: {', '.join(concepts[:6])}")
            elif lyric:
                lines.append(f"  letra guardada: {lyric[:100]}")
            if micro:
                lines.append(f"  escucha breve ({source}): {micro[:90]}")
        profile = list(getattr(self.owner, "music_personality_concepts", []))[-12:]
        if profile:
            lines.append("Perfil musical resumido: " + ", ".join(profile))
        return "\n".join(lines)
