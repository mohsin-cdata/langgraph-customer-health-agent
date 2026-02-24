"""LangGraph workflow definition.

Builds a 3-node sequential pipeline:
  gather (ReAct) -> analyze (LLM) -> render (deterministic)

Extensibility: add your agents to the PIPELINE list below.
"""
from langgraph.graph import StateGraph

from state import AgentState
from agents.gatherer import gather_node
from agents.analyst import analyze_node
from agents.renderer import render_node

# Extensible pipeline -- add your agents to this list.
# Each entry is (node_name, node_function).
PIPELINE = [
    ("gather", gather_node),
    ("analyze", analyze_node),
    ("render", render_node),
]


def build_graph():
    """Build and compile the LangGraph workflow."""
    graph = StateGraph(AgentState)

    # Add all nodes
    for name, func in PIPELINE:
        graph.add_node(name, func)

    # Set entry point
    graph.set_entry_point(PIPELINE[0][0])

    # Add sequential edges
    for i in range(len(PIPELINE) - 1):
        graph.add_edge(PIPELINE[i][0], PIPELINE[i + 1][0])

    return graph.compile()
