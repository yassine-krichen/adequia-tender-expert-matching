'use client';

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  XAxis,
  YAxis,
} from 'recharts';

import { MiniRadialStat } from '@/common/components/mini-radial-stat';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/common/components/ui/chart';
import type { MetricGroup, MetricsSnapshot } from '@/features/metrics/types/metrics.types';

function numeric(value: number | string | undefined | null): number {
  return typeof value === 'number' ? value : 0;
}

function percentFormatter(value: number | string): string {
  return `${Math.round(Number(value) * 100)}%`;
}

function secondsFormatter(value: number | string): string {
  return `${Number(value).toLocaleString()}s`;
}

// extraction: two small pass/fail donuts (TDR, CV) — uses the real counts
// the snapshot already has instead of the derived rate.
function DonutStat({ title, passed, total }: { title: string; passed: number; total: number }) {
  const failed = Math.max(total - passed, 0);
  const config: ChartConfig = {
    passed: { label: 'Passed', color: 'var(--chart-1)' },
    failed: { label: 'Failed', color: 'var(--chart-4)' },
  };
  const data = [
    { key: 'passed', value: passed, fill: 'var(--color-passed)' },
    { key: 'failed', value: failed, fill: 'var(--color-failed)' },
  ];

  return (
    <div className="flex flex-col items-center gap-1">
      <ChartContainer config={config} className="mx-auto aspect-square max-h-[120px] w-full">
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent nameKey="key" hideLabel />} />
          <Pie data={data} dataKey="value" nameKey="key" innerRadius="55%" outerRadius="90%" />
        </PieChart>
      </ChartContainer>
      <p className="text-center text-xs text-muted-foreground">{title}</p>
    </div>
  );
}

function ExtractionChart({ values }: { values: Record<string, number | string> }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <DonutStat
        title={`TDR ${numeric(values.tdr_passed)}/${numeric(values.tdr_total)}`}
        passed={numeric(values.tdr_passed)}
        total={numeric(values.tdr_total)}
      />
      <DonutStat
        title={`CV ${numeric(values.cv_passed)}/${numeric(values.cv_total)}`}
        passed={numeric(values.cv_passed)}
        total={numeric(values.cv_total)}
      />
    </div>
  );
}

// retrieval / report_quality: two independent 0-1 proportions, no
// part-whole or ordinal relationship — a direct side-by-side bar compare.
function TwoBarChart({ items }: { items: { key: string; label: string; value: number }[] }) {
  const config: ChartConfig = Object.fromEntries(
    items.map((item, index) => [
      item.key,
      { label: item.label, color: `var(--chart-${(index % 5) + 1})` },
    ])
  );
  const data = items.map((item) => ({
    metric: item.label,
    value: item.value,
    fill: `var(--color-${item.key})`,
  }));

  return (
    <ChartContainer config={config} className="max-h-[140px] w-full">
      <BarChart data={data} layout="vertical" margin={{ left: 8 }}>
        <CartesianGrid horizontal={false} />
        <XAxis
          type="number"
          domain={[0, 1]}
          tickFormatter={percentFormatter}
          tickLine={false}
          axisLine={false}
        />
        <YAxis type="category" dataKey="metric" width={100} tickLine={false} axisLine={false} />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => percentFormatter(value as number)}
              hideLabel
            />
          }
        />
        <Bar dataKey="value" radius={4} />
      </BarChart>
    </ChartContainer>
  );
}

// anomaly_detection: the one group with 4 comparable 0-1 axes, so a radar
// silhouette is meaningful — false_positive_rate is the one inverted axis.
function AnomalyRadarChart({ values }: { values: Record<string, number | string> }) {
  const data = [
    { axis: 'Precision', value: numeric(values.precision) },
    { axis: 'Recall', value: numeric(values.recall) },
    { axis: 'F1', value: numeric(values.f1) },
    { axis: 'False positive rate', value: numeric(values.false_positive_rate) },
  ];
  const config: ChartConfig = { value: { label: 'Score', color: 'var(--chart-1)' } };

  return (
    <div className="space-y-1">
      <ChartContainer config={config} className="mx-auto aspect-square max-h-[220px] w-full">
        <RadarChart data={data}>
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value) => percentFormatter(value as number)}
                hideLabel
              />
            }
          />
          <PolarGrid />
          <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10 }} />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <Radar
            dataKey="value"
            fill="var(--color-value)"
            fillOpacity={0.35}
            stroke="var(--color-value)"
          />
        </RadarChart>
      </ChartContainer>
      <p className="text-center text-xs text-muted-foreground">
        Lower is better for false positive rate
      </p>
    </div>
  );
}

// guardrails: a single KPI (pass_rate) — a gauge reads faster than a bar.
function GuardrailsChart({ values }: { values: Record<string, number | string> }) {
  const passed = numeric(values.passed);
  const total = numeric(values.total);

  return (
    <MiniRadialStat
      label="Injection-resistance pass rate"
      value={numeric(values.pass_rate)}
      centerLabel={`${passed}/${total}`}
      size="md"
    />
  );
}

// scoring_agreement: kappa mapped -1..1 -> 0..100% fill, rendered visibly
// smaller/muted than the guardrails gauge — n=2 caveat lives right next to
// it in metrics/page.tsx (bumped to text-foreground with an icon there).
function ScoringAgreementChart({ values }: { values: Record<string, number | string> }) {
  const kappa = numeric(values.cohens_kappa);
  const fraction = (kappa + 1) / 2;

  return (
    <MiniRadialStat
      label="Cohen's kappa (AI vs. reviewer)"
      value={fraction}
      centerLabel={kappa.toFixed(2)}
      size="sm"
      muted
      className="mx-auto max-w-[140px]"
    />
  );
}

// efficiency: split by what's actually comparable, not one chart forced
// onto wildly different scales (per-match seconds vs extraction seconds).
function EfficiencyChart({ values }: { values: Record<string, number | string> }) {
  const latencyData = [
    { percentile: 'p50', seconds: numeric(values.overall_per_match_p50_s) },
    { percentile: 'p95', seconds: numeric(values.overall_per_match_p95_s) },
  ];
  const latencyConfig: ChartConfig = {
    seconds: { label: 'Per-match latency (s)', color: 'var(--chart-1)' },
  };

  const stageData = [
    { stage: 'Extract TDR', seconds: numeric(values.extract_tdr_p50_s), fill: 'var(--color-tdr)' },
    { stage: 'Extract CV', seconds: numeric(values.extract_cv_p50_s), fill: 'var(--color-cv)' },
  ];
  const stageConfig: ChartConfig = {
    tdr: { label: 'Extract TDR', color: 'var(--chart-2)' },
    cv: { label: 'Extract CV', color: 'var(--chart-3)' },
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">Per-match latency (s)</p>
        <ChartContainer config={latencyConfig} className="max-h-[140px] w-full">
          <AreaChart data={latencyData}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="percentile" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={28} />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  formatter={(value) => secondsFormatter(value as number)}
                  hideLabel
                />
              }
            />
            {/* p95 is by definition >= p50, so this step-up is a real,
                honest shape across the two-point ordinal category. */}
            <Area
              dataKey="seconds"
              type="step"
              fill="var(--color-seconds)"
              fillOpacity={0.35}
              stroke="var(--color-seconds)"
            />
          </AreaChart>
        </ChartContainer>
      </div>
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">Extraction latency by stage (s)</p>
        <ChartContainer config={stageConfig} className="max-h-[140px] w-full">
          <BarChart data={stageData}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="stage" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
            <YAxis tickLine={false} axisLine={false} width={36} />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  formatter={(value) => secondsFormatter(value as number)}
                  hideLabel
                />
              }
            />
            <Bar dataKey="seconds" radius={4} />
          </BarChart>
        </ChartContainer>
      </div>
    </div>
  );
}

/**
 * Chart-type mapping is picked per metric group's real fields, not a
 * checklist — see the sprint-4/hardening plan for the full reasoning.
 * Additive: the numeric `<dl>` values below each chart are the source of
 * truth and stay untouched, so a chart failure never hides real numbers.
 */
export function MetricGroupChart({
  groupKey,
  group,
}: {
  groupKey: keyof MetricsSnapshot;
  group: MetricGroup;
}) {
  if (group.status !== 'available' || group.values === null) {
    return null;
  }

  const values = group.values;

  switch (groupKey) {
    case 'extraction':
      return <ExtractionChart values={values} />;
    case 'retrieval':
      return (
        <TwoBarChart
          items={[
            { key: 'recall', label: 'Recall@3', value: numeric(values.recall_at_3) },
            { key: 'precision', label: 'Precision@3', value: numeric(values.precision_at_3) },
          ]}
        />
      );
    case 'anomaly_detection':
      return <AnomalyRadarChart values={values} />;
    case 'guardrails':
      return <GuardrailsChart values={values} />;
    case 'scoring_agreement':
      return <ScoringAgreementChart values={values} />;
    case 'report_quality':
      return (
        <TwoBarChart
          items={[
            { key: 'faithfulness', label: 'Faithfulness', value: numeric(values.faithfulness) },
            {
              key: 'citation',
              label: 'Citation coverage',
              value: numeric(values.citation_coverage),
            },
          ]}
        />
      );
    case 'efficiency':
      return <EfficiencyChart values={values} />;
    default:
      return null;
  }
}
