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
|   |-- test_config_flow.py       # Setup, replacement, and duplicate tests
|   |-- test_metadata.py          # UI metadata and translation contracts
|   `-- test_integration.py       # HA action response and lifecycle tests
`-- custom_components/
    `-- kakaomap/
        |-- __init__.py           # Response action registration and cleanup
        |-- api.py                # Async Kakao keyword search client
        |-- config_flow.py        # API-key setup, replacement, reauthentication
        |-- const.py              # Shared identifiers and request defaults
        |-- manifest.json         # HA metadata; repository URLs need replacement
        |-- services.yaml         # Search action fields
        |-- strings.json          # English UI source strings
        `-- translations/
            |-- en.json           # English setup strings
            `-- ko.json           # Korean setup strings
```

Version 0.1.0 has no entities or scheduled polling. Conversation-agent tool
registration is a future extension. The ignored .venv directory is local only.
