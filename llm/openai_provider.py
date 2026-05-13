from __future__ import annotations

import json
import uuid
from typing import Any

from openai import OpenAI

from .base import BaseLLMProvider, LLMResponse, Message, ToolCall


def _to_openai_messages(messages: list[Message], system: str) -> list[dict]:
    result = []
    if system:
        result.append({"role": "system", "content": system})
    for msg in messages:
        if msg.role == "tool":
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id or "unknown",
                "content": msg.content,
            })
        elif msg.role == "assistant" and msg.tool_calls:
            tool_calls_payload = []
            for tc in msg.tool_calls:
                tool_calls_payload.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                })
            result.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": tool_calls_payload,
            })
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _tools_to_openai(tools: list[dict]) -> list[dict]:
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


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._model = model
        self._client = OpenAI(api_key=api_key)

    def provider_name(self) -> str:
        return "OpenAI"

    def model_name(self) -> str:
        return self._model

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        system: str = "",
    ) -> LLMResponse:
        oai_messages = _to_openai_messages(messages, system)
        oai_tools = _tools_to_openai(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
            "temperature": 0,
            "max_tokens": 4096,
        }
        if oai_tools:
            kwargs["tools"] = oai_tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        content = msg.content or ""
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                try:
                    args = json.loads(fn.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=fn.name,
                    arguments=args,
                ))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(content=content, tool_calls=tool_calls, stop_reason=stop_reason)
