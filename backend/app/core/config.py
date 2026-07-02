from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved from this file so it loads regardless of CWD
# (config.py -> core -> app -> backend -> repo root). OS env vars still take
# precedence, so containers that inject env are unaffected.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


@dataclass(frozen=True)
class AIEndpoint:
    """Resolved connection settings for one AI role (chat or embeddings)."""

    base_url: str | None  # None targets api.openai.com; ".../v1" for Ollama
    api_key: str
    model: str
    send_dimensions: bool = False  # OpenAI text-embedding-3-* only (Matryoshka)


class ExternalScraperConfig(BaseModel):
    """One self-hosted external scraper behind the universal /scrape contract."""

    name: str
    url: str
    is_scraped: bool = True


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str | None = None  # falls back to a per-environment default

    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Auth 
    SECRET_KEY: str 
    ACCESS_TOKEN_LIFETIME_SECONDS: int = 60 * 60 * 24 * 7 # 7 days - persistent sessions
    COOKIE_NAME: str = "jobagent_auth" 
    COOKIE_SECURE: bool = False # set True in production (HTTPS-only cookie)
    FRONTEND_URL: str = "http://localhost:3000" # CORS origin allowed to send the auth cookie

    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_PORT: int = 9000
    MINIO_CONSOLE_PORT: int = 9001

    # S3 / object storage. S3_ENDPOINT_URL=None targets real AWS; set it
    # (e.g. http://localhost:9000 local, http://minio:9000 in Compose) for MinIO.
    S3_ENDPOINT_URL: str | None = None
    # Endpoint used only to build presigned URLs — must be reachable by the client
    # (browser). Defaults to S3_ENDPOINT_URL; override when storage sits on a private
    # network (e.g. MinIO at http://minio:9000 internally, public URL for clients).
    S3_PUBLIC_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "cvs"
    S3_REGION: str = "us-east-1"
    # Server-side encryption algorithm sent on upload (e.g. "AES256"). Leave unset
    # for local MinIO without a KMS; set to "AES256" against real AWS S3.
    S3_SSE: str | None = None

    # CV upload
    CV_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB hard cap
    CV_ALLOWED_MIME: set[str] = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    }
    CV_DOWNLOAD_URL_TTL_SECONDS: int = 300  # presigned GET lifetime

    # ── AI providers ──────────────────────────────────────────────────────────
    # Chat and embeddings are chosen independently, so you can mix providers.
    # Common setups (chat is Ollama Cloud in both A and B):
    #   A) CHAT_PROVIDER=ollama (cloud) + EMBED_PROVIDER=ollama (local)  — fully free
    #   B) CHAT_PROVIDER=ollama (cloud) + EMBED_PROVIDER=openai          — no local models
    # Ollama Cloud serves chat models only (no embeddings), so when chat targets the
    # cloud, embeddings must come from a local Ollama (OLLAMA_EMBED_BASE_URL) or OpenAI.
    CHAT_PROVIDER: Literal["ollama", "openai"] = "ollama"
    EMBED_PROVIDER: Literal["ollama", "openai"] = "ollama"

    # Ollama — local by default. For Ollama Cloud set OLLAMA_BASE_URL=https://ollama.com
    # and OLLAMA_API_KEY=<key from ollama.com/settings/keys>.
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_API_KEY: str | None = None  # required for Ollama Cloud; ignored by local Ollama
    OLLAMA_CHAT_MODEL: str = "gemma3:4b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    # Optional separate Ollama host/key for embeddings — lets chat hit the cloud while
    # embeddings stay on a local Ollama. Default: reuse OLLAMA_BASE_URL / OLLAMA_API_KEY.
    OLLAMA_EMBED_BASE_URL: str | None = None
    OLLAMA_EMBED_API_KEY: str | None = None

    # OpenAI (BYOK). OPENAI_BASE_URL optionally points at an OpenAI-compatible gateway.
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"

    # Ingestion / scraping
    REDIS_URL: str = "redis://localhost:6379"
    EMBED_DIM: int = 768  # must match jobs.embedding Vector(768); text-embedding-3-small uses Matryoshka truncation (dimensions=768)
    SOURCE_HTTP_TIMEOUT: float = 30.0
    INGEST_DEFAULT_QUERIES: list[str] = ["python developer"]  # nightly cron queries

    # Adzuna (sanctioned API)
    ADZUNA_ENABLED: bool = True
    ADZUNA_APP_ID: str | None = None
    ADZUNA_APP_KEY: str | None = None
    ADZUNA_COUNTRY: str = "gb"
    ADZUNA_BASE_URL: str = "https://api.adzuna.com/v1/api"

    # Jooble (sanctioned API)
    JOOBLE_ENABLED: bool = True
    JOOBLE_API_KEY: str | None = None
    JOOBLE_BASE_URL: str = "https://jooble.org/api"

    # Indeed via Apify (scraped — best-effort, off by default)
    INDEED_ENABLED: bool = False
    APIFY_API_TOKEN: str | None = None
    APIFY_INDEED_ACTOR: str = "misceres~indeed-scraper"
    APIFY_BASE_URL: str = "https://api.apify.com/v2"
    APIFY_TIMEOUT: float = 120.0

    # Pluggable external scrapers, each a service exposing POST {url}/scrape. Configure
    # as JSON: EXTERNAL_SCRAPERS='[{"name":"pracuj","url":"http://host:8080"}]'
    EXTERNAL_SCRAPERS: list[ExternalScraperConfig] = []
    EXTERNAL_SCRAPER_TIMEOUT: float = 120.0

    # Email — Postmark
    POSTMARK_API_TOKEN: str | None = None
    POSTMARK_SENDER_EMAIL: str | None = None

    def chat_endpoint(self) -> AIEndpoint:
        """Where chat/completion calls go, based on CHAT_PROVIDER."""
        if self.CHAT_PROVIDER == "openai":
            return AIEndpoint(self.OPENAI_BASE_URL, self.OPENAI_API_KEY or "", self.OPENAI_CHAT_MODEL)
        base = self.OLLAMA_BASE_URL.rstrip("/")
        return AIEndpoint(f"{base}/v1", self.OLLAMA_API_KEY or "ollama", self.OLLAMA_CHAT_MODEL)

    def embed_endpoint(self) -> AIEndpoint:
        """Where embedding calls go, based on EMBED_PROVIDER. Independent of chat so chat
        can hit Ollama Cloud while embeddings stay on a local Ollama or OpenAI."""
        if self.EMBED_PROVIDER == "openai":
            return AIEndpoint(
                self.OPENAI_BASE_URL, self.OPENAI_API_KEY or "", self.OPENAI_EMBED_MODEL,
                send_dimensions=True,
            )
        base = (self.OLLAMA_EMBED_BASE_URL or self.OLLAMA_BASE_URL).rstrip("/")
        key = self.OLLAMA_EMBED_API_KEY or self.OLLAMA_API_KEY or "ollama"
        return AIEndpoint(f"{base}/v1", key, self.OLLAMA_EMBED_MODEL)

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL, assembled from the POSTGRES_* parts."""
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        # An OpenAI key is required whenever either role targets OpenAI.
        if (self.CHAT_PROVIDER == "openai" or self.EMBED_PROVIDER == "openai") and not self.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY must be set when CHAT_PROVIDER or EMBED_PROVIDER is 'openai'."
            )
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY in ("change-me", "", "changeme"):
                raise ValueError("SECRET_KEY must be set to a strong value in production")
            if not self.COOKIE_SECURE:
                self.COOKIE_SECURE = True
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
