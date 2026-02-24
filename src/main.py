"""CLI entry point for the LangGraph Customer Health Agent."""
import argparse
import os
import sys

from logger import start_run, print_summary, get_logger

log = get_logger("main")


def main():
    parser = argparse.ArgumentParser(
        description="LangGraph Customer Health Agent -- "
        "Analyze customer data via CData Connect AI"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help='Open-ended query (e.g., "Which industries have the highest revenue?")',
    )
    parser.add_argument(
        "--account",
        type=str,
        help='Account name shortcut (e.g., "Premium Auto Group Europe")',
    )
    parser.add_argument(
        "--refresh-schema",
        action="store_true",
        help="Force refresh of the schema cache",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args()

    # Set log level early so all modules pick it up
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Handle schema refresh
    if args.refresh_schema:
        from schema_cache import CACHE_FILE
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        log.info("Schema cache cleared", extra={"node": "main"})

    # Determine the user prompt
    if args.account:
        user_prompt = (
            f"Perform a complete health analysis for the account "
            f"'{args.account}'. Query all relevant tables (accounts, "
            f"opportunities, tickets/cases) and gather comprehensive data."
        )
    elif args.prompt:
        user_prompt = args.prompt
    else:
        parser.print_help()
        return 1

    start_run()

    from graph import build_graph
    from state import AgentState

    graph = build_graph()

    initial_state = {
        "messages": [],
        "user_prompt": user_prompt,
        "gathered_data": "",
        "analysis": "",
        "brief_path": "",
        "errors": [],
    }

    log.info(f"Starting agent: {user_prompt[:80]}...", extra={"node": "main"})

    result = graph.invoke(initial_state)

    if result.get("errors"):
        for err in result["errors"]:
            log.error(f"Error: {err}", extra={"node": "main"})
        return 1

    brief_path = result.get("brief_path", "")
    if brief_path:
        print(f"\n[OK] Health brief saved to: {brief_path}")

    print_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
