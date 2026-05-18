from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from agent.nodes import (
    extract_category_node,
    human_clarification_node,
    market_study_node,
    route_after_extract,
)
from agent.state import CategoryGraphState


def create_category_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compile category + clarification + market-study"""

    saver = checkpointer if checkpointer is not None else InMemorySaver()

    graph = StateGraph(CategoryGraphState)
    graph.add_node("extract_category", extract_category_node)
    graph.add_node("human_clarification", human_clarification_node)
    graph.add_node("market_study", market_study_node)

    graph.add_edge(START, "extract_category")
    graph.add_conditional_edges(
        "extract_category",
        route_after_extract,
        {
            "clarify": "human_clarification",
            "market_study": "market_study",
            "end": END,
        },
    )
    graph.add_edge("human_clarification", "extract_category")
    graph.add_edge("market_study", END)

    return graph.compile(checkpointer=saver)
