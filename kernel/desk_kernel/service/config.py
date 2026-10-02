from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from desk_kernel.chain import is_address
from desk_kernel.claim import ClaimClass, get_claim

DEFAULT_JWT = "cite-desk-dev-secret-change-me"
DUMMY_TREASURY = "0x1111111111111111111111111111111111111111"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    desk_id: str = "tideline"
    app_env: str = "development"
    #: live = merchant (USDC checkout when the rail is configured).
    #: demo = public reference host: checkout closed, sample briefs, no Hub burn.
    desk_mode: str = "live"
    #: When DESK_MODE=demo the watch scheduler stays off unless this is true.
    desk_demo_scheduler: bool = False
    public_url: str = "http://localhost:8080"
    database_url: str = "sqlite:///./desk.db"
    jwt_secret: str = DEFAULT_JWT
    jwt_ttl_hours: int = 24
    hub_mode: str = "fixture"
    hub_url: str = "https://modelmarket.dev"
    hub_api_key: str = ""
    hub_payment_channel: str = ""
    hub_payment_channel_secret: str = ""
    #: Second seller. `hub_url` above is normally ATLAS, which sells its own products and
    #: answers 404 for `gaia.*`; point this at a hub that federates the sensor relays (the
    #: central Hub) with its own prepaid key. Empty keeps the single-seller behaviour.
    gaia_hub_url: str = ""
    gaia_hub_api_key: str = ""
    seed_demo: bool = True
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    pay_mint_secret: str = ""
    pay_mode: str = "fixture"
    pay_base_rpc_url: str = ""
    pay_base_address: str = ""
    pay_usdc_address: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    pay_base_chain_id: int = 8453
    pay_base_confirmations: int = 2
    pay_invoice_ttl_minutes: int = 45
    pay_late_grace_hours: int = 24
    #: How often the settlement poll runs. This interval is the only thing standing
    #: between a buyer's USDC and their desk key, so it is seconds, not minutes.
    pay_scan_interval_seconds: int = 20
    login_rate_limit: int = 20
    #: Proxies this service sits behind that append to X-Forwarded-For (our own web
    #: container counts as one). Everything further left is caller-supplied.
    trusted_proxy_hops: int = 1
    cookie_secure: bool = False
    fixture_dir: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def is_demo(self) -> bool:
        from desk_kernel.demo import is_demo as _is_demo

        return _is_demo(self)


def assert_runtime_safety(settings: Settings, claim: ClaimClass) -> None:
    if not settings.is_production:
        return
    if not settings.jwt_secret or settings.jwt_secret == DEFAULT_JWT or len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be set to a non-default value in production")
    if settings.is_demo:
        # Public reference host: checkout is closed in pay.py. Fixture Hub + sample
        # seed are the honest demo. Merchant gates (treasury, live Hub) do not apply.
        return
    if settings.seed_demo:
        raise RuntimeError("SEED_DEMO must be false in production")
    if f"{claim.id}:{claim.id}@" in (settings.database_url or ""):
        raise RuntimeError("default database password is not allowed in production")
    if (settings.pay_mode or "live").lower() == "fixture":
        raise RuntimeError("PAY_MODE=fixture is not allowed in production")
    if (settings.hub_mode or "").lower() == "fixture":
        raise RuntimeError("HUB_MODE=fixture is not allowed in production")
    channel = settings.hub_payment_channel.strip()
    channel_secret = settings.hub_payment_channel_secret.strip()
    if bool(channel) != bool(channel_secret):
        raise RuntimeError(
            "HUB_PAYMENT_CHANNEL and HUB_PAYMENT_CHANNEL_SECRET must be set together"
        )
    if not settings.hub_api_key and not channel:
        raise RuntimeError(
            "configure HUB_API_KEY or HUB_PAYMENT_CHANNEL + HUB_PAYMENT_CHANNEL_SECRET in production"
        )
    if not settings.pay_mint_secret:
        raise RuntimeError("PAY_MINT_SECRET is required in production")
    # A production desk that cannot settle is a shop with a till nobody can reach: the
    # buy button 503s and the only route to a desk key is a human reading mail. Refuse to
    # boot instead of selling nothing quietly.
    addr = (settings.pay_base_address or "").strip().lower()
    if addr == DUMMY_TREASURY:
        raise RuntimeError("PAY_BASE_ADDRESS must be a real treasury in production")
    if not addr:
        raise RuntimeError("PAY_BASE_ADDRESS is required in production; checkout cannot open without a treasury")
    if not is_address(addr):
        raise RuntimeError("PAY_BASE_ADDRESS is not a valid Base address")
    if not is_address(settings.pay_usdc_address):
        raise RuntimeError("PAY_USDC_ADDRESS is not a valid token address")


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def current_claim() -> ClaimClass:
    return get_claim(get_settings().desk_id)
