from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file, regardless of CWD.
# This ensures `python web/server.py` and `uvicorn web.server:app` both find it.
_ENV_FILE = Path(__file__).parent / ".env"


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    BEDROCK = "bedrock"
    OPENAI = "openai"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: LLMProvider = LLMProvider.OLLAMA

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # AWS Bedrock
    aws_region: str = "us-east-1"
    # Bearer-token API key (AWS_BEARER_TOKEN_BEDROCK) — preferred auth method
    bedrock_api_key: Optional[str] = None
    # IAM credentials — fallback when no Bearer token is set
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # Kubernetes
    kubeconfig: Optional[str] = None
    k8s_context: Optional[str] = None

    # Behaviour
    auto_fix: bool = False
    runbook_dir: Path = Path("./runbooks")
    max_log_lines: int = 200
    debug: bool = False

    # Coerce blank env-var values ("") to None so callers can rely on truthiness.
    @field_validator(
        "bedrock_api_key",
        "aws_access_key_id", "aws_secret_access_key", "aws_session_token",
        "openai_api_key", "kubeconfig", "k8s_context",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("runbook_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str) -> Path:
        return Path(v).expanduser().resolve()

    def effective_kubeconfig(self) -> Optional[str]:
        if self.kubeconfig:
            return str(Path(self.kubeconfig).expanduser())
        env_val = os.environ.get("KUBECONFIG")
        if env_val:
            return env_val
        default = Path.home() / ".kube" / "config"
        return str(default) if default.exists() else None

    def ensure_runbook_dir(self) -> Path:
        self.runbook_dir.mkdir(parents=True, exist_ok=True)
        return self.runbook_dir


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def persist_to_env_file(updates: dict[str, str]) -> None:
    """
    Write key=value pairs back to the .env file so they survive server restarts.

    - Existing lines (including comments and blank lines) are preserved.
    - Keys already present are updated in-place.
    - Keys not yet in the file are appended at the end.
    - If .env doesn't exist it is created from .env.example (if available) or from scratch.
    """
    env_path = _ENV_FILE

    # Bootstrap from the example file if .env doesn't exist yet
    if not env_path.exists():
        example = env_path.parent / ".env.example"
        if example.exists():
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_path.write_text("", encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Preserve blank lines and comments unchanged
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, val in updates.items():
        if key not in updated:
            new_lines.append(f"{key}={val}\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")
