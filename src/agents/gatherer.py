"""ReAct data gatherer agent.

Uses create_react_agent with MCP tools to autonomously discover schemas
and query relevant data from CData Connect AI.
"""
import json

from langgraph.prebuilt import create_react_agent

from config import get_llm, CDATA_CATALOG, MAX_ITERATIONS
from mcp_tools import get_catalogs, get_schemas, get_tables, get_columns, query_data
import schema_cache
from logger import get_logger, track

log = get_logger("gatherer")

TOOLS = [get_catalogs, get_schemas, get_tables, get_columns, query_data]

SYSTEM_PROMPT = """You are a data gathering agent. Discover the data schema and query relevant data.

Steps:
1. If a catalog is provided, skip get_catalogs. Otherwise call get_catalogs first.
2. Call get_schemas to find schemas in the catalog.
3. Call get_tables to list tables. Pick ONLY the tables relevant to the question.
4. Call get_columns on at most 3 relevant tables.
5. Call query_data to get the data you need.

SQL rules:
- Fully qualified names: [Catalog].[Schema].[Table]
- Quote columns: [ColumnName]
- ALWAYS use TOP 20 to limit results
- If tables have duplicate names like "table_2", ignore the "_2" variants

CRITICAL: Be efficient. You have limited steps. Do NOT explore unnecessary tables.
Aim for 3-4 queries maximum. Once you have the data, IMMEDIATELY write your summary.

Your final message MUST be a structured summary of all data you gathered."""


def _extract_query_results(messages: list) -> str:
    """Fallback: extract raw query results from tool messages.

    If the agent ran out of steps before summarizing, the actual data
    is still in the ToolMessage objects from query_data calls.
    """
    results = []
    for msg in messages:
        name = getattr(msg, "name", "")
        content = getattr(msg, "content", "")
        if name == "query_data" and content:
            # Parse the JSON to extract just the rows (skip schema metadata)
            try:
                data = json.loads(content)
                for result_set in data.get("results", []):
                    schema = result_set.get("schema", [])
                    rows = result_set.get("rows", [])
                    if schema and rows:
                        col_names = [c["columnName"] for c in schema]
                        table_name = schema[0].get("tableName", "unknown")
                        records = [dict(zip(col_names, row)) for row in rows]
                        results.append(
                            f"Table: {table_name} ({len(records)} rows)\n"
                            + json.dumps(records, indent=2, default=str)
                        )
            except (json.JSONDecodeError, KeyError):
                # If we can't parse, include the raw text (truncated)
                results.append(content[:2000])

    if results:
        return "Gathered data from queries:\n\n" + "\n\n---\n\n".join(results)
    return ""


def gather_node(state: dict) -> dict:
    """ReAct data gatherer node."""
    prompt = state.get("user_prompt", "")

    # Build system prompt with optional schema cache and catalog hint
    sys_prompt = SYSTEM_PROMPT

    if CDATA_CATALOG:
        sys_prompt += f"\n\nUse this catalog: {CDATA_CATALOG}"

    if schema_cache.is_valid():
        log.info("Schema cache hit", extra={"node": "gatherer"})
        cached = schema_cache.load()
        # Inject only a compact summary, not the full JSON
        cache_summary = json.dumps(cached, separators=(",", ":"))
        if len(cache_summary) > 2000:
            cache_summary = cache_summary[:2000] + "..."
        sys_prompt += f"\n\nCached schema (skip discovery):\n{cache_summary}"
    else:
        log.info("No schema cache -- agent will discover", extra={"node": "gatherer"})

    llm = get_llm()
    track("llm_calls")

    agent = create_react_agent(llm, TOOLS, prompt=sys_prompt)

    result = agent.invoke(
        {"messages": [("user", prompt)]},
        config={"recursion_limit": MAX_ITERATIONS * 2},
    )

    # Extract gathered data from the final message
    last_msg = result["messages"][-1]
    gathered = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # Fallback: if the agent ran out of steps or returned an unhelpful message,
    # extract the actual query results from tool messages
    if len(gathered) < 200 or "sorry" in gathered.lower() or "more steps" in gathered.lower():
        log.info("Agent did not summarize -- extracting from tool messages", extra={"node": "gatherer"})
        fallback = _extract_query_results(result["messages"])
        if fallback:
            gathered = fallback

    # Cache schema on first successful run
    if not schema_cache.is_valid():
        try:
            schema_cache.discover_and_cache()
        except Exception as e:
            log.debug(f"Schema caching skipped: {e}", extra={"node": "gatherer"})

    log.info(f"Gathered {len(gathered)} chars of data", extra={"node": "gatherer"})
    return {"gathered_data": gathered}
