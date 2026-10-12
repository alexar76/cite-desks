from functools import lru_cache

from desk_kernel.chain import parse_rpc_urls
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT = "emberline-dev-secret-change-me"

__all__ = ["Settings", "get_settings", "parse_rpc_urls"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Emberline"
    app_env: str = "development"
    #: live = merchant. demo = public reference host (checkout closed).
    desk_mode: str = "live"
    desk_demo_scheduler: bool = False
    public_url: str = "http://localhost:8080"  # production: https://emberlinedesk.com
    database_url: str = "sqlite:///./emberline.db"
    jwt_secret: str = _DEFAULT_JWT
    jwt_ttl_hours: int = 24
    hub_mode: str = "fixture"  # fixture | live
    hub_url: str = "https://modelmarket.dev"
    hub_api_key: str = ""
    hub_payment_channel: str = ""
    hub_payment_channel_secret: str = ""
    hub_sandbox_visitor: str = "emberline_desk"
    seed_demo: bool = True
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:8080,http://127.0.0.1:8080"
    pay_mint_secret: str = ""
    ops_secret: str = ""  # optional; empty falls back to PAY_MINT_SECRET
    pay_mode: str = "live"  # live | fixture
    pay_base_rpc_url: str = ""
    pay_base_address: str = ""
    pay_usdc_address: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    pay_base_chain_id: int = 8453
    pay_base_confirmations: int = 2
    pay_invoice_ttl_minutes: int = 45
    # A transfer that lands after the quote lapses still settles for this long.
    # Without it a slow wallet becomes a manual refund.
    pay_late_grace_hours: int = 24
    login_rate_limit: int = 20
    cookie_secure: bool = False
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_mailto: str = "mailto:desk@emberlinedesk.com"

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


def assert_runtime_safety(settings: Settings) -> None:
    if not settings.is_production:
        return
    if not settings.jwt_secret or settings.jwt_secret == _DEFAULT_JWT:
        raise RuntimeError("JWT_SECRET must be set to a non-default value in production")
    if settings.is_demo:
        # Public reference host: checkout closed in basepay. Fixture Hub + sample seed ok.
        return
    if settings.seed_demo:
        raise RuntimeError("SEED_DEMO must be false in production")
    if "emberline:emberline@" in settings.database_url:
        raise RuntimeError("default database password is not allowed in production")
    if (settings.pay_mode or "live").lower() == "fixture":
        raise RuntimeError("PAY_MODE=fixture is not allowed in production")
    if not settings.pay_mint_secret:
        raise RuntimeError("PAY_MINT_SECRET is required in production")
    addr = (settings.pay_base_address or "").strip()
    if addr and addr.lower() == "0x1111111111111111111111111111111111111111":
        raise RuntimeError("PAY_BASE_ADDRESS must be a real treasury in production")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
