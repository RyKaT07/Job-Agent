"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Briefcase, Search } from "lucide-react"

import {
  JobDetailDrawer,
  searchResultsToRows,
  type JobRow,
} from "@/components/jobs/job-detail-drawer"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { ErrorBanner } from "@/components/ui/error-banner"
import { Input } from "@/components/ui/input"
import { LoadingSkeleton } from "@/components/ui/loading-skeleton"
import { listCVs } from "@/lib/api/cvs"
import { listJobs } from "@/lib/api/jobs"
import {
  getSearch,
  listSearches,
  triggerSearch,
  type SearchDetail,
} from "@/lib/api/searches"
import { toast } from "@/lib/toast"

async function fetchJobsPageData(): Promise<
  | { ok: true; jobs: JobRow[]; search: SearchDetail | null }
  | { ok: false; message: string }
> {
  const searchesRes = await listSearches({ limit: 1 })

  let latestSearch: SearchDetail | null = null
  if (searchesRes.ok && searchesRes.data.length > 0) {
    const detailRes = await getSearch(searchesRes.data[0].id)
    if (detailRes.ok) {
      latestSearch = detailRes.data
    }
  }

  // With a search, show its ranked matches (score + explanation). Without one,
  // fall back to browsing the most recent corpus jobs.
  if (latestSearch) {
    return {
      ok: true,
      jobs: searchResultsToRows(latestSearch),
      search: latestSearch,
    }
  }

  const jobsRes = await listJobs({ limit: 100 })
  if (!jobsRes.ok) {
    return { ok: false, message: jobsRes.error.message }
  }
  return { ok: true, jobs: jobsRes.data, search: null }
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobRow[]>([])
  const [search, setSearch] = useState<SearchDetail | null>(null)
  const [filter, setFilter] = useState("")
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [searchPrompt, setSearchPrompt] = useState("")

  useEffect(() => {
    let active = true

    async function load() {
      const result = await fetchJobsPageData()
      if (!active) return

      if (!result.ok) {
        setError(result.message)
        setLoading(false)
        return
      }

      setSearch(result.search)
      setJobs(result.jobs)
      if (result.search) {
        setSearchPrompt(result.search.prompt)
      }
      setLoading(false)
    }

    void load()

    return () => {
      active = false
    }
  }, [])

  async function reloadJobs() {
    const result = await fetchJobsPageData()
    if (!result.ok) {
      setError(result.message)
      return
    }

    setSearch(result.search)
    setJobs(result.jobs)
    if (result.search) {
      setSearchPrompt(result.search.prompt)
    }
  }

  const filteredJobs = useMemo(() => {
    const query = filter.trim().toLowerCase()
    if (!query) return jobs

    return jobs.filter((job) => {
      const haystack = [job.title, job.company, job.location]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
      return haystack.includes(query)
    })
  }, [jobs, filter])

  const stats = useMemo(() => {
    const highFit = jobs.filter((job) => (job.score ?? 0) >= 0.8).length
    return {
      total: jobs.length,
      saved: 0,
      highFit,
      newThisWeek: jobs.length,
    }
  }, [jobs])

  async function handleRunSearch() {
    const prompt = searchPrompt.trim()
    if (!prompt) {
      toast.error("Enter a search prompt")
      return
    }

    setSearching(true)
    setError(null)

    const cvsRes = await listCVs({ limit: 100 })
    if (!cvsRes.ok) {
      setError(cvsRes.error.message)
      setSearching(false)
      return
    }
    if (cvsRes.data.length === 0) {
      toast.error("Upload a CV before running a search")
      setSearching(false)
      return
    }

    const activeCv =
      cvsRes.data.find((cv) => cv.is_active) ?? cvsRes.data[0]
    const cvId = activeCv.id

    const pollSearch = async (attempt = 0): Promise<void> => {
      const result = await triggerSearch({ cv_id: cvId, prompt })
      if (!result.ok) {
        setError(result.error.message)
        setSearching(false)
        return
      }

      if (result.data.kind === "ingesting") {
        if (attempt === 0) {
          toast.info("No jobs yet — ingestion started. Retrying shortly…")
        }
        if (attempt >= 10) {
          toast.error("Ingestion is taking longer than expected. Try again later.")
          setSearching(false)
          return
        }
        window.setTimeout(() => {
          void pollSearch(attempt + 1)
        }, 3000)
        return
      }

      setSearch(result.data.data)
      toast.success("Search complete")
      await reloadJobs()
      setSearching(false)
    }

    await pollSearch()
  }

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-5 sm:px-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
          <p className="text-sm text-muted-foreground">
            Semantic matches from your latest search.
          </p>
        </div>
        <div className="flex w-full max-w-md flex-col gap-2 sm:flex-row">
          <Input
            value={searchPrompt}
            onChange={(event) => setSearchPrompt(event.target.value)}
            placeholder="e.g. React developer in Warsaw"
          />
          <Button onClick={() => void handleRunSearch()} disabled={searching}>
            <Search />
            {searching ? "Searching…" : "Run new search"}
          </Button>
        </div>
      </header>

      {error ? (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total matches", value: stats.total },
          { label: "Saved", value: stats.saved },
          { label: "High fit (80+)", value: stats.highFit },
          { label: "New this week", value: stats.newThisWeek },
        ].map((stat) => (
          <Card
            key={stat.label}
            className="border-border bg-[var(--color-accent-subtle)]"
          >
            <CardContent className="px-4 py-4">
              <p className="font-mono text-[28px] font-semibold tabular-nums text-foreground">
                {stat.value}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="border-border">
        <CardHeader className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-base">
              {search ? "Matches" : "All jobs"}
            </CardTitle>
            <CardDescription>
              {filteredJobs.length} {search ? "matches" : "listings"}
              {search ? ` from “${search.prompt}”` : ""}.
            </CardDescription>
          </div>
          <div className="w-full max-w-xs">
            <Input
              type="search"
              placeholder="Filter by title or company…"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6">
              <LoadingSkeleton rows={5} />
            </div>
          ) : filteredJobs.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No jobs yet"
              description="Upload a CV and run a semantic search to see matched opportunities here."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  nativeButton={false}
                  render={<Link href="/dashboard/cvs" />}
                >
                  Upload CV
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-border">
              {filteredJobs.map((job) => (
                <li key={job.id}>
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-4 px-4 py-4 text-left transition-colors hover:bg-[var(--color-surface-hover)]"
                    onClick={() => setSelectedJobId(job.id)}
                  >
                    <div className="min-w-0">
                      <p className="font-medium">{job.title}</p>
                      <p className="text-sm text-muted-foreground">
                        {[job.company, job.location]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                      {job.explanation ? (
                        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                          {job.explanation}
                        </p>
                      ) : null}
                    </div>
                    {job.score !== undefined ? (
                      <span className="shrink-0 font-mono text-sm tabular-nums text-[var(--color-accent-hover)]">
                        {Math.round(job.score * 100)}%
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <JobDetailDrawer
        jobId={selectedJobId}
        search={search}
        onClose={() => setSelectedJobId(null)}
      />
    </div>
  )
}
