import sys
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
tools_base = import_module("tools.base")
ToolCall = tools_base.ToolCall
ToolProvider = tools_base.ToolProvider
ToolResult = tools_base.ToolResult
ToolSpec = tools_base.ToolSpec
HttpApiToolProvider = import_module("tools.http_api").HttpApiToolProvider
ResponseOrchestrator = import_module("tools.orchestrator").ResponseOrchestrator


class FakeLLM:
    def __init__(self):
        self.generate_count = 0
        self.stream_messages = None

    def generate(self, _messages, _tools=None, **_kwargs):
        del _messages, _tools, _kwargs
        self.generate_count += 1
        if self.generate_count == 1:
            return {"tool_calls": [{"id": "c1", "name": "lookup", "arguments": {"id": "42"}}]}
        return {"content": ""}

    def stream(self, messages, _tools=None):
        del _tools
        self.stream_messages = messages
        yield "final"


class LookupTool(ToolProvider):
    type_name = "lookup_provider"

    def get_tools(self):
        return [ToolSpec("lookup", "Lookup by id", {"type": "object", "properties": {}})]

    def execute(self, call: ToolCall):
        return ToolResult(call.call_id, call.name, f"found {call.arguments['id']}")


class GenerationToolTests(unittest.TestCase):
    def test_orchestrator_resolves_tool_calls_before_streaming_final_answer(self):
        llm = FakeLLM()
        tokens = list(ResponseOrchestrator(llm, [LookupTool({})]).stream([{"role": "user", "content": "hi"}]))

        self.assertEqual(tokens, ["final"])
        self.assertEqual(llm.generate_count, 2)
        self.assertEqual(llm.stream_messages[-1], {
            "role": "tool",
            "tool_call_id": "c1",
            "name": "lookup",
            "content": "found 42",
        })

    def test_http_api_tool_provider_maps_path_query_and_response(self):
        captured = {}

        class FakeClient:
            def __init__(self, timeout):
                captured["timeout"] = timeout

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                del _args
                return None

            def request(self, method, url, params=None, json=None, headers=None):
                captured.update(method=method, url=url, params=params, json=json, headers=headers)
                return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

        with patch("tools.http_api.httpx.Client", FakeClient):
            provider = HttpApiToolProvider({
                "base_url": "https://internal.example/v1",
                "headers": {"X-Client": "voxen"},
                "timeout": 3,
                "endpoints": [{
                    "name": "get_order",
                    "method": "GET",
                    "path": "/orders/{order_id}",
                    "query_params": ["include"],
                }],
            })
            result = provider.execute(ToolCall("get_order", {"order_id": "o1", "include": "items"}, "c2"))

        self.assertEqual(result.content, 'HTTP 200 {"ok":true}')
        self.assertEqual(captured, {
            "timeout": 3,
            "method": "GET",
            "url": "https://internal.example/v1/orders/o1",
            "params": {"include": "items"},
            "json": {},
            "headers": {"X-Client": "voxen"},
        })


if __name__ == "__main__":
    unittest.main()