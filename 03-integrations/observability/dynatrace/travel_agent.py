import os
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from ddgs import DDGS

app = BedrockAgentCoreApp()


@tool
def get_weather(location: str):
    """
    Get current weather information for a specific location.
    
    Args:
        location: City name or location (e.g., "London", "New York", "Tokyo")
    
    Returns:
        Current weather information including temperature, conditions, and wind speed
    """
    try:
        # First, get coordinates for the location using geocoding
        geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocoding_params = {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json"
        }
        
        geo_response = requests.get(geocoding_url, params=geocoding_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data.get("results"):
            return f"Location '{location}' not found. Please provide a valid city name."
        
        result = geo_data["results"][0]
        latitude = result["latitude"]
        longitude = result["longitude"]
        location_name = result["name"]
        country = result.get("country", "")
        
        # Get weather data
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh"
        }
        
        weather_response = requests.get(weather_url, params=weather_params, timeout=10)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        current = weather_data["current"]
        
        # Weather code interpretation
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        
        weather_description = weather_codes.get(current["weather_code"], "Unknown")
        
        return (
            f"Weather in {location_name}, {country}:\n"
            f"Temperature: {current['temperature_2m']}°C (feels like {current['apparent_temperature']}°C)\n"
            f"Conditions: {weather_description}\n"
            f"Humidity: {current['relative_humidity_2m']}%\n"
            f"Wind Speed: {current['wind_speed_10m']} km/h\n"
            f"Precipitation: {current['precipitation']} mm"
        )
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {str(e)}"
    except Exception as e:
        return f"Error processing weather request: {str(e)}"


@tool
def web_search(query: str, max_results: int = 5):
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        A list of search results with title, link, and snippet
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. {result.get('title', 'No title')}\n"
                    f"   URL: {result.get('href', 'No URL')}\n"
                    f"   {result.get('body', 'No description')}"
                )
            return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Error performing web search: {str(e)}"


model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[get_weather, web_search],
    system_prompt="You're a helpful travel assistant. You can search the web for travel information, check current weather conditions for any location, and do simple math calculations. Use web search to find current information about destinations, flights, hotels, attractions, and travel tips. Use get_weather to provide accurate, real-time weather information for travelers.",
)

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    response = agent(user_input)
    return response.message["content"][0]["text"]