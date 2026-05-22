import os

from providers.gemini import GeminiProvider
from providers.ollama import OllamaProvider


def _is_compatible(provider: str, model: str) -> bool:
    m = model.lower()
    if provider == "gemini":
        return m.startswith("gemini") or m.startswith("models/gemini")
    return not (m.startswith("gemini") or m.startswith("models/gemini"))


def get_provider(model_override: str | None = None):
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    env_model = os.getenv("LLM_MODEL", "gemma3").strip()
    # Drop an incoming override that doesn't match the active provider
    # (e.g. frontend still sending an Ollama model name after switching to Gemini).
    if model_override and _is_compatible(provider, model_override):
        model = model_override
    else:
        model = env_model
    if provider == "gemini":
        return GeminiProvider(os.getenv("GEMINI_API_KEY", ""), model)
    return OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model)
