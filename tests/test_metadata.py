"""Check published UI contracts; related files: manifest.json, services.yaml, translations."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "kakaomap"


def test_ui_metadata_and_translations():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.0"
    assert manifest["config_flow"] is True
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    assert set(services["search_places"]["fields"]) == {"name", "address", "limit"}
    source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for language in ("ko", "en"):
        translated = json.loads((COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8"))
        assert translated["config"]["error"].keys() == source["config"]["error"].keys()
        assert translated["config"]["step"].keys() == source["config"]["step"].keys()
