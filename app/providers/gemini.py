from typing import Iterator


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def stream(self, messages: list[dict]) -> Iterator[str]:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        chat_messages = [m for m in messages if m["role"] != "system"]
        system_instruction = "\n".join(system_parts) or None

        model = genai.GenerativeModel(self.model, system_instruction=system_instruction)
        # Gemini expects roles "user" / "model"; map "assistant" → "model".
        history = [
            {"role": "model" if m["role"] == "assistant" else m["role"], "parts": [m["content"]]}
            for m in chat_messages[:-1]
        ]
        chat = model.start_chat(history=history)
        for chunk in chat.send_message(chat_messages[-1]["content"], stream=True):
            if chunk.text:
                yield chunk.text
