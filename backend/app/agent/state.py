from typing import TypedDict


class AgentState(TypedDict):
    question: str
    history: list[dict]
    tool_name: str       # "rag" | "web"
    context: str
    sources: list[str]
    answer: str
    retried: bool
