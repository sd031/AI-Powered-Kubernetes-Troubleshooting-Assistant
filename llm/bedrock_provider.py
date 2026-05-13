from __future__ import annotations

import os
from typing import Any, Optional

import boto3
import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from .base import BaseLLMProvider, LLMResponse, Message, ToolCall


def _to_bedrock_messages(messages: list[Message]) -> list[dict]:
    """
    Convert our internal message list to Bedrock's converse format.

    Bedrock requires that ALL toolResult blocks for a given assistant turn
    appear together in a single user message — one toolResult per toolUseId.
    We therefore merge consecutive tool-role messages into one user turn.
    """
    result = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        if msg.role == "tool":
            # Collect every consecutive tool result and emit them as one user message.
            tool_results: list[dict] = []
            while i < len(messages) and messages[i].role == "tool":
                m = messages[i]
                tool_results.append({
                    "toolResult": {
                        "toolUseId": m.tool_call_id or "unknown",
                        "content": [{"text": m.content}],
                    }
                })
                i += 1
            result.append({"role": "user", "content": tool_results})

        elif msg.role == "assistant" and msg.tool_calls:
            content_parts: list[dict] = []
            if msg.content:
                content_parts.append({"text": msg.content})
            for tc in msg.tool_calls:
                content_parts.append({
                    "toolUse": {
                        "toolUseId": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                })
            result.append({"role": "assistant", "content": content_parts})
            i += 1

        else:
            result.append({
                "role": msg.role,
                "content": [{"text": msg.content}],
            })
            i += 1

    return result


def _tools_to_bedrock(tools: list[dict]) -> list[dict]:
    converted = []
    for t in tools:
        converted.append({
            "toolSpec": {
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": {
                    "json": t.get("parameters", {"type": "object", "properties": {}})
                },
            }
        })
    return converted


class BedrockProvider(BaseLLMProvider):
    """
    Authentication priority:
      1. api_key  — Bedrock Bearer token (AWS Console → Bedrock → API keys).
                    Set AWS_BEARER_TOKEN_BEDROCK before the boto3 client is created
                    (requires boto3 ≥ 1.38).
      2. access_key_id + secret_access_key  — IAM user long-term credentials.
      3. Default AWS credential chain  — IAM role, ~/.aws/credentials, env vars, etc.
    """

    def __init__(
        self,
        model_id: str,
        region: str,
        api_key: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
    ) -> None:
        self._model_id = model_id
        self._api_key = api_key

        if api_key:
            # boto3 >= 1.38 reads this env var and sends the value as a Bearer token.
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
        elif "AWS_BEARER_TOKEN_BEDROCK" in os.environ and not api_key:
            # Clear any stale Bearer token so IAM credentials take over.
            del os.environ["AWS_BEARER_TOKEN_BEDROCK"]

        session_kwargs: dict[str, Any] = {"region_name": region}
        if access_key_id:
            session_kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            session_kwargs["aws_secret_access_key"] = secret_access_key
        if session_token:
            session_kwargs["aws_session_token"] = session_token

        session = boto3.Session(**session_kwargs)
        self._client = session.client("bedrock-runtime")

    def provider_name(self) -> str:
        return "AWS Bedrock"

    def model_name(self) -> str:
        return self._model_id

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        system: str = "",
    ) -> LLMResponse:
        bedrock_messages = _to_bedrock_messages(messages)
        bedrock_tools = _tools_to_bedrock(tools) if tools else []

        kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": bedrock_messages,
            "inferenceConfig": {"maxTokens": 4096, "temperature": 0},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        if bedrock_tools:
            kwargs["toolConfig"] = {"tools": bedrock_tools}

        try:
            response = self._client.converse(**kwargs)
        except Exception as exc:
            err = str(exc)
            # Surface actionable hints for the two most common errors
            if "Invalid API Key format" in err or "Must start with pre-defined prefix" in err:
                raise RuntimeError(
                    "Bedrock API Key rejected — the Bearer token format is invalid. "
                    "Go to Settings and paste the token exactly as shown in "
                    "AWS Console → Amazon Bedrock → API keys. "
                    "Alternatively, leave the API Key blank and set IAM credentials "
                    "(AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) in .env instead."
                ) from exc
            if "on-demand throughput isn't supported" in err or "inference profile" in err.lower():
                raise RuntimeError(
                    f"Model '{self._model_id}' requires a cross-region inference profile. "
                    "Use the 'us.' prefixed ID (e.g. us.anthropic.claude-sonnet-4-6) "
                    "available in the Settings model dropdown."
                ) from exc
            raise

        output = response["output"]["message"]
        content_text = ""
        tool_calls: list[ToolCall] = []

        for part in output.get("content", []):
            if "text" in part:
                content_text += part["text"]
            elif "toolUse" in part:
                tu = part["toolUse"]
                tool_calls.append(ToolCall(
                    id=tu["toolUseId"],
                    name=tu["name"],
                    arguments=tu.get("input", {}),
                ))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )
