"""Normalize route summaries for conversation; related files: api.py, services.yaml.

Exclude route geometry to keep action responses readable and compact.
"""

from typing import Any


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
