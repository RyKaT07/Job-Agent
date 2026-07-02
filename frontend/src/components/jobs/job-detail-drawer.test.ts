import { describe, expect, it } from "vitest"

import { searchResultsToRows } from "@/components/jobs/job-detail-drawer"
import type { Job } from "@/lib/api/jobs"
import type { SearchDetail } from "@/lib/api/searches"

describe("searchResultsToRows", () => {
  const job = (id: string): Job => ({
    id,
    title: "Engineer",
    company: "Acme",
    location: "Berlin",
    url: `https://example.com/${id}`,
  })

  it("returns rows sorted by rank, carrying score and explanation", () => {
    const search: SearchDetail = {
      id: "search-1",
      prompt: "python",
      created_at: "2026-06-01T00:00:00Z",
      results: [
        { job: job("b"), rank: 2, score: 0.7, explanation: "second" },
        { job: job("a"), rank: 1, score: 0.91, explanation: "first" },
      ],
    }

    const rows = searchResultsToRows(search)

    expect(rows.map((r) => r.id)).toEqual(["a", "b"]) // sorted by rank
    expect(rows[0].score).toBe(0.91)
    expect(rows[0].explanation).toBe("first")
  })
})
