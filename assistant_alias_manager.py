import json
import re
from pathlib import Path


class AliasManager:
    """Modo comandos pro: alias personalizados de disparo rapido para Mimi.

    Sintaxis de uso:
        trigger +arg      ->  expande template reemplazando {arg}
        trigger arg       ->  igual pero sin el signo +
        trigger+arg       ->  pegado, tambien funciona
        trigger           ->  expande templates sin argumento

    Ejemplos con los alias por defecto:
        carpeta +proyectos  ->  crea carpeta proyectos
        web +github.com     ->  abre github.com
        nota +pendientes    ->  crear nota pendientes
        captura             ->  captura de pantalla
    """

    DEFAULT_ALIASES = [
        {
            "trigger": "carpeta",
            "template": "crea carpeta {arg}",
            "description": "Crea carpeta en escritorio",
        },
        {
            "trigger": "web",
            "template": "abre {arg}",
            "description": "Abre sitio web o URL",
        },
        {
            "trigger": "nota",
            "template": "crear nota {arg}",
            "description": "Crea nota rapida con ese contenido",
        },
        {
            "trigger": "app",
            "template": "abre {arg}",
            "description": "Lanza aplicacion por nombre",
        },
        {
            "trigger": "recuerda",
            "template": "recordatorio en {arg}",
            "description": "Recordatorio rapido (ej: recuerda 5 minutos tomar agua)",
        },
        {
            "trigger": "busca",
            "template": "buscar archivo {arg}",
            "description": "Busca archivo o carpeta en escritorio",
        },
        {
            "trigger": "renombra",
            "template": "renombra {arg}",
            "description": "Renombra elemento (ej: renombra viejo a nuevo)",
        },
        {
            "trigger": "mueve",
            "template": "mueve {arg}",
            "description": "Mueve elemento (ej: mueve archivo a carpeta)",
        },
        {
            "trigger": "captura",
            "template": "captura de pantalla",
            "description": "Toma captura de pantalla (sin argumento)",
        },
        {
            "trigger": "limpia",
            "template": "limpiar escritorio",
            "description": "Limpia escritorio (sin argumento)",
        },
        {
            "trigger": "bloquea",
            "template": "bloquea pc",
            "description": "Bloquea la sesion de Windows (sin argumento)",
        },
    ]

    # Triggers: solo letras minusculas, digitos, guion bajo y caracteres acentuados basicos
    _TRIGGER_RE = re.compile(r"^[a-z0-9_\u00e0-\u00fc]{1,30}$")

    def __init__(self, owner):
        self.owner = owner
        self._aliases = {}  # trigger -> record dict
        self._load()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _aliases_file(self):
        return Path(__file__).resolve().parent / "assistant_aliases.json"

    def _load(self):
        file = self._aliases_file()
        records = []
        if file.exists():
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    records = raw
            except Exception:
                pass

        if not records:
            records = list(self.DEFAULT_ALIASES)
            self._persist(records)

        for rec in records:
            trigger = str(rec.get("trigger", "")).strip().lower()
            template = str(rec.get("template", "")).strip()
            description = str(rec.get("description", "")).strip()
            if trigger and template:
                self._aliases[trigger] = {
                    "trigger": trigger,
                    "template": template,
                    "description": description,
                }

    def _persist(self, records):
        try:
            self._aliases_file().write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def save(self):
        self._persist(list(self._aliases.values()))

    # ------------------------------------------------------------------
    # Gestion de alias
    # ------------------------------------------------------------------

    def add(self, trigger, template, description=""):
        """Agrega o actualiza un alias. Retorna True si fue guardado."""
        trigger = str(trigger).strip().lower()
        if not self._TRIGGER_RE.match(trigger):
            return False
        template = str(template).strip()
        if not template or len(template) > 200:
            return False
        self._aliases[trigger] = {
            "trigger": trigger,
            "template": template,
            "description": str(description).strip()[:80],
        }
        self.save()
        return True

    def remove(self, trigger):
        """Elimina un alias. Retorna True si existia."""
        trigger = str(trigger).strip().lower()
        if trigger not in self._aliases:
            return False
        del self._aliases[trigger]
        self.save()
        return True

    def list_all(self):
        """Retorna lista de records ordenada por trigger."""
        return sorted(self._aliases.values(), key=lambda r: r["trigger"])

    def get(self, trigger):
        return self._aliases.get(str(trigger).strip().lower())

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def expand(self, raw_command):
        """Retorna el comando expandido si coincide con un alias, o None."""
        raw = (raw_command or "").strip()
        if not raw:
            return None
        raw_lower = raw.lower()

        for trigger, record in self._aliases.items():
            template = record["template"]
            has_arg = "{arg}" in template

            # 1) Coincidencia exacta (alias sin argumento)
            if raw_lower == trigger:
                return None if has_arg else template

            # 2) trigger+arg  (signo + pegado al trigger, sin espacio)
            prefix_plus = trigger + "+"
            if raw_lower.startswith(prefix_plus):
                arg = raw[len(prefix_plus) :].strip()
                if arg and has_arg:
                    return template.replace("{arg}", arg)
                if not has_arg and not arg:
                    return template

            # 3) trigger +arg  (espacio, luego signo +)
            prefix_space_plus = trigger + " +"
            if raw_lower.startswith(prefix_space_plus):
                arg = raw[len(prefix_space_plus) :].strip()
                if arg and has_arg:
                    return template.replace("{arg}", arg)

            # 4) trigger arg  (solo espacio, forma larga sin +)
            prefix_space = trigger + " "
            if raw_lower.startswith(prefix_space):
                arg = raw[len(prefix_space) :].strip()
                if arg and has_arg:
                    return template.replace("{arg}", arg)

        return None
