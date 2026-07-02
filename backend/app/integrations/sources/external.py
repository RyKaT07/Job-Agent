from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.logger import get_logger
from app.integrations.sources.base import RawJob

logger = get_logger("app.integrations.sources.external")

_RETRY = dict(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    wait=wait_exponential(multiplier=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class ExternalScraperSource:
    """A JobSource backed by an external scraping service over a fixed contract:

        POST {base_url}/scrape  {"query", "location", "limit"}
        -> 200 {"jobs": [{"source_job_id", "title", "url", "description",
                          "company", "location", "posted_at"}]}

    Any service conforming to it plugs in by config. A non-2xx response raises and the
    ingestion service skips this source for the run.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        is_scraped: bool,
        client: httpx.AsyncClient,
        settings: Settings,
    ) -> None:
        self.name = name
        self.is_scraped = is_scraped  # typically True — loses to sanctioned APIs on dedup
        self._url = base_url.rstrip("/") + "/scrape"
        self._client = client
        self._settings = settings

    @retry(**_RETRY)
    async def _post(self, body: dict) -> dict:
        resp = await self._client.post(
            self._url, json=body, timeout=self._settings.EXTERNAL_SCRAPER_TIMEOUT
        )
        resp.raise_for_status()  # 5xx/timeout retried; 4xx surfaces (reraise)
        return resp.json()

    async def fetch(self, query: str, location: str | None = None) -> list[RawJob]:
        data = await self._post({"query": query, "location": location, "limit": 50})
        jobs: list[RawJob] = []
        for r in data.get("jobs", []):
            url = r.get("url")
            source_job_id = r.get("source_job_id")
            if not url or not source_job_id:
                continue  # a row violating the contract is dropped, not the whole batch
            jobs.append(
                RawJob(
                    source_job_id=str(source_job_id),
                    title=r.get("title", ""),
                    url=url,
                    description=r.get("description", ""),
                    company=r.get("company") or None,
                    location=r.get("location") or None,
                    posted_at=_parse_dt(r.get("posted_at")),
                )
            )
        logger.info("External source %s returned %d jobs for %r", self.name, len(jobs), query)
        return jobs
