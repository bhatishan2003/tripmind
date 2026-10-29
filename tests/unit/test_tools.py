"""Unit & integration tests for agent tools and function calling execution."""

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.database import Base
from app.db.models.trip import Trip
from app.db.models.user import User
from app.services.tools import execute_tool

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_context():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        user = User(email="traveler@example.com", hashed_password=hash_password("pw123"), full_name="Agent Tester")
        s.add(user)
        await s.commit()
        await s.refresh(user)

        # Create a sample 3-day trip
        trip = Trip(
            user_id=user.id,
            destination="Kyoto",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3),
            budget=Decimal("2000.00"),
            currency="USD",
            travelers=2,
            travel_style="balanced",
            interests=["culture", "food"],
            status="planned",
            itinerary={
                "summary": "3-day Kyoto trip",
                "total_estimated_cost": 600.0,
                "currency": "USD",
                "days": [
                    {
                        "day_number": 1,
                        "date": "2026-04-01",
                        "theme": "Historic Higashiyama",
                        "activities": [
                            {"time": "09:00", "title": "Kiyomizu-dera", "category": "culture", "cost_estimate": 10.0},
                            {"time": "19:00", "title": "Dinner at Casual Izakaya", "category": "food", "cost_estimate": 40.0},
                        ],
                    },
                    {
                        "day_number": 2,
                        "date": "2026-04-02",
                        "theme": "Central Kyoto & Markets",
                        "activities": [
                            {"time": "09:30", "title": "Nishiki Market Tour", "category": "food", "cost_estimate": 25.0},
                            {"time": "19:00", "title": "Hotel Dinner", "category": "food", "cost_estimate": 50.0},
                        ],
                    },
                    {
                        "day_number": 3,
                        "date": "2026-04-03",
                        "theme": "Northern Temples",
                        "activities": [
                            {"time": "09:00", "title": "Kinkaku-ji", "category": "culture", "cost_estimate": 15.0},
                        ],
                    },
                ],
            },
        )
        s.add(trip)
        await s.commit()
        await s.refresh(trip)

        uid = user.id
        tid = trip.id

    async with Session() as s:
        yield s, uid, tid

    await engine.dispose()


@pytest.mark.asyncio
async def test_convert_currency_frankfurter():
    res_str = await execute_tool("convert_currency", {"amount": 100, "from_currency": "USD", "to_currency": "EUR"})
    res = json.loads(res_str)
    assert "error" not in res
    assert res["from_currency"] == "USD"
    assert res["to_currency"] == "EUR"
    assert res["amount"] == 100.0
    assert res["converted_amount"] > 0
    assert res["rate"] > 0


@pytest.mark.asyncio
async def test_convert_currency_same_currency():
    res_str = await execute_tool("convert_currency", {"amount": 50, "from_currency": "USD", "to_currency": "USD"})
    res = json.loads(res_str)
    assert res["rate"] == 1.0
    assert res["converted_amount"] == 50.0


@pytest.mark.asyncio
async def test_get_weather_forecast_open_meteo():
    res_str = await execute_tool("get_weather_forecast", {"destination": "Kyoto"})
    res = json.loads(res_str)
    assert "error" not in res
    assert "Kyoto" in res["destination"]
    assert len(res["days"]) > 0
    assert "packing_advice" in res
    assert isinstance(res["packing_advice"], list)


@pytest.mark.asyncio
async def test_list_and_get_trip(db_context):
    session, uid, tid = db_context

    # List trips
    list_str = await execute_tool("list_my_trips", {}, session=session, user_id=uid)
    listed = json.loads(list_str)
    assert listed["total"] == 1
    assert listed["trips"][0]["destination"] == "Kyoto"

    # Get trip by ID
    get_str = await execute_tool("get_trip", {"trip_id": str(tid)}, session=session, user_id=uid)
    detail = json.loads(get_str)
    assert detail["destination"] == "Kyoto"
    assert len(detail["itinerary"]["days"]) == 3


@pytest.mark.asyncio
async def test_modify_itinerary_add_day(db_context):
    session, uid, tid = db_context

    # Request: "Add a 4th day to my Kyoto trip focused on Arashiyama bamboo forest"
    payload = {
        "destination": "Kyoto",
        "action": "add_day",
        "day_number": 4,
        "theme": "Arashiyama Bamboo Forest & Western Kyoto",
        "notes": "Enjoy the bamboo groves and monkey park",
    }

    res_str = await execute_tool("modify_itinerary", payload, session=session, user_id=uid)
    res = json.loads(res_str)
    assert res["status"] == "success"
    assert res["total_days"] == 4

    # Verify persisted in database
    get_str = await execute_tool("get_trip", {"trip_id": str(tid)}, session=session, user_id=uid)
    detail = json.loads(get_str)
    days = detail["itinerary"]["days"]
    assert len(days) == 4
    day4 = days[3]
    assert day4["day_number"] == 4
    assert "Arashiyama" in day4["theme"]


@pytest.mark.asyncio
async def test_modify_itinerary_update_activity(db_context):
    session, uid, tid = db_context

    # Request: "Change Day 2 dinner to an authentic ramen shop."
    payload = {
        "destination": "Kyoto",
        "action": "update_activity",
        "day_number": 2,
        "activity_time_or_title": "dinner",
        "activity": {
            "time": "19:00",
            "title": "Authentic Ramen at Gion",
            "description": "Rich tonkotsu ramen with seasonal local appetizers",
            "location": "Gion, Kyoto",
            "category": "food",
            "cost_estimate": 18.0,
        },
    }

    res_str = await execute_tool("modify_itinerary", payload, session=session, user_id=uid)
    res = json.loads(res_str)
    assert res["status"] == "success"

    # Verify persisted in database
    get_str = await execute_tool("get_trip", {"trip_id": str(tid)}, session=session, user_id=uid)
    detail = json.loads(get_str)
    day2_acts = detail["itinerary"]["days"][1]["activities"]
    dinner_act = [a for a in day2_acts if "Ramen" in a["title"]]
    assert len(dinner_act) == 1
    assert dinner_act[0]["cost_estimate"] == 18.0
    assert dinner_act[0]["category"] == "food"


@pytest.mark.asyncio
async def test_delete_trip_requires_confirmation(db_context):
    session, uid, tid = db_context

    # Attempt delete without explicit confirmation string
    blocked_str = await execute_tool("delete_trip", {"trip_id": str(tid), "confirmation": "yes"}, session=session, user_id=uid)
    blocked = json.loads(blocked_str)
    assert "error" in blocked

    # Delete with explicit 'confirm delete'
    confirmed_str = await execute_tool(
        "delete_trip", {"trip_id": str(tid), "confirmation": "confirm delete"}, session=session, user_id=uid
    )
    confirmed = json.loads(confirmed_str)
    assert confirmed["status"] == "deleted"

    # Confirm it is gone
    list_str = await execute_tool("list_my_trips", {}, session=session, user_id=uid)
    assert json.loads(list_str)["total"] == 0
