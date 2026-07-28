'use client';

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  ClipboardCheck,
  FileText,
  UserCheck,
  Upload,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { fetchCandidates } from '@/features/candidates/api/fetch-candidates';
import { getMetrics } from '@/features/metrics/api/get-metrics';
import type { MetricsSnapshot } from '@/features/metrics/types/metrics.types';
import { listTdrs } from '@/features/tdrs/api/list-tdrs';

const PIPELINE_STEPS = [
  { icon: Upload, label: 'Upload' },
  { icon: FileText, label: 'Extract' },
  { icon: Users, label: 'Match' },
  { icon: BarChart3, label: 'Score' },
  { icon: AlertTriangle, label: 'Detect anomalies' },
  { icon: ClipboardCheck, label: 'Cited report' },
  { icon: UserCheck, label: 'Human review' },
];

const FEATURES = [
  {
    icon: FileText,
    title: 'CV & TDR extraction',
    description:
      "Pulls structured fields — education, experience, certifications, required skills, deadlines — out of real PDF/docx TDRs and CVs, not just plain-text templates.",
  },
  {
    icon: Users,
    title: 'Matching & scoring',
    description:
      "Checks every candidate against a position's hard filters (diploma, minimum experience, required certifications), then scores the survivors on skill coverage, sector fit, and an LLM qualitative-fit judgment.",
  },
  {
    icon: AlertTriangle,
    title: 'Anomaly detection & guardrails',
    description:
      "Flags employment gaps, date overlaps, and expired certifications in a candidate's CV, and resists prompt-injection attempts hidden in uploaded documents.",
  },
  {
    icon: ClipboardCheck,
    title: 'Cited, human-reviewable reports',
    description:
      'Every claim in a match rationale is backed by a citation into the source CV or TDR text, and a reviewer approves, rejects, or overrides each recommendation with a required note.',
  },
];

const QUICK_LINKS = [
  {
    href: '/tdrs',
    icon: FileText,
    title: 'Upload TDR',
    description: 'Extract mission, client, and expert positions from a TDR document.',
  },
  {
    href: '/candidates',
    icon: Users,
    title: 'Upload candidate',
    description: 'Turn a CV into structured, extracted data.',
  },
  {
    href: '/metrics',
    icon: BarChart3,
    title: 'View metrics',
    description: 'See eval harness results for extraction, matching, and report quality.',
  },
];

function formatPercent(value: number | string | undefined): string | null {
  if (typeof value !== 'number') return null;
  return `${Math.round(value * 100)}%`;
}

function MetricsTeaser({ metrics }: { metrics: MetricsSnapshot }) {
  const headlineMetrics = [
    {
      label: 'CV extraction pass-rate',
      value: formatPercent(metrics.extraction.values?.cv_pass_rate),
    },
    {
      label: 'Anomaly detection F1',
      value: formatPercent(metrics.anomaly_detection.values?.f1),
    },
    {
      label: 'Report faithfulness',
      value: formatPercent(metrics.report_quality.values?.faithfulness),
    },
    {
      label: 'Retrieval recall@3',
      value: formatPercent(metrics.retrieval.values?.recall_at_3),
    },
  ].filter((metric) => metric.value !== null);

  if (headlineMetrics.length === 0) return null;

  return (
    <section className="mx-auto max-w-5xl space-y-4 px-8">
      <div className="grid gap-4 sm:grid-cols-4">
        {headlineMetrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="space-y-1 py-6 text-center">
              <p className="text-3xl font-semibold text-primary">{metric.value}</p>
              <p className="text-sm text-muted-foreground">{metric.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-center">
        <Link href="/metrics" className="text-sm font-medium text-primary hover:underline">
          See full eval report →
        </Link>
      </p>
    </section>
  );
}

export default function Home() {
  const [candidateCount, setCandidateCount] = useState<number | null>(null);
  const [tdrCount, setTdrCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchCounts() {
      setIsLoading(true);
      setError(null);
      const [candidatesResult, tdrsResult] = await Promise.all([fetchCandidates(), listTdrs()]);
      if (cancelled) return;

      if (candidatesResult.error !== null || tdrsResult.error !== null) {
        setError(candidatesResult.error ?? tdrsResult.error);
      } else {
        setCandidateCount(candidatesResult.data.length);
        setTdrCount(tdrsResult.data.length);
      }
      setIsLoading(false);
    }

    void fetchCounts();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchMetricsTeaser() {
      // Credibility content, not critical path: a failure here just means
      // the teaser section doesn't render — no error state to show.
      const result = await getMetrics();
      if (cancelled) return;
      if (result.error === null) {
        setMetrics(result.data);
      }
    }

    void fetchMetricsTeaser();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="space-y-16 py-12">
      {/* Hero */}
      <section className="mx-auto max-w-3xl space-y-4 px-8 text-center">
        <h1 className="font-heading text-4xl">AdéquIA</h1>
        <p className="text-lg font-medium text-muted-foreground">
          Le bon profil, pour la bonne mission.
        </p>
        <p className="text-muted-foreground">
          Consulting firms respond to tenders (TDRs) that list precise expert requirements —
          diplomas, years of experience, certifications, sector background — then have to check
          those requirements by hand against a stack of candidate CVs. AdéquIA reads both sides,
          extracts what they actually say, and produces a scored, cited match report a reviewer
          can approve, reject, or override in minutes instead of hours.
        </p>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-8">
        <h2 className="mb-6 text-center font-heading text-sm text-muted-foreground">
          How it works
        </h2>
        <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-4">
          {PIPELINE_STEPS.map(({ icon: Icon, label }, index) => (
            <div key={label} className="flex items-center gap-2">
              <div className="flex flex-col items-center gap-1.5">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                  <Icon className="size-5 text-primary" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">{label}</span>
              </div>
              {index < PIPELINE_STEPS.length - 1 && (
                <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Feature highlights */}
      <section className="mx-auto max-w-5xl px-8">
        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <Card key={title}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Icon className="size-5 text-primary" />
                  {title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Credibility / metrics teaser */}
      {metrics !== null && <MetricsTeaser metrics={metrics} />}

      {/* Closing CTA */}
      <section className="mx-auto max-w-5xl px-8">
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild>
            <Link href="/tdrs">
              <FileText />
              Upload a TDR
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/candidates">
              <Users />
              Upload a candidate
            </Link>
          </Button>
        </div>
      </section>

      {/* Workspace — daily-use view below the fold */}
      <section className="mx-auto max-w-6xl space-y-6 px-8">
        <div>
          <h2 className="font-heading text-2xl">Your workspace</h2>
          <p className="text-muted-foreground">
            Current candidate and TDR counts, and quick links into each workflow.
          </p>
        </div>

        {isLoading && (
          <p className="text-muted-foreground" role="status">
            Loading…
          </p>
        )}

        {error !== null && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}

        {!isLoading && error === null && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Candidates</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold">{candidateCount} candidates</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>TDRs</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold">{tdrCount} TDRs</p>
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          {QUICK_LINKS.map(({ href, icon: Icon, title, description }) => (
            <Link key={href} href={href}>
              <Card className="h-full transition-colors hover:bg-muted">
                <CardContent className="flex flex-col items-start gap-2 py-6">
                  <Icon className="size-6 text-primary" />
                  <p className="font-medium">{title}</p>
                  <p className="text-sm text-muted-foreground">{description}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
