"""Kakao HTTP client; related files: routes.py, const.py, config_flow.py, __init__.py.

Keep credentials and upstream response bodies out of exceptions and logs.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError

from .const import ADDRESS_URL, API_URL, CAR_AVOID, CAR_PRIORITIES, CATEGORY_CODES, CATEGORY_URL, DEFAULT_LIMIT, REQUEST_TIMEOUT, ROUTE_URLS, SEARCH_RECT
from .routes import normalize_car_routes, normalize_routes


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

    # Road-name and lot-number geocoding; related files: __init__.py, llm.py.
    async def async_geocode_address(
        self, *, query: str, limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Return address candidates without silently choosing an ambiguous match."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Enter a road-name or lot-number address.")
        if type(limit) is not int or not 1 <= limit <= 15:
            raise ValueError("Limit must be an integer between 1 and 15.")
        query = query.strip()
        payload = await self._async_request(ADDRESS_URL, {"query": query, "size": limit})
        try:
            documents, meta = payload["documents"], payload["meta"]
            if not isinstance(documents, list) or not isinstance(meta, dict):
                raise ValueError
            total, is_end = meta["total_count"], meta["is_end"]
            if type(total) is not int or total < 0 or type(is_end) is not bool:
                raise ValueError
            addresses = [self._normalize_address(item) for item in documents[:limit]]
        except (KeyError, TypeError, ValueError, OverflowError):
            raise KakaoMapResponseError from None
        return {"query": query, "count": len(addresses), "total_count": total,
                "is_end": is_end, "addresses": addresses}

    @staticmethod
    def _normalize_address(item: dict[str, Any]) -> dict[str, Any]:
        """Keep optional address objects nullable; related file: services.yaml."""
        longitude, latitude = float(item["x"]), float(item["y"])
        if not (math.isfinite(longitude) and math.isfinite(latitude)
                and -180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise ValueError
        name, kind = item["address_name"], item["address_type"]
        if not isinstance(name, str) or not name.strip() or kind not in (
            "REGION", "ROAD", "REGION_ADDR", "ROAD_ADDR",
        ):
            raise ValueError
        result = {"address_name": name, "address_type": kind,
                  "latitude": latitude, "longitude": longitude,
                  "jibun_address": None, "road_address": None, "zone_no": None}
        for key, target in (("address", "jibun_address"), ("road_address", "road_address")):
            detail = item.get(key)
            if detail is None:
                continue
            if not isinstance(detail, dict) or not isinstance(detail["address_name"], str):
                raise ValueError
            result[target] = detail["address_name"]
            if key == "road_address":
                zone_no = detail.get("zone_no")
                if zone_no is not None and not isinstance(zone_no, str):
                    raise ValueError
                result["zone_no"] = zone_no
        return result

    # Nearby search with explicit coordinates; related files: __init__.py, llm.py.
    async def async_search_nearby(
        self, *, latitude: float, longitude: float, query: str = "",
        category: str = "", radius: int = 1000, limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Search an official radius scope, returning center distances in meters."""
        for coordinate, bound in ((latitude, 90), (longitude, 180)):
            if (isinstance(coordinate, bool) or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate) or not -bound <= coordinate <= bound):
                raise ValueError("Invalid center coordinate.")
        if not isinstance(query, str) or not isinstance(category, str):
            raise ValueError("Query and category must be strings.")
        query, category = query.strip(), category.strip()
        if bool(query) == bool(category) or (category and category not in CATEGORY_CODES):
            raise ValueError("Provide exactly one keyword or supported category.")
        if type(radius) is not int or not 1 <= radius <= 20000:
            raise ValueError("Radius must be an integer between 1 and 20000.")
        if type(limit) is not int or not 1 <= limit <= 15:
            raise ValueError("Limit must be an integer between 1 and 15.")
        params = {"x": longitude, "y": latitude, "radius": radius,
                  "size": limit, "sort": "distance"}
        params["query" if query else "category_group_code"] = query or category
        payload = await self._async_request(API_URL if query else CATEGORY_URL, params)
        try:
            documents, meta = payload["documents"], payload["meta"]
            if not isinstance(documents, list) or not isinstance(meta, dict):
                raise ValueError
            total, is_end = meta["total_count"], meta["is_end"]
            if type(total) is not int or total < 0 or type(is_end) is not bool:
                raise ValueError
            places = []
            for place in documents[:limit]:
                normalized = self._normalize_place(place)
                distance = place["distance"]
                if not isinstance(distance, str) or not distance.isascii() or not distance.isdecimal():
                    raise ValueError
                normalized["distance_m"] = int(distance)
                if normalized["distance_m"] > radius:
                    raise ValueError
                places.append(normalized)
            places.sort(key=lambda place: place["distance_m"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise KakaoMapResponseError from None
        return {"query": query, "category": category,
                "center": {"latitude": latitude, "longitude": longitude},
                "radius_m": radius, "count": len(places), "total_count": total,
                "is_end": is_end, "places": places}

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
        priority: str = "RECOMMEND", avoid: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get route summaries using WGS84 coordinates; related file: routes.py."""
        if mode not in ROUTE_URLS:
            raise ValueError("Unsupported travel mode.")
        # Validate driving options before any HTTP call; related file: llm.py.
        if (priority not in CAR_PRIORITIES or (avoid is not None and (
            not isinstance(avoid, list) or any(item not in CAR_AVOID for item in avoid)
        ))):
            raise ValueError("Invalid driving preferences.")
        if mode != "car" and (priority != "RECOMMEND" or avoid):
            raise ValueError("Driving preferences require car mode.")
        for coordinate, bound in (
            (start_latitude, 90), (start_longitude, 180),
            (end_latitude, 90), (end_longitude, 180),
        ):
            if (isinstance(coordinate, bool) or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate) or not -bound <= coordinate <= bound):
                raise ValueError("Invalid coordinate.")
        if (start_latitude, start_longitude) == (end_latitude, end_longitude):
            raise ValueError("Origin and destination must differ.")
        # Use Mobility's separate request/response contract; related file: routes.py.
        if mode == "car":
            if not isinstance(start_name, str) or not isinstance(end_name, str):
                raise ValueError("Point names must be strings.")
            params = {
                "origin": f"{start_longitude},{start_latitude}",
                "destination": f"{end_longitude},{end_latitude}",
                "priority": priority, "summary": "false", "alternatives": "false",
            }
            if avoid:
                params["avoid"] = "|".join(dict.fromkeys(avoid))
            payload = await self._async_request(ROUTE_URLS[mode], params)
            route_url = (
                f"https://map.kakao.com/link/by/car/{quote(start_name, safe='')},{start_latitude},{start_longitude}"
                f"/{quote(end_name, safe='')},{end_latitude},{end_longitude}"
            )
            try:
                return normalize_car_routes(payload, route_url, priority, avoid or [])
            except (KeyError, TypeError, ValueError, OverflowError):
                raise KakaoMapResponseError from None
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
