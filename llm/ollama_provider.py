from __future__ import annotations

import json
import uuid
from typing import Any

import ollama as _ollama

from .base import BaseLLMProvider, LLMResponse, Message, ToolCall


def _to_ollama_messages(messages: list[Message]) -> list[dict]:
    result = []
    for msg in messages:
        if msg.role == "tool":
            result.append({
                "role": "tool",
                "content": msg.content,
            })
        elif msg.role == "assistant" and msg.tool_calls:
            tool_calls_payload = []
            for tc in msg.tool_calls:
                tool_calls_payload.append({
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                })
            result.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_calls_payload,
            })
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _tools_to_ollama(tools: list[dict]) -> list[dict]:
    """Convert generic tool dicts to Ollama format."""
    converted = []
    for t in tools:
        converted.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return converted


class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str, model: str) -> None:
        self._host = host
        self._model = model
        self._client = _ollama.Client(host=host)

    def provider_name(self) -> str:
        return "Ollama"

    def model_name(self) -> str:
        return self._model

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        system: str = "",
    ) -> LLMResponse:
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(_to_ollama_messages(messages))

        ollama_tools = _tools_to_ollama(tools) if tools else None

        response = self._client.chat(
            model=self._model,
            messages=ollama_messages,
            tools=ollama_tools,
        )

        msg = response.message
        content = msg.content or ""
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                args = fn.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4()),
                    name=fn.name,
                    arguments=args,
                ))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(content=content, tool_calls=tool_calls, stop_reason=stop_reason)
