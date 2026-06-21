"""Shared pytest configuration.

Make the suite hermetic: some agent modules call ``load_dotenv()`` at import
time, which loads a developer's real ``.env`` into ``os.environ`` for the whole
test session. If that ``.env`` sets, e.g., ``AGRIBROKER_BUYER_PAYMENT_MODE=stripe``
plus a real ``STRIPE_SECRET_KEY``, tests that don't explicitly override those vars
would create real Stripe checkouts and assert against the wrong payment status.

This autouse fixture clears the behavior-controlling env vars before every test so
results never depend on the machine's ``.env``. Tests that need a specific value
still set it via ``monkeypatch.setenv`` after this fixture runs.
"""

from __future__ import annotations

import pytest

# Env vars that change AgriBroker behavior and may leak in from a local .env.
_NEUTRALIZED_ENV_VARS = (
    "AGRIBROKER_BUYER_PAYMENT_MODE",
    "AGRIBROKER_FARM_PAYMENT_MODE",
    "AGRIBROKER_PAYMENT_MODE",
    "AGRIBROKER_INTENT_MODE",
    "AGRIBROKER_DISCOVERY_MODE",
    "AGRIBROKER_REGISTRY_ADDRESS",
    "AGRIBROKER_CHAT_PROGRESS",
    "STRIPE_SECRET_KEY",
    "STRIPE_CONNECT_TRANSFERS_ENABLED",
    "STRIPE_CONNECT_ONBOARDING_ENABLED",
    "ASI_ONE_API_KEY",
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _NEUTRALIZED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
