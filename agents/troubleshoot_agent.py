from __future__ import annotations

import inspect
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from k8s.tools import K8sTools
from llm.base import BaseLLMProvider, Message, ToolCall

from .tool_definitions import TOOL_DEFINITIONS

console = Console()

SYSTEM_PROMPT = """You are an expert Kubernetes Site Reliability Engineer and troubleshooter.
Your job is to diagnose and fix issues in Kubernetes clusters.

## Workflow
1. When asked to investigate an issue or scan the cluster, use the available tools to gather information.
2. Start broad (check_cluster_health, get_nodes, get_pods) then drill down to specifics.
3. Correlate pod logs, events, resource quotas, and node conditions to find the root cause.
4. Propose fixes that are safe and minimal — prefer restarts/rollbacks before config changes.
5. ALWAYS explain your reasoning before calling tools or applying fixes.
6. After fixing, verify the fix worked by re-checking the affected resources.

## Guidelines
- Never delete pods that are not managed by a controller without warning the user.
- When applying manifests, show the full YAML before applying.
- For CrashLoopBackOff: check logs (including previous container) and events.
- For Pending pods: check node conditions, resource quotas, PVC status, taints/tolerations.
- For ImagePullBackOff: check image name, tag, and pull secret.
- For OOMKilled: check memory limits and recent usage.
- Be concise but thorough in your analysis.

## Output format
- Use markdown for clarity.
- Structure your final response with: **Root Cause**, **Fix Applied**, **Verification**, **Prevention**.
- If you cannot find the issue or fix it, explain why and suggest manual steps.
"""


@dataclass
class IssueRecord:
    """Tracks a single diagnosed issue for runbook generation."""
    description: str
    symptoms: list[str] = field(default_factory=list)
    root_cause: str = ""
    affected_resources: list[str] = field(default_factory=list)
    fix_applied: str = ""
    fix_commands: list[str] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    prevention: str = ""
    resolved: bool = False
    conversation_summary: str = ""


def _sanitise_args(method: Any, args: dict) -> dict:
    """
    Return only the kwargs that *method* actually declares, dropping:
      - keys not present in the method signature  (LLM hallucination guard)
      - values that are None                       (LLM sends null for optional params)
    If the method accepts **kwargs, the full dict (minus Nones) is passed through.
    """
    try:
        sig = inspect.signature(method)
        params = sig.parameters
        # If the method accepts **kwargs, just strip Nones and pass everything
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return {k: v for k, v in args.items() if v is not None}
        valid = {k for k, p in params.items() if p.kind not in (
            inspect.Parameter.VAR_POSITIONAL,  # *args
            inspect.Parameter.POSITIONAL_ONLY,
        )}
        return {k: v for k, v in args.items() if k in valid and v is not None}
    except (ValueError, TypeError):
        return {k: v for k, v in args.items() if v is not None}


class TroubleshootAgent:
    """
    Agentic loop that connects the LLM to Kubernetes tools.
    Provider-agnostic: works with Ollama, Bedrock, or OpenAI.

    When `on_event` is set, all output is delivered as structured dicts
    (suitable for WebSocket streaming) instead of being printed to the console.
    """

    MAX_ITERATIONS = 30

    def __init__(
        self,
        llm: BaseLLMProvider,
        k8s_tools: K8sTools,
        runbook_callback: Optional[Callable[[IssueRecord], None]] = None,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._llm = llm
        self._tools = k8s_tools
        self._runbook_callback = runbook_callback
        self._messages: list[Message] = []
        self._tool_call_log: list[dict] = []

        # Streaming event callback — set by web server for WebSocket delivery
        self.on_event = on_event

        # Confirmation signalling for web mode (set externally per-session)
        self._confirm_event: Optional[threading.Event] = None
        self._confirm_result: bool = False

        self._tools.confirm_callback = self._confirm_handler

    # ──────────────────────────────────────────────────────────────────────────
    # Event emission
    # ──────────────────────────────────────────────────────────────────────────

    def _emit(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def run_interactive(self) -> None:
        """REPL-style interactive troubleshooting session."""
        console.print(Panel(
            f"[bold green]K8s Troubleshooting Agent[/bold green]\n"
            f"LLM: [cyan]{self._llm.provider_name()} / {self._llm.model_name()}[/cyan]\n"
            "Type your issue or question. Type [bold]scan[/bold] for a full cluster scan. "
            "Type [bold]exit[/bold] to quit.",
            title="AI-Powered Kubernetes Troubleshooter",
        ))

        while True:
            try:
                user_input = console.input("[bold blue]You:[/bold blue] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[yellow]Goodbye![/yellow]")
                break
            if user_input.lower() == "scan":
                user_input = (
                    "Please perform a comprehensive health scan of the entire Kubernetes cluster. "
                    "Check all nodes, pods across all namespaces, recent warning events, and "
                    "any pending or failed resources. Report all issues found and propose fixes."
                )

            self._process_turn(user_input)

    def run_scan(self) -> IssueRecord:
        """Non-interactive: scan the cluster and return issues found."""
        prompt = (
            "Perform a comprehensive Kubernetes cluster health scan. "
            "Check all nodes, pods in all namespaces, events, and resource quotas. "
            "Identify all issues, diagnose root causes, and apply fixes where safe and appropriate. "
            "After completing, provide a structured summary."
        )
        return self._process_turn(prompt, record_issue=True)

    def run_diagnose(self, problem: str) -> IssueRecord:
        """Diagnose a specific problem described in natural language."""
        return self._process_turn(problem, record_issue=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    def _process_turn(self, user_input: str, record_issue: bool = False) -> IssueRecord:
        self._messages.append(Message(role="user", content=user_input))
        issue = IssueRecord(description=user_input)
        response = None

        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            try:
                response = self._llm.chat_with_tools(
                    messages=self._messages,
                    tools=TOOL_DEFINITIONS,
                    system=SYSTEM_PROMPT,
                )
            except Exception as exc:
                err = f"LLM error: {exc}"
                console.print(f"[red]{err}[/red]")
                if self.on_event:
                    self._emit({"type": "error", "message": err})
                else:
                    console.print(traceback.format_exc(), style="dim")
                break

            self._messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            if response.content:
                if self.on_event:
                    self._emit({"type": "text", "content": response.content})
                else:
                    console.print()
                    console.print(Markdown(response.content))
                    console.print()

            if not response.has_tool_calls:
                issue.conversation_summary = response.content
                if self.on_event:
                    self._emit({"type": "done"})
                break

            for tc in response.tool_calls:
                result = self._execute_tool(tc)
                self._tool_call_log.append({
                    "tool": tc.name,
                    "args": tc.arguments,
                    "result_snippet": result[:500],
                })
                self._messages.append(Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                ))

        if iteration >= self.MAX_ITERATIONS:
            msg = "Max iterations reached."
            if self.on_event:
                self._emit({"type": "status", "message": msg})
                self._emit({"type": "done"})
            else:
                console.print(f"[yellow]{msg}[/yellow]")

        if record_issue and response and response.content:
            issue = self._parse_issue_from_response(user_input, response.content, issue)
            if self._runbook_callback:
                self._runbook_callback(issue)

        return issue

    def _execute_tool(self, tc: ToolCall) -> str:
        """Dispatch a tool call to the corresponding K8sTools method."""
        if self.on_event:
            self._emit({
                "type": "tool_call",
                "id": tc.id,
                "name": tc.name,
                "args": tc.arguments,
            })
        else:
            console.print(
                f"  [dim cyan]⚙ Tool:[/dim cyan] [cyan]{tc.name}[/cyan] "
                f"[dim]{tc.arguments}[/dim]"
            )

        method = getattr(self._tools, tc.name, None)
        if method is None:
            result = f"Unknown tool: {tc.name}"
        else:
            try:
                result = method(**_sanitise_args(method, tc.arguments))
            except Exception as e:
                result = f"Tool execution error: {e}"

        result = str(result)

        if self.on_event:
            self._emit({
                "type": "tool_result",
                "id": tc.id,
                "name": tc.name,
                # Send preview to UI; full content stays in conversation history
                "preview": "\n".join(result.splitlines()[:20]),
                "line_count": len(result.splitlines()),
            })
        else:
            lines = result.splitlines()
            preview = "\n".join(lines[:6])
            if len(lines) > 6:
                preview += f"\n  ... ({len(lines) - 6} more lines)"
            console.print(f"  [dim green]↳ Result preview:[/dim green]\n{preview}\n", style="dim")

        return result

    def _confirm_handler(self, action: str) -> bool:
        """Called by K8sTools before any destructive operation."""
        if self.on_event and self._confirm_event is not None:
            # Web mode: emit event, then block thread until UI responds
            confirm_id = str(uuid.uuid4())
            self._emit({
                "type": "confirmation_required",
                "id": confirm_id,
                "action": action,
            })
            self._confirm_event.wait(timeout=300)
            self._confirm_event.clear()
            return self._confirm_result

        # CLI mode: rich prompt
        console.print(Panel(
            f"[yellow]{action}[/yellow]",
            title="[bold red]Confirmation Required[/bold red]",
            border_style="red",
        ))
        ans = console.input("[bold]Proceed? (yes/no): [/bold]").strip().lower()
        return ans in ("yes", "y")

    def resolve_confirmation(self, answer: bool) -> None:
        """Called by the web server when the user answers a confirmation dialog."""
        self._confirm_result = answer
        if self._confirm_event:
            self._confirm_event.set()

    def _parse_issue_from_response(
        self, description: str, response_text: str, issue: IssueRecord
    ) -> IssueRecord:
        issue.description = description
        issue.conversation_summary = response_text

        lines = response_text.splitlines()
        current_section = None
        section_content: list[str] = []

        def save_section() -> None:
            if current_section and section_content:
                text = "\n".join(section_content).strip()
                if "root cause" in current_section:
                    issue.root_cause = text
                elif "fix applied" in current_section:
                    issue.fix_applied = text
                elif "verification" in current_section:
                    issue.verification_steps = [
                        ln.lstrip("- *").strip()
                        for ln in text.splitlines()
                        if ln.strip()
                    ]
                elif "prevention" in current_section:
                    issue.prevention = text

        for line in lines:
            lower = line.lower()
            if "**root cause**" in lower or "## root cause" in lower:
                save_section(); current_section = "root cause"; section_content = []
            elif "**fix applied**" in lower or "## fix" in lower:
                save_section(); current_section = "fix applied"; section_content = []
            elif "**verification**" in lower or "## verification" in lower:
                save_section(); current_section = "verification"; section_content = []
            elif "**prevention**" in lower or "## prevention" in lower:
                save_section(); current_section = "prevention"; section_content = []
            elif current_section:
                section_content.append(line)

        save_section()

        tools_used = {log["tool"] for log in self._tool_call_log}
        if "restart_deployment" in tools_used or "rollback_deployment" in tools_used:
            issue.resolved = True

        return issue

    def reset_conversation(self) -> None:
        self._messages.clear()
        self._tool_call_log.clear()
