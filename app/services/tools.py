"""Agentic tool definitions and real async implementations (Phase 2B).

Provides:
- Schema definitions in OpenAI function-calling format for Groq/OpenAI.
- Real async database-connected tools for trips, itineraries, knowledge base, and catalog.
- Real external integrations: Frankfurter (live currency conversion) and Open-Meteo (live weather forecasts).
- Safe destructive actions requiring explicit confirmation.
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.trip import Trip
from app.db.repositories import trip as trip_repo
from app.rag.retriever import retrieve_sources
from app.rag.store import semantic_search
from app.schemas.trip import TripCreate

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes (Open-Meteo)
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Tool schemas in OpenAI `tools` format (Groq & OpenAI compatible)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the local travel knowledge base (RAG) for destination guides, cultural etiquette, attractions, and local tips.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'Kyoto temples', 'local etiquette')"},
                    "destination": {"type": "string", "description": "Optional destination filter"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_trip",
            "description": "Create a new trip plan with dates, budget, and destination, generating a full day-by-day itinerary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination city or region"},
                    "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                    "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                    "budget": {"type": "string", "description": "Total budget (e.g. '1500.00')"},
                    "currency": {
                        "type": "string",
                        "default": "USD",
                        "description": "3-letter currency code (e.g. USD, EUR, JPY)",
                    },
                    "travelers": {"type": "integer", "default": 1, "description": "Number of travelers"},
                    "travel_style": {
                        "type": "string",
                        "default": "balanced",
                        "enum": ["relaxed", "balanced", "adventure", "luxury", "budget", "family"],
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of interests (e.g. ['food', 'culture', 'nature'])",
                    },
                },
                "required": ["destination", "start_date", "end_date", "budget"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_trip",
            "description": "Update top-level constraints (dates, budget, travelers, style, interests) of an existing trip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "Trip UUID (optional if bound to conversation or destination specified)",
                    },
                    "destination": {"type": "string", "description": "Destination name to match if trip_id is omitted"},
                    "start_date": {"type": "string", "description": "New start date YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "New end date YYYY-MM-DD"},
                    "budget": {"type": "string", "description": "New budget"},
                    "travel_style": {
                        "type": "string",
                        "enum": ["relaxed", "balanced", "adventure", "luxury", "budget", "family"],
                    },
                    "interests": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_itinerary",
            "description": "Modify, add, or replace days or activities in a trip's itinerary (e.g. add a 4th day, change Day 2 dinner to ramen, replace an activity).",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "Trip UUID (optional if destination provided or bound to conversation)",
                    },
                    "destination": {"type": "string", "description": "Destination name to match if trip_id is omitted"},
                    "action": {
                        "type": "string",
                        "enum": ["add_day", "update_activity", "add_activity", "remove_activity", "replace_day"],
                        "description": "The modification action to take.",
                    },
                    "day_number": {
                        "type": "integer",
                        "description": "1-based day number (e.g. 2 for Day 2, 4 for adding Day 4)",
                    },
                    "date": {"type": "string", "description": "Optional date YYYY-MM-DD for the day"},
                    "theme": {
                        "type": "string",
                        "description": "Theme or highlight for the day (e.g. 'Arashiyama Bamboo Forest')",
                    },
                    "activity_index": {
                        "type": "integer",
                        "description": "0-based activity index within the day (e.g. 0 for morning, 1 for afternoon, 2 for dinner)",
                    },
                    "activity_time_or_title": {
                        "type": "string",
                        "description": "Fuzzy matcher for activity (e.g. 'dinner', 'morning', '19:00') if index is unknown",
                    },
                    "activity": {
                        "type": "object",
                        "properties": {
                            "time": {"type": "string", "description": "Time e.g. '19:00'"},
                            "title": {"type": "string", "description": "Activity title"},
                            "description": {"type": "string", "description": "Activity description"},
                            "location": {"type": "string", "description": "Location or neighborhood"},
                            "category": {
                                "type": "string",
                                "enum": ["food", "culture", "nature", "nightlife", "history", "shopping", "sightseeing"],
                            },
                            "cost_estimate": {"type": "number", "description": "Estimated cost"},
                        },
                    },
                    "meals": {"type": "array", "items": {"type": "string"}, "description": "Meal suggestions for the day"},
                    "notes": {"type": "string", "description": "Notes for the day"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_trips",
            "description": "List all saved trips for the current user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trip",
            "description": "Get full details and itinerary for a specific trip by ID or destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string", "description": "Trip UUID"},
                    "destination": {"type": "string", "description": "Destination name to match if trip_id is omitted"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_destinations",
            "description": "Search destinations in the travel knowledge base catalog.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Destination query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_trip",
            "description": "Delete a trip. REQUIRES explicit user confirmation string 'confirm delete'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string", "description": "Trip UUID to delete"},
                    "confirmation": {"type": "string", "description": "Must be exactly 'confirm delete'"},
                },
                "required": ["trip_id", "confirmation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get real-time weather forecasts, weather warnings, and packing advice for a destination using Open-Meteo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination city (e.g. 'Kyoto', 'Rome', 'Paris')"},
                    "start_date": {"type": "string", "description": "Optional start date in YYYY-MM-DD format"},
                    "end_date": {"type": "string", "description": "Optional end date in YYYY-MM-DD format"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert currency amounts using real-time foreign exchange rates from Frankfurter API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount to convert"},
                    "from_currency": {"type": "string", "description": "Source 3-letter currency code (e.g. 'USD')"},
                    "to_currency": {"type": "string", "description": "Target 3-letter currency code (e.g. 'EUR', 'JPY')"},
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search restaurant and dining recommendations from the knowledge base for a destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination city or region"},
                    "query": {
                        "type": "string",
                        "description": "Food style or query (e.g. 'ramen', 'vegetarian', 'local dinner')",
                    },
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activities",
            "description": "Search attractions, sightseeing, and activities from the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination city or region"},
                    "query": {
                        "type": "string",
                        "description": "Type of activity or query (e.g. 'temples', 'museums', 'hiking')",
                    },
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search accommodation, neighborhoods, and lodging advice from the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination city"},
                    "query": {"type": "string", "description": "Preferred neighborhood or lodging style"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search flight route information, typical connections, and transit guidance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Departure city or airport"},
                    "destination": {"type": "string", "description": "Destination city or airport"},
                    "date": {"type": "string", "description": "Date of travel"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: Find trip
# ---------------------------------------------------------------------------


async def _resolve_trip(
    session: AsyncSession,
    user_id: uuid.UUID,
    trip_id: str | None = None,
    destination: str | None = None,
) -> Trip | None:
    """Resolve trip by UUID or fuzzy match on user's trips by destination name."""
    if trip_id:
        try:
            parsed_id = uuid.UUID(str(trip_id).strip())
            trip = await trip_repo.get_owned(session, user_id, parsed_id)
            if trip:
                return trip
        except (ValueError, TypeError):
            pass

    trips, _ = await trip_repo.list_by_user(session, user_id, limit=50)
    if not trips:
        return None

    if destination and destination.strip():
        dest_lower = destination.strip().lower()
        for t in trips:
            if dest_lower in t.destination.lower() or t.destination.lower() in dest_lower:
                return t

    # If only 1 trip exists for the user, use it
    if len(trips) == 1:
        return trips[0]

    return trips[0] if trips else None


# ---------------------------------------------------------------------------
# Real async tool implementations
# ---------------------------------------------------------------------------


async def convert_currency_impl(args: dict[str, Any]) -> str:
    """Convert currency using the free, open Frankfurter API."""
    try:
        amount = float(args.get("amount", 1.0))
        from_curr = str(args.get("from_currency", "USD")).strip().upper()
        to_curr = str(args.get("to_currency", "EUR")).strip().upper()

        if from_curr == to_curr:
            return json.dumps(
                {
                    "amount": amount,
                    "from_currency": from_curr,
                    "to_currency": to_curr,
                    "rate": 1.0,
                    "converted_amount": amount,
                    "date": datetime.now(UTC).date().isoformat(),
                }
            )

        url = "https://api.frankfurter.dev/v1/latest"
        params = {"amount": amount, "from": from_curr, "to": to_curr}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("Frankfurter API error status=%s body=%s", resp.status_code, resp.text)
                return json.dumps(
                    {
                        "error": f"Currency conversion failed: provider returned {resp.status_code}",
                        "details": resp.text,
                    }
                )

            data = resp.json()
            rates = data.get("rates", {})
            converted = rates.get(to_curr)
            rate = (converted / amount) if (converted and amount > 0) else None

            return json.dumps(
                {
                    "amount": amount,
                    "from_currency": from_curr,
                    "to_currency": to_curr,
                    "rate": round(rate, 4) if rate else None,
                    "converted_amount": round(converted, 2) if converted else None,
                    "date": data.get("date"),
                }
            )
    except Exception as exc:
        logger.exception("convert_currency failed")
        return json.dumps({"error": f"Could not convert currency: {exc}"})


async def get_weather_forecast_impl(args: dict[str, Any]) -> str:
    """Get live weather forecasts and packing advice using Open-Meteo."""
    destination = str(args.get("destination", "")).strip()
    if not destination:
        return json.dumps({"error": "Destination is required for weather forecast."})

    start_date_str = args.get("start_date")
    end_date_str = args.get("end_date")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: Geocoding
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            geo_resp = await client.get(geo_url, params={"name": destination, "count": 1, "language": "en", "format": "json"})
            if geo_resp.status_code != 200:
                return json.dumps({"error": f"Geocoding service returned status {geo_resp.status_code}"})

            geo_data = geo_resp.json()
            results = geo_data.get("results")
            if not results:
                return json.dumps({"error": f"Could not find coordinates for '{destination}'."})

            place = results[0]
            lat = place["latitude"]
            lon = place["longitude"]
            place_name = place.get("name", destination)
            country = place.get("country", "")

            # Step 2: Forecast
            forecast_url = "https://api.open-meteo.com/v1/forecast"
            params: dict[str, Any] = {
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            }

            # If dates provided and in valid forecast range (within next 14 days)
            use_custom_dates = False
            if start_date_str and end_date_str:
                try:
                    s_date = date.fromisoformat(str(start_date_str))
                    e_date = date.fromisoformat(str(end_date_str))
                    today = datetime.now(UTC).date()
                    if today <= s_date <= today + timedelta(days=14):
                        params["start_date"] = s_date.isoformat()
                        params["end_date"] = min(e_date, today + timedelta(days=15)).isoformat()
                        use_custom_dates = True
                except (ValueError, TypeError):
                    pass

            w_resp = await client.get(forecast_url, params=params)
            if w_resp.status_code != 200:
                # If custom dates failed (e.g. out of range), retry default 7-day forecast
                params.pop("start_date", None)
                params.pop("end_date", None)
                w_resp = await client.get(forecast_url, params=params)

            if w_resp.status_code != 200:
                return json.dumps({"error": f"Weather service returned status {w_resp.status_code}"})

            w_data = w_resp.json()
            daily = w_data.get("daily", {})
            times = daily.get("time", [])
            codes = daily.get("weathercode", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precips = daily.get("precipitation_sum", [])

            days_summary: list[dict[str, Any]] = []
            has_rain = False
            min_temp_all = 999.0
            max_temp_all = -999.0

            for i, t in enumerate(times):
                code = codes[i] if i < len(codes) else 0
                max_t = max_temps[i] if i < len(max_temps) else 0
                min_t = min_temps[i] if i < len(min_temps) else 0
                precip = precips[i] if i < len(precips) else 0.0

                if code in {51, 53, 55, 61, 63, 65, 80, 81, 82, 95} or (precip and precip > 0.5):
                    has_rain = True
                min_temp_all = min(min_temp_all, min_t)
                max_temp_all = max(max_temp_all, max_t)

                days_summary.append(
                    {
                        "date": t,
                        "condition": WMO_WEATHER_CODES.get(code, "Unknown"),
                        "temp_max_c": max_t,
                        "temp_min_c": min_t,
                        "precipitation_mm": precip,
                    }
                )

            # Formulate packing tips & warnings
            packing_advice: list[str] = []
            warnings: list[str] = []

            if has_rain:
                packing_advice.append("Pack a compact umbrella and waterproof jacket (rain expected).")
                warnings.append("Rain is forecasted on some days; plan indoor alternatives (museums/markets).")
            if min_temp_all < 10.0:
                packing_advice.append("Pack warm layers, sweaters, and a light jacket for cool mornings/evenings.")
            if min_temp_all < 2.0:
                packing_advice.append("Pack thermal base layers, gloves, and a warm hat.")
                warnings.append("Near-freezing temperatures expected.")
            if max_temp_all > 26.0:
                packing_advice.append("Pack breathable cotton clothes, sunglasses, and high-SPF sunscreen.")

            return json.dumps(
                {
                    "destination": f"{place_name}, {country}".strip(", "),
                    "date_range": f"{times[0]} to {times[-1]}" if times else "Upcoming 7 days",
                    "custom_dates_used": use_custom_dates,
                    "days": days_summary,
                    "warnings": warnings,
                    "packing_advice": packing_advice,
                }
            )
    except Exception as exc:
        logger.exception("get_weather_forecast failed")
        return json.dumps({"error": f"Weather forecast lookup failed: {exc}"})


async def search_knowledge_impl(args: dict[str, Any], session: AsyncSession | None = None) -> str:
    """Search the local knowledge base using pgvector semantic search."""
    query = str(args.get("query", "")).strip()
    destination = args.get("destination")
    if not query:
        return json.dumps({"results": [], "message": "Query string is required."})

    if session is None:
        return json.dumps({"results": [], "message": "Session context unavailable."})

    try:
        sources = await retrieve_sources(session, destination=destination or query, top_k=5)
        if not sources and destination:
            sources = await retrieve_sources(session, destination="", interests=[query], top_k=5)

        results = [
            {
                "title": s.title,
                "destination": s.destination,
                "category": s.category,
                "snippet": s.snippet,
                "source_uri": s.source_uri,
            }
            for s in sources
            if s.snippet
        ]
        return json.dumps({"results": results, "count": len(results)})
    except Exception as exc:  # noqa: BLE001
        logger.warning("search_knowledge failed (%s)", exc)
        return json.dumps({"results": [], "error": str(exc)})


async def create_trip_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Create a new planned trip in the database with a generated itinerary."""
    if session is None or user_id is None:
        return json.dumps({"error": "Database session and authenticated user required."})

    try:
        from app.services import trip_service

        destination = str(args["destination"]).strip()
        start_date = date.fromisoformat(str(args["start_date"]).strip())
        end_date = date.fromisoformat(str(args["end_date"]).strip())
        budget = Decimal(str(args["budget"]).strip())
        currency = str(args.get("currency", "USD")).strip().upper()
        travelers = int(args.get("travelers", 1))
        travel_style = str(args.get("travel_style", "balanced")).strip().lower()
        if travel_style not in {"relaxed", "balanced", "adventure", "luxury", "budget", "family"}:
            travel_style = "balanced"
        interests = [str(i) for i in args.get("interests", [])]

        payload = TripCreate(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            currency=currency,
            travelers=travelers,
            travel_style=travel_style,
            interests=interests,
        )

        trip = await trip_service.create_trip(session, user_id, payload)
        summary = trip.itinerary.get("summary") if trip.itinerary else ""
        days_count = len(trip.itinerary.get("days", [])) if trip.itinerary else 0

        return json.dumps(
            {
                "status": "created",
                "trip_id": str(trip.id),
                "destination": trip.destination,
                "start_date": str(trip.start_date),
                "end_date": str(trip.end_date),
                "budget": str(trip.budget),
                "currency": trip.currency,
                "travelers": trip.travelers,
                "travel_style": trip.travel_style,
                "days_count": days_count,
                "summary": summary,
            }
        )
    except Exception as exc:
        logger.exception("create_trip tool failed")
        return json.dumps({"error": f"Failed to create trip: {exc}"})


async def list_my_trips_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """List trips owned by the user."""
    if session is None or user_id is None:
        return json.dumps({"trips": [], "count": 0, "message": "Session context unavailable."})

    try:
        limit = int(args.get("limit", 20))
        trips, total = await trip_repo.list_by_user(session, user_id, limit=limit)
        items = [
            {
                "id": str(t.id),
                "destination": t.destination,
                "start_date": str(t.start_date),
                "end_date": str(t.end_date),
                "budget": str(t.budget),
                "currency": t.currency,
                "travelers": t.travelers,
                "travel_style": t.travel_style,
                "interests": t.interests or [],
                "status": t.status,
            }
            for t in trips
        ]
        return json.dumps({"trips": items, "total": total})
    except Exception as exc:
        logger.exception("list_my_trips failed")
        return json.dumps({"error": str(exc)})


async def get_trip_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Get trip details and day-by-day itinerary."""
    if session is None or user_id is None:
        return json.dumps({"error": "Session context unavailable."})

    trip_id = args.get("trip_id")
    destination = args.get("destination")
    trip = await _resolve_trip(session, user_id, trip_id, destination)
    if not trip:
        return json.dumps({"error": "Trip not found."})

    return json.dumps(
        {
            "id": str(trip.id),
            "destination": trip.destination,
            "start_date": str(trip.start_date),
            "end_date": str(trip.end_date),
            "budget": str(trip.budget),
            "currency": trip.currency,
            "travelers": trip.travelers,
            "travel_style": trip.travel_style,
            "interests": trip.interests or [],
            "status": trip.status,
            "itinerary": trip.itinerary,
        }
    )


async def update_trip_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Update trip top-level constraints."""
    if session is None or user_id is None:
        return json.dumps({"error": "Session context unavailable."})

    trip_id = args.get("trip_id")
    destination = args.get("destination")
    trip = await _resolve_trip(session, user_id, trip_id, destination)
    if not trip:
        return json.dumps({"error": "Trip not found."})

    try:
        if args.get("budget"):
            trip.budget = Decimal(str(args["budget"]))
        if args.get("start_date"):
            trip.start_date = date.fromisoformat(str(args["start_date"]))
        if args.get("end_date"):
            trip.end_date = date.fromisoformat(str(args["end_date"]))
        if args.get("travelers"):
            trip.travelers = int(args["travelers"])
        if args.get("travel_style"):
            trip.travel_style = str(args["travel_style"]).lower()
        if "interests" in args and isinstance(args["interests"], list):
            trip.interests = [str(i) for i in args["interests"]]
        if args.get("destination"):
            trip.destination = str(args["destination"])

        trip = await trip_repo.save(session, trip)
        return json.dumps(
            {
                "status": "updated",
                "trip_id": str(trip.id),
                "destination": trip.destination,
                "start_date": str(trip.start_date),
                "end_date": str(trip.end_date),
                "budget": str(trip.budget),
                "currency": trip.currency,
                "travelers": trip.travelers,
                "travel_style": trip.travel_style,
                "interests": trip.interests,
            }
        )
    except Exception as exc:
        logger.exception("update_trip failed")
        return json.dumps({"error": str(exc)})


async def modify_itinerary_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Modify, add, or replace days or activities in a trip's itinerary."""
    if session is None or user_id is None:
        return json.dumps({"error": "Session context unavailable."})

    trip_id = args.get("trip_id")
    destination = args.get("destination")
    trip = await _resolve_trip(session, user_id, trip_id, destination)
    if not trip:
        return json.dumps({"error": "Trip not found. Please provide trip_id or destination."})

    itinerary = trip.itinerary or {"summary": "", "total_estimated_cost": 0.0, "currency": trip.currency, "days": []}
    days: list[dict[str, Any]] = itinerary.get("days", [])
    action = str(args.get("action", "")).strip().lower()
    day_number = args.get("day_number")

    try:
        # ACTION 1: add_day
        if action == "add_day":
            new_day_num = day_number or (len(days) + 1)
            # Calculate date for the new day
            if days and "date" in days[-1]:
                try:
                    last_date = date.fromisoformat(days[-1]["date"])
                    new_date_str = (last_date + timedelta(days=1)).isoformat()
                except (ValueError, TypeError):
                    new_date_str = str(trip.end_date)
            else:
                new_date_str = str(trip.end_date)

            if args.get("date"):
                new_date_str = str(args["date"]).strip()

            theme = args.get("theme") or f"Explore {trip.destination}"
            activities = []

            # If user provided a specific activity to start the day with
            if args.get("activity") and isinstance(args["activity"], dict):
                act = args["activity"]
                activities.append(
                    {
                        "time": act.get("time", "09:30"),
                        "title": act.get("title", f"Explore {theme}"),
                        "description": act.get("description", ""),
                        "location": act.get("location", trip.destination),
                        "category": act.get("category", "sightseeing"),
                        "cost_estimate": float(act.get("cost_estimate", 0.0)),
                    }
                )
            else:
                activities = [
                    {
                        "time": "09:30",
                        "title": f"Morning: {theme}",
                        "description": f"Highlights of {theme} in {trip.destination}",
                        "location": trip.destination,
                        "category": "sightseeing",
                        "cost_estimate": 25.0,
                    },
                    {
                        "time": "13:00",
                        "title": "Local Lunch",
                        "description": "Sample regional cuisine",
                        "location": trip.destination,
                        "category": "food",
                        "cost_estimate": 20.0,
                    },
                    {
                        "time": "15:00",
                        "title": f"Afternoon: Discover {theme}",
                        "description": f"Immersive exploration around {theme}",
                        "location": trip.destination,
                        "category": "culture",
                        "cost_estimate": 15.0,
                    },
                ]

            new_day = {
                "day_number": new_day_num,
                "date": new_date_str,
                "theme": theme,
                "activities": activities,
                "meals": args.get("meals") or ["Regional lunch", "Local dinner"],
                "notes": args.get("notes", f"Added by assistant: {theme}"),
            }
            days.append(new_day)

            # Update trip end date if new date is later
            try:
                new_date_obj = date.fromisoformat(new_date_str)
                trip.end_date = max(trip.end_date, new_date_obj)
            except (ValueError, TypeError):
                pass

            msg = f"Added Day {new_day_num} ({new_date_str}) focused on '{theme}'."

        # ACTION 2: update_activity
        elif action == "update_activity":
            if not day_number:
                return json.dumps({"error": "day_number is required to update an activity."})

            target_day = next((d for d in days if d.get("day_number") == day_number), None)
            if not target_day:
                return json.dumps({"error": f"Day {day_number} not found in this itinerary."})

            act_list: list[dict[str, Any]] = target_day.get("activities", [])
            act_idx = args.get("activity_index")
            matcher = str(args.get("activity_time_or_title", "")).lower()

            # Find target activity index
            if act_idx is None or act_idx >= len(act_list):
                if matcher:
                    for i, a in enumerate(act_list):
                        if (
                            matcher in a.get("title", "").lower()
                            or matcher in a.get("time", "").lower()
                            or matcher in a.get("category", "").lower()
                        ):
                            act_idx = i
                            break
                if act_idx is None:
                    # Default to last activity (e.g. evening/dinner) if user asked about dinner
                    act_idx = (len(act_list) - 1) if ("dinner" in matcher or "evening" in matcher) else 0

            new_act_data = args.get("activity", {})
            if 0 <= act_idx < len(act_list):
                existing = act_list[act_idx]
                for k in ["time", "title", "description", "location", "category", "cost_estimate"]:
                    if k in new_act_data:
                        existing[k] = new_act_data[k]
                msg = f"Updated Day {day_number} activity #{act_idx + 1}: {existing.get('title')} ({existing.get('time')})."
            else:
                # Add as new activity if none found
                act_list.append(new_act_data)
                msg = f"Added new activity to Day {day_number}: {new_act_data.get('title')}."

        # ACTION 3: add_activity
        elif action == "add_activity":
            if not day_number:
                return json.dumps({"error": "day_number is required to add an activity."})
            target_day = next((d for d in days if d.get("day_number") == day_number), None)
            if not target_day:
                return json.dumps({"error": f"Day {day_number} not found in this itinerary."})

            act_data = args.get("activity") or {
                "time": "16:00",
                "title": args.get("theme", "Special Highlight"),
                "description": args.get("notes", ""),
                "location": trip.destination,
                "category": "sightseeing",
                "cost_estimate": 10.0,
            }
            target_day.setdefault("activities", []).append(act_data)
            msg = f"Added activity '{act_data.get('title')}' to Day {day_number}."

        # ACTION 4: remove_activity
        elif action == "remove_activity":
            if not day_number:
                return json.dumps({"error": "day_number is required to remove an activity."})
            target_day = next((d for d in days if d.get("day_number") == day_number), None)
            if not target_day:
                return json.dumps({"error": f"Day {day_number} not found."})

            act_list = target_day.get("activities", [])
            act_idx = args.get("activity_index", 0)
            if 0 <= act_idx < len(act_list):
                removed = act_list.pop(act_idx)
                msg = f"Removed activity '{removed.get('title')}' from Day {day_number}."
            else:
                return json.dumps({"error": "Invalid activity index."})

        else:
            return json.dumps({"error": f"Unsupported itinerary action '{action}'."})

        # Recalculate total estimated cost
        total_cost = 0.0
        for d in days:
            for a in d.get("activities", []):
                total_cost += float(a.get("cost_estimate", 0.0))

        itinerary["days"] = days
        itinerary["total_estimated_cost"] = round(total_cost, 2)
        trip.itinerary = copy.deepcopy(itinerary)
        flag_modified(trip, "itinerary")

        # Save and refresh
        trip = await trip_repo.save(session, trip)

        return json.dumps(
            {
                "status": "success",
                "message": msg,
                "trip_id": str(trip.id),
                "destination": trip.destination,
                "total_days": len(days),
                "total_estimated_cost": itinerary["total_estimated_cost"],
                "currency": trip.currency,
            }
        )
    except Exception as exc:
        logger.exception("modify_itinerary failed")
        return json.dumps({"error": f"Failed to modify itinerary: {exc}"})


async def delete_trip_impl(
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Delete a trip with explicit confirmation."""
    confirmation = str(args.get("confirmation", "")).strip().lower()
    if confirmation != "confirm delete":
        return json.dumps(
            {
                "error": "Destructive action blocked. Please confirm with the user first, and call with confirmation='confirm delete'."
            }
        )

    if session is None or user_id is None:
        return json.dumps({"error": "Session context unavailable."})

    trip_id = args.get("trip_id")
    trip = await _resolve_trip(session, user_id, trip_id)
    if not trip:
        return json.dumps({"error": "Trip not found."})

    try:
        dest = trip.destination
        tid = str(trip.id)
        await trip_repo.delete(session, trip)
        return json.dumps({"status": "deleted", "trip_id": tid, "destination": dest})
    except Exception as exc:
        logger.exception("delete_trip failed")
        return json.dumps({"error": str(exc)})


async def search_destinations_impl(args: dict[str, Any], session: AsyncSession | None = None) -> str:
    """Search catalog destinations."""
    if session is None:
        return json.dumps({"results": [], "message": "Session context unavailable."})

    try:
        from app.services import destination_service

        query = str(args.get("query", "")).strip()
        summaries = await destination_service.search_destinations(session, query=query, limit=10)
        return json.dumps(
            {
                "results": [
                    {
                        "destination": s.destination,
                        "document_count": s.document_count,
                        "categories": s.categories,
                    }
                    for s in summaries
                ]
            }
        )
    except Exception as exc:
        logger.exception("search_destinations failed")
        return json.dumps({"results": [], "error": str(exc)})


async def search_restaurants_impl(args: dict[str, Any], session: AsyncSession | None = None) -> str:
    """Search restaurant recommendations in RAG."""
    dest = str(args.get("destination", "")).strip()
    query = str(args.get("query", "food dining restaurants")).strip()
    full_query = f"{dest} {query} restaurants authentic local food"

    if session is None:
        return json.dumps({"results": [], "message": f"Try local dining specialties in {dest}."})

    try:
        hits = await semantic_search(session, full_query, top_k=4)
        results = [{"title": h.title, "snippet": h.content[:240], "category": h.category} for h in hits]
        return json.dumps({"destination": dest, "results": results})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"destination": dest, "error": str(exc)})


async def search_activities_impl(args: dict[str, Any], session: AsyncSession | None = None) -> str:
    """Search activities and attractions in RAG."""
    dest = str(args.get("destination", "")).strip()
    query = str(args.get("query", "sightseeing highlights attractions")).strip()
    full_query = f"{dest} {query} things to do attractions"

    if session is None:
        return json.dumps({"results": [], "message": f"Explore top attractions in {dest}."})

    try:
        hits = await semantic_search(session, full_query, top_k=4)
        results = [{"title": h.title, "snippet": h.content[:240], "category": h.category} for h in hits]
        return json.dumps({"destination": dest, "results": results})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"destination": dest, "error": str(exc)})


async def search_hotels_impl(args: dict[str, Any], session: AsyncSession | None = None) -> str:
    """Search hotel/neighborhood recommendations in RAG."""
    dest = str(args.get("destination", "")).strip()
    query = str(args.get("query", "neighborhoods stay hotels accommodation")).strip()
    full_query = f"{dest} {query} best areas to stay"

    if session is None:
        return json.dumps({"results": [], "message": f"Recommended areas to stay in {dest}."})

    try:
        hits = await semantic_search(session, full_query, top_k=4)
        results = [{"title": h.title, "snippet": h.content[:240], "category": h.category} for h in hits]
        return json.dumps({"destination": dest, "results": results})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"destination": dest, "error": str(exc)})


async def search_flights_impl(args: dict[str, Any]) -> str:
    """Flight guidance."""
    origin = args.get("origin", "")
    dest = args.get("destination", "")
    return json.dumps(
        {
            "origin": origin,
            "destination": dest,
            "note": f"Live ticket pricing requires airline distribution APIs. Recommend checking Google Flights or Skyscanner for {origin} to {dest}.",
        }
    )


# ---------------------------------------------------------------------------
# Master Async Tool Dispatcher
# ---------------------------------------------------------------------------


async def execute_tool(
    name: str,
    args: dict[str, Any],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Unified executor for all agent tools with session and user context."""
    logger.info("Executing tool '%s' with args=%s (user_id=%s, has_session=%s)", name, args, user_id, session is not None)

    try:
        if name == "convert_currency":
            return await convert_currency_impl(args)
        elif name == "get_weather_forecast":
            return await get_weather_forecast_impl(args)
        elif name == "search_knowledge":
            return await search_knowledge_impl(args, session=session)
        elif name == "create_trip":
            return await create_trip_impl(args, session=session, user_id=user_id)
        elif name == "list_my_trips":
            return await list_my_trips_impl(args, session=session, user_id=user_id)
        elif name == "get_trip":
            return await get_trip_impl(args, session=session, user_id=user_id)
        elif name == "update_trip":
            return await update_trip_impl(args, session=session, user_id=user_id)
        elif name == "modify_itinerary":
            return await modify_itinerary_impl(args, session=session, user_id=user_id)
        elif name == "delete_trip":
            return await delete_trip_impl(args, session=session, user_id=user_id)
        elif name == "search_destinations":
            return await search_destinations_impl(args, session=session)
        elif name == "search_restaurants":
            return await search_restaurants_impl(args, session=session)
        elif name == "search_activities":
            return await search_activities_impl(args, session=session)
        elif name == "search_hotels":
            return await search_hotels_impl(args, session=session)
        elif name == "search_flights":
            return await search_flights_impl(args)
        else:
            return json.dumps({"error": f"Unknown tool '{name}'."})
    except Exception as exc:
        logger.exception("Error executing tool '%s'", name)
        return json.dumps({"error": f"Tool execution failed: {exc}"})


# ---------------------------------------------------------------------------
# Backward-compatibility synchronous map (for stubs / fallback code)
# ---------------------------------------------------------------------------


def _sync_stub(name: str):
    def _call(args: dict[str, Any]) -> str:
        logger.info("Synchronous call to '%s' (fallback wrapper)", name)
        return json.dumps({"name": name, "message": "Invoked through sync wrapper."})

    return _call


TOOL_MAP = {t["function"]["name"]: _sync_stub(t["function"]["name"]) for t in TOOLS}
