"""Agentic tool wrappers (Phase 2B) — OpenAI function-calling format."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool schemas in OpenAI `tools` format (Groq-compatible)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the local knowledge base (RAG) for relevant travel snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g., 'Kyoto temples')"},
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
            "description": "Create a new trip plan. Confirm destructive actions explicitly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "budget": {"type": "string"},
                    "currency": {"type": "string", "default": "USD"},
                    "travelers": {"type": "integer", "default": 1},
                    "travel_style": {"type": "string", "default": "balanced"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["destination", "start_date", "end_date", "budget"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_trip",
            "description": "Update an existing trip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string"},
                    "destination": {"type": "string"},
                    "budget": {"type": "string"},
                    "travel_style": {"type": "string"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["trip_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_trips",
            "description": "List the user's saved trips.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trip",
            "description": "Get details for a specific trip by ID.",
            "parameters": {
                "type": "object",
                "properties": {"trip_id": {"type": "string"}},
                "required": ["trip_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_destinations",
            "description": "Search destinations in the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_trip",
            "description": "Delete a trip. REQUIRES explicit user confirmation string 'confirm delete' in the call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string"},
                    "confirmation": {"type": "string", "description": "Must be exactly 'confirm delete'"},
                },
                "required": ["trip_id", "confirmation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search flights (stub — requires licensed provider).",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search hotels (stub — requires licensed provider).",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "check_in": {"type": "string"},
                    "check_out": {"type": "string"},
                },
                "required": ["destination", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search restaurants (stub — requires licensed provider).",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activities",
            "description": "Search activities (stub — requires licensed provider).",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert currency amounts (stub — requires licensed provider).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "from_currency": {"type": "string"},
                    "to_currency": {"type": "string"},
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
]


def search_knowledge(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_knowledge args=%s", args)
    # Stub: returns empty since retriever requires an AsyncSession
    return json.dumps({"results": [], "message": "Requires session context. Stub response."})


def create_trip(args: dict[str, Any]) -> str:
    logger.info("Tool call: create_trip args=%s", args)
    return json.dumps({"trip_id": "stub", "status": "created (stub)"})


def update_trip(args: dict[str, Any]) -> str:
    logger.info("Tool call: update_trip args=%s", args)
    return json.dumps({"trip_id": args.get("trip_id"), "status": "updated (stub)"})


def list_my_trips(args: dict[str, Any]) -> str:
    logger.info("Tool call: list_my_trips args=%s", args)
    return json.dumps({"trips": [], "count": 0})


def get_trip(args: dict[str, Any]) -> str:
    logger.info("Tool call: get_trip args=%s", args)
    return json.dumps({"trip_id": args.get("trip_id"), "status": "not_found (stub)"})


def search_destinations(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_destinations args=%s", args)
    return json.dumps({"results": [], "message": "Requires session context. Stub response."})


def delete_trip(args: dict[str, Any]) -> str:
    confirmation = args.get("confirmation", "")
    if confirmation.strip().lower() != "confirm delete":
        return json.dumps({"error": "Destructive action blocked. User must provide confirmation='confirm delete'."})
    logger.info("Tool call: delete_trip (confirmed) args=%s", args)
    return json.dumps({"trip_id": args.get("trip_id"), "status": "deleted (stub)"})


def search_flights(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_flights (stub) args=%s", args)
    return json.dumps({"results": [], "message": "Requires licensed provider adapter."})


def search_hotels(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_hotels (stub) args=%s", args)
    return json.dumps({"results": [], "message": "Requires licensed provider adapter."})


def search_restaurants(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_restaurants (stub) args=%s", args)
    return json.dumps({"results": [], "message": "Requires licensed provider adapter."})


def search_activities(args: dict[str, Any]) -> str:
    logger.info("Tool call: search_activities (stub) args=%s", args)
    return json.dumps({"results": [], "message": "Requires licensed provider adapter."})


def convert_currency(args: dict[str, Any]) -> str:
    logger.info("Tool call: convert_currency (stub) args=%s", args)
    return json.dumps({"message": "Requires licensed provider adapter."})


TOOL_MAP = {
    "search_knowledge": search_knowledge,
    "create_trip": create_trip,
    "update_trip": update_trip,
    "list_my_trips": list_my_trips,
    "get_trip": get_trip,
    "search_destinations": search_destinations,
    "delete_trip": delete_trip,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "search_restaurants": search_restaurants,
    "search_activities": search_activities,
    "convert_currency": convert_currency,
}
