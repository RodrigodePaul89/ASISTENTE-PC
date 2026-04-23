import json
import re
import unicodedata
from difflib import SequenceMatcher


class CommandTextParser:
    def sanitize_folder_name(self, raw_name):
        cleaned = re.sub(r'[<>:"/\\|?*]+', "", raw_name or "")
        cleaned = cleaned.strip().strip(".")
        if not cleaned:
            return ""
        return cleaned[:80]

    def normalize_command_text(self, text):
        raw_text = str(text or "").strip().lower()
        if not raw_text:
            return ""

        normalized = unicodedata.normalize("NFKD", raw_text)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def compact_for_matching(self, text):
        normalized = self.normalize_command_text(text)
        if not normalized:
            return ""
        normalized = re.sub(r"[^a-z0-9]+", "", normalized)
        return normalized

    def fuzzy_contains(self, command, phrases, threshold=0.84):
        normalized_command = self.normalize_command_text(command)
        compact_command = self.compact_for_matching(command)
        if not normalized_command or not compact_command:
            return False

        command_tokens = normalized_command.split()
        for phrase in phrases:
            normalized_phrase = self.normalize_command_text(phrase)
            compact_phrase = self.compact_for_matching(phrase)
            if not normalized_phrase or not compact_phrase:
                continue

            if normalized_phrase in normalized_command or compact_phrase in compact_command:
                return True

            ratio_full = SequenceMatcher(None, compact_command, compact_phrase).ratio()
            if ratio_full >= threshold:
                return True

            phrase_tokens = normalized_phrase.split()
            token_window_size = len(phrase_tokens)
            if token_window_size <= 0:
                continue

            for index in range(0, len(command_tokens) - token_window_size + 1):
                window_tokens = command_tokens[index : index + token_window_size]
                window_compact = self.compact_for_matching(" ".join(window_tokens))
                if not window_compact:
                    continue
                ratio_window = SequenceMatcher(None, window_compact, compact_phrase).ratio()
                if ratio_window >= threshold:
                    return True

        return False

    def extract_json_object(self, raw_text):
        content = str(raw_text or "").strip()
        if not content:
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {}

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    def extract_folder_name_from_command(self, command):
        normalized = " ".join((command or "").strip().split())
        patterns = [
            r"(?:crea|crear|haz|genera)\s+(?:una\s+)?(?:nueva\s+)?carpeta(?:\s+nueva)?(?:\s+en\s+el\s+escritorio)?(?:\s+(?:llamada|con\s+nombre|de\s+nombre))?\s+(.+)$",
            r"(?:crea|crear|haz|genera)\s+(?:una\s+)?(?:nueva\s+)?carpeta\s+(.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            candidate = match.group(1).strip(" .,:;!?\"'")
            candidate = re.sub(r"^(?:que\s+se\s+llame|llamada|con\s+nombre)\s+", "", candidate).strip()
            return self.sanitize_folder_name(candidate)

        return ""

    def extract_quoted_text(self, command):
        content = str(command or "")
        match = re.search(r"[\"']([^\"']+)[\"']", content)
        if not match:
            return ""
        return match.group(1).strip()

    def extract_folder_structure_from_command(self, command):
        normalized = self.normalize_command_text(command)
        if not normalized:
            return []

        if not self.fuzzy_contains(
            normalized,
            (
                "estructura de carpetas",
                "estructura carpetas",
                "arbol de carpetas",
                "crear varias carpetas",
                "crear carpetas",
            ),
            threshold=0.79,
        ):
            return []

        raw = str(command or "")
        quoted = self.extract_quoted_text(raw)
        source = quoted if quoted else raw

        source = source.replace("\\", "/")
        source = re.sub(r"\s*/\s*", "/", source)
        source = re.sub(r"\s*[,;|>]+\s*", ",", source)
        source = re.sub(r"\s+", " ", source).strip()

        for marker in (
            "estructura de carpetas",
            "estructura carpetas",
            "arbol de carpetas",
            "crear varias carpetas",
            "crea varias carpetas",
            "crear carpetas",
            "crea carpetas",
        ):
            marker_index = source.lower().find(marker)
            if marker_index >= 0:
                source = source[marker_index + len(marker) :].strip(" :,-")
                break

        if not source:
            return []

        chunks = [chunk.strip(" .") for chunk in source.split(",") if chunk.strip(" .")]
        candidates = []
        for chunk in chunks:
            if "/" in chunk:
                for nested in chunk.split("/"):
                    nested = self.sanitize_folder_name(nested)
                    if nested:
                        candidates.append(nested)
                continue

            cleaned = self.sanitize_folder_name(chunk)
            if cleaned:
                candidates.append(cleaned)

        unique = []
        seen = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)

        return unique[:20]
