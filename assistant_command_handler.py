import random
import re
import time
from difflib import SequenceMatcher


class AssistantCommandHandler:
    def __init__(self, owner):
        self.owner = owner

    def _match(self, command, *phrases, threshold=0.84):
        return self.owner.text_parser.fuzzy_contains(command, phrases, threshold=threshold)

    def _extract_after_markers(self, raw_command, markers):
        raw = str(raw_command or "").strip()
        lowered = raw.lower()
        for marker in markers:
            index = lowered.find(marker)
            if index >= 0:
                return raw[index + len(marker) :].strip(" :,-")
        return ""

    def _extract_url_from_command(self, raw_command):
        command = str(raw_command or "").strip()
        if not command:
            return ""
        match = re.search(r"(https?://\S+|www\.\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?)", command)
        if not match:
            return ""
        return match.group(1).strip(" .,!?:;)")

    def _extract_rename_args(self, raw_command):
        normalized = self.owner.normalize_command_text(raw_command)
        if not normalized:
            return "", ""

        patterns = (
            r"(?:renombra|cambia nombre)\s+(.+?)\s+(?:a|por)\s+(.+)$",
            r"(?:pon(?:le)?\s+de\s+nombre)\s+(.+?)\s+(?:a|por)\s+(.+)$",
            r"(?:rename)\s+(.+?)\s+(?:to)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            source = self.owner.sanitize_folder_name(match.group(1).strip(" .,:;!?'\""))
            target = self.owner.sanitize_folder_name(match.group(2).strip(" .,:;!?'\""))
            return source, target

        return "", ""

    def _extract_move_args(self, raw_command):
        normalized = self.owner.normalize_command_text(raw_command)
        if not normalized:
            return "", ""

        match = re.search(r"(?:mueve|move|manda|lleva|pon)\s+(.+?)\s+(?:a|al|hacia|dentro de)\s+(.+)$", normalized)
        if not match:
            return "", ""

        item_name = self.owner.sanitize_folder_name(match.group(1).strip(" .,:;!?'\""))
        target_folder = self.owner.sanitize_folder_name(match.group(2).strip(" .,:;!?'\""))
        return item_name, target_folder

    def _extract_reminder_args(self, raw_command):
        normalized = self.owner.normalize_command_text(raw_command)
        if not normalized:
            return 0, ""

        pattern = re.search(
            r"(?:recordatorio|recu[eé]rdame|recuerdame)\s*(?:en)?\s*(\d+)\s*(segundos?|minutos?|horas?)\s*(.*)$",
            normalized,
        )
        if pattern:
            value = pattern.group(1)
            unit = pattern.group(2)
            message = pattern.group(3).strip(" .,:;!?") or "Recordatorio"
            seconds = self.owner.action_manager._parse_time_to_seconds(value, unit)
            return seconds, message

        # Forma alternativa: "recuérdame tomar agua en 10 minutos"
        pattern_alt = re.search(
            r"(?:recordatorio|recu[eé]rdame|recuerdame)\s+(.+?)\s+(?:en)\s+(\d+)\s*(segundos?|minutos?|horas?)$",
            normalized,
        )
        if not pattern_alt:
            return 0, ""

        message = pattern_alt.group(1).strip(" .,:;!?") or "Recordatorio"
        value = pattern_alt.group(2)
        unit = pattern_alt.group(3)
        seconds = self.owner.action_manager._parse_time_to_seconds(value, unit)
        return seconds, message

    def _extract_open_target(self, raw_command):
        markers = ("abre", "abrir", "abreme", "ábreme", "inicia", "ejecuta", "lanza", "abrime")
        target = self._extract_after_markers(raw_command, markers)
        return target.strip(" .,:;!?")

    def _extract_song_request(self, raw_command):
        raw = str(raw_command or "").strip()
        if not raw:
            return ""

        normalized = self.owner.normalize_command_text(raw)
        marker_patterns = (
            r"(?:pon(?:me)?\s+una\s+cancion\s+de)\s+(.+)$",
            r"(?:pon(?:me)?\s+una\s+cancion)\s+(.+)$",
            r"(?:pon\s+cancion\s+de)\s+(.+)$",
            r"(?:pon\s+cancion)\s+(.+)$",
            r"(?:reproduce)\s+(.+)$",
            r"(?:reproducir)\s+(.+)$",
        )
        for pattern in marker_patterns:
            match = re.search(pattern, normalized)
            if match:
                return match.group(1).strip(" .,:;!?")

        return ""

    def _handle_bang_music_command(self, raw_command):
        raw = str(raw_command or "").strip()
        if not raw.startswith("!"):
            return ""

        body = raw[1:].strip()
        if not body:
            return "Comando musical vacio. Usa !musichelp para ver ejemplos."

        lower = body.lower()
        if lower == "musichelp":
            return (
                "Comandos musicales disponibles:\n"
                "- !play <cancion> : busca y reproduce en segundo plano desde YouTube\n"
                "- !next <cancion> : agrega la cancion a la cola\n"
                "- !queue : muestra la cola actual\n"
                "- !exit : cierra sesion musical y limpia cola"
            )

        if lower == "exit":
            self.owner.exit_music_session()
            return "Sesion musical cerrada."

        if lower == "queue":
            queue = list(getattr(self.owner, "music_queue", []))
            if not queue:
                return "Cola musical vacia."
            return "Cola musical:\n- " + "\n- ".join(queue[:10])

        if lower.startswith("play "):
            if not self.owner.has_permission("media"):
                return "Tu nivel de permisos actual no permite controlar multimedia."
            query = body[5:].strip()
            if not query:
                return "Indica la cancion: !play nombre"
            ok, has_lyrics, title, _lyrics = self.owner.action_manager.play_song_on_youtube_music(query, auto=True)
            if not ok:
                detail = str(getattr(self.owner, "last_music_error_detail", "")).strip()
                if detail:
                    return (
                        "No pude reproducir esa cancion en segundo plano. "
                        f"Detalle tecnico: {detail}."
                    )
                return "No pude reproducir esa cancion en segundo plano. Verifica yt-dlp y backend local (pygame+winsound+ffmpeg)."
            final_title = title or query
            if has_lyrics:
                return f"Listo, ya esta sonando: {final_title}. Aprendi conceptos y una parte de la letra."
            return f"Listo, ya esta sonando: {final_title}. Aprendi conceptos principales de la cancion."

        if lower.startswith("next "):
            query = body[5:].strip()
            if not query:
                return "Indica la cancion: !next nombre"
            if self.owner.action_manager.queue_song_for_next(query):
                return f"Agregada a la cola: {query}."
            return "No pude agregar esa cancion a la cola."

        return "Comando musical no reconocido. Usa !musichelp."

    def _resolve_style_name(self, raw_command):
        available = list(getattr(self.owner, "available_styles", []))
        if not available:
            return ""

        normalized = self.owner.normalize_command_text(raw_command)
        markers = ("usar estilo", "cambiar estilo", "pon estilo", "estilo")
        candidate = ""
        for marker in markers:
            if normalized.startswith(marker):
                index = len(marker)
                candidate = normalized[index:].strip(" .,:;!?")
                break

        if not candidate:
            return ""

        for style in available:
            if self.owner.normalize_command_text(style) == candidate:
                return style

        best_style = ""
        best_ratio = 0.0
        for style in available:
            style_key = self.owner.normalize_command_text(style)
            if not style_key:
                continue
            ratio = SequenceMatcher(None, candidate, style_key).ratio()
            if candidate in style_key or style_key in candidate:
                ratio = max(ratio, 0.92)
            if ratio > best_ratio:
                best_ratio = ratio
                best_style = style

        if best_ratio >= 0.72:
            return best_style
        return ""

    def interpret_local_action(self, raw_command):
        if not self.owner.llm_enabled:
            return {}

        system_prompt = (
            "Eres un clasificador de intenciones para un asistente local de PC. "
            "Debes devolver solo JSON valido sin explicaciones. "
            "Acciones permitidas: create_folder, archive_item, media_next, media_prev, media_play_pause, "
            "mode_free, mode_platform, ollama_status, ollama_test, permission_query, permission_files, "
            "permission_full, llm_enable, llm_disable, llm_mode_local, llm_mode_cloud, set_model, open_app, open_website, none. "
            "Usa el formato exacto: {\"action\":\"...\",\"args\":{}}. "
            "Si el mensaje no pide una accion local concreta o faltan datos, responde {\"action\":\"none\",\"args\":{}}. "
            "No conviertas preguntas conversacionales o personales en acciones del sistema. "
            "Solo devuelve una accion si el usuario esta pidiendo claramente que ejecutes algo en el PC. "
            "Corrige espacios de mas, acentos, y errores leves de escritura. "
            "Para create_folder usa args.folder_name. Para archive_item usa args.item_name. Para set_model usa args.model. "
            "Para open_app usa args.app_name. Para open_website usa args.url."
        )

        response = self.owner.query_ollama_local_with_system(system_prompt, raw_command)
        parsed = self.owner.extract_json_object(response)
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def handle(self, text, _alias_expanded=False):
        raw_command = (text or "").strip()
        command = self.owner.normalize_command_text(raw_command)
        if not command:
            return "No escuche un comando claro."

        actions = self.owner.action_manager

        if actions.has_active_pending_action():
            if actions.is_affirmative_command(command):
                return actions.execute_pending_action()
            if actions.is_negative_command(command):
                description = self.owner.pending_action.get("description", "la accion pendiente")
                self.owner.pending_action = None
                return f"Cancelado: {description}."

        # Evita respuestas inesperadas cuando "no" llega sin una accion pendiente.
        if actions.is_negative_command(command):
            return "Entendido, no hare ningun cambio por ahora."

        # Comandos rapidos de musica por prefijo '!'.
        bang_result = self._handle_bang_music_command(raw_command)
        if bang_result:
            return bang_result

        # ---- MODO COMANDOS PRO: expansion de alias ----
        if not _alias_expanded:
            expanded = self.owner.alias_manager.expand(raw_command)
            if expanded and expanded.lower() != raw_command.lower():
                return self.handle(expanded, _alias_expanded=True)

        # ---- GESTION DE ALIAS PRO ----
        if self._match(command, "ver alias", "mis alias", "lista alias", "mostrar alias") or command.strip() == "alias":
            alias_list = self.owner.alias_manager.list_all()
            if not alias_list:
                return "No hay alias configurados."
            lines = ["Alias pro activos:"]
            for rec in alias_list:
                tmpl = rec["template"]
                trigger = rec["trigger"]
                desc = rec["description"]
                arg_hint = "+argumento" if "{arg}" in tmpl else "(sin argumento)"
                desc_part = f"  [{desc}]" if desc else ""
                lines.append(f"  {trigger} {arg_hint}  ->  {tmpl}{desc_part}")
            lines.append("")
            lines.append("Para agregar: nuevo alias nombre: plantilla  (usa {arg} para el argumento)")
            lines.append("Para borrar:  borrar alias nombre")
            lines.append("Ejemplo:      nuevo alias yt: abre youtube.com")
            return "\n".join(lines)

        _alias_add = re.search(
            r"(?:nuevo|agregar|crear)\s+alias\s+([a-z0-9_\u00e0-\u00fc]+)\s*:\s*(.+)$",
            command,
        )
        if _alias_add:
            a_trigger = _alias_add.group(1).strip()
            a_template = _alias_add.group(2).strip()
            if self.owner.alias_manager.add(a_trigger, a_template):
                arg_hint = "+argumento" if "{arg}" in a_template else ""
                return f"Alias '{a_trigger}' guardado. Ejemplo de uso: {a_trigger} {arg_hint}  ->  {a_template}"
            return "No pude guardar el alias. El nombre debe ser una sola palabra (letras o numeros)."

        _alias_del = re.search(
            r"(?:borrar|eliminar|quitar|remover)\s+alias\s+([a-z0-9_\u00e0-\u00fc]+)$",
            command,
        )
        if _alias_del:
            a_trigger = _alias_del.group(1).strip()
            if self.owner.alias_manager.remove(a_trigger):
                return f"Alias '{a_trigger}' eliminado."
            return f"No encontre el alias '{a_trigger}'. Escribe 'ver alias' para ver los disponibles."

        if self._match(command, "historial de acciones", "ultimas acciones", "ultimas tareas"):
            return actions.format_recent_actions()

        if self._match(command, "ver apps", "lista apps", "mostrar apps", "apps disponibles", "alias de apps"):
            return actions.format_registered_apps_summary()

        if self._match(command, "recargar apps", "recarga apps", "actualizar apps"):
            count = actions.reload_app_catalog()
            return f"Catalogo de apps recargado. Entradas disponibles: {count}."

        if self._match(command, "diagnostico funciones", "diagnostico de funciones", "estado de funciones", "que funciones tienes"):
            diagnostics = actions.get_capability_diagnostics()
            lines = ["Diagnostico de funciones activas:"]
            for area, capabilities in diagnostics.items():
                lines.append(f"- {area}: {', '.join(capabilities)}")
            lines.append("Prueba rapida: crea carpeta proyectos 2026 | abre chrome | recordatorio en 2 minutos tomar agua")
            return "\n".join(lines)

        if self._match(command, "limpiar chat", "borra chat", "borrar chat"):
            self.owner.chat_transcript = [("Mascota", "Chat local limpio. ¿En que te ayudo ahora?")]
            if self.owner.chat_history is not None and self.owner.chat_history.winfo_exists():
                self.owner.chat_history.config(state="normal")
                self.owner.chat_history.delete("1.0", "end")
                self.owner.chat_history.insert("end", "Mascota: Chat local limpio. ¿En que te ayudo ahora?\n")
                self.owner.chat_history.config(state="disabled")
            self.owner.save_assistant_config()
            return "Historial de chat limpiado."

        if command in {"salir", "cerrar chat", "salir chat"}:
            if self.owner.chat_window is not None and self.owner.chat_window.winfo_exists():
                self.owner.close_chat_bubble()
                return "Cierro el chat y vuelvo a caminar."
            return "No hay chat abierto en este momento."

        if self._match(command, "contexto del equipo", "cargar contexto del equipo", "conocer mi computadora"):
            return actions.get_computer_context_summary()

        if self._match(command, "que estoy haciendo", "que hay en pantalla", "contexto de pantalla"):
            title = actions.get_active_window_title()
            if not title:
                return "No pude leer la ventana activa en este momento."
            return f"Ventana activa detectada: {title}."

        if self._match(command, "estado contexto navegador", "estado brave extension", "estado extension brave"):
            enabled = "activo" if bool(getattr(self.owner, "browser_context_server_enabled", False)) else "inactivo"
            port = int(getattr(self.owner, "browser_context_port", 37655))
            return f"Servidor de contexto navegador: {enabled} en 127.0.0.1:{port}."

        if self._match(command, "activar contexto navegador", "activar extension navegador"):
            self.owner.browser_context_server_enabled = True
            self.owner.start_browser_context_server()
            self.owner.save_assistant_config()
            return f"Contexto de navegador activado en 127.0.0.1:{self.owner.browser_context_port}."

        if self._match(command, "desactivar contexto navegador", "desactivar extension navegador"):
            self.owner.browser_context_server_enabled = False
            self.owner.stop_browser_context_server()
            self.owner.save_assistant_config()
            return "Contexto de navegador desactivado."

        if self._match(command, "activar modo compania", "modo companera", "modo consejera"):
            self.owner.companion_mode_enabled = True
            self.owner.save_assistant_config()
            return "Modo compania activado. Sere mas cercana y proactiva en apoyo cotidiano."

        if self._match(command, "desactivar modo compania", "quitar modo companera", "modo asistente normal"):
            self.owner.companion_mode_enabled = False
            self.owner.save_assistant_config()
            return "Modo compania desactivado. Vuelvo a modo asistente general."

        if self._match(command, "activar burbuja automatica", "chat automatico", "abrir chat automatico"):
            self.owner.auto_open_chat_on_context = True
            self.owner.save_assistant_config()
            return "Burbuja automatica activada segun el contexto de pantalla."

        if self._match(command, "desactivar burbuja automatica", "quitar chat automatico"):
            self.owner.auto_open_chat_on_context = False
            self.owner.save_assistant_config()
            return "Burbuja automatica desactivada."

        if self._match(command, "activar investigacion en segundo plano", "activar consulta en segundo plano"):
            self.owner.proactive_research_enabled = True
            self.owner.save_assistant_config()
            return "Investigacion en segundo plano activada para temas detectados en tus ventanas."

        if self._match(command, "desactivar investigacion en segundo plano", "desactivar consulta en segundo plano"):
            self.owner.proactive_research_enabled = False
            self.owner.save_assistant_config()
            return "Investigacion en segundo plano desactivada."

        if self._match(command, "mostrar intereses", "perfil de intereses", "que intereses detectaste"):
            profile = list(getattr(self.owner, "interest_profile", []))
            if not profile:
                return "Aun no detecto intereses frecuentes."
            ranked = sorted(profile, key=lambda item: -float(item.get("score", 0.0)))
            lines = ["Intereses detectados:"]
            for item in ranked[:10]:
                lines.append(f"- {item.get('topic', 'tema')} (afinidad {float(item.get('score', 0.0)):.1f})")
            return "\n".join(lines)

        if self._match(command, "mostrar conocimiento", "que aprendiste sola", "memoria de conocimiento"):
            knowledge = list(getattr(self.owner, "background_knowledge", []))
            if not knowledge:
                return "Todavia no tengo conocimiento tematico aprendido en segundo plano."
            lines = ["Conocimiento tematico reciente:"]
            for item in knowledge[-8:]:
                topic = str(item.get("topic", "tema")).strip()
                summary = str(item.get("summary", "")).strip()
                if topic and summary:
                    lines.append(f"- {topic}: {summary[:140]}")
            return "\n".join(lines)

        if self._match(command, "estructura de mimi", "de que estas hecha", "como esta hecho tu codigo"):
            return actions.get_self_structure_summary()

        if command.startswith("buscar en codigo "):
            query = raw_command[raw_command.lower().find("buscar en codigo") + len("buscar en codigo ") :].strip()
            if not query:
                return "Dime que texto quieres buscar dentro del codigo."
            results = actions.search_project_code(query, limit=8)
            if not results:
                return "No encontre coincidencias en los archivos Python del proyecto."
            return "Coincidencias en codigo:\n- " + "\n- ".join(results)

        if self._match(command, "recomendacion casual", "dame recomendacion", "sugerencia casual"):
            self.owner.open_chat_bubble()
            tip = actions.build_casual_recommendation()
            self.owner.append_chat_message("Mimi", tip)
            return tip

        if self._match(command, "activar palabra clave"):
            self.owner.require_wake_word = True
            self.owner.save_assistant_config()
            return f"Palabra clave activada: {self.owner.voice_wake_word}."

        if self._match(command, "desactivar palabra clave"):
            self.owner.require_wake_word = False
            self.owner.save_assistant_config()
            return "Palabra clave desactivada temporalmente."

        if command.startswith("palabra clave "):
            new_wake = self.owner.sanitize_folder_name(raw_command[raw_command.lower().find("palabra clave") + len("palabra clave ") :]).lower()
            if not new_wake:
                return "No detecte una palabra clave valida."
            self.owner.voice_wake_word = new_wake
            self.owner.save_assistant_config()
            return f"Nueva palabra clave configurada: {self.owner.voice_wake_word}."

        if self._match(command, "permiso consulta"):
            self.owner.set_permission_level("query")
            return "Permiso cambiado a consulta."

        if self._match(command, "permiso archivos"):
            self.owner.set_permission_level("files")
            return "Permiso cambiado a archivos."

        if self._match(command, "permiso completo"):
            self.owner.set_permission_level("full")
            return "Permiso cambiado a completo."

        if self._match(command, "activar ia", "activar llm"):
            self.owner.llm_enabled = True
            self.owner.save_assistant_config()
            return "IA conversacional activada."

        if self._match(command, "desactivar ia", "desactivar llm"):
            self.owner.llm_enabled = False
            self.owner.save_assistant_config()
            return "IA conversacional desactivada."

        if self._match(command, "activar automatizaciones", "activar funciones automaticas"):
            self.owner.functional_automation_enabled = True
            self.owner.save_assistant_config()
            return "Automatizaciones funcionales activadas."

        if self._match(command, "desactivar automatizaciones", "quitar automatizaciones"):
            self.owner.functional_automation_enabled = False
            self.owner.save_assistant_config()
            return "Automatizaciones funcionales desactivadas temporalmente."

        if self._match(command, "estado automatizaciones"):
            if self.owner.functional_automation_enabled:
                return "Automatizaciones funcionales: activadas."
            return "Automatizaciones funcionales: desactivadas."

        if self._match(command, "activar voz continua", "activar voz en tiempo real", "modo voz continua", "modo manos libres"):
            self.owner.start_realtime_listening()
            return "Voz continua activada. Di la palabra clave seguida del comando."

        if self._match(command, "desactivar voz continua", "quitar voz continua", "apagar voz en tiempo real"):
            self.owner.stop_realtime_listening()
            return "Voz continua desactivada."

        if self._match(command, "activar respuestas por voz", "hablame", "responde por voz"):
            self.owner.voice_response_enabled = True
            self.owner.save_assistant_config()
            return "Respuestas por voz activadas."

        if self._match(command, "desactivar respuestas por voz", "no hables", "solo texto"):
            self.owner.voice_response_enabled = False
            self.owner.save_assistant_config()
            return "Respuestas por voz desactivadas."

        if self._match(command, "estado de voz", "estado voz", "como esta la voz"):
            realtime = "activa" if self.owner.voice_realtime_enabled else "desactivada"
            spoken = "activadas" if self.owner.voice_response_enabled else "desactivadas"
            wake = "obligatoria" if self.owner.require_wake_word else "opcional"
            return (
                f"Voz continua: {realtime}. Respuestas por voz: {spoken}. "
                f"Palabra clave: {wake} ({self.owner.voice_wake_word})."
            )

        if self._match(command, "ver estilos", "lista estilos", "mostrar estilos", "estilos disponibles"):
            styles = list(getattr(self.owner, "available_styles", []))
            if not styles:
                return "No encontre estilos visuales disponibles en la carpeta img."
            return "Estilos disponibles: " + ", ".join(styles)

        if self._match(command, "recargar estilos", "actualizar estilos", "refrescar estilos"):
            current = self.owner.current_style
            self.owner.available_styles = self.owner.discover_available_styles()
            if current not in self.owner.available_styles and self.owner.available_styles:
                self.owner.switch_style(self.owner.available_styles[0])
            self.owner.save_assistant_config()
            return "Estilos recargados. Usa: usar estilo <nombre>."

        if command.startswith("usar estilo") or command.startswith("cambiar estilo") or command.startswith("estilo "):
            selected_style = self._resolve_style_name(raw_command)
            if not selected_style:
                return "No detecte un estilo valido. Di: ver estilos para consultar opciones."
            self.owner.switch_style(selected_style)
            self.owner.save_assistant_config()
            return f"Estilo visual actualizado a {self.owner.current_style}."

        if command.startswith("tu nombre es ") or command.startswith("te llamas "):
            raw_lower = raw_command.lower()
            marker = "tu nombre es " if raw_lower.startswith("tu nombre es ") else "te llamas "
            new_name = raw_command[len(marker) :].strip()
            new_name = self.owner.sanitize_folder_name(new_name)
            if not new_name:
                return "No detecte un nombre valido para mi."
            self.owner.pet_name = new_name[:40]
            self.owner.save_assistant_config()
            self.owner.refresh_chat_header_mode()
            return f"Listo. Mi nuevo nombre es {self.owner.pet_name}."

        if command.startswith("mi nombre es "):
            user_name = raw_command[len("mi nombre es ") :].strip()
            user_name = self.owner.sanitize_folder_name(user_name)
            if not user_name:
                return "No detecte tu nombre con claridad."
            self.owner.user_name_memory = user_name[:40]
            self.owner.save_assistant_config()
            return f"Entendido, te recordare como {self.owner.user_name_memory}."

        if command.startswith("recuerda que "):
            memory_note = raw_command[len("recuerda que ") :].strip()
            if not memory_note:
                return "No detecte el recuerdo que quieres guardar."
            self.owner.pet_memory_notes.append(memory_note[:120])
            self.owner.pet_memory_notes = self.owner.pet_memory_notes[-20:]
            self.owner.save_assistant_config()
            return "Listo, lo guarde en mi memoria."

        if self._match(command, "mostrar memoria", "que recuerdas", "que recuerdas de mi"):
            return self.owner.format_pet_memory()

        if self._match(command, "borrar memoria", "limpiar memoria"):
            self.owner.pet_memory_notes = []
            self.owner.save_assistant_config()
            return "He limpiado mis recuerdos guardados."

        if self._match(command, "modo local", "ia local"):
            self.owner.activate_local_ai_mode()
            return "Modo local activado con Ollama en 127.0.0.1."

        if self._match(command, "modo nube", "ia en nube", "ia + internet"):
            self.owner.activate_cloud_ai_mode()
            if self.owner.llm_enabled:
                return "Modo nube activado."
            return "Modo nube configurado, pero falta OPENAI_API_KEY para usarlo."

        if command.startswith("modelo ia "):
            new_model = raw_command[raw_command.lower().find("modelo ia") + len("modelo ia ") :].strip()
            if not new_model:
                return "No detecte un nombre de modelo valido."
            self.owner.llm_model = new_model
            self.owner.save_assistant_config()
            return f"Modelo IA actualizado a {self.owner.llm_model}."

        if self._match(command, "estado ia local", "estado ollama"):
            ok, model_count = self.owner.check_ollama_health()
            if not ok:
                return "No pude conectar con Ollama en local. Revisa que el servicio este activo."
            return f"Ollama local activo. Modelos detectados: {model_count}. Modelo seleccionado: {self.owner.llm_model}."

        if self._match(command, "probar ia local"):
            ok, model_count = self.owner.check_ollama_health()
            if not ok:
                return "No pude conectar con Ollama local para la prueba."
            if model_count <= 0:
                return "Ollama esta activo, pero no hay modelos descargados."
            test_answer = self.owner.query_ollama_local_with_system(
                "Responde exactamente con OK_LOCAL. No anadas texto adicional.",
                "Responde solo con: OK_LOCAL",
            )
            if test_answer:
                compact = " ".join(test_answer.split())
                return f"Prueba local completada. Respuesta del modelo: {compact}"
            return "Ollama responde, pero el modelo no devolvio contenido en esta prueba."

        if self._match(command, "que hora", "hora es"):
            now = time.strftime("%H:%M")
            return f"Son las {now}."

        if self._match(command, "que fecha", "que dia es", "fecha de hoy"):
            return f"Hoy es {time.strftime('%d/%m/%Y')}."

        if self._match(command, "como estas", "como te sientes"):
            avg_needs = sum(self.owner.needs.values()) / max(1, len(self.owner.needs))
            if avg_needs >= 70:
                return "Estoy muy bien y lista para ayudarte."
            if avg_needs >= 45:
                return "Estoy estable, puedo seguir trabajando."
            return "Estoy algo cansada, pero aun puedo ayudar."

        if self._match(command, "quien eres", "que eres"):
            return f"Soy {self.owner.pet_name}, tu mascota asistente de PC."

        structure_folders = self.owner.text_parser.extract_folder_structure_from_command(raw_command)
        if structure_folders:
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite crear carpetas."
            created = actions.create_folder_structure(structure_folders)
            if not created:
                return "No pude crear nuevas carpetas con esa estructura, revisa si ya existen."
            return f"Estructura creada en escritorio: {', '.join(created)}."

        if command.startswith("crea carpeta "):
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite crear carpetas."
            folder_name = raw_command[raw_command.lower().find("crea carpeta") + len("crea carpeta ") :].strip()
            safe_folder_name = self.owner.sanitize_folder_name(folder_name)
            if not safe_folder_name:
                return "No detecte un nombre de carpeta valido."
            return actions.queue_pending_action(
                "create_folder",
                {"folder_name": safe_folder_name},
                f"crear la carpeta {safe_folder_name} en tu escritorio",
            )

        extracted_folder_name = self.owner.extract_folder_name_from_command(raw_command)
        if extracted_folder_name:
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite crear carpetas."
            return actions.queue_pending_action(
                "create_folder",
                {"folder_name": extracted_folder_name},
                f"crear la carpeta {extracted_folder_name} en tu escritorio",
            )

        if command.startswith("archiva ") or self._match(command, "archivar"):
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite archivar elementos."
            item_name = self._extract_after_markers(raw_command, ["archiva", "archivar"]) 
            safe_item_name = self.owner.sanitize_folder_name(item_name)
            if not safe_item_name:
                return "No detecte un elemento valido para archivar."
            return actions.queue_pending_action(
                "archive_item",
                {"item_name": safe_item_name},
                f"mover {safe_item_name} a la carpeta de archivado",
            )

        source_name, target_name = self._extract_rename_args(raw_command)
        if source_name and target_name:
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite renombrar elementos."
            return actions.queue_pending_action(
                "rename_item",
                {"source_name": source_name, "target_name": target_name},
                f"renombrar {source_name} a {target_name}",
            )

        move_item, move_target = self._extract_move_args(raw_command)
        if move_item and move_target:
            if not self.owner.has_permission("files"):
                return "Tu nivel de permisos actual no permite mover elementos."
            return actions.queue_pending_action(
                "move_item",
                {"item_name": move_item, "target_folder": move_target},
                f"mover {move_item} a la carpeta {move_target}",
            )

        if self._match(command, "elimina", "borra") and ("carpeta" in command or "archivo" in command):
            item_name = self._extract_after_markers(raw_command, ["elimina", "borra"])
            safe_item_name = self.owner.sanitize_folder_name(item_name)
            if not safe_item_name:
                return "No detecte un elemento valido para eliminar."
            return actions.queue_pending_action(
                "delete_item",
                {"item_name": safe_item_name},
                f"eliminar {safe_item_name} del escritorio",
            )

        if self._match(command, "buscar archivo", "buscar carpeta", "buscar en escritorio"):
            query = self._extract_after_markers(raw_command, ["buscar archivo", "buscar carpeta", "buscar en escritorio", "buscar"])
            matches = actions.search_desktop_items(query, limit=8)
            if not matches:
                return "No encontre coincidencias en el escritorio."
            return "Coincidencias en escritorio: " + ", ".join(matches)

        if self._match(command, "localizar archivo", "buscar en computadora", "buscar en mi pc", "buscar en el equipo"):
            query = self._extract_after_markers(raw_command, ["localizar archivo", "buscar en computadora", "buscar en mi pc", "buscar en el equipo", "buscar"])
            if not query:
                return "Dime que archivo o carpeta quieres localizar."
            matches = actions.search_computer_items(query, limit=10)
            if not matches:
                return "No encontre coincidencias en las carpetas principales del equipo."
            return "Coincidencias en equipo:\n- " + "\n- ".join(matches)

        if self._match(command, "crear nota", "nueva nota", "anota"):
            tail = self._extract_after_markers(raw_command, ["crear nota", "nueva nota", "anota"])
            note_title = self.owner.sanitize_folder_name(tail[:40]) if tail else "nota_rapida"
            note_content = tail if tail else "Nota creada por comando de voz/texto."
            note_file = actions.create_note(note_title, note_content)
            if not note_file:
                return "No pude crear la nota."
            return f"Nota creada en: {note_file}"

        reminder_seconds, reminder_message = self._extract_reminder_args(raw_command)
        if reminder_seconds > 0:
            if actions.create_reminder(reminder_seconds, reminder_message):
                return f"Recordatorio programado en {reminder_seconds} segundos: {reminder_message}."
            return "No pude crear el recordatorio."

        if self._match(command, "captura de pantalla", "tomar captura", "screenshot"):
            return actions.queue_pending_action(
                "take_screenshot",
                {"name": "captura"},
                "tomar una captura de pantalla",
            )

        if self._match(command, "limpiar escritorio", "ordenar escritorio"):
            moved = actions.run_desktop_cleanup()
            return f"Limpieza completada. Elementos movidos a archivado: {moved}."

        if self._match(command, "abre", "abrir", "abreme", "inicia", "ejecuta", "lanza", "navega", "ir a", threshold=0.78) and self._match(command, "www", "http", ".com", ".net", ".org", ".io", ".dev", threshold=0.75):
            url = self._extract_url_from_command(raw_command)
            if not url:
                return "No detecte una URL valida."
            return actions.queue_pending_action(
                "open_website",
                {"url": url},
                f"abrir el sitio {url}",
            )

        if self._match(command, "abre", "abrir", "abreme", "inicia", "ejecuta", "lanza", "abrime", threshold=0.78):
            app_name = self._extract_open_target(raw_command)
            if not app_name:
                return "No detecte que aplicacion abrir."
            return actions.queue_pending_action(
                "open_app",
                {"app_name": app_name},
                f"abrir la aplicacion {app_name}",
            )

        if self._match(command, "bloquea pc", "bloquear pc", "lock pc"):
            return actions.queue_pending_action(
                "system_control",
                {"operation": "lock"},
                "bloquear la sesion de Windows",
            )

        if self._match(command, "reinicia pc", "reiniciar pc"):
            return actions.queue_pending_action(
                "system_control",
                {"operation": "restart"},
                "reiniciar el equipo",
            )

        if self._match(command, "apaga pc", "apagar pc"):
            return actions.queue_pending_action(
                "system_control",
                {"operation": "shutdown"},
                "apagar el equipo",
            )

        if self._match(command, "siguiente cancion", "siguiente canción"):
            return "Para siguiente usa el boton 'Siguiente' del panel Mimi Music o agrega una cancion con !next <nombre>."

        if self._match(
            command,
            "pon una cancion",
            "ponme una cancion",
            "pon cancion",
            "reproduce",
            "reproducir",
            "poner musica",
        ):
            if not self.owner.has_permission("media"):
                return "Tu nivel de permisos actual no permite controlar multimedia."

            song_query = self._extract_song_request(raw_command)
            if not song_query:
                return "Dime el nombre de la cancion para reproducirla desde YouTube en segundo plano."

            ok, has_lyrics, title, _lyrics = actions.play_song_on_youtube_music(song_query, auto=True)
            if not ok:
                detail = str(getattr(self.owner, "last_music_error_detail", "")).strip()
                if detail:
                    return (
                        "No pude reproducir la cancion en segundo plano. "
                        f"Detalle tecnico: {detail}."
                    )
                return "No pude reproducir la cancion en segundo plano. Verifica yt-dlp y backend local (pygame+winsound+ffmpeg)."
            final_title = title or song_query
            if has_lyrics:
                return f"Listo, ya esta sonando: {final_title}. Guarde una parte de la letra en mi memoria."
            return f"Listo, ya esta sonando: {final_title}. Guarde la cancion en mi memoria musical."

        if self._match(command, "mostrar memoria musical", "memoria musical", "que canciones recuerdas"):
            return self.owner.format_music_memory()

        if self._match(command, "borrar memoria musical", "limpiar memoria musical"):
            self.owner.music_memory = []
            self.owner.save_assistant_config()
            return "Memoria musical limpiada."

        if self._match(command, "cancion anterior", "canción anterior"):
            return "La navegacion musical ahora se gestiona desde el panel Mimi Music."

        if self._match(command, "pausa musica", "pausar musica", "play pausa", "reanudar musica"):
            return "Usa el boton 'Pausa' del panel Mimi Music para pausar o reanudar."

        if self._match(command, "modo libre"):
            self.owner.set_mode_free()
            return "Modo libre activado."

        if self._match(command, "modo suelo"):
            self.owner.set_mode_platform()
            return "Modo suelo activado."

        if self._match(command, "persigue cursor", "sigue cursor"):
            self.owner.free_mood = "feliz"
            self.owner.next_free_mood_change_at = time.time() + random.uniform(*self.owner.free_mood_interval_range)
            return "De acuerdo, perseguire el cursor."

        if self._match(command, "huye cursor", "escapa cursor"):
            self.owner.free_mood = "brava"
            self.owner.next_free_mood_change_at = time.time() + random.uniform(*self.owner.free_mood_interval_range)
            return "Entendido, me alejare del cursor."

        if self._match(command, "ayuda", "que puedes hacer"):
            return (
                "Puedo crear estructura de carpetas, crear/mover/renombrar/eliminar en escritorio, "
                "buscar archivos, crear notas y recordatorios, abrir apps y sitios web, capturas, limpieza de escritorio, "
                "poner canciones en YouTube Music con memoria musical y comandos !play/!next/!exit, alternar IA local/nube, editar memoria y revisar estado de Ollama, "
                "activar voz continua y gestionar estilos visuales de la mascota. "
                "Tambien puedo usar modo compania, abrir chat segun contexto de pantalla, investigar temas en segundo plano, "
                "mostrar perfil de intereses y explicar mi estructura de codigo. "
                "Modo pro: escribe 'ver alias' para shortcuts rapidos personalizados."
            )

        if self._match(command, "hola"):
            return f"Hola, soy {self.owner.pet_name}. Estoy lista para asistirte."

        interpreted_action = self.interpret_local_action(raw_command) if actions.looks_like_system_request(command) else {}
        action_name = str(interpreted_action.get("action", "")).strip().lower()
        action_args = interpreted_action.get("args", {})

        if action_name == "create_folder":
            folder_name = self.owner.sanitize_folder_name(action_args.get("folder_name", ""))
            if folder_name:
                if not self.owner.has_permission("files"):
                    return "Tu nivel de permisos actual no permite crear carpetas."
                return actions.queue_pending_action(
                    "create_folder",
                    {"folder_name": folder_name},
                    f"crear la carpeta {folder_name} en tu escritorio",
                )

        if action_name == "archive_item":
            item_name = self.owner.sanitize_folder_name(action_args.get("item_name", ""))
            if item_name:
                if not self.owner.has_permission("files"):
                    return "Tu nivel de permisos actual no permite archivar elementos."
                return actions.queue_pending_action(
                    "archive_item",
                    {"item_name": item_name},
                    f"mover {item_name} a la carpeta de archivado",
                )

        if action_name == "open_app":
            app_name = str(action_args.get("app_name", "")).strip()
            if app_name:
                if not self.owner.has_permission("full"):
                    return "Tu nivel de permisos actual no permite abrir aplicaciones."
                return actions.queue_pending_action(
                    "open_app",
                    {"app_name": app_name},
                    f"abrir la aplicacion {app_name}",
                )

        if action_name == "open_website":
            url = str(action_args.get("url", "")).strip() or self._extract_url_from_command(raw_command)
            if url:
                if not self.owner.has_permission("full"):
                    return "Tu nivel de permisos actual no permite abrir sitios web."
                return actions.queue_pending_action(
                    "open_website",
                    {"url": url},
                    f"abrir el sitio {url}",
                )

        if action_name == "media_next":
            return "Usa el boton 'Siguiente' del panel Mimi Music o !next para cola."

        if action_name == "media_prev":
            return "La navegacion musical se controla desde Mimi Music."

        if action_name == "media_play_pause":
            return "Usa el boton 'Pausa' del panel Mimi Music."

        if action_name == "mode_free":
            self.owner.set_mode_free()
            return "Modo libre activado."

        if action_name == "mode_platform":
            self.owner.set_mode_platform()
            return "Modo suelo activado."

        if action_name == "ollama_status":
            ok, model_count = self.owner.check_ollama_health()
            if not ok:
                return "No pude conectar con Ollama en local. Revisa que el servicio este activo."
            return f"Ollama local activo. Modelos detectados: {model_count}. Modelo seleccionado: {self.owner.llm_model}."

        if action_name == "ollama_test":
            ok, model_count = self.owner.check_ollama_health()
            if not ok:
                return "No pude conectar con Ollama local para la prueba."
            if model_count <= 0:
                return "Ollama esta activo, pero no hay modelos descargados."
            test_answer = self.owner.query_ollama_llm("Responde solo con: OK_LOCAL")
            if test_answer:
                compact = " ".join(test_answer.split())
                return f"Prueba local completada. Respuesta del modelo: {compact}"
            return "Ollama responde, pero el modelo no devolvio contenido en esta prueba."

        if action_name == "permission_query":
            self.owner.set_permission_level("query")
            return "Permiso cambiado a consulta."

        if action_name == "permission_files":
            self.owner.set_permission_level("files")
            return "Permiso cambiado a archivos."

        if action_name == "permission_full":
            self.owner.set_permission_level("full")
            return "Permiso cambiado a completo."

        if action_name == "llm_enable":
            self.owner.llm_enabled = True
            self.owner.save_assistant_config()
            return "IA conversacional activada."

        if action_name == "llm_disable":
            self.owner.llm_enabled = False
            self.owner.save_assistant_config()
            return "IA conversacional desactivada."

        if action_name == "llm_mode_local":
            self.owner.llm_provider = "ollama"
            self.owner.llm_endpoint = "http://127.0.0.1:11434/api/chat"
            self.owner.llm_offline_only = True
            self.owner.llm_enabled = True
            self.owner.save_assistant_config()
            return "Modo local activado con Ollama en 127.0.0.1."

        if action_name == "llm_mode_cloud":
            self.owner.llm_provider = "openai"
            self.owner.llm_endpoint = "https://api.openai.com/v1/chat/completions"
            self.owner.llm_offline_only = False
            self.owner.llm_enabled = bool(self.owner.llm_api_key)
            self.owner.save_assistant_config()
            if self.owner.llm_enabled:
                return "Modo nube activado."
            return "Modo nube configurado, pero falta OPENAI_API_KEY para usarlo."

        if action_name == "set_model":
            new_model = str(action_args.get("model", "")).strip()
            if new_model:
                self.owner.llm_model = new_model
                self.owner.save_assistant_config()
                return f"Modelo IA actualizado a {self.owner.llm_model}."

        if self.owner.llm_enabled and self.owner.has_permission("query"):
            llm_response = self.owner.query_optional_llm(raw_command)
            if llm_response:
                return llm_response

        return "No entendi ese comando todavia, pero puedo aprender mas funciones."
