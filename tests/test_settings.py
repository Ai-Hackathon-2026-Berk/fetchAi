import pytest

from agents.settings import discovery_mode


def test_discovery_mode_accepts_business() -> None:
    assert discovery_mode("business") == "business"


def test_discovery_mode_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        discovery_mode("unknown")
