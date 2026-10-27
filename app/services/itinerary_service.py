"""LLM-backed itinerary generation with deterministic fallback.

Phase 1 contract:
- If a Groq key is configured, use the Groq provider (`GPT-OSS-120b`).
  The client is OpenAI-compatible, so the same interface is used.
- Otherwise (local dev / CI / no key), build a sensible template itinerary so the
  end-to-end flow works without external calls.
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.schemas.itinerary import Activity, DayPlan, Itinerary, ItinerarySource
from app.services import tools as agent_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a travel planner. Given trip constraints, output ONLY valid JSON
matching this schema:
{"summary": str, "total_estimated_cost": number, "currency": str, "days": [
  {"day_number": int, "date": "YYYY-MM-DD", "theme": str,
   "activities": [{"time": "HH:MM", "title": str, "description": str,
                   "location": str, "category": str, "cost_estimate": number}],
   "meals": [str], "notes": str}]}
Rules: 3-5 activities per day, respect budget (total_estimated_cost <= budget),
spread interests across days, include meal suggestions, keep locations in/near destination.
When "Relevant local knowledge" is provided, ground recommendations in it and prefer
those neighborhoods, dishes, and tips over generic suggestions.
"""


def _first_sentence(text: str, max_len: int = 200) -> str:
    """First sentence of a chunk, trimmed — used to ground fallback descriptions."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if idx != -1:
            text = text[: idx + 1]
            break
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _fallback_itinerary(
    *,
    destination: str,
    start: date,
    end: date,
    budget: Decimal,
    currency: str,
    travelers: int,
    travel_style: str,
    interests: list[str],
    sources: list[ItinerarySource] | None = None,
) -> Itinerary:
    """Deterministic template so the flow works with no API key.

    When knowledge-base `sources` are provided, the morning highlight of each day
    is grounded in a retrieved snippet so even the fallback reflects the RAG corpus.
    """
    sources = sources or []
    knowledge = [s for s in sources if s.snippet]
    n_days = (end - start).days + 1
    focus = interests or ["sightseeing", "food", "culture"]
    per_day = float(budget) / max(n_days, 1)
    days: list[DayPlan] = []
    for i in range(n_days):
        day_date = start + timedelta(days=i)
        theme = focus[i % len(focus)]
        morning, afternoon = focus[i % len(focus)], focus[(i + 1) % len(focus)]
        morning_description = f"Morning {morning} highlight, {travel_style} pace for {travelers} traveler(s)."
        day_notes = "Template itinerary (no LLM key configured)."
        if knowledge:
            src = knowledge[i % len(knowledge)]
            grounded = _first_sentence(src.snippet)
            if grounded:
                morning_description = grounded
            day_notes = f"Grounded in “{src.title}” (knowledge base)."
        days.append(
            DayPlan(
                day_number=i + 1,
                date=day_date.isoformat(),
                theme=f"{theme.title()} in {destination} ({travel_style} pace)",
                activities=[
                    Activity(
                        time="09:00",
                        title=f"Explore {destination} — {morning}",
                        description=morning_description,
                        location=destination,
                        category=morning,
                        cost_estimate=round(per_day * 0.3, 2),
                    ),
                    Activity(
                        time="13:00",
                        title="Local lunch",
                        description="Restaurant pick near the morning stop.",
                        location=destination,
                        category="food",
                        cost_estimate=round(per_day * 0.25, 2),
                    ),
                    Activity(
                        time="15:00",
                        title=f"Afternoon — {afternoon}",
                        description=f"Afternoon {afternoon} activity with downtime built in.",
                        location=destination,
                        category=afternoon,
                        cost_estimate=round(per_day * 0.3, 2),
                    ),
                    Activity(
                        time="19:30",
                        title="Dinner + evening stroll",
                        description="Dinner followed by an easy evening walk.",
                        location=destination,
                        category="food",
                        cost_estimate=round(per_day * 0.15, 2),
                    ),
                ],
                meals=["Breakfast at hotel", "Local lunch", "Dinner"],
                notes=day_notes,
            )
        )
    grounded_note = f" Grounded in {len(knowledge)} local source(s)." if knowledge else ""
    return Itinerary(
        summary=f"{n_days}-day {travel_style} trip to {destination} for {travelers} traveler(s), "
        f"focused on {', '.join(focus)}.{grounded_note}",
        total_estimated_cost=float(budget) * 0.9,
        currency=currency,
        days=days,
        sources=sources,
    )


def _llm_candidates() -> list[tuple[str, str, str, str]]:
    """Return configured provider: Groq (primary) or OpenAI (alternative)."""
    provider = (settings.LLM_PROVIDER or "groq").lower()
    if provider not in {"groq"}:
        provider = "groq"

    groq_key = settings.GROQ_API_KEY.strip()

    providers = [provider]
    candidates: list[tuple[str, str, str, str]] = []
    for name in providers:
        if name == "groq" and groq_key:
            candidates.append(("groq", groq_key, settings.GROQ_MODEL, settings.GROQ_BASE_URL))
    return candidates


def _resolve_llm() -> tuple[str, str, str, str] | None:
    """Return the primary provider tuple, or None when no key is configured."""
    candidates = _llm_candidates()
    return candidates[0] if candidates else None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8), reraise=True)
def _call_provider(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    user_prompt: str,
    tools: list[dict] | None = None,
) -> str:
    from openai import BadRequestError, OpenAI

    kwargs: dict = {"api_key": api_key, "timeout": settings.LLM_TIMEOUT_SECONDS}
    if base_url:
        kwargs["base_url"] = base_url
    logger.info("Calling LLM provider=%s model=%s tools=%s", provider, model, bool(tools))
    client = OpenAI(**kwargs)
    request: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    if tools:
        request["tools"] = tools
        request["tool_choice"] = "auto"
    try:
        resp = client.chat.completions.create(**request, response_format={"type": "json_object"})
    except BadRequestError:
        logger.warning("provider=%s rejected json_object mode — retrying without it", provider)
        if tools:
            request.pop("response_format", None)
        resp = client.chat.completions.create(**request)
    # Handle function/tool calling
    message = resp.choices[0].message
    if message.tool_calls:
        results = []
        for call in message.tool_calls:
            fn_name = call.function.name
            fn_args = json.loads(call.function.arguments or "{}")
            fn_result = agent_tools.TOOL_MAP.get(fn_name, lambda a: json.dumps({"error": "unknown tool"}))(fn_args)
            results.append({"name": fn_name, "args": fn_args, "result": fn_result})
        return json.dumps({"tool_calls": results})
    return message.content or "{}"


def _call_llm(user_prompt: str, tools: list[dict] | None = None) -> str:
    """Try each configured provider in priority order, returning the first success."""
    candidates = _llm_candidates()
    if not candidates:
        raise RuntimeError("No LLM key configured")

    last_exc: Exception | None = None
    for provider, api_key, model, base_url in candidates:
        try:
            return _call_provider(provider, api_key, model, base_url, user_prompt, tools=tools)
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            logger.warning("LLM provider=%s failed (%s)", provider, exc)
            last_exc = exc
    raise RuntimeError("All configured LLM providers failed") from last_exc


MAX_ITERATIONS = 5


def agent_loop(user_prompt: str, max_iterations: int = MAX_ITERATIONS) -> str:
    """Agent loop: act (LLM + tools) -> observe -> respond. Keeps deterministic fallback."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]
    for iteration in range(1, max_iterations + 1):
        logger.info("Agent loop iteration %d/%d", iteration, max_iterations)
        user_content = messages[-1]["content"] if messages else user_prompt
        raw = _call_llm(str(user_content), tools=agent_tools.TOOLS)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"response": raw}
        tool_results = parsed.get("tool_calls")
        if tool_results:
            observations = []
            for result in tool_results:
                observations.append(f"Tool {result.get('name')} result: {result.get('result')}")
                # Confirm-before-write enforced in delete_trip; max-iterations enforced by loop
            messages.append({"role": "assistant", "content": f"Used tools: {[r.get('name') for r in tool_results]}"})
            messages.append({"role": "user", "content": "\n".join(observations)})
            continue
        else:
            response_text = parsed.get("response", raw) if isinstance(parsed, dict) else raw
            messages.append({"role": "assistant", "content": response_text})
            return response_text
    return "Agent reached max iterations without final response. Fallback applied."


def _knowledge_block(sources: list[ItinerarySource]) -> str:
    usable = [s for s in sources if s.snippet]
    if not usable:
        return ""
    lines = "\n".join(f"- [{s.title}] {s.snippet}" for s in usable)
    return f"\nRelevant local knowledge (ground your plan in these; do not invent facts beyond them):\n{lines}\n"


def generate_itinerary(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    budget: Decimal,
    currency: str = "USD",
    travelers: int = 1,
    travel_style: str = "balanced",
    interests: list[str] | None = None,
    sources: list[ItinerarySource] | None = None,
) -> Itinerary:
    interests = interests or []
    sources = sources or []
    if _resolve_llm() is None:
        logger.info("No LLM key set (GROQ_API_KEY) — using fallback generator")
        return _fallback_itinerary(
            destination=destination,
            start=start_date,
            end=end_date,
            budget=budget,
            currency=currency,
            travelers=travelers,
            travel_style=travel_style,
            interests=interests,
            sources=sources,
        )
    n_days = (end_date - start_date).days + 1
    user_prompt = (
        f"Destination: {destination}\nDates: {start_date} to {end_date} ({n_days} days)\n"
        f"Budget: {budget} {currency}\nTravelers: {travelers}\n"
        f"Travel style: {travel_style}\nInterests: {', '.join(interests) or 'general'}\n"
        f"Total estimated cost must be <= {budget} {currency}."
        f"{_knowledge_block(sources)}"
    )
    try:
        raw = _call_llm(user_prompt)
        data = json.loads(raw)
        data.setdefault("currency", currency)
        itinerary = Itinerary.model_validate(data)
        if itinerary.total_estimated_cost > float(budget):
            itinerary.total_estimated_cost = float(budget) * 0.95
        itinerary.sources = sources
        return itinerary
    except Exception as exc:  # noqa: BLE001 - any LLM/parse/validation failure falls back to template
        logger.warning("LLM call failed (%s) — falling back to template", exc)
        return _fallback_itinerary(
            destination=destination,
            start=start_date,
            end=end_date,
            budget=budget,
            currency=currency,
            travelers=travelers,
            travel_style=travel_style,
            interests=interests,
            sources=sources,
        )
