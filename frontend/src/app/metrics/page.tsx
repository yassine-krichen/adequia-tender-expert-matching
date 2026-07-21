'use client';

import { Clock } from 'lucide-react';
import { useEffect, useState } from 'react';

import { EmptyState } from '@/common/components/empty-state';
import { InfoTooltip } from '@/common/components/info-tooltip';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { getMetrics } from '@/features/metrics/api/get-metrics';
import type { MetricGroup, MetricsSnapshot } from '@/features/metrics/types/metrics.types';

const GROUPS: { key: keyof MetricsSnapshot; title: string; explanation: string }[] = [
  {
    key: 'extraction',
    title: 'Extraction quality',
    explanation:
      'How often the AI correctly pulls structured fields (education, experience, dates…) out of a real TDR or CV document, checked by hand against each document.',
  },
  {
    key: 'retrieval',
    title: 'Retrieval / matching quality',
    explanation:
      'Whether the true best-fit candidate for a position actually shows up in the shortlist the AI produces, and how much noise comes with it.',
  },
  {
    key: 'anomaly_detection',
    title: 'Anomaly detection',
    explanation:
      'How reliably the system flags real red flags in a CV (gaps, overlaps, expired certifications…) without wrongly flagging clean CVs.',
  },
  {
    key: 'guardrails',
    title: 'Guardrails',
    explanation:
      "Whether text hidden in a CV or TDR trying to manipulate the AI's score or output actually succeeds — it should never.",
  },
  {
    key: 'scoring_agreement',
    title: 'Scoring agreement',
    explanation:
      "How closely the AI's ranking of candidates matches what a human reviewer would decide — the strongest evidence the tool can be trusted for real decisions.",
  },
  {
    key: 'report_quality',
    title: 'Report quality',
    explanation:
      "Whether every claim in the AI's written rationale is actually backed by something real in the source document, not invented.",
  },
  {
    key: 'efficiency',
    title: 'Efficiency',
    explanation:
      'How much time and cost the AI pipeline takes per candidate–position match, compared to manual review.',
  },
];

const ACRONYMS = new Set(['tdr', 'cv', 'f1']);

function formatMetricLabel(key: string): string {
  return key
    .split('_')
    .map((word) =>
      ACRONYMS.has(word) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(' ');
}

function formatMetricValue(value: number | string): string {
  if (typeof value === 'number' && value >= 0 && value <= 1) {
    return `${Math.round(value * 100)}%`;
  }
  return String(value);
}

function MetricGroupCard({
  title,
  explanation,
  group,
}: {
  title: string;
  explanation: string;
  group: MetricGroup;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          {title}
          <InfoTooltip text={explanation} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {group.status === 'pending' ? (
          <EmptyState
            icon={Clock}
            title="Not measured yet"
            description={group.pending_reason ?? 'This metric is not available yet.'}
          />
        ) : (
          <div className="space-y-3">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {Object.entries(group.values ?? {}).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-muted-foreground">{formatMetricLabel(key)}</dt>
                  <dd className="font-medium">{formatMetricValue(value)}</dd>
                </div>
              ))}
            </dl>
            <p className="text-xs text-muted-foreground">
              {group.dataset}
              {group.sample_size != null && ` · n=${group.sample_size}`}
            </p>
            {group.note && <p className="text-xs text-muted-foreground">{group.note}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchMetrics() {
      setIsLoading(true);
      setError(null);
      const result = await getMetrics();
      if (cancelled) return;
      if (result.error !== null) {
        setError(result.error);
      } else {
        setMetrics(result.data);
      }
      setIsLoading(false);
    }

    void fetchMetrics();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-8">
      <div>
        <h1 className="font-heading text-2xl">Eval metrics</h1>
        <p className="text-muted-foreground">
          Eval harness output — see docs/04-evaluation-metrics.md for full methodology.
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

      {metrics !== null && (
        <div className="grid gap-4 sm:grid-cols-2">
          {GROUPS.map(({ key, title, explanation }) => (
            <MetricGroupCard
              key={key}
              title={title}
              explanation={explanation}
              group={metrics[key]}
            />
          ))}
        </div>
      )}
    </main>
  );
}
