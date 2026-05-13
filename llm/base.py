from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # for tool result messages
    tool_name: Optional[str] = None     # for tool result messages


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseLLMProvider(ABC):
    """Unified interface for all LLM backends."""

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        system: str = "",
    ) -> LLMResponse:
        """Send messages + tool schemas, get back text and/or tool calls."""

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    def model_name(self) -> str:
        """Model being used."""
