"""Kakao HTTP client; related files: routes.py, const.py, config_flow.py, __init__.py.

Keep credentials and upstream response bodies out of exceptions and logs.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError

from .const import API_URL, DEFAULT_LIMIT, REQUEST_TIMEOUT, ROUTE_URLS, SEARCH_RECT
from .routes import normalize_routes


class KakaoMapError(Exception):
    """Base exception for safe user-facing failures."""


class KakaoMapAuthError(KakaoMapError):
    """The API rejected authentication."""


class KakaoMapPermissionError(KakaoMapError):
    """The app or key does not have permission to use the API."""


class KakaoMapConnectionError(KakaoMapError):
    """The API could not be reached or returned a server error."""


class KakaoMapRateLimitError(KakaoMapError):
    """The API quota or rate limit was reached."""


class KakaoMapResponseError(KakaoMapError):
    """The request or upstream payload was invalid."""


class KakaoMapRouteError(KakaoMapError):
    """The API could not calculate a route for the requested points."""


class KakaoMapClient:
    """Use the caller-owned HTTP session for on-demand searches."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def async_validate(self) -> None:
        """Check authentication with one small, ordinary search request."""
        await self.async_search(name="서울역", limit=1)

    async def async_search(
        self, *, name: str = "", address: str = "", limit: int = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        """Return basic place information; an empty result is successful."""
        query = " ".join(part.strip() for part in (address, name) if part.strip())
        if not query:
            raise ValueError("Enter a place name or address.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 15:
            raise ValueError("Limit must be an integer between 1 and 15.")
        payload = await self._async_request(
            API_URL, {"query": query, "size": limit, "rect": SEARCH_RECT}
        )

        try:
            documents = payload["documents"]
            meta = payload["meta"]
            if not isinstance(documents, list) or not isinstance(meta, dict):
                raise ValueError
            total = meta["total_count"]
            is_end = meta["is_end"]
            if type(total) is not int or total < 0 or type(is_end) is not bool:
                raise ValueError
            places = [self._normalize_place(place) for place in documents[:limit]]
        except (KeyError, TypeError, ValueError, OverflowError):
            raise KakaoMapResponseError from None
        return {
            "query": query,
            "count": len(places),
            "total_count": total,
            "is_end": is_end,
            "places": places,
        }

    async def _async_request(self, url: str, params: dict[str, Any]) -> Any:
        """Share safe HTTP handling between search and routing; see routes.py."""
        try:
            async with self._session.get(
                url,
                params=params,
                headers={"Authorization": f"KakaoAK {self._api_key}"},
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise KakaoMapAuthError from None
                if response.status == 403:
                    raise KakaoMapPermissionError from None
                if response.status == 429:
                    raise KakaoMapRateLimitError from None
                if response.status >= 500:
                    raise KakaoMapConnectionError from None
                if response.status != 200:
                    raise KakaoMapResponseError from None
                return await response.json()
        except ContentTypeError:
            raise KakaoMapResponseError from None
        except (ClientError, asyncio.TimeoutError):
            raise KakaoMapConnectionError from None
        except (ValueError, UnicodeError):
            raise KakaoMapResponseError from None

    async def async_get_route(
        self, *, start_latitude: float, start_longitude: float,
        end_latitude: float, end_longitude: float,
        mode: str = "public_transport", start_name: str = "출발", end_name: str = "도착",
    ) -> dict[str, Any]:
        """Get route summaries using WGS84 coordinates; related file: routes.py."""
        if mode not in ROUTE_URLS:
            raise ValueError("Unsupported travel mode.")
        for coordinate, bound in (
            (start_latitude, 90), (start_longitude, 180),
            (end_latitude, 90), (end_longitude, 180),
        ):
            if (isinstance(coordinate, bool) or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate) or not -bound <= coordinate <= bound):
                raise ValueError("Invalid coordinate.")
        if (start_latitude, start_longitude) == (end_latitude, end_longitude):
            raise ValueError("Origin and destination must differ.")
        payload = await self._async_request(ROUTE_URLS[mode], {
            "start_x": start_longitude, "start_y": start_latitude,
            "end_x": end_longitude, "end_y": end_latitude,
            "s_name": start_name, "e_name": end_name,
            "input_coord": "WGS84", "output_coord": "WGS84",
        })
        if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
            raise KakaoMapResponseError from None
        status = payload["status"]
        empty_status = "NO_RESULTS" if mode == "public_transport" else "ROUTE_RESULT_NOT_FOUND"
        if status == empty_status:
            return {"mode": mode, "count": 0, "routes": [], "route_url": ""}
        messages = {
            "STARTNODES_NULL": "출발지 주변의 대중교통 경로를 찾을 수 없습니다.",
            "ENDNODES_NULL": "도착지 주변의 대중교통 경로를 찾을 수 없습니다.",
            "EQUAL_POINTS": "출발지와 도착지가 같은 위치로 판정되었습니다.",
            "SAME_POINT": "출발지와 도착지가 같은 위치로 판정되었습니다.",
            "START_LINK_NOT_FOUND": "출발지 주변 도로를 찾을 수 없습니다.",
            "END_LINK_NOT_FOUND": "도착지 주변 도로를 찾을 수 없습니다.",
            "TOO_MANY_SEARCH_LINK": "경로가 복잡해 탐색을 완료하지 못했습니다.",
            "TOO_FAR_AWAY": "출발지와 도착지가 너무 멀리 떨어져 있습니다.",
        }
        if status in messages:
            raise KakaoMapRouteError(messages[status]) from None
        if status != "OK":
            raise KakaoMapResponseError from None
        try:
            return normalize_routes(payload, mode)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise KakaoMapResponseError from None

    @staticmethod
    def _normalize_place(place: dict[str, Any]) -> dict[str, Any]:
        """Convert coordinate strings to finite, JSON-compatible numbers."""
        longitude, latitude = float(place["x"]), float(place["y"])
        if not (math.isfinite(longitude) and math.isfinite(latitude)
                and -180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise ValueError
        fields = ("id", "place_name", "address_name", "road_address_name",
                  "phone", "category_name", "place_url")
        normalized = {field: place[field] for field in fields}
        if not all(isinstance(value, str) for value in normalized.values()):
            raise ValueError
        return {**normalized, "latitude": latitude, "longitude": longitude}
