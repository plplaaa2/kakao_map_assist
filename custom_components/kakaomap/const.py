"""Shared identifiers; related files: api.py, routes.py, config_flow.py, __init__.py."""

DOMAIN = "kakaomap"
SERVICE_SEARCH_PLACES = "search_places"
SERVICE_GET_ROUTE = "get_route"
ROUTE_URLS = {
    "public_transport": "https://dapi.kakao.com/v2/routing/publictraffic",
    "walk": "https://dapi.kakao.com/v2/routing/walk",
    "bicycle": "https://dapi.kakao.com/v2/routing/bicycle",
}
API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
# Include Korea and nearby islands without restricting searches to the HA home.
SEARCH_RECT = "124,32,132,40"
DEFAULT_LIMIT = 5
REQUEST_TIMEOUT = 10
