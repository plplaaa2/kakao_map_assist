"""Shared identifiers; related files: api.py, routes.py, config_flow.py, __init__.py."""

DOMAIN = "kakaomap"
SERVICE_SEARCH_PLACES = "search_places"
SERVICE_SEARCH_NEARBY = "search_nearby"
# Official nearby category codes; related files: api.py, llm.py, services.yaml.
CATEGORY_CODES = (
    "MT1", "CS2", "PS3", "SC4", "AC5", "PK6", "OL7", "SW8", "BK9",
    "CT1", "AG2", "PO3", "AT4", "AD5", "FD6", "CE7", "HP8", "PM9",
)
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
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
