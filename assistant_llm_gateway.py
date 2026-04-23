import json
import urllib.error
import urllib.request


class LLMGateway:
    def query_openai_chat(self, endpoint, api_key, model, system_prompt, user_prompt, timeout_seconds):
        if not api_key:
            return ""

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
        }

        request_body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        target_endpoint = endpoint or "https://api.openai.com/v1/chat/completions"
        request = urllib.request.Request(target_endpoint, data=request_body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            choices = parsed.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            return str(message.get("content", "")).strip()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return ""

    def query_ollama_chat(
        self,
        endpoint,
        model,
        system_prompt,
        user_prompt,
        timeout_seconds,
        temperature=0.4,
        num_ctx=2048,
    ):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }

        request_body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        target_endpoint = endpoint or "http://127.0.0.1:11434/api/chat"
        request = urllib.request.Request(target_endpoint, data=request_body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            message = parsed.get("message", {})
            return str(message.get("content", "")).strip()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return ""

    def query_ollama_local_chat(self, model, system_prompt, user_prompt, timeout_seconds):
        return self.query_ollama_chat(
            endpoint="http://127.0.0.1:11434/api/chat",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=timeout_seconds,
            temperature=0.3,
            num_ctx=1536,
        )

    def check_ollama_health(self, endpoint, timeout_seconds):
        source_endpoint = (endpoint or "http://127.0.0.1:11434/api/chat").strip()
        tags_endpoint = source_endpoint
        if tags_endpoint.endswith("/api/chat"):
            tags_endpoint = tags_endpoint[: -len("/api/chat")] + "/api/tags"

        request = urllib.request.Request(tags_endpoint, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(3, timeout_seconds)) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            models = parsed.get("models", [])
            return True, len(models)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return False, 0
