import json


class JsonConfigStore:
    def load(self, file_path):
        if not file_path.exists():
            return {}

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    def save(self, file_path, payload):
        try:
            file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False
