"""Thin HTTP client for the FastAPI travel-agent backend (Phase 1)."""

import os

import requests

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


class ApiError(Exception):
    pass


class TravelApiClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    # -- helpers ---------------------------------------------------------
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{API_PREFIX}{path}"

    def _raise(self, resp: requests.Response) -> None:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        if isinstance(detail, dict):
            msg = detail.get("detail", detail)
        else:
            msg = detail
        raise ApiError(f"[{resp.status_code}] {msg}")

    # -- health ----------------------------------------------------------
    def health(self) -> dict:
        resp = requests.get(f"{self.base_url}/health", timeout=10)
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()

    # -- auth ------------------------------------------------------------
    def register(self, email: str, password: str, full_name: str | None = None) -> dict:
        resp = requests.post(
            self._url("/auth/register"),
            json={"email": email, "password": password, "full_name": full_name},
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            self._raise(resp)
        return resp.json()

    def login(self, email: str, password: str) -> str:
        resp = requests.post(
            self._url("/auth/login"),
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()["access_token"]

    def me(self) -> dict:
        resp = requests.get(self._url("/auth/me"), headers=self._headers(), timeout=10)
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()

    # -- trips -----------------------------------------------------------
    def list_trips(self, limit: int = 50, offset: int = 0) -> list[dict]:
        resp = requests.get(
            self._url("/trips"),
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
            timeout=15,
        )
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()

    def create_trip(self, payload: dict) -> dict:
        resp = requests.post(self._url("/trips"), headers=self._headers(), json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            self._raise(resp)
        return resp.json()

    def get_trip(self, trip_id: str) -> dict:
        resp = requests.get(self._url(f"/trips/{trip_id}"), headers=self._headers(), timeout=15)
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()

    def update_trip(self, trip_id: str, payload: dict) -> dict:
        resp = requests.patch(
            self._url(f"/trips/{trip_id}"),
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()

    def delete_trip(self, trip_id: str) -> None:
        resp = requests.delete(self._url(f"/trips/{trip_id}"), headers=self._headers(), timeout=15)
        if resp.status_code not in (200, 204):
            self._raise(resp)

    def regenerate(self, trip_id: str) -> dict:
        resp = requests.post(
            self._url(f"/trips/{trip_id}/generate"),
            headers=self._headers(),
            timeout=120,
        )
        if resp.status_code != 200:
            self._raise(resp)
        return resp.json()
