"""Kakao place search client; related files: const.py, config_flow.py, __init__.py.

Keep credentials and upstream response bodies out of exceptions and logs.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError

from .const import API_URL, DEFAULT_LIMIT, REQUEST_TIMEOUT, SEARCH_RECT


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
        try:
            async with self._session.get(
                API_URL,
                params={"query": query, "size": limit, "rect": SEARCH_RECT},
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
                payload = await response.json()
        except ContentTypeError:
            raise KakaoMapResponseError from None
        except (ClientError, asyncio.TimeoutError):
            raise KakaoMapConnectionError from None
        except (ValueError, UnicodeError):
            raise KakaoMapResponseError from None

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
