"""Travel Concierge — a rule-based (no-LLM) A2A client / orchestrator.

It discovers two A2A agents via their well-known Agent Cards, calls each with an
authenticated request (x-api-key), and merges the replies into one trip summary.

Run (after both agents are up):
    python concierge.py --city Paris --amount 100 --home USD
"""

import argparse
import asyncio
import warnings
from uuid import uuid4

import httpx

# The legacy A2AClient (used here) is functional but emits a deprecation warning.
warnings.filterwarnings("ignore", category=DeprecationWarning)

from a2a.client import A2ACardResolver, A2AClient, create_text_message_object
from a2a.types import MessageSendParams, SendMessageRequest

from auth import API_KEY, API_KEY_HEADER

WEATHER_URL = "http://localhost:8001"
CURRENCY_URL = "http://localhost:8002"

# Rule-based routing: which local currency does a destination use?
CITY_CURRENCY = {"paris": "EUR", "tokyo": "JPY", "london": "GBP", "new york": "USD"}


def extract_text(resp) -> str:
    """Pull the text out of a SendMessageResponse (Message or Task result)."""
    result = getattr(resp.root, "result", None)
    parts = getattr(result, "parts", None) or []
    chunks = []
    for part in parts:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if text:
            chunks.append(text)
    return " ".join(chunks) if chunks else str(result)


async def ask(client: A2AClient, text: str) -> str:
    request = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(message=create_text_message_object(content=text)),
    )
    response = await client.send_message(request)
    return extract_text(response)


async def run(city: str, amount: float, home: str) -> None:
    local = CITY_CURRENCY.get(city.lower(), "USD")
    headers = {API_KEY_HEADER: API_KEY}  # authenticate every call

    async with httpx.AsyncClient(headers=headers, timeout=30) as http:
        # 1. Discovery — fetch each agent's well-known Agent Card.
        weather_card = await A2ACardResolver(http, WEATHER_URL).get_agent_card()
        currency_card = await A2ACardResolver(http, CURRENCY_URL).get_agent_card()
        print(f"Discovered: {weather_card.name} + {currency_card.name}")

        weather = A2AClient(http, agent_card=weather_card)
        currency = A2AClient(http, agent_card=currency_card)

        # 2. Orchestrate — call both agents.
        weather_reply = await ask(weather, city)
        currency_reply = await ask(currency, f"{amount} {home} to {local}")

    # 3. Merge into one trip summary.
    print(f"\nTrip to {city} ->")
    print(f"   {weather_reply}")
    print(f"   Money: {currency_reply} (spend in {local})")
    print("   Have a great trip!\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="A2A Travel Concierge")
    parser.add_argument("--city", default="Paris")
    parser.add_argument("--amount", type=float, default=100)
    parser.add_argument("--home", default="USD")
    args = parser.parse_args()
    asyncio.run(run(args.city, args.amount, args.home))


if __name__ == "__main__":
    main()
