"""Tools for querying CRM data via CData MCP.

Supports both Salesforce and Google Sheets data sources.
Uses production MCP client implementing correct MCP protocol (tools/list, tools/call).
"""
from typing import Dict, List, Any
from mcp_client_production import MCPClientProduction
from config import Config


def get_connection_info():
    """Get connection name and schema based on data source."""
    if Config.DATA_SOURCE == "salesforce":
        return Config.SALESFORCE_CONNECTION, "Salesforce"
    else:  # google_sheets
        return Config.GOOGLE_SHEETS_CONNECTION, "GoogleSheets"


def get_table_name(table_type: str) -> str:
    """Get correct table name based on data source."""
    if Config.DATA_SOURCE == "salesforce":
        return table_type  # Account, Opportunity, Case
    else:  # google_sheets
        table_map = {
            "Account": "demo_organization_account",
            "Opportunity": "demo_organization_opportunity",
            "Case": "demo_organization_tickets"  # Google Sheets uses 'tickets' instead of 'Case'
        }
        return table_map.get(table_type, table_type)


def gather_account(account_name: str) -> Dict[str, Any]:
    """Query Account data via MCP (Salesforce or Google Sheets)."""
    try:
        client = MCPClientProduction()
        if not client.initialize():
            return None

        connection, schema = get_connection_info()
        account_table = get_table_name("Account")

        # Escape single quotes in account name
        safe_name = account_name.replace("'", "''")
        query = f"""SELECT [Id], [Name], [Industry], [AnnualRevenue], [NumberOfEmployees] FROM [{connection}].[{schema}].[{account_table}] WHERE [Name] = '{safe_name}'"""

        results = client.query_data(query)
        return results[0] if results else None

    except Exception as e:
        print(f"[MCP] Error querying account: {str(e)}")
        return None


def gather_opportunities(account_id: str) -> List[Dict[str, Any]]:
    """Query Opportunity data via MCP (Salesforce or Google Sheets)."""
    try:
        client = MCPClientProduction()
        if not client.initialize():
            return []

        connection, schema = get_connection_info()
        opportunity_table = get_table_name("Opportunity")

        query = f"""SELECT [Id], [Name], [StageName], [Amount], [CloseDate], [Probability], [IsClosed] FROM [{connection}].[{schema}].[{opportunity_table}] WHERE [AccountId] = '{account_id}'"""

        results = client.query_data(query)
        return results if results else []

    except Exception as e:
        print(f"[MCP] Error querying opportunities: {str(e)}")
        return []


def gather_cases(account_id: str) -> List[Dict[str, Any]]:
    """Query Support Tickets/Cases data via MCP (Salesforce or Google Sheets)."""
    try:
        client = MCPClientProduction()
        if not client.initialize():
            return []

        connection, schema = get_connection_info()
        case_table = get_table_name("Case")

        query = f"""SELECT [Id], [Subject], [Status], [Priority], [CreatedAt] FROM [{connection}].[{schema}].[{case_table}] WHERE [AccountId] = '{account_id}'"""

        results = client.query_data(query)
        return results if results else []

    except Exception as e:
        print(f"[MCP] Error querying cases: {str(e)}")
        return []
