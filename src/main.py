"""
Main entry point for LangGraph Customer Health Agent CLI

Modes:
1. Account Mode: python src/main.py --account "Flashdog"
2. Query Mode: python src/main.py --query "SELECT TOP 10 [Name], [AnnualRevenue] FROM [...]"
"""
import argparse
import sys
import os
import json
from datetime import datetime
from langgraph_agent import run_agent
from mcp_client_production import MCPClientProduction
from nl_query import NLQueryParser
from config import Config


def run_account_health(account_name: str):
    """Run full health analysis for an account"""
    print(f"[*] Gathering account data for: {account_name}")
    brief = run_agent(account_name)

    if brief:
        print("\n" + "=" * 70)
        print(brief[:500] + "..." if len(brief) > 500 else brief)
        print("=" * 70)
        return 0
    else:
        print("\n[!] Agent failed to generate brief. Check errors above.")
        return 1


def run_nl_query(nl_query: str):
    """Run a natural language query (English to SQL conversion)"""
    try:
        parser = NLQueryParser()
        query_result = parser.execute_nl_query(nl_query)

        results = query_result.get("results", [])
        if not results:
            print("[!] Query returned no results")
            return 1

        # Display results in formatted table
        print(f"[RESULT] {query_result['count']} rows returned\n")

        columns = list(results[0].keys())
        col_widths = {col: max(len(col), max(len(str(row.get(col, ""))) for row in results)) for col in columns}

        # Print header
        header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
        print(header)
        print("-" * len(header))

        # Print rows (limit to first 20 for readability)
        for row in results[:20]:
            print(" | ".join(f"{str(row.get(col, '')):<{col_widths[col]}}" for col in columns))

        if len(results) > 20:
            print(f"... and {len(results) - 20} more rows")

        # Generate insights
        print(f"\n[INSIGHTS]")
        insights = parser.generate_insights(query_result)
        print(f"{insights}\n")

        # Save results to both JSON and HTML in output folder
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save JSON
        json_file = f"output/nl_query_results_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(query_result, f, indent=2, default=str)

        # Save HTML
        html_brief = parser.generate_html_brief(query_result)
        html_file = f"output/{timestamp}_nl_query_brief.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_brief)

        print(f"[OK] JSON results saved to: {json_file}")
        print(f"[OK] HTML brief saved to: {html_file}")
        return 0

    except Exception as e:
        print(f"[!] Query failed: {str(e)}")
        return 1


def run_custom_query(query: str):
    """Run a custom SQL query and display results"""
    print(f"[*] Executing custom query...")

    try:
        client = MCPClientProduction()
        if not client.initialize():
            print("[!] Failed to initialize MCP connection")
            return 1

        results = client.query_data(query)

        if not results:
            print("[!] Query returned no results")
            return 1

        # Display results in formatted table
        print(f"\n[RESULT] Query returned {len(results)} rows\n")

        # Get column names from first row
        if results:
            columns = list(results[0].keys())
            col_widths = {col: max(len(col), max(len(str(row.get(col, ""))) for row in results)) for col in columns}

            # Print header
            header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
            print(header)
            print("-" * len(header))

            # Print rows
            for row in results:
                print(" | ".join(f"{str(row.get(col, '')):<{col_widths[col]}}" for col in columns))

        # Save results to JSON in output folder
        os.makedirs("output", exist_ok=True)
        output_file = f"output/query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n[OK] Results saved to: {output_file}")
        return 0

    except Exception as e:
        print(f"[!] Query execution failed: {str(e)}")
        return 1


def main():
    """CLI interface for running the customer health agent"""
    parser = argparse.ArgumentParser(
        description="LangGraph Customer Health Agent - Analyze Salesforce customer health via CData Connect AI MCP"
    )

    # Create mutually exclusive group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--account",
        type=str,
        help="Salesforce account name to analyze (e.g., 'Flashdog')"
    )
    group.add_argument(
        "--nlquery",
        type=str,
        help='Natural language query (e.g., "Show me the top 10 customers by revenue")'
    )
    group.add_argument(
        "--query",
        type=str,
        help='Custom SQL query (e.g., "SELECT TOP 10 [Name] FROM [LangGraph_Customer_Health_Agent].[Salesforce].[Account]")'
    )

    args = parser.parse_args()

    if args.account:
        return run_account_health(args.account)
    elif args.nlquery:
        return run_nl_query(args.nlquery)
    elif args.query:
        return run_custom_query(args.query)


if __name__ == "__main__":
    sys.exit(main())
