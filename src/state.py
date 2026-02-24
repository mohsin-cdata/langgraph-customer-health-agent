"""Shared state definition for the customer health agent."""
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State schema for the customer health agent workflow."""
    messages: Annotated[list, add_messages]
    user_prompt: str
    gathered_data: str
    analysis: str
    brief_path: str
    errors: list[str]
