"""Currency Agent — agent logic built with LangGraph, exposed over A2A.

This agent is deliberately built with a *different* framework than the Weather
agent to demonstrate A2A's framework-agnostic interoperability:

  - the **agent logic** is a LangGraph ``StateGraph`` (deterministic, no LLM),
  - it is **exposed over A2A** via the official ``a2a-sdk`` server layer,
  - the same ``a2a-sdk`` client (concierge.py) calls it identically to the
    plain ``a2a-sdk`` Weather agent.

Run: ``python currency_agent.py``  ->  serves http://localhost:8002
"""

import re
from typing import TypedDict

import uvicorn
from langgraph.graph import END, START, StateGraph

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from auth import ApiKeyMiddleware, api_key_security

HOST, PORT = "localhost", 8002

# Stubbed "brain": static rates relative to USD instead of a live API / LLM.
RATES = {"USD": 1.0, "EUR": 0.92, "JPY": 156.0, "GBP": 0.79, "INR": 83.2}

# e.g. "100 USD to EUR"  /  "convert 50 gbp into jpy"
PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*([A-Za-z]{3})\s*(?:to|into|->)\s*([A-Za-z]{3})", re.IGNORECASE
)


def convert(text: str) -> str:
    m = PATTERN.search(text or "")
    if not m:
        return "Sorry, use the form '<amount> <FROM> to <TO>', e.g. '100 USD to EUR'."
    amount, src, dst = float(m.group(1)), m.group(2).upper(), m.group(3).upper()
    if src not in RATES or dst not in RATES:
        return f"Unknown currency. Supported: {', '.join(RATES)}."
    converted = amount / RATES[src] * RATES[dst]
    return f"{amount:g} {src} = {converted:.2f} {dst}"


# --- LangGraph: a one-node deterministic graph (the "agent logic") ---
class CurrencyState(TypedDict):
    query: str
    result: str


def _convert_node(state: CurrencyState) -> dict:
    return {"result": convert(state["query"])}


def build_graph():
    builder = StateGraph(CurrencyState)
    builder.add_node("convert", _convert_node)
    builder.add_edge(START, "convert")
    builder.add_edge("convert", END)
    return builder.compile()


class CurrencyExecutor(AgentExecutor):
    """Bridges the A2A request to the LangGraph graph."""

    def __init__(self) -> None:
        self.graph = build_graph()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        state = await self.graph.ainvoke({"query": context.get_user_input() or ""})
        await event_queue.enqueue_event(new_agent_text_message(state["result"]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass


def main() -> None:
    print(f"Running CurrencyAgent (LangGraph) on http://{HOST}:{PORT}")
    skill = AgentSkill(
        id="convert_currency",
        name="Convert Currency",
        description="Converts an amount between currencies (LangGraph, stubbed rates).",
        tags=["currency", "travel"],
        examples=["100 USD to EUR", "convert 50 GBP into JPY"],
    )
    security_schemes, security = api_key_security()
    card = AgentCard(
        name="CurrencyAgent",
        description="Converts money between currencies (LangGraph, stubbed rates).",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
        security_schemes=security_schemes,
        security=security,
    )
    handler = DefaultRequestHandler(
        agent_executor=CurrencyExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(agent_card=card, http_handler=handler)
    app = server.build()
    app.add_middleware(ApiKeyMiddleware)  # enforce x-api-key (except /.well-known)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
