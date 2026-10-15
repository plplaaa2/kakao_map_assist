"""Normalize route summaries for conversation; related files: api.py, services.yaml.

Exclude route geometry to keep action responses readable and compact.
"""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import CAR_PRIORITIES


def _number(value: Any) -> int:
    """Validate nonnegative API durations, distances, fares, and transfers."""
    if type(value) is not int or value < 0:
        raise ValueError
    return value


def _text(value: Any) -> str:
    """Reject unexpected structures without copying them into errors."""
    if not isinstance(value, str):
        raise ValueError
    return value


def _list(value: Any) -> list:
    """Require a JSON list for route and step collections."""
    if not isinstance(value, list):
        raise ValueError
    return value


def _step(step: dict[str, Any], mode: str) -> dict[str, Any]:
    """Keep guidance, stops and vehicle names without path coordinates."""
    props = step["properties"]
    result = {
        "guidance": _text(props["guidance"]),
        "distance_m": _number(props["distance"]),
        "duration_s": _number(props["time"]),
        "mode": _text(props["type"]) if mode == "public_transport" else mode,
    }
    if mode == "public_transport":
        result["stops"] = [_text(stop["name"]) for stop in _list(props.get("stops", []))]
        result["vehicles"] = [
            {"name": _text(vehicle["name"]), "type": _text(vehicle["type"])}
            for vehicle in _list(props.get("vehicles", []))
        ]
    return result


def normalize_routes(payload: dict[str, Any], mode: str) -> dict[str, Any]:
    """Return consistent units and lists for all three Kakao route responses."""
    transit = mode == "public_transport"
    raw_routes = _list(payload["routes"]) if transit else [payload["route"]]
    route_url = _text(payload["properties"]["landingURL"]) if transit else _text(
        payload["route"]["properties"]["landingUrl"]
    )
    routes = []
    for route in raw_routes:
        props = route["properties"]
        duration = _number(props["totalTime"])
        summary = {
            "mode": _text(props["type"]) if transit else mode,
            "distance_m": _number(props["totalDistance"]),
            "duration_s": duration,
            "duration_minutes": round(duration / 60, 1),
            "transfers": _number(props["transfers"]) if transit else None,
            "fare": None,
            "route_url": route_url,
        }
        if transit:
            fare = props.get("fare")
            if fare is not None:
                if not isinstance(fare, dict):
                    raise ValueError
                summary["fare"] = {key: _number(fare[key]) for key in ("value", "min", "max") if key in fare}
            steps = _list(route["steps"])
        else:
            steps = [step for leg in _list(route["legs"]) for step in _list(leg["steps"])]
        summary["steps"] = [_step(step, mode) for step in steps]
        routes.append(summary)
    return {"mode": mode, "count": len(routes), "routes": routes, "route_url": route_url}


# Mobility driving summaries without road geometry; related files: api.py, services.yaml.
def normalize_car_routes(
    payload: dict[str, Any], route_url: str, priority: str, avoid: list[str],
    alternatives: bool = False,
) -> dict[str, Any]:
    """Preserve driving units, tolls and guidance without confusing taxi estimates with tolls."""
    from .api import KakaoMapRouteError

    raw_routes = _list(payload["routes"])
    if not raw_routes:
        raise ValueError
    routes = []
    skipped = 0
    for index, route in enumerate(raw_routes, 1):
        code = route["result_code"]
        if type(code) is not int:
            raise ValueError
        if code != 0:
            if alternatives and routes:
                skipped += 1
                continue
            raise KakaoMapRouteError("자동차 경로를 찾을 수 없습니다. 출발·도착 위치와 경로 조건을 확인하세요.")
        summary = route["summary"]
        duration = _number(summary["duration"])
        actual_priority = _text(summary["priority"])
        if actual_priority not in CAR_PRIORITIES:
            raise ValueError
        fare = summary["fare"]
        toll = _number(fare["toll"])
        steps = []
        for section in _list(route["sections"]):
            for guide in _list(section["guides"]):
                steps.append({
                    "guidance": _text(guide["guidance"]),
                    "distance_m": _number(guide["distance"]),
                    "duration_s": _number(guide["duration"]), "mode": "car",
                })
        routes.append({
            "mode": "car", "distance_m": _number(summary["distance"]),
            "duration_s": duration, "duration_minutes": round(duration / 60, 1),
            "transfers": None, "fare": None, "toll_fare": toll,
            "priority": actual_priority, "route_url": route_url, "steps": steps,
            "route_index": index, "is_primary": index == 1,
        })
    result = {"mode": "car", "count": len(routes), "route_url": route_url,
              "priority": priority, "avoid": list(avoid), "routes": routes,
              "alternatives_requested": alternatives, "skipped_alternatives": skipped}
    if alternatives:
        primary = routes[0]
        for route in routes:
            route["difference_from_primary"] = {
                "duration_s": route["duration_s"] - primary["duration_s"],
                "distance_m": route["distance_m"] - primary["distance_m"],
                "toll_fare": route["toll_fare"] - primary["toll_fare"],
            }
    return result


# Request-time arrival estimates for every travel mode; related files: api.py, README.md.
def add_arrival_times(
    result: dict[str, Any], departure_time: datetime, time_zone: ZoneInfo,
) -> dict[str, Any]:
    """Add elapsed seconds in UTC before local conversion to handle date and DST changes."""
    if not result["routes"]:
        return result
    result["departure_time"] = departure_time.astimezone(time_zone).isoformat()
    result["time_zone"] = time_zone.key
    for route in result["routes"]:
        route["arrival_time"] = (
            departure_time + timedelta(seconds=route["duration_s"])
        ).astimezone(time_zone).isoformat()
    return result
