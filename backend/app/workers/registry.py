import httpx

from app.core.config import Settings
from app.integrations.apify_client import ApifyClient
from app.integrations.sources.adzuna import AdzunaSource
from app.integrations.sources.apify_indeed import ApifyIndeedSource
from app.integrations.sources.base import JobSource
from app.integrations.sources.external import ExternalScraperSource
from app.integrations.sources.jooble import JoobleSource


def build_sources(client: httpx.AsyncClient, settings: Settings) -> dict[str, JobSource]:
    """Include only sources that are enabled AND have credentials set (ADR-004)."""
    sources: dict[str, JobSource] = {}
    if settings.ADZUNA_ENABLED and settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
        sources["adzuna"] = AdzunaSource(client, settings)
    if settings.JOOBLE_ENABLED and settings.JOOBLE_API_KEY:
        sources["jooble"] = JoobleSource(client, settings)
    if settings.INDEED_ENABLED and settings.APIFY_API_TOKEN:
        sources["indeed"] = ApifyIndeedSource(ApifyClient(client, settings))
    for cfg in settings.EXTERNAL_SCRAPERS:
        sources[cfg.name] = ExternalScraperSource(
            cfg.name, cfg.url, cfg.is_scraped, client, settings
        )
    return sources
