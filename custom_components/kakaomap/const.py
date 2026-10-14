"""Shared identifiers; related files: api.py, config_flow.py, __init__.py."""

DOMAIN = "kakaomap"
SERVICE_SEARCH_PLACES = "search_places"
API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
# Include Korea and nearby islands without restricting searches to the HA home.
SEARCH_RECT = "124,32,132,40"
DEFAULT_LIMIT = 5
REQUEST_TIMEOUT = 10
