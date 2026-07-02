"use client"

import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import { ErrorBanner } from "@/components/ui/error-banner"
import { LoadingSkeleton } from "@/components/ui/loading-skeleton"
import { getJob, type Job, type JobDetail } from "@/lib/api/jobs"
import {
  findJobMatch,
  type SearchDetail,
  type SearchResult,
} from "@/lib/api/searches"

type JobDetailPanelProps = {
  jobId: string
  search: SearchDetail | null
}

function JobDetailPanel({ jobId, search }: JobDetailPanelProps) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [match, setMatch] = useState<SearchResult | undefined>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      const result = await getJob(jobId)
      if (!active) return

      if (!result.ok) {
        setError(result.error.message)
        setJob(null)
      } else {
        setJob(result.data)
        setMatch(findJobMatch(search, jobId))
      }
      setLoading(false)
    }

    void load()

    return () => {
      active = false
    }
  }, [jobId, search])

  if (loading) return <LoadingSkeleton rows={4} />
  if (error) return <ErrorBanner message={error} />
  if (!job) return null

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">{job.title}</h3>
        <p className="text-sm text-muted-foreground">
          {[job.company, job.location].filter(Boolean).join(" · ")}
        </p>
      </div>
      {match ? (
        <Card className="border-border bg-[var(--color-accent-subtle)]">
          <CardContent className="space-y-2 px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Match score</span>
              <Badge>{Math.round(match.score * 100)}%</Badge>
            </div>
            <p className="text-sm text-muted-foreground">{match.explanation}</p>
          </CardContent>
        </Card>
      ) : null}
      <div className="space-y-2">
        <h4 className="text-sm font-medium">Description</h4>
        <p className="whitespace-pre-wrap text-sm text-muted-foreground">
          {job.description}
        </p>
      </div>
      <Button
        nativeButton={false}
        render={
          <a href={job.url} target="_blank" rel="noopener noreferrer" />
        }
      >
        View original posting
      </Button>
    </div>
  )
}

type JobDetailDrawerProps = {
  jobId: string | null
  search: SearchDetail | null
  onClose: () => void
}

export function JobDetailDrawer({
  jobId,
  search,
  onClose,
}: JobDetailDrawerProps) {
  if (!jobId) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        aria-label="Close job details"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-card shadow-lg">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-base font-semibold">Job details</h2>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <JobDetailPanel key={jobId} jobId={jobId} search={search} />
        </div>
      </aside>
    </div>
  )
}

export type JobRow = Job & {
  score?: number
  explanation?: string
}

export function searchResultsToRows(search: SearchDetail): JobRow[] {
  return search.results
    .slice()
    .sort((a, b) => a.rank - b.rank)
    .map((result) => ({
      ...result.job,
      score: result.score,
      explanation: result.explanation,
    }))
}
