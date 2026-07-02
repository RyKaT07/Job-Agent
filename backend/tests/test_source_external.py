import json

import httpx

from app.core.config import settings
from app.integrations.sources.external import ExternalScraperSource


def _client(payload: dict) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/scrape"
        body = json.loads(request.content)
        assert body["query"] == "python"
        return httpx.Response(200, content=json.dumps(payload))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_external_fetch_maps_and_skips_bad_rows():
    payload = {
        "jobs": [
            {
                "source_job_id": "abc",
                "title": "Python Dev",
                "url": "https://board/1",
                "description": "work",
                "company": "ACME",
                "location": "Warszawa",
                "posted_at": "2026-06-20T10:00:00Z",
            },
            {"source_job_id": "", "title": "no url/id", "url": ""},  # contract violation
        ]
    }
    async with _client(payload) as client:
        src = ExternalScraperSource("pracuj", "http://svc:8080/", True, client, settings)
        jobs = await src.fetch("python", "Warszawa")

    assert src.name == "pracuj" and src.is_scraped is True
    assert len(jobs) == 1  # the malformed row was dropped, the good one kept
    assert jobs[0].source_job_id == "abc"
    assert jobs[0].url == "https://board/1" and jobs[0].company == "ACME"
    assert jobs[0].posted_at is not None
