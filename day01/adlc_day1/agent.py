"""Day 1 (ADLC): a weather/time agent built with Google ADK, running on Claude.

Same behavior as the course's scaffolded prototype, but the model is Claude through
LiteLLM instead of Gemini. The tools return canned data so runs are free and
repeatable apart from the model call.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

# Swap the model here. Cheaper options: "anthropic/claude-sonnet-5-5", "anthropic/claude-haiku-4-5".
MODEL = LiteLlm(model="anthropic/claude-opus-5-5")

CITIES = {
    "san francisco": {"tz": "America/Los_Angeles", "weather": "Foggy, 16°C (61°F)"},
    "detroit": {"tz": "America/Detroit", "weather": "Partly cloudy, 12°C (54°F)"},
    "nairobi": {"tz": "Africa/Nairobi", "weather": "Sunny, 24°C (75°F)"},
}


def get_weather(city: str) -> dict:
    """Returns the current weather report for a city.

    Args:
        city: Name of the city, e.g. "San Francisco".
    """
    info = CITIES.get(city.strip().lower())
    if info is None:
        return {"status": "error", "error_message": f"No weather data for '{city}'."}
    return {"status": "success", "report": f"The weather in {city.title()} is {info['weather']}."}


def get_current_time(city: str) -> dict:
    """Returns the current local time in a city.

    Args:
        city: Name of the city, e.g. "Detroit".
    """
    info = CITIES.get(city.strip().lower())
    if info is None:
        return {"status": "error", "error_message": f"No timezone data for '{city}'."}
    now = datetime.now(ZoneInfo(info["tz"]))
    return {"status": "success", "report": f"The current time in {city.title()} is {now:%Y-%m-%d %H:%M %Z}."}


root_agent = Agent(
    model=MODEL,
    name="adlc_day1",
    description="Answers weather and time questions for supported cities.",
    instruction=(
        "You answer questions about the weather and the current time in a city. "
        "Use get_weather for weather and get_current_time for time. "
        "Do not answer from memory, and if a tool returns an error, say the city isn't supported."
    ),
    tools=[get_weather, get_current_time],
)
