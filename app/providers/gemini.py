from typing import Iterator


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def stream(self, messages: list[dict], tools: list[dict] | None = None) -> Iterator[str]:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        system_instruction, chat_messages = _prepare_messages(messages)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_instruction,
            tools=_to_gemini_tools(tools),
        )
        for chunk in model.generate_content(_to_gemini_contents(chat_messages), stream=True):
            if chunk.text:
                yield chunk.text

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        system_instruction, chat_messages = _prepare_messages(messages)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_instruction,
            tools=_to_gemini_tools(tools),
        )
        response = model.generate_content(_to_gemini_contents(chat_messages))
        return _normalise_response(response)


def _prepare_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    return "\n".join(system_parts) or None, [m for m in messages if m.get("role") != "system"]


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    contents: list[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "assistant":
            if not content and message.get("tool_calls"):
                continue
            contents.append({"role": "model", "parts": [content]})
        elif role == "tool":
            contents.append({"role": "user", "parts": [f"Tool {message.get('name')} returned:\n{content}"]})
        else:
            contents.append({"role": "user", "parts": [content]})
    return contents


def _to_gemini_tools(tools: list[dict] | None) -> list[dict] | None:
    if not tools:
        return None
    return [{"function_declarations": [tool["function"] for tool in tools]}]


def _normalise_response(response) -> dict:
    content_parts: list[str] = []
    tool_calls: list[dict] = []
    for candidate in getattr(response, "candidates", []) or []:
        for part in getattr(candidate.content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if function_call and getattr(function_call, "name", None):
                args = dict(getattr(function_call, "args", {}) or {})
                tool_calls.append({"id": None, "name": function_call.name, "arguments": args})
            text = getattr(part, "text", None)
            if text:
                content_parts.append(text)
    if not content_parts and not tool_calls:
        try:
            content_parts.append(response.text)
        except Exception:
            pass
    return {"content": "".join(content_parts), "tool_calls": tool_calls}
