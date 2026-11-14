# Project structure

```text
kakaomap/
|-- .gitignore                    # Local artifacts and secret exclusions
|-- README.md                     # Korean project and development guide
|-- tree.md                       # English structure reference
|-- changelog.jsonl               # Internal development history
|-- caution.jsonl                 # Development cautions
|-- hacs.json                     # HACS repository metadata
|-- requirements-dev.txt          # Verified Windows test dependencies
|-- pytest.ini                    # Async test configuration
|-- tests/
|   |-- conftest.py               # Real Home Assistant runtime fixtures
|   |-- test_api.py               # Loopback HTTP and payload tests
|   |-- test_nearby.py            # Nearby keyword/category HTTP, action and Assist tests
|   |-- test_geocode.py           # Address candidates, HTTP errors and tool composition
|   |-- test_config_flow.py       # Setup, replacement, and duplicate tests
|   |-- test_metadata.py          # UI metadata and translation contracts
|   |-- test_llm.py               # Provider registration, tool calls, and lifecycle
|   |-- test_location.py          # Request-user isolation and home/away tool composition
|   |-- test_notifications.py     # Auth alerts, deduplication and recovery
|   |-- test_routes.py            # Route HTTP, normalization and HA action tests
|   |-- test_car_routes.py        # Driving defaults, preferences, tolls and HTTP errors
|   |-- test_route_extensions.py  # ETA rollover/DST, ordered waypoints and alternative comparison
|   |-- test_future_routes.py    # Future endpoint, offset conversion, forecast ETA and validation
|   `-- test_integration.py       # HA action response and lifecycle tests
`-- custom_components/
    `-- kakaomap/
        |-- __init__.py           # Response action registration and cleanup
        |-- api.py                # Async Kakao place, address, nearby and routing client
        |-- routes.py             # Route summary normalization without geometry
        |-- llm.py                # Opt-in Assist provider, tools and instructions
        |-- notifications.py      # Auth error notices and validated-key recovery
        |-- config_flow.py        # API-key setup, replacement, reauthentication
        |-- const.py              # Shared identifiers and request defaults
        |-- manifest.json         # HA metadata; repository URLs need replacement
        |-- services.yaml         # Place, address, nearby and route action fields
        |-- strings.json          # English UI source strings
        `-- translations/
            |-- en.json           # English setup strings
            `-- ko.json           # Korean setup strings
```

The integration has no entities or scheduled polling. The KakaoMap LLM provider
must be selected in a compatible conversation agent. The ignored .venv directory is local only.
