"""Schema cache for CData Connect AI metadata.

Caches discovered schema (catalogs, tables, columns) to disk so the
ReAct agent can skip discovery on subsequent runs within the TTL window.
"""
import json
import time
from pathlib import Path

from config import SCHEMA_CACHE_TTL

CACHE_DIR = Path.home() / ".cache" / "langgraph-health"
CACHE_FILE = CACHE_DIR / "schema.json"


def is_valid() -> bool:
    """Check if the cache exists and is within TTL."""
    if not CACHE_FILE.exists():
        return False
    age = time.time() - CACHE_FILE.stat().st_mtime
    return age < SCHEMA_CACHE_TTL


def load() -> dict:
    """Load cached schema data."""
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save(schema_data: dict):
    """Save schema data to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(schema_data, f, indent=2)


def discover_and_cache() -> dict:
    """Discover schema via deterministic MCP calls and cache the result.

    Calls getCatalogs, getSchemas, and getTables to build a schema map.
    No LLM needed -- purely deterministic MCP metadata calls.
    """
    from mcp_tools import _call_mcp, _extract_text, _ensure_initialized
    from config import CDATA_CATALOG
    from logger import get_logger

    log = get_logger("cache")
    _ensure_initialized()

    schema = {"discovered_at": time.time(), "catalogs": {}}

    # Get catalogs
    if CDATA_CATALOG:
        catalog_names = [CDATA_CATALOG]
        log.info(f"Using forced catalog: {CDATA_CATALOG}", extra={"node": "cache"})
    else:
        result = _call_mcp("tools/call", {
            "name": "getCatalogs", "arguments": {},
        })
        catalogs_text = _extract_text(result)
        schema["catalogs_raw"] = catalogs_text
        # Parse catalog names from CSV/text response
        catalog_names = [
            line.strip().strip('"').strip(",")
            for line in catalogs_text.split("\n")
            if line.strip() and not line.startswith("catalog")
        ]

    for cat in catalog_names:
        if not cat:
            continue
        catalog_info = {"schemas": {}}

        # Get schemas
        result = _call_mcp("tools/call", {
            "name": "getSchemas",
            "arguments": {"catalogName": cat},
        })
        schemas_text = _extract_text(result)
        catalog_info["schemas_raw"] = schemas_text

        # Get tables for each schema-like entry
        result = _call_mcp("tools/call", {
            "name": "getTables",
            "arguments": {"catalogName": cat, "schemaName": ""},
        })
        catalog_info["tables_raw"] = _extract_text(result)

        schema["catalogs"][cat] = catalog_info

    save(schema)
    log.info("Schema cached successfully", extra={"node": "cache"})
    return schema
