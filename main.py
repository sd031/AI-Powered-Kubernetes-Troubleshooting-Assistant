#!/usr/bin/env python3
"""
AI-Powered Kubernetes Troubleshooting Assistant
================================================
Entry point — provides a Typer CLI with three commands:

  chat   — interactive REPL (default)
  scan   — automated cluster health scan
  fix    — diagnose and fix a specific problem
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config import LLMProvider, Settings, get_settings
from k8s.client import K8sClient
from k8s.tools import K8sTools
from llm.factory import get_llm_provider
from agents.troubleshoot_agent import TroubleshootAgent
from runbook.generator import RunbookGenerator

app = typer.Typer(
    name="k8s-ai",
    help="AI-Powered Kubernetes Troubleshooting Assistant",
    add_completion=False,
)
console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _print_banner(settings: Settings, k8s: K8sClient) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("LLM Provider", f"[cyan]{settings.llm_provider.value}[/cyan]")
    table.add_row(
        "Model",
        f"[cyan]"
        + {
            LLMProvider.OLLAMA: settings.ollama_model,
            LLMProvider.BEDROCK: settings.bedrock_model_id,
            LLMProvider.OPENAI: settings.openai_model,
        }[settings.llm_provider]
        + "[/cyan]",
    )
    table.add_row("K8s Context", f"[green]{k8s.current_context()}[/green]")
    table.add_row("K8s Version", f"[green]{k8s.server_version()}[/green]")
    table.add_row("Runbooks Dir", str(settings.runbook_dir))
    table.add_row("Auto-fix", "[red]ON[/red]" if settings.auto_fix else "[yellow]OFF[/yellow]")
    console.print(Panel(table, title="[bold]K8s AI Troubleshooter[/bold]", border_style="blue"))


def _build_components(settings: Settings):
    with console.status("[bold green]Connecting to Kubernetes cluster…"):
        k8s_client = K8sClient(
            kubeconfig=settings.effective_kubeconfig(),
            context=settings.k8s_context or None,
        )

    with console.status("[bold green]Initializing LLM provider…"):
        llm = get_llm_provider(settings)

    k8s_tools = K8sTools(
        k8s=k8s_client,
        max_log_lines=settings.max_log_lines,
        auto_fix=settings.auto_fix,
    )

    runbook_gen = RunbookGenerator(
        output_dir=settings.ensure_runbook_dir(),
        cluster_context=k8s_client.current_context(),
        llm_provider=f"{llm.provider_name()} / {llm.model_name()}",
    )

    def on_issue_resolved(issue):
        path = runbook_gen.generate(issue)
        runbook_gen.generate_index()
        console.print(
            f"\n[bold green]📄 Runbook saved:[/bold green] [link={path}]{path}[/link]"
        )

    agent = TroubleshootAgent(
        llm=llm,
        k8s_tools=k8s_tools,
        runbook_callback=on_issue_resolved,
    )

    return k8s_client, llm, agent, runbook_gen


# ──────────────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def chat(
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider override: ollama | bedrock | openai",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model override (e.g. llama3.2, gpt-4o)",
    ),
    context: Optional[str] = typer.Option(
        None, "--context", "-c",
        help="Kubernetes context to use",
    ),
    auto_fix: bool = typer.Option(
        False, "--auto-fix",
        help="Apply fixes without confirmation prompts",
    ),
    namespace: Optional[str] = typer.Option(
        None, "--namespace", "-n",
        help="Default namespace to investigate",
    ),
) -> None:
    """Start an interactive troubleshooting chat session."""
    settings = get_settings()
    _apply_overrides(settings, provider, model, context, auto_fix)

    try:
        k8s_client, llm, agent, _ = _build_components(settings)
    except Exception as e:
        console.print(f"[red]Startup error: {e}[/red]")
        raise typer.Exit(1)

    _print_banner(settings, k8s_client)
    agent.run_interactive()


@app.command()
def scan(
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    context: Optional[str] = typer.Option(None, "--context", "-c"),
    auto_fix: bool = typer.Option(False, "--auto-fix"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Save scan results to a file",
    ),
) -> None:
    """Scan the cluster for issues and generate a runbook."""
    settings = get_settings()
    _apply_overrides(settings, provider, model, context, auto_fix)

    try:
        k8s_client, llm, agent, runbook_gen = _build_components(settings)
    except Exception as e:
        console.print(f"[red]Startup error: {e}[/red]")
        raise typer.Exit(1)

    _print_banner(settings, k8s_client)
    console.print("[bold]Starting comprehensive cluster scan…[/bold]\n")

    issue = agent.run_scan()

    path = runbook_gen.generate(issue)
    runbook_gen.generate_index()
    console.print(f"\n[bold green]Runbook saved:[/bold green] {path}")
    console.print(f"[bold green]Index updated:[/bold green] {settings.runbook_dir / 'index.md'}")

    if output:
        output.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        console.print(f"[green]Results also saved to:[/green] {output}")


@app.command()
def fix(
    problem: str = typer.Argument(..., help="Describe the problem in natural language"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    context: Optional[str] = typer.Option(None, "--context", "-c"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n"),
    auto_fix: bool = typer.Option(False, "--auto-fix"),
) -> None:
    """Diagnose and fix a specific Kubernetes problem."""
    settings = get_settings()
    _apply_overrides(settings, provider, model, context, auto_fix)

    try:
        k8s_client, llm, agent, runbook_gen = _build_components(settings)
    except Exception as e:
        console.print(f"[red]Startup error: {e}[/red]")
        raise typer.Exit(1)

    _print_banner(settings, k8s_client)

    full_problem = problem
    if namespace:
        full_problem = f"[Namespace: {namespace}] {problem}"

    console.print(f"\n[bold]Problem:[/bold] {full_problem}\n")
    issue = agent.run_diagnose(full_problem)

    path = runbook_gen.generate(issue)
    runbook_gen.generate_index()
    console.print(f"\n[bold green]Runbook saved:[/bold green] {path}")


@app.command()
def runbooks(
    list_all: bool = typer.Option(True, "--list/--no-list"),
) -> None:
    """List all generated runbooks."""
    settings = get_settings()
    runbook_dir = settings.runbook_dir

    if not runbook_dir.exists():
        console.print("[yellow]No runbooks directory found. Run a scan first.[/yellow]")
        raise typer.Exit()

    files = sorted(runbook_dir.glob("*.md"))
    files = [f for f in files if f.name != "index.md"]

    if not files:
        console.print("[yellow]No runbooks generated yet.[/yellow]")
        raise typer.Exit()

    table = Table(title="Generated Runbooks", show_header=True, header_style="bold blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("Runbook")
    table.add_column("Date", width=18)
    table.add_column("Path", style="dim")

    for i, path in enumerate(reversed(files), 1):
        try:
            from datetime import datetime
            dt = datetime.strptime(path.stem[:15], "%Y%m%d-%H%M%S")
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            date_str = "?"
        title = path.stem[16:].replace("-", " ").title()
        table.add_row(str(i), title, date_str, str(path))

    console.print(table)


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _apply_overrides(
    settings: Settings,
    provider: Optional[str],
    model: Optional[str],
    context: Optional[str],
    auto_fix: bool,
) -> None:
    if provider:
        settings.llm_provider = LLMProvider(provider)
    if model:
        if settings.llm_provider == LLMProvider.OLLAMA:
            settings.ollama_model = model
        elif settings.llm_provider == LLMProvider.OPENAI:
            settings.openai_model = model
        elif settings.llm_provider == LLMProvider.BEDROCK:
            settings.bedrock_model_id = model
    if context:
        settings.k8s_context = context
    if auto_fix:
        settings.auto_fix = True


if __name__ == "__main__":
    app()
