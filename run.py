"""Interactive runner for the LangGraph Customer Health Agent.

Run with:  python run.py
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Auto-install rich if missing
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Installing rich library...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "rich", "-q"],
    )
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.text import Text

console = Console()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
SRC_DIR = ROOT / "src"
CACHE_FILE = Path.home() / ".cache" / "langgraph-health" / "schema.json"

# ---------------------------------------------------------------------------
# LLM provider configs
# ---------------------------------------------------------------------------
PROVIDERS = {
    "1": {
        "name": "OpenAI",
        "provider": "openai",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default_model": "gpt-4o",
        "key_var": "OPENAI_API_KEY",
        "key_hint": "sk-proj-...",
        "extra_vars": {},
    },
    "2": {
        "name": "Google Gemini",
        "provider": "google",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "default_model": "gemini-2.0-flash",
        "key_var": "GOOGLE_API_KEY",
        "key_hint": "AIza...",
        "extra_vars": {},
    },
    "3": {
        "name": "DeepSeek",
        "provider": "openai",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "key_var": "OPENAI_API_KEY",
        "key_hint": "sk-...",
        "extra_vars": {"OPENAI_API_BASE": "https://api.deepseek.com"},
    },
}

# ---------------------------------------------------------------------------
# Sample data for suggestions
# ---------------------------------------------------------------------------
SAMPLE_ACCOUNTS = [
    "Premium Auto Group Europe",
    "Nordic Energy Solutions",
    "Pacific Rim Logistics",
]

SAMPLE_QUERIES = [
    "Show me the top 10 customers by annual revenue",
    "Which industries have the most high-priority open tickets?",
    "How many open opportunities do we have and what is the total value?",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_env_file():
    """Parse .env without python-dotenv dependency."""
    if not ENV_FILE.exists():
        return {}
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _run_main(*args):
    """Run src/main.py with the given arguments."""
    cmd = [sys.executable, str(SRC_DIR / "main.py")] + list(args)
    console.print(f"\n[dim]> {' '.join(cmd)}[/dim]\n")
    console.rule(style="dim")
    result = subprocess.run(cmd, cwd=str(ROOT))
    console.rule(style="dim")
    return result.returncode


# ---------------------------------------------------------------------------
# Banner & menu
# ---------------------------------------------------------------------------
def show_banner():
    console.print()
    console.print(
        Panel(
            "[bold white]LangGraph Customer Health Agent[/bold white]\n"
            "[dim]Autonomous data discovery and analysis powered by "
            "CData Connect AI[/dim]",
            border_style="blue",
            padding=(1, 2),
        )
    )
    console.print()


def show_menu():
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=4)
    table.add_column()
    table.add_row("1.", "Setup wizard  [dim](configure credentials & LLM provider)[/dim]")
    table.add_row("2.", "Run health analysis  [dim](for a specific account)[/dim]")
    table.add_row("3.", "Run open-ended query  [dim](ask anything about your data)[/dim]")
    table.add_row("4.", "Refresh schema cache")
    table.add_row("5.", "Check setup  [dim](verify credentials & MCP connection)[/dim]")
    table.add_row("0.", "Exit")
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# 1. Setup wizard
# ---------------------------------------------------------------------------
def setup_wizard():
    console.print("\n[bold blue]--- Setup Wizard ---[/bold blue]\n")

    if ENV_FILE.exists():
        if not Confirm.ask(
            "[yellow].env already exists.[/yellow] Reconfigure?", default=False
        ):
            return

    # ---- CData credentials ----
    console.print("[bold]Step 1: CData Connect AI Credentials[/bold]")
    console.print(
        "[dim]Sign up or log in at https://cloud.cdata.com/\n"
        "Create a PAT under Settings > Access Tokens[/dim]\n"
    )
    email = Prompt.ask("  CData email")
    pat = Prompt.ask("  CData PAT (Personal Access Token)")

    # ---- Optional catalog ----
    catalog = ""
    console.print()
    if Confirm.ask(
        "Force a specific catalog? [dim](recommended for demos to skip discovery)[/dim]",
        default=False,
    ):
        catalog = Prompt.ask("  Catalog name")

    # ---- LLM provider ----
    console.print("\n[bold]Step 2: LLM Provider[/bold]\n")
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("#", style="bold cyan", width=3)
    table.add_column("Provider")
    table.add_column("Default Model", style="dim")
    for key, cfg in PROVIDERS.items():
        table.add_row(key, cfg["name"], cfg["default_model"])
    console.print(table)
    console.print(
        "\n[dim]To add more providers (Anthropic, Ollama, Grok), edit .env after setup.\n"
        "Set LLM_PROVIDER and LLM_MODEL -- see README > Multi-Provider LLM Support.[/dim]\n"
    )

    choice = Prompt.ask("  Select provider", choices=["1", "2", "3"], default="1")
    provider_cfg = PROVIDERS[choice]

    # ---- Model selection ----
    models = provider_cfg["models"]
    console.print(f"\n  Available models for {provider_cfg['name']}:")
    for i, m in enumerate(models, 1):
        suffix = " [dim](default)[/dim]" if m == provider_cfg["default_model"] else ""
        console.print(f"    [cyan]{i}.[/cyan] {m}{suffix}")
    console.print()
    model_choice = Prompt.ask(
        "  Select model",
        choices=[str(i) for i in range(1, len(models) + 1)],
        default="1",
    )
    model = models[int(model_choice) - 1]

    # ---- API key ----
    console.print()
    api_key = Prompt.ask(
        f"  {provider_cfg['name']} API key [dim]({provider_cfg['key_hint']})[/dim]",
        password=True,
    )

    # ---- Build .env ----
    lines = [
        "# CData Connect AI",
        f"CDATA_EMAIL={email}",
        f"CDATA_PAT={pat}",
        "",
        "# LLM Provider",
        f"LLM_PROVIDER={provider_cfg['provider']}",
        f"LLM_MODEL={model}",
        f"{provider_cfg['key_var']}={api_key}",
    ]

    for var, val in provider_cfg.get("extra_vars", {}).items():
        lines.append(f"{var}={val}")

    if catalog:
        lines.extend(["", f"# Demo catalog (skip catalog discovery)", f"CDATA_CATALOG={catalog}"])

    lines.extend([
        "",
        "# Optional (uncomment to customize)",
        "# SCHEMA_CACHE_TTL=86400",
        "# LOG_LEVEL=INFO",
        "# MAX_ITERATIONS=25",
    ])

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print("\n[bold green]Setup complete![/bold green] Credentials saved to .env")
    console.print("[dim]Run option 5 (Check setup) to verify the connection.[/dim]")


# ---------------------------------------------------------------------------
# 2. Run health analysis
# ---------------------------------------------------------------------------
def run_health_analysis():
    console.print("\n[bold blue]--- Health Analysis ---[/bold blue]\n")
    console.print(
        "Examples from the demo dataset [dim](type any account name from your data source)[/dim]:"
    )
    for i, name in enumerate(SAMPLE_ACCOUNTS, 1):
        console.print(f"  [cyan]{i}.[/cyan] {name}")
    console.print()

    account = Prompt.ask("Enter account name [dim](or pick 1-3 for examples)[/dim]")
    if account in ("1", "2", "3"):
        account = SAMPLE_ACCOUNTS[int(account) - 1]

    verbose = Confirm.ask("Verbose output?", default=False)

    args = ["--account", account]
    if verbose:
        args.append("--verbose")

    _run_main(*args)


# ---------------------------------------------------------------------------
# 3. Run open-ended query
# ---------------------------------------------------------------------------
def run_open_query():
    console.print("\n[bold blue]--- Open-Ended Query ---[/bold blue]\n")
    console.print("Example queries [dim](type any question about your data)[/dim]:")
    for i, q in enumerate(SAMPLE_QUERIES, 1):
        console.print(f"  [cyan]{i}.[/cyan] {q}")
    console.print()

    query = Prompt.ask("Enter your question [dim](or pick 1-3 for examples)[/dim]")
    if query in ("1", "2", "3"):
        query = SAMPLE_QUERIES[int(query) - 1]

    verbose = Confirm.ask("Verbose output?", default=False)

    args = [query]
    if verbose:
        args.append("--verbose")

    _run_main(*args)


# ---------------------------------------------------------------------------
# 4. Refresh schema cache
# ---------------------------------------------------------------------------
def refresh_cache():
    console.print()
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        console.print("[green]Schema cache cleared.[/green] Next run will re-discover schemas.")
    else:
        console.print("[yellow]No cache file found.[/yellow] Nothing to clear.")


# ---------------------------------------------------------------------------
# 5. Check setup
# ---------------------------------------------------------------------------
def check_setup():
    console.print("\n[bold blue]--- Setup Check ---[/bold blue]\n")

    # ---- .env file ----
    if not ENV_FILE.exists():
        console.print("[red]No .env file found.[/red] Run the setup wizard first (option 1).")
        return

    console.print("[green]OK[/green]  .env file found")

    env = _load_env_file()

    # ---- Required CData vars ----
    missing = [v for v in ("CDATA_EMAIL", "CDATA_PAT") if not env.get(v)]
    if missing:
        console.print(f"[red]MISSING[/red]  Required variables: {', '.join(missing)}")
        return
    console.print("[green]OK[/green]  CData credentials configured")

    # ---- LLM config ----
    provider = env.get("LLM_PROVIDER", "openai")
    model = env.get("LLM_MODEL", "gpt-4o")
    console.print(f"[green]OK[/green]  LLM provider: {provider} ({model})")

    # ---- API key ----
    key_var = "GOOGLE_API_KEY" if provider == "google" else "OPENAI_API_KEY"
    if env.get(key_var):
        masked = env[key_var][:8] + "..." + env[key_var][-4:] if len(env[key_var]) > 12 else "***"
        console.print(f"[green]OK[/green]  {key_var} configured ({masked})")
    else:
        console.print(f"[yellow]WARN[/yellow]  {key_var} not found in .env")

    # ---- Optional catalog ----
    if env.get("CDATA_CATALOG"):
        console.print(f"[green]OK[/green]  CDATA_CATALOG: {env['CDATA_CATALOG']}")
    else:
        console.print("[dim]--[/dim]  CDATA_CATALOG not set (agent will discover catalogs)")

    # ---- MCP connection test ----
    console.print("\n[dim]Testing MCP connection...[/dim]")
    try:
        import base64
        import json
        import urllib.request
        import urllib.error

        creds = f"{env['CDATA_EMAIL']}:{env['CDATA_PAT']}"
        encoded = base64.b64encode(creds.encode()).decode()

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "health-agent-check", "version": "1.0"},
            },
        }).encode()

        req = urllib.request.Request(
            "https://mcp.cloud.cdata.com/mcp",
            data=payload,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )

        start = time.time()
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - start
            if resp.status == 200:
                console.print(
                    f"[bold green]OK[/bold green]  MCP connection successful ({elapsed:.1f}s)"
                )
            else:
                console.print(f"[red]FAIL[/red]  MCP returned status {resp.status}")
    except urllib.error.HTTPError as e:
        console.print(f"[red]FAIL[/red]  MCP error: HTTP {e.code}")
    except Exception as e:
        console.print(f"[red]FAIL[/red]  MCP connection failed: {e}")

    # ---- Schema cache ----
    if CACHE_FILE.exists():
        age_h = (time.time() - CACHE_FILE.stat().st_mtime) / 3600
        console.print(f"[green]OK[/green]  Schema cache exists (age: {age_h:.1f}h)")
    else:
        console.print("[dim]--[/dim]  No schema cache (will be created on first run)")

    # ---- Dependencies check ----
    console.print()
    deps_ok = True
    for pkg, imp in [("langgraph", "langgraph"), ("langchain-core", "langchain_core"),
                      ("requests", "requests"), ("jinja2", "jinja2")]:
        try:
            __import__(imp)
            console.print(f"[green]OK[/green]  {pkg}")
        except ImportError:
            console.print(f"[red]MISSING[/red]  {pkg}  [dim](pip install -r requirements.txt)[/dim]")
            deps_ok = False

    if deps_ok:
        console.print("\n[bold green]All checks passed![/bold green] Ready to run.")
    else:
        console.print(
            "\n[yellow]Some dependencies missing.[/yellow] "
            "Run: [bold]pip install -r requirements.txt[/bold]"
        )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    show_banner()

    try:
        while True:
            show_menu()
            choice = Prompt.ask(
                "Select option",
                choices=["0", "1", "2", "3", "4", "5"],
                default="0",
            )

            if choice == "0":
                console.print("\n[dim]Session closed.[/dim]\n")
                break
            elif choice == "1":
                setup_wizard()
            elif choice == "2":
                run_health_analysis()
            elif choice == "3":
                run_open_query()
            elif choice == "4":
                refresh_cache()
            elif choice == "5":
                check_setup()

            console.print()
    except KeyboardInterrupt:
        console.print("\n\n[dim]Session closed.[/dim]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
