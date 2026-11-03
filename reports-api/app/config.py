"""Reports API configuration, loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Issuer as it appears in the token (external host as seen by the browser).
    keycloak_issuer: str = "http://localhost:8080/realms/reports-realm"
    # Base URL the API uses to reach Keycloak from inside docker to fetch JWKS.
    keycloak_internal_url: str = "http://keycloak:8080"
    keycloak_realm: str = "reports-realm"

    reports_api_audience: str = "reports-api"
    reports_required_role: str = "prothetic_user"
    frontend_origin: str = "http://localhost:3000"

    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def jwks_uri(self) -> str:
        return (
            f"{self.keycloak_internal_url}/realms/{self.keycloak_realm}"
            "/protocol/openid-connect/certs"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
