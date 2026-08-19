from pathlib import Path

import yaml

COMPONENT_MAP = Path("hermes-integration/install/component-map.yaml")


def test_install_component_map_requires_exact_head_verified_factory_package_candidate():
    document = yaml.safe_load(COMPONENT_MAP.read_text(encoding="utf-8"))
    package = document["components"]["FACTORY_PACKAGE"]

    assert package["source"] == "verified_exact_head_factory_package_candidate"
    assert package["mechanism"] == "install_verified_factory_wheel"
    assert "pestoura/hermes-factory" not in COMPONENT_MAP.read_text(encoding="utf-8")
