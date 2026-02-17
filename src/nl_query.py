"""
Natural Language Query Parser - Convert English to SQL
Uses an OpenAI-compatible LLM to interpret user intent and generate appropriate SQL queries.
"""
import os
import requests
import json
from typing import Dict, Any, List
from datetime import datetime
from mcp_client_production import MCPClientProduction
from config import Config


class NLQueryParser:
    """Convert natural language queries to SQL and execute them."""

    def __init__(self):
        self.mcp_client = MCPClientProduction()
        self.api_key = Config.OPENAI_API_KEY
        self.api_url = Config.OPENAI_API_URL
        self.model = Config.OPENAI_MODEL
        # Set connection based on data source
        self.connection = Config.GOOGLE_SHEETS_CONNECTION if Config.DATA_SOURCE == "google_sheets" else Config.SALESFORCE_CONNECTION

    def parse_to_sql(self, nl_query: str) -> str:
        """Convert natural language query to SQL using LLM."""

        # Determine schema and tables based on data source
        if Config.DATA_SOURCE == "salesforce":
            schema = "Salesforce"
            tables = "Account, Opportunity, Case"
            example1 = f"SELECT TOP 10 [Name], [AnnualRevenue] FROM [{self.connection}].[Salesforce].[Account] ORDER BY [AnnualRevenue] DESC"
            example2 = f"SELECT [Name], [Industry], [AnnualRevenue] FROM [{self.connection}].[Salesforce].[Account] WHERE [Industry] = 'Energy'"
            example3 = f"SELECT COUNT(*) as [OpenCases] FROM [{self.connection}].[Salesforce].[Case] WHERE [Status] = 'Open'"
        else:  # google_sheets
            schema = "GoogleSheets"
            tables = "demo_organization_account, demo_organization_opportunity, demo_organization_tickets"
            example1 = f"SELECT TOP 10 [Name], [AnnualRevenue] FROM [{self.connection}].[GoogleSheets].[demo_organization_account] ORDER BY [AnnualRevenue] DESC"
            example2 = f"SELECT [Name], [Industry], [AnnualRevenue] FROM [{self.connection}].[GoogleSheets].[demo_organization_account] WHERE [Industry] = 'Energy'"
            example3 = f"SELECT COUNT(*) as [OpenTickets] FROM [{self.connection}].[GoogleSheets].[demo_organization_tickets] WHERE [Status] = 'Open'"

        prompt = f"""You are a CRM SQL expert. Convert the following natural language query to a valid SQL query.

IMPORTANT RULES:
1. Connection name: [{self.connection}]
2. Schema: [{schema}]
3. Available tables: {tables}
4. Use proper column names (with square brackets): [Id], [Name], [Amount], [StageName], [Status], [Priority], [AccountId], [AnnualRevenue], [NumberOfEmployees], [CloseDate], [IsClosed]
5. For "top N" queries, use TOP N or ORDER BY ... LIMIT N
6. Always return complete, executable SQL
7. Do NOT include markdown formatting, code blocks, or explanations
8. Return ONLY the SQL query

Examples:
- "Top 10 customers by revenue" → {example1}
- "Show me accounts in the energy industry" → {example2}
- "How many open support tickets do we have?" → {example3}

User query: {nl_query}

SQL Query:"""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.3  # Lower temperature for deterministic SQL
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            sql_query = response.json()["choices"][0]["message"]["content"].strip()

            # Clean up the SQL if it has code block markers
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.startswith("```"):
                sql_query = sql_query[3:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]

            return sql_query.strip()

        except Exception as e:
            raise Exception(f"Failed to parse natural language query: {str(e)}")

    def execute_nl_query(self, nl_query: str) -> Dict[str, Any]:
        """Execute a natural language query end-to-end."""

        print(f"[*] Parsing natural language query...")
        print(f"    User: {nl_query}\n")

        # Convert to SQL
        sql_query = self.parse_to_sql(nl_query)
        print(f"[*] Generated SQL:")
        print(f"    {sql_query}\n")

        # Initialize MCP client
        if not self.mcp_client.initialize():
            raise Exception("Failed to initialize MCP connection")

        # Execute SQL
        print(f"[*] Executing query...")
        results = self.mcp_client.query_data(sql_query)

        if not results:
            print(f"[!] Query returned no results")
            return {
                "nl_query": nl_query,
                "sql_query": sql_query,
                "results": [],
                "count": 0
            }

        print(f"[OK] Query returned {len(results)} rows\n")

        return {
            "nl_query": nl_query,
            "sql_query": sql_query,
            "results": results,
            "count": len(results)
        }

    def generate_insights(self, query_result: Dict[str, Any]) -> str:
        """Generate natural language insights from query results."""

        results = query_result.get("results", [])
        nl_query = query_result.get("nl_query", "")

        if not results:
            return "No data found for your query."

        # Use LLM to generate insights
        result_summary = json.dumps(results[:5], indent=2, default=str)  # First 5 rows

        prompt = f"""Analyze these query results and provide a brief, actionable insight for a business user.

User Query: {nl_query}
Total Rows: {len(results)}

Sample Results (first 5 rows):
{result_summary}

Provide 2-3 sentences of key insights. Focus on business implications, not just data facts."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            return response.json()["choices"][0]["message"]["content"].strip()

        except Exception as e:
            return f"(Could not generate insights: {str(e)})"

    def generate_html_brief(self, query_result: Dict[str, Any]) -> str:
        """Generate beautiful HTML brief from query results."""
        import markdown

        nl_query = query_result.get("nl_query", "")
        sql_query = query_result.get("sql_query", "")
        results = query_result.get("results", [])
        count = query_result.get("count", 0)
        insights = self.generate_insights(query_result)

        # Convert markdown to HTML
        insights_html = markdown.markdown(insights)

        if not results:
            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Query Results</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 40px 20px; min-height: 100vh; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
        .content {{ padding: 40px; }}
        .content p {{ color: #999; font-size: 1.1em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Query Results</h1>
            <div class="subtitle">No results found</div>
        </div>
        <div class="content">
            <p>Your query returned no results. Please try broadening your search criteria.</p>
        </div>
    </div>
</body>
</html>"""

        # Build results table HTML
        columns = list(results[0].keys())
        table_rows = ""

        for row in results:
            row_html = "<tr>"
            for col in columns:
                value = row.get(col, "")
                # Format numeric values with commas
                if isinstance(value, (int, float)):
                    if isinstance(value, float) and value == int(value):
                        value = f"{int(value):,}"
                    else:
                        value = f"{value:,}"
                row_html += f"<td>{value}</td>"
            row_html += "</tr>"
            table_rows += row_html

        header_row = "".join(f"<th>{col}</th>" for col in columns)

        # Calculate summary statistics for results
        summary_stats_html = ""
        numeric_cols = []
        for col in columns:
            values = [r.get(col) for r in results if isinstance(r.get(col), (int, float))]
            if values:
                numeric_cols.append((col, values))

        if numeric_cols:
            summary_stats_html = '<div class="signals-grid">'
            summary_stats_html += f'<div class="signal-card"><div class="signal-label">Total Rows</div><div class="signal-value">{count:,}</div></div>'
            for col, values in numeric_cols[:3]:  # Show top 3 numeric columns
                summary_stats_html += f'<div class="signal-card"><div class="signal-label">{col} Avg</div><div class="signal-value">${sum(values)/len(values):,.0f}</div></div>'
            summary_stats_html += '</div>'

        brief = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Query Results: {nl_query[:50]}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 40px 20px; min-height: 100vh; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .subtitle {{ font-size: 1.1em; opacity: 0.9; }}
        .content-section {{ padding: 40px; border-bottom: 1px solid #e9ecef; }}
        .content-section h2 {{ color: #2d3748; font-size: 1.8em; margin-bottom: 25px; }}
        .query-info {{ background: #f5f7fa; padding: 20px; border-radius: 8px; margin-bottom: 30px; font-family: 'Courier New', monospace; font-size: 0.9em; color: #333; line-height: 1.6; word-break: break-word; }}
        .query-label {{ color: #667eea; font-weight: bold; margin-top: 15px; }}
        .query-label:first-child {{ margin-top: 0; }}
        .results-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .results-table th {{ background: #667eea; color: white; padding: 15px 20px; text-align: left; }}
        .results-table td {{ padding: 15px 20px; border-bottom: 1px solid #e9ecef; }}
        .results-table tr:hover {{ background: #f5f7fa; }}
        .results-count {{ background: #667eea; color: white; padding: 12px 20px; border-radius: 6px; display: inline-block; font-weight: bold; margin-bottom: 20px; }}
        .signals-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .signal-card {{ background: #f5f7fa; padding: 25px; border-radius: 10px; text-align: center; border-left: 4px solid #667eea; }}
        .signal-label {{ color: #666; font-size: 0.9em; margin-bottom: 8px; text-transform: uppercase; }}
        .signal-value {{ font-size: 2.5em; font-weight: 700; color: #2d3748; }}
        .insights-box {{ background: #f0f4ff; border-left: 4px solid #667eea; padding: 25px; border-radius: 8px; margin: 20px 0; }}
        .insights-box h3 {{ color: #667eea; margin-bottom: 15px; }}
        .insights-box p {{ color: #2d3748; line-height: 1.8; margin-bottom: 15px; }}
        .insights-box strong {{ color: #667eea; }}
        .insights-box ul {{ margin-left: 20px; }}
        .insights-box li {{ margin-bottom: 10px; color: #2d3748; line-height: 1.6; }}
        .footer {{ background: #f8f9fa; padding: 20px 40px; text-align: center; color: #999; border-top: 1px solid #e9ecef; font-size: 0.9em; }}
        .table-wrapper {{ overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Query Results</h1>
            <div class="subtitle">{nl_query}</div>
        </div>

        <div class="content-section">
            <h2>Query Information</h2>
            <div class="query-info">
                <div class="query-label">Natural Language Query:</div>
                {nl_query}
                <div class="query-label">Generated SQL:</div>
                {sql_query}
            </div>
        </div>

        <div class="content-section">
            <h2>Results Summary</h2>
            {summary_stats_html}
        </div>

        <div class="content-section">
            <h2>Data Results</h2>
            <div class="results-count">[OK] {count} row(s) returned</div>
            <div class="table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>{header_row}</tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="content-section">
            <h2>Business Insights & Recommendations</h2>
            <div class="insights-box">
                {insights_html}
            </div>
        </div>

        <div class="footer">
            <p>Generated by LangGraph Customer Health Agent &mdash; Natural Language Query Mode</p>
            <p>Query executed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}</p>
        </div>
    </div>
</body>
</html>"""

        return brief
