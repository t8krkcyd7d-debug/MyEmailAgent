"""Small LangGraph workflows for direct input and inbox input."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.nodes import analyze_email_node, fetch_email_node


class AnalysisState(TypedDict, total=False):
    email_content: str
    user_instruction: str
    summary: str
    urgency: str
    draft_reply: str
    emails: list[dict[str, Any]]
    current_email_id: int
    email_limit: int
    fetch_error: str | None


def _after_fetch(state: AnalysisState) -> str:
    return "end" if state.get("fetch_error") or not state.get("email_content") else "analyze"


def build_analysis_graph():
    builder = StateGraph(AnalysisState)
    builder.add_node("analyze", analyze_email_node)
    builder.set_entry_point("analyze")
    builder.add_edge("analyze", END)
    return builder.compile()


def build_inbox_graph():
    builder = StateGraph(AnalysisState)
    builder.add_node("fetch", fetch_email_node)
    builder.add_node("analyze", analyze_email_node)
    builder.set_entry_point("fetch")
    builder.add_conditional_edges("fetch", _after_fetch, {"analyze": "analyze", "end": END})
    builder.add_edge("analyze", END)
    return builder.compile()


analysis_graph = build_analysis_graph()
inbox_graph = build_inbox_graph()
