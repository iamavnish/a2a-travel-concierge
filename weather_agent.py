"""Weather Agent — an A2A server built directly with the official ``a2a-sdk``.

Its logic is a plain stub (no agent framework, no LLM) — contrast with
``currency_agent.py``, whose logic is built with LangGraph. Both are called
identically by the same A2A client, which is the point of A2A.

Given a message mentioning a city, it returns canned weather from a dict.
Run: ``python weather_agent.py``  ->  serves http://localhost:8001
"""

import uvicorn

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from auth import ApiKeyMiddleware, api_key_security

HOST, PORT = "localhost", 8001

# Stubbed "brain": deterministic lookup instead of an LLM call.
WEATHER = {
    "paris": "18C, light rain",
    "tokyo": "26C, sunny",
    "london": "15C, overcast",
    "new york": "22C, cloudy",
}
DEFAULT_WEATHER = "20C, clear"


class WeatherExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = (context.get_user_input() or "").lower()
        report = next((v for k, v in WEATHER.items() if k in text), DEFAULT_WEATHER)
        await event_queue.enqueue_event(new_agent_text_message(f"Weather: {report}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass


def main() -> None:
    print(f"Running WeatherAgent on http://{HOST}:{PORT}")
    skill = AgentSkill(
        id="get_weather",
        name="Get Weather",
        description="Returns current weather for a city.",
        tags=["weather", "travel"],
        examples=["What's the weather in Paris?", "weather Tokyo"],
    )
    security_schemes, security = api_key_security()
    card = AgentCard(
        name="WeatherAgent",
        description="Provides current weather for a city (stubbed data).",
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
        agent_executor=WeatherExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(agent_card=card, http_handler=handler)
    app = server.build()
    app.add_middleware(ApiKeyMiddleware)  # enforce x-api-key (except /.well-known)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
