# Project structure

```text
kakaomap/
|-- .gitignore                    # Local artifacts and secret exclusions
|-- README.md                     # Korean project and development guide
|-- tree.md                       # English structure reference
|-- changelog.jsonl               # Internal development history
|-- caution.jsonl                 # Development cautions
|-- hacs.json                     # HACS repository metadata
`-- custom_components/
    `-- kakaomap/
        |-- __init__.py           # Integration package; no setup logic yet
        |-- const.py              # Shared domain identifier
        `-- manifest.json         # HA metadata with publishing placeholders
```

Add config flows, translations, platforms, coordinators, services, and tests
only when their corresponding behavior is implemented.
