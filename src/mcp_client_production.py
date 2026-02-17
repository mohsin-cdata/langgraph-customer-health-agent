"""
Production MCP Client - Uses correct MCP protocol (tools/list, tools/call).
Based on proven implementation from Talent Intelligence Platform.
"""
import base64
import requests
import json
from typing import Any, Dict, List
from config import Config


class MCPClientProduction:
    """Production MCP client using standard MCP protocol.

    MCP Server exposes:
    - initialize: Initialize connection
    - tools/list: List available tools
    - tools/call: Call a specific tool

    This is the CORRECT approach confirmed by Talent Intelligence Platform.
    """

    def __init__(self):
        self.endpoint = Config.MCP_ENDPOINT
        self.auth_header = self._create_auth_header()
        self.request_id = 0
        self.initialized = False

    def _create_auth_header(self) -> str:
        """Create HTTP Basic Auth header."""
        credentials = f"{Config.CDATA_EMAIL}:{Config.CDATA_PAT}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _make_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Make a JSON-RPC 2.0 request using MCP protocol."""
        self.request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }

        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=30,
                stream=True
            )
            response.raise_for_status()

            # Parse response (handle SSE format)
            content = response.text.strip()

            # Extract JSON from SSE format (data: {...})
            if content.startswith("data: "):
                content = content.replace("data: ", "", 1).strip()

            # Handle multiple lines
            lines = content.split("\n")
            json_str = ""
            for line in lines:
                if line.startswith("data: "):
                    json_str = line.replace("data: ", "", 1).strip()
                elif line.strip() and not json_str:
                    json_str = line.strip()

            result = json.loads(json_str)

            if "error" in result and result["error"]:
                raise Exception(f"MCP Error: {result['error'].get('message', 'Unknown error')}")

            return result.get("result")

        except requests.exceptions.RequestException as e:
            raise Exception(f"MCP request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse MCP response: {str(e)}")

    def initialize(self) -> bool:
        """Initialize MCP connection."""
        try:
            params = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "LangGraph Customer Health Agent",
                    "version": "1.0.0"
                }
            }
            result = self._make_request("initialize", params)
            self.initialized = True
            return True
        except Exception as e:
            print(f"[MCP] Initialize failed: {str(e)}")
            return False

    def list_tools(self) -> List[str]:
        """List available MCP tools."""
        try:
            result = self._make_request("tools/list", {})
            if result and "tools" in result:
                return [tool.get("name") for tool in result.get("tools", [])]
            return []
        except Exception as e:
            print(f"[MCP] List tools failed: {str(e)}")
            return []

    def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Call an MCP tool."""
        try:
            params = {
                "name": name,
                "arguments": args
            }
            result = self._make_request("tools/call", params)
            return result
        except Exception as e:
            print(f"[MCP] Tool call ({name}) failed: {str(e)}")
            return None

    def query_data(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SELECT query using queryData tool.

        MCP returns structured JSON with schema and rows.
        """
        try:
            # Call the queryData tool
            result = self.call_tool("queryData", {
                "query": query,
                "llmContext": {
                    "provider": "anthropic",
                    "model": "claude-opus-4-6",
                    "reason": "Query Salesforce data for customer health analysis"
                }
            })

            if not result:
                return []

            # Parse response: {content: [{type: "text", text: "{json}"}]}
            text_content = ""
            if isinstance(result, dict) and "content" in result:
                for item in result.get("content", []):
                    if item.get("type") == "text":
                        text_content = item.get("text", "")
                        break

            if not text_content:
                return []

            # Parse JSON response
            try:
                response_data = json.loads(text_content)
            except json.JSONDecodeError:
                # If it's not JSON, return empty
                return []

            # Extract data from nested structure:
            # {results: [{schema: [...], rows: [...]}]}
            if "results" not in response_data or not response_data["results"]:
                return []

            result_set = response_data["results"][0]
            schema = result_set.get("schema", [])
            rows = result_set.get("rows", [])

            if not schema or not rows:
                return []

            # Get column names from schema
            column_names = [col.get("columnName") for col in schema]

            # Convert rows to list of dicts
            data = []
            for row in rows:
                row_dict = dict(zip(column_names, row))
                data.append(row_dict)

            return data

        except Exception as e:
            print(f"[MCP] Query failed: {str(e)}")
            return []
