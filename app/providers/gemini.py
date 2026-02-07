from typing import Any, Dict

from app.exceptions import LLMError


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY not set")
        try:
            import google.generativeai as genai
        except Exception as exc:
            raise LLMError(f"Gemini SDK not installed: {exc}")

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            result = model.generate_content(prompt)
            text = (result.text or "").strip()
        except Exception as exc:
            raise LLMError(str(exc))

        if not text:
            raise LLMError("Gemini returned empty response")
        return {"text": text}
