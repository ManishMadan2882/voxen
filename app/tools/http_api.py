import json
import logging
import re
from typing import Any

import httpx

from tools.base import ToolCall, ToolProvider, ToolResult, ToolSpec
from tools.registry import register_provider

logger = logging.getLogger(__name__)

_PATH_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_MAX_BODY_CHARS = 4000
_DEFAULT_TIMEOUT = 15.0


@register_provider
class HttpApiToolProvider(ToolProvider):
    type_name = "http_api"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url: str = (config.get("base_url") or "").rstrip("/")
        self.headers: dict = dict(config.get("headers") or {})
        self.timeout: float = float(config.get("timeout") or _DEFAULT_TIMEOUT)
        self._endpoints: dict[str, dict] = {}
        for ep in config.get("endpoints") or []:
            name = ep.get("name")
            if name:
                self._endpoints[name] = ep
        if not self.base_url:
            raise ValueError("http_api: base_url is required")

    def get_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=ep["name"],
                description=ep.get("description", ""),
                parameters=ep.get("parameters") or {"type": "object", "properties": {}},
            )
            for ep in self._endpoints.values()
        ]

    def execute(self, call: ToolCall) -> ToolResult:
        ep = self._endpoints.get(call.name)
        if ep is None:
            return ToolResult(call.call_id, call.name, f"Unknown tool: {call.name}", is_error=True)

        method = (ep.get("method") or "GET").upper()
        args = dict(call.arguments or {})
        try:
            path, used = _render_path(ep.get("path") or "/", args, ep.get("path_params"))
        except KeyError as e:
            return ToolResult(call.call_id, call.name, f"Missing path param: {e}", is_error=True)

        remaining = {k: v for k, v in args.items() if k not in used}
        params, body = _split_params(method, remaining, ep)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(
                    method,
                    self.base_url + path,
                    params=params,
                    json=body,
                    headers=self.headers,
                )
        except httpx.HTTPError as e:
            logger.exception("http_api tool %s failed", call.name)
            return ToolResult(call.call_id, call.name, f"Request error: {e}", is_error=True)

        return ToolResult(
            call.call_id,
            call.name,
            _format_response(resp),
            is_error=resp.status_code >= 400,
        )


def _split_params(method: str, remaining: dict, ep: dict) -> tuple[dict | None, dict | None]:
    query_keys = ep.get("query_params")
    body_keys = ep.get("body_params")
    if query_keys is not None or body_keys is not None:
        return (
            {k: remaining[k] for k in (query_keys or []) if k in remaining},
            {k: remaining[k] for k in (body_keys or []) if k in remaining},
        )
    if method in ("GET", "DELETE", "HEAD"):
        return remaining, None
    return None, remaining


def _render_path(template: str, args: dict, declared: list[str] | None) -> tuple[str, set[str]]:
    used: set[str] = set()
    keys = declared if declared is not None else _PATH_PARAM_RE.findall(template)

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in args:
            raise KeyError(key)
        used.add(key)
        return str(args[key])

    rendered = _PATH_PARAM_RE.sub(repl, template)
    for key in keys:
        if key not in used and key in args:
            used.add(key)
    return rendered, used


def _format_response(resp: httpx.Response) -> str:
    try:
        if "json" in resp.headers.get("content-type", ""):
            text = json.dumps(resp.json(), separators=(",", ":"))
        else:
            text = resp.text
    except Exception:
        text = resp.text
    if len(text) > _MAX_BODY_CHARS:
        text = text[:_MAX_BODY_CHARS] + "…[truncated]"
    return f"HTTP {resp.status_code} {text}"