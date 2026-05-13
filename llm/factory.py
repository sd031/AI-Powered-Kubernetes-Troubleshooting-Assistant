from __future__ import annotations

from config import LLMProvider, Settings
from .base import BaseLLMProvider


def get_llm_provider(settings: Settings) -> BaseLLMProvider:
    provider = settings.llm_provider

    if provider == LLMProvider.OLLAMA:
        from .ollama_provider import OllamaProvider
        return OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)

    elif provider == LLMProvider.BEDROCK:
        from .bedrock_provider import BedrockProvider
        return BedrockProvider(
            model_id=settings.bedrock_model_id,
            region=settings.aws_region,
            api_key=settings.bedrock_api_key,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            session_token=settings.aws_session_token,
        )

    elif provider == LLMProvider.OPENAI:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)

    raise ValueError(f"Unknown LLM provider: {provider}")
