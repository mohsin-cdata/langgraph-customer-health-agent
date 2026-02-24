"""MCP tool wrappers for CData Connect AI.

Provides 5 @tool-decorated functions for the ReAct agent to discover
schemas and query data through CData Connect AI's MCP endpoint.
"""
import base64
import json

import requests
from langchain_core.tools import tool

from config import CDATA_EMAIL, CDATA_PAT, MCP_ENDPOINT, CDATA_CATALOG
from logger import get_logger, track

log = get_logger("mcp")

# Shared session with Basic Auth
_session = requests.Session()
_credentials = f"{CDATA_EMAIL}:{CDATA_PAT}"
_encoded = base64.b64encode(_credentials.encode()).decode()
_session.headers.update({
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
})

_request_id = 0
_initialized = False


def _call_mcp(method: str, params: dict) -> dict:
    """Send a JSON-RPC 2.0 request to the MCP endpoint."""
    global _request_id
    _request_id += 1
    track("mcp_calls")

    payload = {
        "jsonrpc": "2.0",
        "id": _request_id,
        "method": method,
        "params": params,
    }

    resp = _session.post(MCP_ENDPOINT, json=payload, timeout=60, stream=True)
    resp.raise_for_status()

    # Parse SSE response
    text = resp.text.strip()
    json_str = ""
    for line in text.split("\n"):
        if line.startswith("data: "):
            json_str = line[6:].strip()
    if not json_str:
        json_str = text

    result = json.loads(json_str)
    if "error" in result and result["error"]:
        raise RuntimeError(
            f"MCP error: {result['error'].get('message', 'Unknown')}"
        )
    return result.get("result", {})


def _extract_text(result: dict) -> str:
    """Extract text content from an MCP tool response."""
    if isinstance(result, dict) and "content" in result:
        for item in result.get("content", []):
            if item.get("type") == "text":
                return item.get("text", "")
    return str(result)


def _ensure_initialized():
    """Initialize MCP connection if not already done."""
    global _initialized
    if not _initialized:
        _call_mcp("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "LangGraphHealthAgent", "version": "2.0"},
        })
        _initialized = True
        log.debug("MCP connection initialized", extra={"node": "mcp"})


@tool
def get_catalogs() -> str:
    """List all available data source connections (catalogs) in CData Connect AI.

    Call this first to discover what data sources are available.
    Returns a list of catalog names.
    """
    _ensure_initialized()
    if CDATA_CATALOG:
        return f"Available catalogs:\n- {CDATA_CATALOG}"
    result = _call_mcp("tools/call", {
        "name": "getCatalogs",
        "arguments": {},
    })
    return _extract_text(result)


@tool
def get_schemas(catalog_name: str) -> str:
    """List schemas available in a specific catalog (data source connection).

    Args:
        catalog_name: The catalog name returned by get_catalogs.
    """
    _ensure_initialized()
    result = _call_mcp("tools/call", {
        "name": "getSchemas",
        "arguments": {"catalogName": catalog_name},
    })
    return _extract_text(result)


@tool
def get_tables(catalog_name: str, schema_name: str) -> str:
    """List tables available in a catalog and schema.

    Args:
        catalog_name: The catalog name.
        schema_name: The schema name returned by get_schemas.
    """
    _ensure_initialized()
    result = _call_mcp("tools/call", {
        "name": "getTables",
        "arguments": {"catalogName": catalog_name, "schemaName": schema_name},
    })
    return _extract_text(result)


@tool
def get_columns(catalog_name: str, schema_name: str, table_name: str) -> str:
    """Get column details for a specific table.

    Args:
        catalog_name: The catalog name.
        schema_name: The schema name.
        table_name: The table name.
    """
    _ensure_initialized()
    result = _call_mcp("tools/call", {
        "name": "getColumns",
        "arguments": {
            "catalogName": catalog_name,
            "schemaName": schema_name,
            "tableName": table_name,
        },
    })
    return _extract_text(result)


@tool
def query_data(sql_query: str) -> str:
    """Execute a SQL SELECT query against CData Connect AI.

    Use fully qualified table names: [Catalog].[Schema].[Table]
    Quote column names with square brackets: [ColumnName]

    Args:
        sql_query: The SQL SELECT query to execute.
    """
    _ensure_initialized()
    result = _call_mcp("tools/call", {
        "name": "queryData",
        "arguments": {"query": sql_query},
    })
    return _extract_text(result)
