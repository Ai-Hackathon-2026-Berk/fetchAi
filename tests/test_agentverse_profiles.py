from agents.agentverse_profiles import (
    default_avatar_url,
    farmer_profile_kwargs,
    image_kwargs,
    orchestrator_profile_kwargs,
    registry_profile_kwargs,
    slugify,
)
from agents.workflow import load_farms


def test_slugify_for_agentverse_handles() -> None:
    assert slugify("Sunny Acres") == "sunny-acres"
    assert slugify("Green Valley!") == "green-valley"


def test_registry_profile_metadata() -> None:
    profile = registry_profile_kwargs()

    assert profile["handle"] == "agribroker-registry"
    assert profile["mailbox"] is True
    assert profile["publish_agent_details"] is True
    assert profile["readme_path"] == "docs/agentverse/registry.md"
    assert profile["avatar_url"].startswith("https://")
    assert profile["banner_url"].startswith("https://")


def test_orchestrator_profile_metadata() -> None:
    profile = orchestrator_profile_kwargs()

    assert profile["handle"] == "agribroker-orchestrator"
    assert profile["readme_path"] == "docs/agentverse/orchestrator.md"
    assert "optimizer" in profile["metadata"]["tags"]
    assert profile["avatar_url"].startswith("https://")


def test_farmer_profile_metadata_for_green_valley() -> None:
    farm = next(farm for farm in load_farms() if farm.name == "Green Valley")
    profile = farmer_profile_kwargs(farm)

    assert profile["handle"] == "agribroker-green-valley"
    assert profile["readme_path"] == "docs/agentverse/green-valley.md"
    assert profile["metadata"]["stripe_connected_account_id"] == "acct_demo_green_valley"
    assert "tomatoes" in profile["metadata"]["items"]
    assert profile["avatar_url"].startswith("https://")


def test_profile_image_overrides(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_AGENT_AVATAR_URL", "https://example.test/avatar.png")
    monkeypatch.setenv("AGRIBROKER_REGISTRY_AVATAR_URL", "https://example.test/registry.png")

    assert image_kwargs("registry")["avatar_url"] == "https://example.test/registry.png"
    assert image_kwargs("farmer")["avatar_url"] == "https://example.test/avatar.png"


def test_default_avatar_url_is_public_svg() -> None:
    assert default_avatar_url("Farm A").startswith("https://api.dicebear.com/")
